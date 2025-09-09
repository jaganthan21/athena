import os
import re
import pandas as pd
from datetime import datetime
from striprtf.striprtf import rtf_to_text
from global_variables import titles, column_names, keywords
import fitz

def modify_gender_string(value):
    """
    Standardize gender values to a consistent format.
    """
    try:
        value = value.strip()
        if value.lower() in ('f', 'female'):
            return 'Female'
        if value.lower() in ('m', 'male'):
            return 'Male'
        return value.capitalize()
    except AttributeError:
        return ''

def read_rtf_file(file_path):
    """
    Read an RTF file and convert it to plain text.
    """
    try:
        with open(file_path, 'rb') as file:
            rtf_content = file.read()
            return rtf_to_text(rtf_content.decode('latin1', errors='ignore'))
    except Exception as e:
        print(f"Error reading {os.path.basename(file_path)}: {e}")
        return ''

def extract_data_from_text(plain_text, file_type):
    """
    Extract data from plain text based on keywords and special fields.
    """
    try:
        if file_type == 'pdf':
            array_of_words = plain_text.split('\n')
        else:
            array_of_words = plain_text.split("|")
        extracted_data = {}

        for i, word in enumerate(array_of_words):
            word = word.strip()
            if not word:
                continue

            for keyword in keywords:
                if re.search(rf'\b{re.escape(keyword)}\b', word, re.IGNORECASE):
                    if keyword in ('Referral Agent details', 'Referrer Agent details', 'Referral Details'):
                        extracted_data[keyword] = ' '.join(array_of_words[i + 1:]).strip()
                        break
                    next_value = ''
                    for j in range(i + 1, len(array_of_words)):
                        next_value = array_of_words[j].strip()
                        if next_value or array_of_words[j] in keywords:
                            break
                    if keyword not in extracted_data:
                        extracted_data[keyword] = next_value
                    break

            if 'Mobile' in word:
                if re.search(r'[0-9]', array_of_words[i].strip()):
                    mobile_value = array_of_words[i].strip().split()
                    mobile_value = ''.join(mobile_value[1:]) if len(mobile_value) > 2 else mobile_value[-1]
                    mobile_value = f'{mobile_value[:5]} {mobile_value[5:]}'.strip()
                    extracted_data['P_Mobile'] = mobile_value.replace("(", "").replace(")", "")
                else:
                    extracted_data['P_Mobile'] = ''

            if 'Information relevant to referral' in word:
                extracted_data['Related_Information'] = array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else ''

            if 'Relevant medical conditions' in word:
                extracted_data['Relevant_Medical_Conditions'] = array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else ''

            if 'To be completed by the referrer' in word:
                # print("Reason details found:", array_of_words[i + 1:i + 4])  # Debugging output
                extracted_data['Reason_For_Referral'] = array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else ''

            if 'Landline' in word:
                if re.search(r'[0-9]', array_of_words[i].strip()):
                    mobile_value = array_of_words[i].strip().split()
                    # checks if it has numbers the string, if not sets to empty
                    mobile_value = ''.join(mobile_value[1:]) if len(mobile_value) > 2 else mobile_value[-1]
                    mobile_value = f'{mobile_value[:5]} {mobile_value[5:]}'.strip()
                    extracted_data['P_HomeTelephone'] = mobile_value.replace("(", "").replace(")", "")
                else:
                    extracted_data['P_HomeTelephone'] = ''
            if word == 'Standing height':
                extracted_data['R_StatType_Height_Value'] = ' '.join(array_of_words[i + 1:i + 2]).strip() if i + 1 < len(array_of_words) else ''
                extracted_data['R_StatType_Height_Date'] = array_of_words[i - 1].strip() if i - 1 >= 0 else ''

            if word == 'Body weight':
                extracted_data['R_StatType_Weight_Value'] = ' '.join(array_of_words[i + 1:i + 2]).strip() if i + 1 < len(array_of_words) else ''
                extracted_data['R_StatType_Weight_Date'] = array_of_words[i - 1].strip() if i - 1 >= 0 else ''

            if word == 'Email':
                extracted_data['P_EmailAddress'] = array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else ''

            if word == 'O/E- blood pressure reading':
                extracted_data['R_StatType_BloodPressure_Date'] = array_of_words[i - 1].strip() if i - 1 >= 0 else ''
                extracted_data['R_StatType_BloodPressure_Value'] = ' '.join(array_of_words[i + 1:i + 3]).strip() if i + 1 < len(array_of_words) else ''
            # print(f"Extracted data: {extracted_data}")  # Debugging output
        return extracted_data
    except Exception as e:
        print(f"Error extracting data: {e}")
        return {}


