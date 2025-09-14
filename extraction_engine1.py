import os
import re
import pandas as pd
from datetime import datetime
from striprtf.striprtf import rtf_to_text
from global_variables import titles, column_names, keywords, default_values
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

def get_next_value(array_of_words, start_index, keywords):
    """
    Get the next non-empty value after a keyword, stopping if another keyword is found.
    """
    for j in range(start_index + 1, len(array_of_words)):
        next_value = array_of_words[j].strip()
        if next_value or array_of_words[j] in keywords:
            return next_value
    return ''

def extract_address(array_of_words, start_index, keywords):
    """
    Extract address lines until another keyword is found.
    Handles cases where address is on the same line as the keyword.
    """
    address_lines = []
    # Check if the keyword line contains address data after the keyword
    keyword_line = array_of_words[start_index]
    match = re.match(r'^(Address|Home address|Contact number)[:\s]*(.*)', keyword_line, re.IGNORECASE)
    if match and match.group(2).strip():
        address_lines.append(match.group(2).strip())
    # Now collect subsequent lines until another keyword
    for j in range(start_index + 1, len(array_of_words)):
        line = array_of_words[j].strip()
        print(f"Address extraction line: '{line}'")
        if not line:
            continue
        if any(re.match(rf'^{re.escape(kw)}[:\-]?', line, re.IGNORECASE) for kw in keywords):
            break
        address_lines.append(line)
    print(f"Extracted address lines: {address_lines}")
    return '\n'.join(address_lines).strip()

def extract_mobile_or_landline(array_of_words, i):
    """
    Extract mobile or landline number from array_of_words at index i.
    """
    number_candidate = array_of_words[i].strip()
    if not re.search(r'[0-9]', number_candidate) and i + 1 < len(array_of_words):
        number_candidate = array_of_words[i + 1].strip()
    if re.search(r'[0-9]', number_candidate):
        mobile_value = number_candidate.split()
        if len(mobile_value) > 2:
            mobile_value = ''.join(mobile_value[1:])
        else:
            mobile_value = mobile_value[-1]
        mobile_value = f'{mobile_value[:5]} {mobile_value[5:]}'.strip()
        return mobile_value.replace("(", "").replace(")", "")
    return ''

def generic_extract(extracted_data, key, value):
    """
    Generic extraction for fields where value is simply appended.
    """
    extracted_data[key] = value

def extract_data_from_text(plain_text, file_type):
    """
    Extract data from plain text based on keywords and special fields.
    """
    try:
        array_of_words = plain_text.split('\n') if file_type == 'pdf' else plain_text.split("|")
        array_of_words = [word.strip() for word in array_of_words if word.strip()]
        extracted_data = {}

        for i, word in enumerate(array_of_words):
            word = word.strip()
            if not word:
                continue

            for keyword in keywords:
                if re.search(rf'\b{re.escape(keyword)}\b', word, re.IGNORECASE):
                    if keyword == "Address":
                        extracted_data[keyword] = extract_address(array_of_words, i, keywords)
                    elif keyword in ('Referral Agent details', 'Referrer Agent details', 'Referral Details') or 'Referral Agent' in word:
                        extracted_data[keyword] = ' '.join(array_of_words[i + 1:]).strip()
                    else:
                        next_value = get_next_value(array_of_words, i, keywords)
                        if keyword not in extracted_data:
                            extracted_data[keyword] = next_value
                    break

            if 'Mobile' in word and not extracted_data.get('P_Mobile'):
                extracted_data['P_Mobile'] = extract_mobile_or_landline(array_of_words, i)

            if 'Information relevant to referral' in word:
                generic_extract(extracted_data, 'Related_Information', array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else '' )

            if 'Relevant medical conditions' in word:
                generic_extract(extracted_data, 'Relevant_Medical_Conditions', array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else '' )

            if 'To be completed by the referrer' in word:
                generic_extract(extracted_data, 'Reason_For_Referral', array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else '' )

            if 'Landline' in word or 'Telephone:' in word and not extracted_data.get('P_HomeTelephone'):
                extracted_data['P_HomeTelephone'] = extract_mobile_or_landline(array_of_words, i)

            if word == 'Standing height':
                extracted_data['R_StatType_Height_Value'] = ' '.join(array_of_words[i + 1:i + 2]).strip() if i + 1 < len(array_of_words) else ''
                extracted_data['R_StatType_Height_Date'] = array_of_words[i - 1].strip() if i - 1 >= 0 else ''

            if word == 'Body weight':
                extracted_data['R_StatType_Weight_Value'] = ' '.join(array_of_words[i + 1:i + 2]).strip() if i + 1 < len(array_of_words) else ''
                extracted_data['R_StatType_Weight_Date'] = array_of_words[i - 1].strip() if i - 1 >= 0 else ''

            if word == 'Email':
                generic_extract(extracted_data, 'P_EmailAddress', array_of_words[i + 1].strip() if i + 1 < len(array_of_words) else '' )

            if word == 'O/E- blood pressure reading':
                extracted_data['R_StatType_BloodPressure_Date'] = array_of_words[i - 1].strip() if i - 1 >= 0 else ''
                extracted_data['R_StatType_BloodPressure_Value'] = ' '.join(array_of_words[i + 1:i + 3]).strip() if i + 1 < len(array_of_words) else ''

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

