import os
import re
import pandas as pd
from datetime import datetime
from striprtf.striprtf import rtf_to_text
from global_variables import titles, column_names, keywords

import fitz

# Configuration for dynamic values
CONFIG = {
    'default_phone': '01234 567890',
    'default_mobile': '07939 064047',
    'default_rf_surname': 'RFSNN',
    'scheme_ids': {
        'Cardiac': '5527',
        'default': '5411'
    },
    'role_keywords': [
        'physiotherapist', 'consultant', 'nurse', 'gp', 'surgeon',
        'therapist', 'specialist', 'doctor', 'pharmacist', 'dentist',
        'midwife', 'practitioner', 'prescriber', 'behavioural'
    ],
    'title_roles': {
        'dr': 'Doctor',
        'prof': 'Doctor',
        'mr': 'Other Health Professional',
        'mrs': 'Other Health Professional',
        'ms': 'Other Health Professional',
        'miss': 'Other Health Professional',
        'nurse': 'Other Health Professional'
    }
}

def normalize_gender(value):
    """Standardize gender values to a consistent format."""
    if not value or not isinstance(value, str):
        return ''
    value = value.strip().lower()
    return 'Female' if value in ('f', 'female') else 'Male' if value in ('m', 'male') else value.capitalize()

def read_rtf_file(file_path):
    """Read an RTF file and convert it to plain text."""
    try:
        with open(file_path, 'rb') as file:
            return rtf_to_text(file.read().decode('latin1', errors='ignore'))
    except Exception as e:
        print(f"Error reading {os.path.basename(file_path)}: {e}")
        return ''

def read_pdf_file(file_path):
    """Read a PDF file and extract text from all pages."""
    try:
        doc = fitz.open(file_path)
        text = '\n'.join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        print(f"Error reading {os.path.basename(file_path)}: {e}")
        return ''

def read_file(file_path):
    """Read file content based on its extension."""
    file_type = file_path.lower().split('.')[-1]
    if file_type == 'pdf':
        return read_pdf_file(file_path), file_type
    elif file_type == 'rtf':
        return read_rtf_file(file_path), file_type
    return '', file_type

def extract_data_from_text(text, file_type, keywords):
    """Extract data from text based on keywords and special fields."""
    try:
        # Split text based on file type
        words = text.split('\n' if file_type == 'pdf' else '|')
        words = [w.strip() for w in words if w.strip()]
        extracted_data = {}

        # Handle keyword-based extraction
        for i, word in enumerate(words):
            for keyword in keywords:
                if re.search(rf'\b{re.escape(keyword)}\b', word, re.IGNORECASE):
                    if 'Referral' in keyword or 'Referral Agent' in word:
                        extracted_data[keyword] = ' '.join(words[i + 1:]).strip()
                        break
                    next_value = next((words[j].strip() for j in range(i + 1, len(words)) if words[j].strip()), '')
                    extracted_data[keyword] = next_value
                    break

            # Define special field handlers
            def handle_phone(word, index, words):
                """Handle phone number fields (Mobile, Landline)."""
                if re.search(r'[0-9]', word):
                    parts = word.split()
                    value = ''.join(parts[1:])[-10:].replace('(', '').replace(')', '')
                    return value
                return ''

            def handle_next_value(word, index, words):
                """Handle fields that take the next word as value."""
                return words[index + 1].strip() if index + 1 < len(words) else ''

            def handle_stat_type(word, index, words, value_field, date_field):
                """Handle stat type fields (Height, Weight)."""
                return {
                    value_field: ' '.join(words[index + 1:index + 2]).strip() if index + 1 < len(words) else '',
                    date_field: words[index - 1].strip() if index - 1 >= 0 else ''
                }

            def handle_blood_pressure(word, index, words):
                """Handle blood pressure field."""
                return {
                    'R_StatType_BloodPressure_Date': words[index - 1].strip() if index - 1 >= 0 else '',
                    'R_StatType_BloodPressure_Value': ' '.join(words[index + 1:index + 3]).strip() if index + 1 < len(words) else ''
                }

            # Special fields configuration
            special_fields = {
                'Mobile': {'field': 'P_Mobile', 'handler': handle_phone},
                'Landline': {'field': 'P_HomeTelephone', 'handler': handle_phone},
                'Email': {'field': 'P_EmailAddress', 'handler': handle_next_value},
                'Information relevant to referral': {'field': 'Related_Information', 'handler': handle_next_value},
                'Relevant medical conditions': {'field': 'Relevant_Medical_Conditions', 'handler': handle_next_value},
                'To be completed by the referrer': {'field': 'Reason_For_Referral', 'handler': handle_next_value},
                'Standing height': {
                    'field': ['R_StatType_Height_Value', 'R_StatType_Height_Date'],
                    'handler': lambda w, i, ws: handle_stat_type(w, i, ws, 'R_StatType_Height_Value', 'R_StatType_Height_Date')
                },
                'Body weight': {
                    'field': ['R_StatType_Weight_Value', 'R_StatType_Weight_Date'],
                    'handler': lambda w, i, ws: handle_stat_type(w, i, ws, 'R_StatType_Weight_Value', 'R_StatType_Weight_Date')
                },
                'O/E- blood pressure reading': {
                    'field': ['R_StatType_BloodPressure_Date', 'R_StatType_BloodPressure_Value'],
                    'handler': handle_blood_pressure
                }
            }

            # Process special fields
            for key, config in special_fields.items():
                if key in word:
                    try:
                        handler = config['handler']
                        field = config['field']
                        if not callable(handler):
                            print(f"Error: Handler for '{key}' is not callable: {handler}")
                            continue
                        if isinstance(field, list):
                            result = handler(word, i, words)
                            if not isinstance(result, dict):
                                print(f"Error: Handler for '{key}' returned invalid result: {result}")
                                continue
                            extracted_data.update(result)
                        else:
                            extracted_data[field] = handler(word, i, words)
                    except Exception as e:
                        print(f"Error processing special field '{key}' in file: {e}")
                    break

        return extracted_data
    except Exception as e:
        print(f"Error extracting data: {e}")
        return {}

