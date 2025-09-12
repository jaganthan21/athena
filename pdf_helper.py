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
        # print("Array of words:", array_of_words)  # Debugging output

        for i, word in enumerate(array_of_words):
            word = word.strip()
            if not word:
                continue

            for keyword in keywords:
                if re.search(rf'\b{re.escape(keyword)}\b', word, re.IGNORECASE):
                    # if keyword contains "Referral" word 
                    if keyword in ('Referral Agent details', 'Referrer Agent details', 'Referral Details') or 'Referral Agent' in word:
                        # print("Found keyword:", keyword)  # Debugging output
                        # print("Context words:", array_of_words[max(0, i-2):min(len(array_of_words), i+5)])  # Debugging output
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
                # Only capture if not already set
                if not extracted_data.get('P_Mobile'):
                    # Look ahead if current slot is blank
                    number_candidate = array_of_words[i].strip()
                    if not re.search(r'[0-9]', number_candidate)  and i + 1 < len(array_of_words):
                        number_candidate = array_of_words[i + 1].strip()

                    print("Candidate mobile:", number_candidate)

                    if re.search(r'[0-9]', number_candidate):
                        mobile_value = number_candidate.split()
                        if len(mobile_value) > 2:
                            mobile_value = ''.join(mobile_value[1:])
                        else:
                            mobile_value = mobile_value[-1]
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

            if 'Landline' in word or 'Telephone:' in word:
                print("Debug: Landline/Telephone found:", word)

                # Only capture if not already set
                if not extracted_data.get('P_HomeTelephone'):
                    # Look ahead if current slot is blank
                    number_candidate = array_of_words[i].strip()
                    if not re.search(r'[0-9]', number_candidate)  and i + 1 < len(array_of_words):
                        number_candidate = array_of_words[i + 1].strip()

                    print("Candidate number:", number_candidate)

                    if re.search(r'[0-9]', number_candidate):
                        mobile_value = number_candidate.split()
                        # if it has extra words before the number
                        if len(mobile_value) > 2:
                            mobile_value = ''.join(mobile_value[1:])
                        else:
                            mobile_value = mobile_value[-1]
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