def handle_name(value):
    value = re.sub(r'[()]', '', value)
    name_array = [part.strip().replace('.', '') for part in value.split()]
    result = {}
    if len(name_array) == 4:
        result = {
            'P_Title': name_array[0],
            'P_FirstName': name_array[1],
            'P_MiddleNames': name_array[2],
            'P_Surname': name_array[3]
        }
    elif len(name_array) == 3:
        if any(title in name_array for title in titles):
            title_index = next((i for i, word in enumerate(name_array) if word in titles), 0)
            if title_index == 2:
                result = {
                    'P_Title': name_array[2],
                    'P_FirstName': name_array[1],
                    'P_Surname': name_array[0]
                }
            else:
                result = {
                    'P_Title': name_array[0],
                    'P_FirstName': name_array[1],
                    'P_Surname': name_array[2]
                }
        else:
            result = {
                'P_FirstName': name_array[0],
                'P_MiddleNames': name_array[1],
                'P_Surname': name_array[2]
            }
    elif len(name_array) == 2:
        result = {
            'P_FirstName': name_array[0],
            'P_Surname': name_array[1]
        }
    # Handle misplaced uppercase surname/firstname with commas
    if 'P_FirstName' in result and ',' in result['P_FirstName'] and result['P_FirstName'].isupper():
        result['P_FirstName'], result['P_Surname'] = result['P_Surname'], result['P_FirstName'].replace(',', '').capitalize()
    elif 'P_Title' in result and ',' in result['P_Title'] and result['P_Title'].isupper():
        result['P_Title'], result['P_Surname'] = result['P_Surname'], result['P_Title'].replace(',', '').capitalize()
    return result

def handle_address(value):
    result = {}
    address = value.splitlines() if value.splitlines() else value.split(',')
    if address and address[0].strip().lower() == "home address":
        address.pop(0)
    if len(address) == 1 and ',' in address[0]:
        address = [part.strip() for part in address[0].split(',')]
    postcode_pattern = r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b'
    phone_pattern = r'(\b07\d{9}\b|\b01\d{9}\b|tel|mob|phone)'
    address_lines = [line for line in address if not re.search(postcode_pattern, line.upper()) and not re.search(phone_pattern, line.lower())]
    for i, add in enumerate(address_lines, 1):
        result[f'P_HomeAddress{i}'] = add.strip()
    # Find postcode in lines that do NOT contain phone numbers
    postcode = next((line.strip().upper() for line in address if re.search(postcode_pattern, line.upper()) and not re.search(phone_pattern, line.lower())), '')
    if postcode:
        result['P_HomePostcode'] = postcode
    return result