def format_date(value, output_format='%d/%m/%Y'):
    """Format a date string to a consistent format, supporting various month formats."""
    if not value or not re.search(r'[0-9]', value):
        return 'NA'
    
    try:
        value = re.sub(r'[-.\s]+', '/', value.strip())
        for fmt in ('%d/%b/%Y', '%d/%B/%Y'):
            try:
                return datetime.strptime(value, fmt).strftime(output_format)
            except ValueError:
                continue
        return value if re.match(r'\d{1,2}/\d{1,2}/\d{4}', value) else 'NA'
    except ValueError:
        return 'NA'

def parse_referral_name(name_val):
    """Parse referral name into FirstName, Surname, and Role."""
    if not name_val:
        return {'RF_FirstName': '', 'RF_Surname': '', 'RF_Role': ''}

    result = {'RF_FirstName': '', 'RF_Surname': '', 'RF_Role': ''}
    first_line = name_val.splitlines()[0].strip()
    parts = [p.strip() for p in first_line.split('-') if p.strip()]
    name_part = re.sub(r'\([^)]*\)', '', parts[0]).strip()
    role_part = parts[1] if len(parts) > 1 else None
    tokens = [t.strip(',.') for t in name_part.split() if t.strip()]

    if tokens:
        if tokens[0].lower() in CONFIG['title_roles']:
            result['RF_Role'] = CONFIG['title_roles'][tokens[0].lower()]
            tokens = tokens[1:]

        if not role_part:
            for i, token in enumerate(tokens):
                if any(r in token.lower() for r in CONFIG['role_keywords']):
                    result['RF_Role'] = ' '.join(tokens[i:])
                    tokens = tokens[:i]
                    break

        if tokens:
            result['RF_FirstName'] = tokens[0]
            surname_candidates = [t for t in tokens[1:] if re.match(r"^[A-Za-z'-]+$", t)]
            result['RF_Surname'] = surname_candidates[-1] if surname_candidates else ''

    if role_part:
        result['RF_Role'] = role_part.strip(' ,.-')

    if result['RF_Role']:
        result['RF_Role'] = 'Doctor' if result['RF_Role'].lower().startswith(('doctor', 'dr')) else 'Other Health Professional'

    return result

def clean_text(value):
    """Remove non-printable characters and extra spaces from text."""
    return re.sub(r'[^\x20-\x7E]', '', str(value).strip()) if value else ''

