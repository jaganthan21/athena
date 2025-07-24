import os
import re
import pandas as pd
from datetime import datetime
from striprtf.striprtf import rtf_to_text
from global_variables import timestamp, excel_file_name, titles, column_names, keywords


def modify_gender_string(value):
    """
    Standardize gender values to a consistent format.

    Args:
        value (str): Gender value to process.

    Returns:
        str: Standardized gender string ('Male', 'Female', or capitalized input).
    """
    try:
        value = value.strip()  # Remove leading/trailing spaces
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

    Args:
        file_path (str): Path to the RTF file.

    Returns:
        str: Plain text content of the RTF file, or empty string if reading fails.
    """
    try:
        with open(file_path, 'rb') as file:
            rtf_content = file.read()
            return rtf_to_text(rtf_content.decode('latin1', errors='ignore'))
    except Exception as e:
        print(f"Error reading {os.path.basename(file_path)}: {e}")
        return ''


def extract_data_from_text(plain_text):
    """
    Extract data from plain text based on keywords and special fields.

    Args:
        plain_text (str): Plain text content from an RTF file.

    Returns:
        dict: Dictionary of extracted data with keywords as keys, values stripped of spaces.
    """
    try:
        array_of_words = plain_text.split("|")
        extracted_data = {}

        for i, word in enumerate(array_of_words):
            word = word.strip()
            if not word:
                continue

            # Keyword-based extraction
            for keyword in keywords:
                if re.search(rf'\b{re.escape(keyword)}\b', word, re.IGNORECASE):
                    if keyword in ('Referral Agent details', 'Referrer Agent details'):
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

            # Special field handling with stripped values
            if 'Mobile' in word:
                mobile_value = array_of_words[i].strip().split()
                mobile_value = ''.join(mobile_value[1:]) if len(mobile_value) > 2 else mobile_value[-1]
                mobile_value = f'{mobile_value[:5]} {mobile_value[5:]}'.strip()
                extracted_data['P_Mobile'] = mobile_value

            if 'Information relevant to referral' in word:
                extracted_data['Related_Information'] = array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else ''

            if 'Relevant medical conditions' in word:
                extracted_data['Relevant_Medical_Conditions'] = array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else ''

            if 'To be completed by the referrer' in word:
                extracted_data['Reason_For_Referral'] = array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else ''

            if 'Landline' in word:
                mobile_value = array_of_words[i].strip().split()
                mobile_value = ''.join(mobile_value[1:]) if len(mobile_value) > 2 else mobile_value[-1]
                mobile_value = f'{mobile_value[:5]} {mobile_value[5:]}'.strip()
                extracted_data['P_HomeTelephone'] = mobile_value

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

        return extracted_data
    except Exception as e:
        print(f"Error extracting data: {e}")
        return {}


def format_date(value, input_format='%d/%b/%Y', output_format='%d/%m/%Y'):
    """
    Format a date string to a consistent format.

    Args:
        value (str): Date string to format.
        input_format (str): Expected input format.
        output_format (str): Desired output format.

    Returns:
        str: Formatted date or 'NA' if parsing fails.
    """
    try:
        value = value.strip()  # Remove leading/trailing spaces
        print("Date value:", value)
        if not re.search(r'[0-9]', value):
            return 'NA'
        date_parts = value.split('-') if '-' in value else value.split('.')
        formatted_date = '/'.join(date_parts)
        if re.search(r'[a-z]', formatted_date, re.IGNORECASE):
            date_obj = datetime.strptime(formatted_date, input_format)
            return date_obj.strftime(output_format)
        return formatted_date
    except ValueError:
        return 'NA'


def clean_text(value):
    """
    Clean a text value by removing non-printable characters and leading/trailing spaces.

    Args:
        value (str): Text value to clean.

    Returns:
        str: Cleaned text value.
    """
    try:
        # Remove non-printable characters and strip spaces
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
                name_array = [part.strip() for part in value.split()]
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
                            json_for_excel['P_Surname'] = name_array[2]
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
            elif key == 'DOB':
                json_for_excel['P_DateOfBirth'] = format_date(value)
            elif key == 'Ethnicity':
                json_for_excel['P_Ethnicity'] = value
            elif key == 'Gender':
                json_for_excel['P_Gender'] = modify_gender_string(value)
            elif key == 'Address':
                address = value.splitlines() if value.splitlines() else value.split(',')
                for i, add in enumerate(address, 1):
                    json_for_excel[f'P_HomeAddress{i}'] = add.strip()
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
                # Split by lines, keep raw values
                ref_details = [line.strip() for line in value.splitlines() if line.strip()]
                if not ref_details:
                    continue

                # Extract organization name (assuming second line, after splitting by spaces)
                org_name = ref_details[1].split()[1:] if len(ref_details) > 1 else []
                json_for_excel['RO_Name'] = ' '.join(org_name).strip()

                # Extract referrer name (first line)
                ref_name = [part.strip() for part in re.sub(r'[()]', '', ref_details[0]).split() if part.strip()]
                
                # Extract date (last line, last word)
                ref_date = ''
                valid_date = False
                if len(ref_details) >= 3:
                    date_parts = ref_details[-1].split()
                    if date_parts:
                        ref_date = date_parts[-1]
                        print("Referrer date:", ref_date)
                        valid_date = bool(re.search(r'[0-9]', ref_date))

                # Parse referrer name
                if len(ref_name) >= 2:
                    if len(ref_name) == 2:
                        json_for_excel['RF_FirstName'] = ref_name[1]
                    elif len(ref_name) == 3:
                        if ref_name[1] == 'Dr':
                            json_for_excel['RF_FirstName'] = ref_name[2]
                            json_for_excel['RF_Role'] = 'Doctor'
                        else:
                            json_for_excel['RF_FirstName'] = ref_name[1]
                            json_for_excel['RF_Surname'] = ref_name[2]
                            json_for_excel['RF_Role'] = 'Other Health Professional'
                    elif len(ref_name) == 4:
                        json_for_excel['RF_FirstName'] = ref_name[2]
                        json_for_excel['RF_Surname'] = ref_name[3]
                        json_for_excel['RF_Role'] = 'Doctor' if ref_name[1] == 'Dr' else 'Other Health Professional'

                # Format referral date
                json_for_excel['R_DateOfReferral'] = format_date(ref_date) if valid_date else 'NA'

            # Collect fields for P_Information
            if key in ('Reason_For_Referral', 'Relevant_Medical_Conditions', 'Related_Information'):
                json_for_excel[key] = value
                p_information_parts.append(value)

        # Combine Reason_For_Referral, Relevant_Medical_Conditions, and Related_Information into P_Information
        json_for_excel['P_Information'] = ', '.join(part for part in p_information_parts if part)

        return json_for_excel
    except Exception as e:
        print(f"Error transforming data: {e}")
        return {}


def create_data_row(json_for_excel):
    """
    Create a data row for the Excel output with default values for missing columns.

    Args:
        json_for_excel (dict): Transformed data for Excel.

    Returns:
        dict: Data row with column names as keys and appropriate values.
    """
    return {
        col: (
            '01234 567890' if col == 'P_HomeTelephone' and json_for_excel.get(col, '') == 'Landline:' else
            '07939 064047' if col == 'P_Mobile' and json_for_excel.get(col, '') == 'Mobile:' else
            'RFSNN' if col == 'RF_Surname' and json_for_excel.get(col, '') == '' else
            '5527' if col == 'RF_SchemeID' and json_for_excel.get('RO_Name', '').startswith('Cardiac') else
            '5411' if col == 'RF_SchemeID' and json_for_excel.get('RO_Name', '') != '' else
            json_for_excel.get(col, '')
        )
        for col in column_names
    }


def save_to_excel(data_rows, folder_path):
    """
    Save the processed data to an Excel file.

    Args:
        data_rows (list): List of data rows to save.
        folder_path (str): Path to the folder where the Excel file will be saved.

    Returns:
        str: Excel file name if successful, empty string if saving fails.
    """
    try:
        df = pd.DataFrame(data_rows)
        # Ensure all values are strings to avoid Excel formatting issues
        df = df.astype(str)
        excel_file_path = os.path.join(folder_path, excel_file_name)
        df.to_excel(excel_file_path, index=False, engine='openpyxl')
        print(f"Data successfully saved to {excel_file_path}")
        return excel_file_name
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        return ''


def process_rtf_files_in_folder(folder_path):
    """
    Process RTF files in the specified folder, extract data, and save to an Excel file.

    Args:
        folder_path (str): Path to the folder containing RTF files.

    Returns:
        str: Path to the generated Excel file or empty string if processing fails.

    Notes:
        - Extracts data based on keywords and formats it into a structured DataFrame.
        - Combines Reason_For_Referral, Relevant_Medical_Conditions, and Related_Information into P_Information.
        - Retains the original three columns in the output.
        - Ensures all values are clean and visible in Excel formula bar.
        - Removes leading/trailing spaces and non-printable characters from Email values only.
    """
    try:
        if not os.path.isdir(folder_path):
            print(f"Invalid folder path: {folder_path}")
            return ''

        data_rows = []
        failed_files = []

        for filename in os.listdir(folder_path):
            if not filename.lower().endswith('.rtf'):
                continue

            file_path = os.path.join(folder_path, filename)
            plain_text = read_rtf_file(file_path)
            if not plain_text:
                failed_files.append(filename)
                continue

            extracted_data = extract_data_from_text(plain_text)
            if not extracted_data:
                failed_files.append(filename)
                continue

            json_for_excel = transform_extracted_data(extracted_data)
            if not json_for_excel:
                failed_files.append(filename)
                continue

            data_row = create_data_row(json_for_excel)
            data_rows.append(data_row)

        if not data_rows:
            print(f"No valid RTF files processed in {folder_path}")
            return ''

        return save_to_excel(data_rows, folder_path)

    except Exception as e:
        print(f"Unexpected error in process_rtf_files_in_folder: {e}")
        return ''