def handle_referral_agent(value):
    tokens = value.split()
    def normalize_token(t): return re.sub(r'[\s:;,.-]+$', '', t.strip().lower())
    def get_field(tokens, keyword, stop_words):
        try:
            norm_keyword = normalize_token(keyword)
            norm_stopwords = [normalize_token(s) for s in stop_words]
            idx = next(i for i, t in enumerate(tokens) if normalize_token(t) == norm_keyword)
            collected = []
            for t in tokens[idx + 1:]:
                if normalize_token(t) in norm_stopwords:
                    break
                collected.append(t)
            return " ".join(collected).strip()
        except StopIteration:
            return ""
    name_val = get_field(tokens, "Name", ["Organisation", "Contact", "Date"])
    org_val = get_field(tokens, "Organisation", ["Name", "Contact", "Date"])
    contact_val = get_field(tokens, "Contact", ["Name", "Organisation", "Date"])
    try:
        date_idx = next(i for i, t in enumerate(tokens) if t.lower() == "date")
        if date_idx + 3 < len(tokens) and tokens[date_idx:date_idx + 3] == ["Date", "of", "referral"]:
            ref_date = tokens[date_idx + 3] if date_idx + 3 < len(tokens) else ""
        else:
            ref_date = ""
    except StopIteration:
        ref_date = ""
    result = {}
    if name_val:
        result.update(parse_referral_name(name_val))
    if org_val:
        result['RO_Name'] = org_val
    if contact_val:
        result['RF_Contact'] = contact_val
    result['R_DateOfReferral'] = format_date(ref_date) if ref_date else "NA"
    return result

def generic_append(json_for_excel, key, value, p_information_parts):
    json_for_excel[key] = value
    p_information_parts.append(value)

def transform_extracted_data(extracted_data):
    """
    Transform extracted data into a format suitable for Excel output.
    """
    try:
        json_for_excel = {}
        p_information_parts = []

        for key, value in extracted_data.items():
            if not value or value.strip() == '':
                print(f"Skipping empty value for key: {key}")
                continue
            if key == 'Name':
                json_for_excel.update(handle_name(value))
            elif key == 'DOB':
                json_for_excel['P_DateOfBirth'] = format_date(value)
            elif key == 'Ethnicity':
                json_for_excel['P_Ethnicity'] = value
            elif key == 'Gender':
                json_for_excel['P_Gender'] = modify_gender_string(value)
            elif key == 'Address':
                print(f"Processing address: {value}")
                json_for_excel.update(handle_address(value))
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
                json_for_excel.update(handle_referral_agent(value))
            elif key in ('Reason_For_Referral', 'Relevant_Medical_Conditions', 'Related_Information'):
                generic_append(json_for_excel, key, value, p_information_parts)
            else:
                # For any other generic field, just append value
                generic_append(json_for_excel, key, value, p_information_parts)

        # Combine into P_Information
        json_for_excel['P_Information'] = ', '.join(
            part.replace('Select from drop down ', '')
                .replace('–', '-')  # replace en dash
                .replace('—', '-')  # replace em dash
                for part in p_information_parts if part
        )

        # Extra cleaning
        if 'P_HomeAddress3' in json_for_excel and re.search(r'[0-9]', json_for_excel['P_HomeAddress3']):
            json_for_excel['P_HomeAddress3'] = ''
        if 'P_DateOfBirth' in json_for_excel and re.search(r'\b\d{4}\b', json_for_excel['P_DateOfBirth']):
            birth_year = int(re.search(r'\b\d{4}\b', json_for_excel['P_DateOfBirth']).group())
            current_year = datetime.now().year
            if birth_year == current_year:
                json_for_excel['P_DateOfBirth'] += ' Invalid date'
        for name_field in ['P_Surname', 'P_FirstName', 'P_MiddleNames']:
            if name_field in json_for_excel and json_for_excel[name_field]:
                json_for_excel[name_field] = json_for_excel[name_field].capitalize().replace(',', '').replace('"', '')

        json_for_excel['R_ReasonForReferral'] = json_for_excel['P_Information']
        # Fill defaults
        for field, default_key in [
            ('RF_Role', "RF_Role"),
            ('RO_Name', "RO_Name"),
            ('RF_FirstName', "RF_FirstName")
        ]:
            if json_for_excel.get(field, '') == '':
                json_for_excel[field] = default_values.get(default_key, "")

        return json_for_excel
    except Exception as e:
        print(f"Error transforming data: {e}")
        return {}