def transform_extracted_data(extracted_data, titles):
    """Transform extracted data into a format suitable for CSV output."""
    try:
        result = {}
        p_information_parts = []

        for key, value in extracted_data.items():
            if not value or not value.strip():
                continue

            if key == 'Name':
                value = re.sub(r'[()]', '', value)
                name_array = [part.strip().replace('.', '').replace('"', '') for part in value.split()]
                name_array = [part for part in name_array if part]

                if len(name_array) == 4:
                    result.update({
                        'P_Title': name_array[0],
                        'P_FirstName': name_array[1].capitalize(),
                        'P_MiddleNames': name_array[2].capitalize(),
                        'P_Surname': name_array[3].capitalize()
                    })
                elif len(name_array) == 3:
                    if any(title in name_array for title in titles):
                        title_index = next(i for i, word in enumerate(name_array) if word in titles)
                        if title_index == 2:
                            result.update({
                                'P_Title': name_array[2],
                                'P_FirstName': name_array[1].capitalize(),
                                'P_Surname': name_array[0].capitalize()
                            })
                        else:
                            result.update({
                                'P_Title': name_array[0],
                                'P_FirstName': name_array[1].capitalize(),
                                'P_Surname': name_array[2].capitalize()
                            })
                    else:
                        result.update({
                            'P_FirstName': name_array[0].capitalize(),
                            'P_MiddleNames': name_array[1].capitalize(),
                            'P_Surname': name_array[2].capitalize()
                        })
                elif len(name_array) == 2:
                    result.update({
                        'P_FirstName': name_array[0].capitalize(),
                        'P_Surname': name_array[1].capitalize()
                    })

                if result.get('P_FirstName', '').isupper() and ',' in result['P_FirstName']:
                    result['P_FirstName'], result['P_Surname'] = result['P_Surname'], result['P_FirstName'].replace(',', '').capitalize()
                elif result.get('P_Title', '').isupper() and ',' in result['P_Title']:
                    result['P_Title'], result['P_Surname'] = result['P_Surname'], result['P_Title'].replace(',', '').capitalize()

            elif key == 'DOB':
                result['P_DateOfBirth'] = format_date(value)
            elif key == 'Ethnicity':
                result['P_Ethnicity'] = value
            elif key == 'Gender':
                result['P_Gender'] = normalize_gender(value)
            elif key == 'Address':
                address = value.splitlines() or value.split(',')
                if address and address[0].strip().lower() == 'home address':
                    address.pop(0)
                if len(address) == 1 and ',' in address[0]:
                    address = [part.strip() for part in address[0].split(',')]
                for i, add in enumerate(address, 1):
                    result[f'P_HomeAddress{i}'] = add.strip()
            elif key == 'Postcode':
                result['P_HomePostcode'] = value.upper()
            elif key in ('Referral Agent details', 'Referrer Agent details'):
                tokens = value.split()
                def get_field(tokens, keyword, stop_words):
                    norm_keyword = re.sub(r'[\s:;,.-]+$', '', keyword.lower())
                    norm_stopwords = [re.sub(r'[\s:;,.-]+$', '', s.lower()) for s in stop_words]
                    try:
                        idx = next(i for i, t in enumerate(tokens) if re.sub(r'[\s:;,.-]+$', '', t.lower()) == norm_keyword)
                        collected = []
                        for t in tokens[idx + 1:]:
                            if re.sub(r'[\s:;,.-]+$', '', t.lower()) in norm_stopwords:
                                break
                            collected.append(t)
                        return ' '.join(collected).strip()
                    except StopIteration:
                        return ''

                name_val = get_field(tokens, 'Name', ['Organisation', 'Contact', 'Date'])
                org_val = get_field(tokens, 'Organisation', ['Name', 'Contact', 'Date'])
                contact_val = get_field(tokens, 'Contact', ['Name', 'Organisation', 'Date'])
                try:
                    date_idx = next(i for i, t in enumerate(tokens) if t.lower() == 'date')
                    ref_date = tokens[date_idx + 3] if date_idx + 3 < len(tokens) and tokens[date_idx:date_idx+3] == ['Date', 'of', 'referral'] else ''
                except StopIteration:
                    ref_date = ''

                if name_val:
                    result.update(parse_referral_name(name_val))
                result['RO_Name'] = org_val or 'NA'
                result['RF_Contact'] = contact_val
                result['R_DateOfReferral'] = format_date(ref_date) if ref_date else 'NA'
            else:
                result[key] = value
                if key in ('Reason_For_Referral', 'Relevant_Medical_Conditions', 'Related_Information'):
                    p_information_parts.append(value)

        result['P_Information'] = ', '.join(part.replace('Select from drop down ', '') for part in p_information_parts if part)
        result['R_ReasonForReferral'] = result.get('P_Information', '')
        
        if result.get('P_HomeAddress3') and re.search(r'[0-9]', result['P_HomeAddress3']):
            result['P_HomeAddress3'] = ''
        if result.get('P_DateOfBirth') and re.search(r'\b\d{4}\b', result['P_DateOfBirth']):
            birth_year = int(re.search(r'\b\d{4}\b', result['P_DateOfBirth']).group())
            if birth_year == datetime.now().year:
                result['P_DateOfBirth'] += ' Invalid date'
        result['RF_Role'] = result.get('RF_Role', 'Other Health Professional')
        result['RF_FirstName'] = result.get('RF_FirstName', 'NA')

        return result
    except Exception as e:
        print(f"Error transforming data: {e}")
        return {}