def format_date(value, output_format='%d/%m/%Y'):
    """
    Format a date string to a consistent format.
    Supports both abbreviated (Aug) and full (August) month names.
    """
    try:
        value = value.strip()
        if not re.search(r'[0-9]', value):
            return 'NA'


        # Normalize separators to "/"
        # date_parts = value.split('-') if '-' in value else value.split('.')
        date_parts = re.split(r'[-.\s]+', value)

        formatted_date = '/'.join(date_parts)

        if re.search(r'[a-z]', formatted_date, re.IGNORECASE):
            # Try both abbreviated (%b) and full month name (%B)
            for fmt in ("%d/%b/%Y", "%d/%B/%Y"):
                try:
                    date_obj = datetime.strptime(formatted_date, fmt)
                    return date_obj.strftime(output_format)
                except ValueError:
                    continue
            return 'NA'  # If neither format works
        return formatted_date
    except ValueError:
        return 'NA'


def clean_text(value):
    """
    Clean a text value by removing non-printable characters and leading/trailing spaces.
    """
    try:
        return re.sub(r'[^\x20-\x7E]', '', value.strip())
    except (AttributeError, TypeError):
        return ''

def transform_extracted_data(extracted_data):
    """
    Transform extracted data into a format suitable for Excel output.

    Args:
        extracted_data (dict): Dictionary of extracted data.

    Returns:
        dict: Transformed data with Excel column names as keys, values processed appropriately.
    """
    try:
        json_for_excel = {}
        # Collect values for P_Information
        p_information_parts = []

        # Process all column mappings first
        for key, value in extracted_data.items():
            if not value or value.strip() == '':
                continue

            if key == 'Name':
                value = re.sub(r'[()]', '', value)
                # value.replace('"', '')
                if "Sofyane" in value:
                    # print("Debug: Found 'Sofyane' in Name value")
                    # print("Original Name value:", value)
                    pass
                name_array = [part.strip() for part in value.split()]
                # replace "." and quotes with "" in name_array elements
                # name_array = [part.replace('"', '') for part in name_array]
                # name_array = [part.capitalize() for part in name_array]

                name_array = [part.replace('.', '') for part in name_array]
                if len(name_array) == 4:
                    json_for_excel['P_Title'] = name_array[0].replace('.', '')
                    json_for_excel['P_FirstName'] = name_array[1]
                    json_for_excel['P_MiddleNames'] = name_array[2]
                    json_for_excel['P_Surname'] = name_array[3]
                elif len(name_array) == 3:
                    if any(title in name_array for title in titles):
                        title_index = next((i for i, word in enumerate(name_array) if word in titles), 0)
                        if title_index == 2:
                            json_for_excel['P_Title'] = name_array[2].replace('.', '')
                            json_for_excel['P_FirstName'] = name_array[1]
                            json_for_excel['P_Surname'] = name_array[0]
                        else:
                            json_for_excel['P_Title'] = name_array[0].replace('.', '')
                            json_for_excel['P_FirstName'] = name_array[1]
                            json_for_excel['P_Surname'] = name_array[2]
                    else:
                        json_for_excel['P_FirstName'] = name_array[0]
                        json_for_excel['P_MiddleNames'] = name_array[1]
                        json_for_excel['P_Surname'] = name_array[2]
                elif len(name_array) == 2:
                    json_for_excel['P_FirstName'] = name_array[0]
                    json_for_excel['P_Surname'] = name_array[1]
                # update P_Surname to captialized
                # if 'P_Surname' in json_for_excel:
                # json_for_excel['P_Surname'] = json_for_excel['P_Surname'].capitalize().replace(',', '') 

                # if first name contains , and is in uppercase, switch first name and surname values without splitting firsname
                if 'P_FirstName' in json_for_excel and ',' in json_for_excel['P_FirstName'] and json_for_excel['P_FirstName'].isupper():
                    json_for_excel['P_FirstName'], json_for_excel['P_Surname'] = json_for_excel['P_Surname'], json_for_excel['P_FirstName'].replace(',', '').capitalize()
                elif 'P_Title' in json_for_excel and ',' in json_for_excel['P_Title'] and json_for_excel['P_Title'].isupper():
                    json_for_excel['P_Title'], json_for_excel['P_Surname'] = json_for_excel['P_Surname'], json_for_excel['P_Title'].replace(',', '').capitalize()
                
            elif key == 'DOB':
                json_for_excel['P_DateOfBirth'] = format_date(value)
            elif key == 'Ethnicity':
                json_for_excel['P_Ethnicity'] = value
            elif key == 'Gender':
                json_for_excel['P_Gender'] = modify_gender_string(value)
            elif key == 'Address':
                address = value.splitlines() if value.splitlines() else value.split(',')
                if address and address[0].strip().lower() == "home address":
                    address.pop(0)
                # print("Debug: Address lines:", address)
                if len(address)==1 and ',' in address[0]:
                    address = [part.strip() for part in address[0].split(',')]

                for i, add in enumerate(address, 1):
                    json_for_excel[f'P_HomeAddress{i}'] = add.strip()
            # json_for_excel['P_HomeAddress3'] = json_for_excel['P_HomeAddress3'].capitalize() 
            elif key == 'Postcode':
                json_for_excel['P_HomePostcode'] = value.upper()
            elif key == 'P_HomeTelephone':
                json_for_excel['P_HomeTelephone'] = value
            elif key == 'P_EmailAddress':
                json_for_excel['P_EmailAddress'] = clean_text(value)
            elif key == 'P_Mobile':
                json_for_excel['P_Mobile'] = value
            elif key == 'R_StatType_Height_Value':
                json_for_excel['R_StatType_Height_Value'] = value
            elif key == 'R_StatType_Height_Date':
                json_for_excel['R_StatType_Height_Date'] = format_date(value)
            elif key == 'R_StatType_Weight_Value':
                json_for_excel['R_StatType_Weight_Value'] = value
            elif key == 'R_StatType_Weight_Date':
                json_for_excel['R_StatType_Weight_Date'] = format_date(value)
            elif key == 'R_StatType_BloodPressure_Date':
                json_for_excel['R_StatType_BloodPressure_Date'] = value
            elif key == 'R_StatType_BloodPressure_Value':
                json_for_excel['R_StatType_BloodPressure_Value'] = value
            elif key in ('Referral Agent details', 'Referrer Agent details'):
                # Normalize text into tokens
                tokens = value.split()
                # Helper: fetch value(s) after a keyword until next keyword
                def get_field(tokens, keyword, stop_words):
                    try:
                        idx = next(i for i, t in enumerate(tokens) if t.lower() == keyword.lower())
                        collected = []
                        for t in tokens[idx + 1:]:
                            if t.lower() in [s.lower() for s in stop_words]:
                                break
                            collected.append(t)
                        return " ".join(collected).strip()
                    except StopIteration:
                        return ""

                # Extract fields
                name_val = get_field(tokens, "Name", ["Organisation", "Contact", "Date"])
                org_val = get_field(tokens, "Organisation", ["Name", "Contact", "Date"])
                contact_val = get_field(tokens, "Contact", ["Name", "Organisation", "Date"])
                
                # Special case: Date of referral -> just take next index
                try:
                    date_idx = next(i for i, t in enumerate(tokens) if t.lower() == "date")
                    if date_idx + 3 < len(tokens) and tokens[date_idx:date_idx+3] == ["Date","of","referral"]:
                        ref_date = tokens[date_idx + 3] if date_idx + 3 < len(tokens) else ""
                    else:
                        ref_date = ""
                except StopIteration:
                    ref_date = ""

                # Assign results
                if name_val:
                    ref_name = [part.strip() for part in re.sub(r'[()]', '', name_val).split() if part.strip()]
                    print("Referal name parts:", ref_name)  # Debugging output
                    if len(ref_name) == 2:
                        json_for_excel['RF_FirstName'] = ref_name[0]
                        json_for_excel['RF_Surname'] = ref_name[1]
                    elif len(ref_name) == 3:
                        if ref_name[1].lower() == 'dr':
                            json_for_excel['RF_FirstName'] = ref_name[2]
                            json_for_excel['RF_Role'] = 'Doctor'
                        else:
                            json_for_excel['RF_FirstName'] = ref_name[1]
                            json_for_excel['RF_Surname'] = ref_name[2]
                            json_for_excel['RF_Role'] = 'Other Health Professional'
                    elif len(ref_name) == 4:
                        json_for_excel['RF_FirstName'] = ref_name[2]
                        json_for_excel['RF_Surname'] = ref_name[3]
                        json_for_excel['RF_Role'] = 'Doctor' if ref_name[1].lower() == 'dr' else 'Other Health Professional'

                if org_val:
                    json_for_excel['RO_Name'] = org_val
                if contact_val:
                    json_for_excel['RF_Contact'] = contact_val

                json_for_excel['R_DateOfReferral'] = format_date(ref_date) if ref_date else "NA"
                print("Referal Organistaion name:", json_for_excel.get('RO_Name', 'Not found'))
                print("Referal Contact name:", json_for_excel.get('RF_Contact', 'Not found'))
                print("Referal First name:", json_for_excel.get('RF_FirstName', 'Not found'))
                print("Referal Surname name:", json_for_excel.get('RF_Surname', 'Not found'))
                print("Referal Role:", json_for_excel.get('RF_Role', 'Not found'))
                print("Referal Date of referral:", json_for_excel.get('R_DateOfReferral', 'Not found'))
           

            # Collect fields for P_Information
        if key in ('Reason_For_Referral', 'Relevant_Medical_Conditions', 'Related_Information'):
            json_for_excel[key] = value
            p_information_parts.append(value)

        # Combine Reason_For_Referral, Relevant_Medical_Conditions, and Related_Information into P_Information
        json_for_excel['P_Information'] = ', '.join(part.replace('Select from drop down ', '') for part in p_information_parts if part)
        # if json_for_excel['P_Surname'] == 'Wilding':
        #     json_for_excel['P_DateOfBirth']='29-09-2025'
        #check if homeaddress3 contains numbers, then remove the home address 3 value
        if 'P_HomeAddress3' in json_for_excel and re.search(r'[0-9]', json_for_excel['P_HomeAddress3']):
            json_for_excel['P_HomeAddress3']=''
        if 'P_DateOfBirth' in json_for_excel and re.search(r'\b\d{4}\b', json_for_excel['P_DateOfBirth']):
            birth_year = int(re.search(r'\b\d{4}\b', json_for_excel['P_DateOfBirth']).group())
            current_year = datetime.now().year
            if birth_year == current_year:
                json_for_excel['P_DateOfBirth'] += ' Invalid date'
        if 'P_Surname' in json_for_excel:
            json_for_excel['P_Surname'] = json_for_excel['P_Surname'].capitalize().replace(',', '').replace('"', '')

        if 'P_FirstName' in json_for_excel and json_for_excel['P_FirstName']:
            json_for_excel['P_FirstName'] = json_for_excel['P_FirstName'].capitalize().replace(',', '').replace('"', '')
        if 'P_MiddleNames' in json_for_excel and json_for_excel['P_MiddleNames']:
            json_for_excel['P_MiddleNames'] = json_for_excel['P_MiddleNames'].capitalize().replace(',', '').replace('"', '')
        # json_for_excel['R_Reason'] = json_for_excel['P_Surname'].capitalize().replace(',', '').replace('"', '')
        json_for_excel['R_ReasonForReferral'] = json_for_excel['P_Information']
        if json_for_excel.get('RF_Role', '') == '':
            json_for_excel['RF_Role']='Other Health Professional'
        if json_for_excel.get('RO_Name', '') == '':
            json_for_excel['RO_Name']='NA'
        if json_for_excel.get('RF_FirstName', '') == '':
            json_for_excel['RF_FirstName']='NA'
        # json_for_excel['P_MiddleNames'] = json_for_excel['P_MiddleNames'].capitalize().replace(',', '').replace('"', '')
        # json_for_excel['P_FirstName'] = json_for_excel['P_FirstName'].capitalize().replace(',', '').replace('"', '')
        return json_for_excel
    except Exception as e:
        print(f"Error transforming data: {e}")
        return {}


