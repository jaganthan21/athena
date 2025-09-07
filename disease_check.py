import re
from striprtf.striprtf import rtf_to_text

file_path = r"C:\Users\Mekkanos\Downloads\check_disease\check.rtf"

def extract_selected_dropdowns(rtf_content):
    results = []
    # Find fldrslt blocks following FORMDROPDOWN
    pattern = r'FORMDROPDOWN.*?{\\fldrslt([^}]*)}'
    for match in re.finditer(pattern, rtf_content, re.DOTALL):
        raw_value = match.group(1)
        # Clean the RTF formatting
        value = rtf_to_text(raw_value).strip()
        if value:
            results.append(value)
    return results

# Example usage
with open(file_path, "r", encoding="utf-8") as f:
    rtf_content = f.read()

selected = extract_selected_dropdowns(rtf_content)
print("Selected dropdowns:", selected)