def create_data_row(json_data, column_names):
    """Create a data row for CSV output with default values for missing columns."""
    return {
        col: (
            CONFIG['default_phone'] if col == 'P_HomeTelephone' and json_data.get(col, '') in ('Landline:', '') else
            CONFIG['default_mobile'] if col == 'P_Mobile' and json_data.get(col, '') in ('Mobile:', '') else
            CONFIG['default_rf_surname'] if col == 'RF_Surname' and json_data.get(col, '') == '' else
            CONFIG['scheme_ids']['Cardiac'] if col == 'RF_SchemeID' and json_data.get('RO_Name', '').startswith('Cardiac') else
            CONFIG['scheme_ids']['default'] if col == 'RF_SchemeID' and json_data.get('RO_Name', '') != '' else
            json_data.get(col, '')
        )
        for col in column_names
    }

def save_to_csv(data_rows, folder_path, email):
    """Save processed data to a CSV file."""
    try:
        df = pd.DataFrame(data_rows).astype(str).iloc[:, :-3]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        sanitized_email = email.replace('@', '_').replace('.', '_')
        csv_filename = f'output_{sanitized_email}_{timestamp}.csv'
        csv_file_path = os.path.join(folder_path, csv_filename)
        df.to_csv(csv_file_path, index=False)
        print(f"Data successfully saved to {csv_file_path}")
        return {
            'success': True,
            'message': f'CSV file saved to {csv_file_path}',
            'fileName': csv_file_path
        }
    except Exception as e:
        print(f"Error saving CSV file: {e}")
        return {
            'success': False,
            'message': f'Error saving CSV file: {str(e)}',
            'fileName': ''
        }

def process_files_in_folder(folder_path, email='check', keywords=keywords ,column_names=column_names, titles=titles):
    """Process RTF and PDF files in the specified folder, extract data, and save to CSV."""
    if not keywords or not column_names or not titles:
        raise ValueError("Required global variables (keywords, column_names, titles) must be provided")

    try:
        if not os.path.isdir(folder_path):
            print(f"Invalid folder path: {folder_path}")
            return {'success': False, 'message': 'Invalid folder path', 'fileName': ''}

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        sanitized_email = email.replace('@', '_').replace('.', '_')
        output_folder = os.path.join(os.path.dirname(folder_path), f'{sanitized_email}_{timestamp}')
        os.makedirs(output_folder, exist_ok=True)

        data_rows = []
        failed_files = []

        for filename in os.listdir(folder_path):
            if not filename.lower().endswith(('.rtf', '.pdf')):
                continue

            file_path = os.path.join(folder_path, filename)
            text, file_type = read_file(file_path)
            if not text:
                failed_files.append(filename)
                continue

            extracted_data = extract_data_from_text(text, file_type, keywords)
            if not extracted_data:
                failed_files.append(filename)
                continue

            json_data = transform_extracted_data(extracted_data, titles)
            if not json_data:
                failed_files.append(filename)
                continue

            data_row = create_data_row(json_data, column_names)
            data_rows.append(data_row)

        if not data_rows:
            print(f"No valid files processed in {folder_path}")
            return {'success': False, 'message': 'No valid files found', 'fileName': ''}

        result = save_to_csv(data_rows, output_folder, email)
        if result['success'] and failed_files:
            result['message'] += f"\nFailed to process: {', '.join(failed_files)}"
        return result

    except Exception as e:
        print(f"Unexpected error in process_files_in_folder: {e}")
        return {'success': False, 'message': f'Unexpected error: {str(e)}', 'fileName': ''}