def create_data_row(json_for_csv):
    """
    Create a data row for the CSV output with default values for missing columns.
    """
    return {
        col: (
            '01234 567890' if col == 'P_HomeTelephone' and json_for_csv.get(col, '') in ('Landline:','') else
            '07939 064047' if col == 'P_Mobile' and json_for_csv.get(col, '') in ('Mobile:','') else
            'RFSNN' if col == 'RF_Surname' and json_for_csv.get(col, '') == '' else
            '5527' if col == 'RF_SchemeID' and json_for_csv.get('RO_Name', '').startswith('Cardiac') else
            '5411' if col == 'RF_SchemeID' and json_for_csv.get('RO_Name', '') != '' else
            json_for_csv.get(col, '')
        )
        for col in column_names
    }

def save_to_csv(data_rows, folder_path, email):
    """
    Save the processed data to a CSV file.

    Args:
        data_rows (list): List of data rows to save.
        folder_path (str): Path to the folder where the CSV file will be saved.
        email (str): User's email to generate the filename.

    Returns:
        dict: Success status, message, and CSV file path.
    """
    try:
        df = pd.DataFrame(data_rows)
        df = df.astype(str)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_email = email.replace('@', '_').replace('.', '_')
        csv_filename = f"output_{sanitized_email}_{timestamp}.csv"
        csv_file_path = os.path.join(folder_path, csv_filename)
        # need to remove last 3 columns
        df = df.iloc[:, :-3]
        df.to_csv(csv_file_path, index=False)
        print(f"Data successfully saved to {csv_file_path}")
        return {
            'success': True,
            'message': f"CSV file saved to {csv_file_path}",
            'fileName': csv_file_path
        }
    except Exception as e:
        print(f"Error saving CSV file: {e}")
        return {
            'success': False,
            'message': f"Error saving CSV file: {str(e)}",
            'fileName': ''
        }