def parse_referral_name(name_val):
    result = {"RF_FirstName": "", "RF_Surname": "", "RF_Role": ""}

    if not name_val:
        return result

    # Step 0: Only keep the first line if multiple lines exist
    first_line = name_val.splitlines()[0].strip()

    # Known role keywords
    role_keywords = {
        "physiotherapist", "consultant", "nurse", "gp", "surgeon",
        "therapist", "specialist", "doctor", "pharmacist", "dentist",
        "midwife", "practitioner", "prescriber", "cognitive","behavioural","psychologist"
    }

    # Noise markers
    noise_markers = {
        "http", "www", "tel", "mob", "fax", "email", "nhs", "hospital",
        "centre", "clinic", "street", "road", "avenue", "building", "floor"
    }

    # Post nominals
    post_nominals = {"fcp", "mbbs", "md", "phd", "msc", "bsc", "frcs", "facs", "do", "mrcgp"}

    # Title roles
    title_roles = {
        "dr": "Doctor",
        "prof": "Doctor",
        "mr": "Other Health Professional",
        "mrs": "Other Health Professional",
        "ms": "Other Health Professional",
        "miss": "Other Health Professional",
        "nurse": "Other Health Professional"
    }

    # Step 1: Tokenize original line
    tokens = first_line.split()

    # Step 2: Remove parenthesis blocks
    removed_indices = set()
    paren_spans_text = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if "(" in tok:
            start = i
            j = i
            found_end = False
            while j < len(tokens):
                if ")" in tokens[j]:
                    found_end = True
                    break
                j += 1
            end = j if found_end else len(tokens) - 1
            span = tokens[start:end + 1] if found_end else tokens[start:]
            cleaned_span = " ".join(re.sub(r'^[\(\)\.,]+|[\(\)\.,]+$', '', s) for s in span).strip()
            if cleaned_span:
                paren_spans_text.append(cleaned_span)
            for idx in range(start, end + 1):
                removed_indices.add(idx)
            i = end + 1
        else:
            i += 1

    tokens_no_paren = [t for idx, t in enumerate(tokens) if idx not in removed_indices]
    lower_tokens_no_paren = [re.sub(r"\W", "", t).lower() for t in tokens_no_paren]

    # Step 3: cut at role/noise marker
    cut_index = len(tokens_no_paren)
    for i, tok in enumerate(lower_tokens_no_paren):
        if tok in role_keywords or any(tok.startswith(marker) for marker in noise_markers):
            cut_index = i
            break

    name_tokens = tokens_no_paren[:cut_index] if cut_index > 0 else tokens_no_paren[:2]
    role_tokens = []
    if cut_index < len(tokens_no_paren) and lower_tokens_no_paren[cut_index] in role_keywords:
        role_tokens = tokens_no_paren[cut_index:]

    name_part = " ".join(name_tokens)
    role_part = " ".join(role_tokens) if role_tokens else None

    if not role_part and paren_spans_text:
        paren_join = " ".join(paren_spans_text).lower()
        if any(k in paren_join for k in role_keywords) or "physio" in paren_join:
            role_part = " ".join(paren_spans_text)

    parts = [p.strip() for p in name_part.split('-') if p.strip()]
    name_part = parts[0] if parts else ""
    role_part = parts[1] if len(parts) > 1 else role_part

    name_clean = re.sub(r'\([^)]*\)', '', name_part).strip()
    raw_tokens = [part.strip().strip(",.") for part in name_clean.split() if part.strip()]

    # Normalize dotted names like R.Norris or A.B.Smith
    ref_name = []
    for tok in raw_tokens:
        if "." in tok and re.match(r"^[A-Za-z](?:\.[A-Za-z])+\.?[A-Za-z]*$", tok):
            ref_name.extend([p for p in tok.split(".") if p])
        else:
            ref_name.append(tok)

    role = None
    first_name = ""
    surname = ""

    if ref_name:
        if ref_name[0].lower() in title_roles:
            role = title_roles[ref_name[0].lower()]
            ref_name = ref_name[1:]

        if not role_part:
            lower_ref_name = [t.lower().strip(",.") for t in ref_name]
            for i, token in enumerate(lower_ref_name):
                if token in role_keywords or token == "physio":
                    role = " ".join(ref_name[i:])
                    ref_name = ref_name[:i]
                    break

        valid_tokens = [t for t in ref_name if t.lower() not in post_nominals]
        if len(valid_tokens) > 1:
            surname = valid_tokens[-1]
            first_name = " ".join(valid_tokens[:-1])
        elif len(valid_tokens) == 1:
            first_name = valid_tokens[0]

    if role_part:
        role = role_part

    if role:
        role = role.strip(" ,.-")
        if role.lower().startswith("doctor") or role.lower().startswith("dr"):
            role = "Doctor"
        else:
            role = "Other Health Professional"

    # --- NEW CHANGE #1: swap if first name is uppercase ---
    if first_name.isupper() and len(first_name) > 1 and surname and not surname.isupper():
        first_name, surname = surname, first_name

    # --- NEW CHANGE #2: final capitalization ---
    first_name = first_name.replace(",", "").title()
    surname = surname.replace(",", "").title()

    result["RF_FirstName"] = first_name
    result["RF_Surname"] = surname
    result["RF_Role"] = role if role else ""

    return result


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
        # print("Extracted referal data:", extracted_data["Referral Agent details"])  # Debugging output
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
                print("Debug: Raw address lines:", value)
                if address and address[0].strip().lower() == "home address":
                    address.pop(0)
                # print("Debug: Address lines:", address)
                if len(address)==1 and ',' in address[0]:
                    address = [part.strip() for part in address[0].split(',')]

                for i, add in enumerate(address, 1):
                    json_for_excel[f'P_HomeAddress{i}'] = add.strip()
                # if last index has numbers then assign it to postcode
                if re.search(r'[0-9]', address[-1]):
                    json_for_excel['P_HomePostcode'] = address[-1].strip().upper()
                    print("Debug: Moved address line 4 to postcode:", json_for_excel['P_HomePostcode'])
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

                def normalize_token(t):
                    """Lowercase and remove trailing punctuation like ':', ',', '.', ';', '-'."""
                    return re.sub(r'[\s:;,.-]+$', '', t.strip().lower())

                def get_field(tokens, keyword, stop_words):
                    try:
                        # normalize keyword and stop_words for comparison
                        norm_keyword = normalize_token(keyword)
                        norm_stopwords = [normalize_token(s) for s in stop_words]

                        # find index of keyword in tokens
                        idx = next(i for i, t in enumerate(tokens) if normalize_token(t) == norm_keyword)

                        collected = []
                        for t in tokens[idx + 1:]:
                            if normalize_token(t) in norm_stopwords:
                                break
                            collected.append(t)

                        return " ".join(collected).strip()
                    except StopIteration:
                        return ""
                # print("Referral Agent details tokens:", tokens)  # Debugging output

                # Extract fields
                name_val = get_field(tokens, "Name", ["Organisation", "Contact", "Date"])
                org_val = get_field(tokens, "Organisation", ["Name", "Contact", "Date"])
                contact_val = get_field(tokens, "Contact", ["Name", "Organisation", "Date"])
                
                if len(org_val.split("\n")) > 1:    
                    # print("Extracted Organisation:", org_val)  # Debugging output
                    pass
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
                    print("Extracted Referral Name:", name_val)  # Debugging output
                    results = parse_referral_name(name_val)
                    json_for_excel.update(results)

                if org_val:
                    json_for_excel['RO_Name'] = org_val
                if contact_val:
                    json_for_excel['RF_Contact'] = contact_val

                json_for_excel['R_DateOfReferral'] = format_date(ref_date) if ref_date else "NA"
                # print("Referal Organistaion name:", json_for_excel.get('RO_Name', 'Not found'))
                # print("Referal Contact name:", json_for_excel.get('RF_Contact', 'Not found'))
                # print("Referal First name:", json_for_excel.get('RF_FirstName', 'Not found'))
                # print("Referal Surname name:", json_for_excel.get('RF_Surname', 'Not found'))
                # print("Referal Role:", json_for_excel.get('RF_Role', 'Not found'))
                # print("Referal Date of referral:", json_for_excel.get('R_DateOfReferral', 'Not found'))
           

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