def get_default_value(col, json_for_csv):
    """
    Return default value for a column if the extracted value is missing or invalid.
    Uses values from global_variables.default_values.
    """
    if col == 'P_HomeTelephone' and json_for_csv.get(col, '') in ('Landline:', ''):
        return default_values.get("P_HomeTelephone", "")
    if col == 'P_Mobile' and json_for_csv.get(col, '') in ('Mobile:', ''):
        return default_values.get("P_Mobile", "")
    if col == 'RF_Surname' and not json_for_csv.get(col, ''):
        return default_values.get("RF_Surname", "")
    if col == 'RF_SchemeID':
        if json_for_csv.get('RO_Name', '').startswith('Cardiac'):
            return default_values.get("RF_SchemeID_Cardiac", "")
        if json_for_csv.get('RO_Name', ''):
            return default_values.get("RF_SchemeID_Other", "")
    if col == 'RF_Role' and not json_for_csv.get(col, ''):
        return default_values.get("RF_Role", "")
    if col == 'RO_Name' and not json_for_csv.get(col, ''):
        return default_values.get("RO_Name", "")
    if col == 'RF_FirstName' and not json_for_csv.get(col, ''):
        return default_values.get("RF_FirstName", "")
    return json_for_csv.get(col, '')

def create_data_row(json_for_csv):
    """
    Create a data row for the CSV output with default values for missing columns.
    """
    return {col: get_default_value(col, json_for_csv) for col in column_names}

def save_to_csv(data_rows, folder_path, email, master_csv_path=None):
    """
    Save the processed data to a CSV file and append to master CSV file if provided.

    Args:
        data_rows (list): List of data rows to save.
        folder_path (str): Path to the folder where the CSV file will be saved.
        email (str): User's email to generate the filename.
        master_csv_path (str, optional): Path to the master CSV file.

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

        # Append to master CSV file
        if master_csv_path:
            if not os.path.exists(master_csv_path):
                df.to_csv(master_csv_path, index=False)
            else:
                df_master = pd.read_csv(master_csv_path, dtype=str)
                df_combined = pd.concat([df_master, df], ignore_index=True)
                df_combined.to_csv(master_csv_path, index=False)
            print(f"Data appended to master CSV: {master_csv_path}")

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

def check_and_print_matching_data(csv_file_path, first_name, surname):
    """
    Check the CSV file for rows where P_FirstName and P_Surname match the given values.
    Print the matching rows.
    """
    try:
        df = pd.read_csv(csv_file_path, dtype=str)
        matches = df[
            (df['P_FirstName'].str.strip().str.lower() == first_name.strip().lower()) &
            (df['P_Surname'].str.strip().str.lower() == surname.strip().lower())
        ]
        if not matches.empty:
            print("Matching rows found:")
            print(matches)
        else:
            print("No matching rows found.")
    except Exception as e:
        print(f"Error checking CSV file: {e}")

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
            file_path = os.path.join(folder_path, filename)
            plain_text = ""
            file_type = filename.lower().split('.')[-1]
            # if condition for pdf
            if filename.lower().endswith('.pdf'):
                doc = fitz.open(file_path)
                # Iterate through all pages
                for page_num, page in enumerate(doc):
                    text = page.get_text()
                    plain_text += text + "\n"
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