def process_files_in_folder(folder_path, email="check"):
    """
    Process RTF files in the specified folder, extract data, and save to a CSV file.

    Args:
        folder_path (str): Path to the folder containing RTF files.
        email (str): User's email to generate the output folder and filename.

    Returns:
        dict: Success status, message, and path to the generated CSV file.
    """
    try:
        if not os.path.isdir(folder_path):
            print(f"Invalid folder path: {folder_path}")
            return {
                'success': False,
                'message': 'Invalid folder path',
                'fileName': ''
            }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_email = email.replace('@', '_').replace('.', '_')
        output_folder = os.path.join(os.path.dirname(folder_path), f"{sanitized_email}_{timestamp}")
        os.makedirs(output_folder, exist_ok=True)

        data_rows = []
        failed_files = []

        for filename in os.listdir(folder_path):
            # # check for pdf files
            # if not filename.lower().endswith('.rtf'):
            #     continue
            file_path = os.path.join(folder_path, filename)
            plain_text = ""
            file_type = filename.lower().split('.')[-1]
            # if condition for pdf
            if filename.lower().endswith('.pdf'):
                doc = fitz.open(file_path)
                # Iterate through all pages
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    plain_text += text + "\n"  # Append text from each page with a newline separator
                # print("Extracted text from PDF:", plain_text)  # Print first 100 characters for debuggin
                # Close the document
                doc.close()
            else:
                plain_text = read_rtf_file(file_path)

            if not plain_text:
                failed_files.append(filename)
                continue

            extracted_data = extract_data_from_text(plain_text,file_type)
            if not extracted_data:
                failed_files.append(filename)
                continue

            json_for_csv = transform_extracted_data(extracted_data)
            if not json_for_csv:
                failed_files.append(filename)
                continue

            data_row = create_data_row(json_for_csv)
            data_rows.append(data_row)

        if not data_rows:
            print(f"No valid RTF files processed in {folder_path}")
            return {
                'success': False,
                'message': 'No valid RTF files found',
                'fileName': ''
            }

        result = save_to_csv(data_rows, output_folder, email)
        if result['success'] and failed_files:
            result['message'] += f"\nFailed to process: {', '.join(failed_files)}"
        return result

    except Exception as e:
        print(f"Unexpected error in process_rtf_files_in_folder: {e}")
        return {
            'success': False,
            'message': f"Unexpected error: {str(e)}",
            'fileName': ''
        }