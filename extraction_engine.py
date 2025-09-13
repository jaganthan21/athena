"""
Refactored RTF/PDF processing module
- Kept public API (process_files_in_folder) name intact as requested
- Removed redundant logic and debug prints
- Modularized helper routines
- Added logging (no prints)
- Added type hints and clearer comments
- Preserved behaviour as much as possible while making code cleaner

Usage: call process_files_in_folder(folder_path, email)

Dependencies: pandas, fitz (PyMuPDF), striprtf, global_variables
"""

import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Any

import pandas as pd
import fitz
from striprtf.striprtf import rtf_to_text

from global_variables import titles, column_names, keywords

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ----------------------------- Utility helpers -----------------------------

def _safe_strip(value: Any) -> str:
    """Return a cleaned string or empty string for None/non-str types."""
    try:
        return str(value).strip()
    except Exception:
        return ""


def clean_text(value: Any) -> str:
    """Remove non-printable characters and trim whitespace."""
    val = _safe_strip(value)
    return re.sub(r"[^\x20-\x7E]", "", val)


# ----------------------------- Input readers --------------------------------

def read_rtf_file(file_path: str) -> str:
    """Read RTF file bytes and convert to plain text. Returns empty string on error."""
    try:
        with open(file_path, "rb") as fh:
            raw = fh.read()
        # striprtf expects a str, decode using latin1 to preserve raw bytes
        return rtf_to_text(raw.decode("latin1", errors="ignore"))
    except Exception as exc:
        logger.warning("read_rtf_file failed for %s: %s", file_path, exc)
        return ""


def read_pdf_text(file_path: str) -> str:
    """Extract text from all pages of a PDF using PyMuPDF."""
    try:
        doc = fitz.open(file_path)
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)
    except Exception as exc:
        logger.warning("read_pdf_text failed for %s: %s", file_path, exc)
        return ""


# ----------------------------- Small formatters -----------------------------

def modify_gender_string(value: Any) -> str:
    """Normalize gender tokens to 'Female' or 'Male' where obvious, otherwise title-case."""
    try:
        v = _safe_strip(value)
        if not v:
            return ""
        lower = v.lower()
        if lower in ("f", "female"):
            return "Female"
        if lower in ("m", "male"):
            return "Male"
        return v.capitalize()
    except Exception:
        return ""


def format_date(value: Any, output_format: str = "%d/%m/%Y") -> str:
    """Attempt to normalize a date-like string to dd/mm/YYYY.

    If parsing fails, returns 'NA'. Accepts separators '-', '.', whitespace and
    both abbreviated and full month names.
    """
    raw = _safe_strip(value)
    if not re.search(r"\d", raw):
        return "NA"

    # Normalize separators to '/'
    normalized = re.sub(r"[-\.\\s]+", "/", raw)

    # If contains letters, try %d/%b/%Y and %d/%B/%Y
    if re.search(r"[A-Za-z]", normalized):
        for fmt in ("%d/%b/%Y", "%d/%B/%Y"):
            try:
                dt = datetime.strptime(normalized, fmt)
                return dt.strftime(output_format)
            except ValueError:
                continue
        return "NA"

    # If already looks numeric-separated, attempt to return as-is (or we could try parsing)
    return normalized


# ----------------------------- Text extraction ------------------------------

def _match_keyword_in_line(line: str, keyword: str) -> bool:
    """Match whole word keyword in a line, case-insensitive."""
    return bool(re.search(rf"\b{re.escape(keyword)}\b", line, re.IGNORECASE))


def extract_data_from_text(plain_text: str, file_type: str) -> Dict[str, str]:
    """Extract fields from a plain-text blob produced from RTF/PDF.

    This preserves the original behaviour but simplifies control flow and removes
    debug prints. Returns a map of discovered keys -> values.
    """
    if not plain_text:
        return {}

    # Choose splitter by type (pdf lines are typically newline separated, RTF data here
    # used '|' as splitter historically). Keep behaviour for backward compatibility.
    lines = plain_text.split("\n") if file_type == "pdf" else plain_text.split("|")
    lines = [l.strip() for l in lines if _safe_strip(l)]

    out: Dict[str, str] = {}

    # helper to look ahead and return next non-empty token or ''
    def _next_value(idx: int) -> str:
        for j in range(idx + 1, len(lines)):
            candidate = _safe_strip(lines[j])
            if candidate:
                return candidate
        return ""

    for i, line in enumerate(lines):
        # keyword matches
        for kw in keywords:
            if _match_keyword_in_line(line, kw):
                # Special-case handling for Referral Agent details and similar
                if kw in ("Referral Agent details", "Referrer Agent details", "Referral Details") or "Referral Agent" in line:
                    out[kw] = " ".join(lines[i + 1:]).strip()
                else:
                    out.setdefault(kw, _next_value(i))
                break

        # Common ad-hoc field patterns preserved from original code
        if "Mobile" in line and not out.get("P_Mobile"):
            candidate = line if re.search(r"\d", line) else _next_value(i)
            if re.search(r"\d", candidate):
                parts = candidate.split()
                # try to isolate phone token (last token usually)
                phone = parts[-1] if parts else candidate
                phone = phone.replace("(", "").replace(")", "")
                phone = phone.replace(" ", "")
                if len(phone) > 5:
                    phone = f"{phone[:5]} {phone[5:]}"
                out["P_Mobile"] = phone
            else:
                out["P_Mobile"] = ""

        if ("Landline" in line or "Telephone:" in line) and not out.get("P_HomeTelephone"):
            candidate = line if re.search(r"\d", line) else _next_value(i)
            if re.search(r"\d", candidate):
                parts = candidate.split()
                phone = parts[-1] if parts else candidate
                phone = phone.replace("(", "").replace(")", "")
                phone = phone.replace(" ", "")
                if len(phone) > 5:
                    phone = f"{phone[:5]} {phone[5:]}"
                out["P_HomeTelephone"] = phone
            else:
                out["P_HomeTelephone"] = ""

        # Explicit single-line fields
        if "Information relevant to referral" in line:
            out["Related_Information"] = _next_value(i)
        if "Relevant medical conditions" in line:
            out["Relevant_Medical_Conditions"] = _next_value(i)
        if "To be completed by the referrer" in line:
            out["Reason_For_Referral"] = _next_value(i)
        if line == "Standing height":
            out["R_StatType_Height_Value"] = _next_value(i)
            out["R_StatType_Height_Date"] = lines[i - 1] if i > 0 else ""
        if line == "Body weight":
            out["R_StatType_Weight_Value"] = _next_value(i)
            out["R_StatType_Weight_Date"] = lines[i - 1] if i > 0 else ""
        if line == "Email":
            out["P_EmailAddress"] = _next_value(i)
        if line == "O/E- blood pressure reading":
            out["R_StatType_BloodPressure_Date"] = lines[i - 1] if i > 0 else ""
            out["R_StatType_BloodPressure_Value"] = " ".join(lines[i + 1 : i + 3]).strip()

    return out


# ----------------------------- Name parsing ---------------------------------

# The parse_referral_name was complex; kept the logic but reorganized for clarity

def parse_referral_name(name_val: str) -> Dict[str, str]:
    """Parse a referrer string and return RF_FirstName, RF_Surname, RF_Role.

    This function aims to preserve original heuristics for titles, noise markers
    and role detection while being easier to read.
    """
    result = {"RF_FirstName": "", "RF_Surname": "", "RF_Role": ""}
    raw = _safe_strip(name_val)
    if not raw:
        return result

    first_line = raw.splitlines()[0].strip()

    role_keywords = {
        "physiotherapist",
        "consultant",
        "nurse",
        "gp",
        "surgeon",
        "therapist",
        "specialist",
        "doctor",
        "pharmacist",
        "dentist",
        "midwife",
        "practitioner",
        "prescriber",
        "cognitive",
        "behavioural",
        "psychologist",
    }

    noise_markers = {
        "http",
        "www",
        "tel",
        "mob",
        "fax",
        "email",
        "nhs",
        "hospital",
        "centre",
        "clinic",
        "street",
        "road",
        "avenue",
        "building",
        "floor",
    }

    post_nominals = {"fcp", "mbbs", "md", "phd", "msc", "bsc", "frcs", "facs", "do", "mrcgp"}

    title_roles = {"dr": "Doctor", "prof": "Doctor", "mr": "Other Health Professional", "mrs": "Other Health Professional", "ms": "Other Health Professional", "miss": "Other Health Professional", "nurse": "Other Health Professional"}

    # Remove parenthetical spans but keep their text separately if useful
    tokens = first_line.split()
    paren_spans: List[str] = []
    cleaned_tokens: List[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if "(" in tok:
            # gather until closing paren
            j = i
            while j < len(tokens) and ")" not in tokens[j]:
                j += 1
            span = tokens[i : j + 1]
            paren_spans.append(" ".join(span).strip("() "))
            i = j + 1
            continue
        cleaned_tokens.append(tok)
        i += 1

    lower_cleaned = [re.sub(r"\W", "", t).lower() for t in cleaned_tokens]

    # decide cut index: stop when we encounter role keyword or noise marker
    cut_idx = len(cleaned_tokens)
    for idx, tok in enumerate(lower_cleaned):
        if tok in role_keywords or any(tok.startswith(nm) for nm in noise_markers):
            cut_idx = idx
            break

    name_tokens = cleaned_tokens[:cut_idx] or cleaned_tokens[:2]
    role_tokens = cleaned_tokens[cut_idx:] if cut_idx < len(cleaned_tokens) and lower_cleaned[cut_idx] in role_keywords else []

    # if role token not found, check paren spans for role words
    if not role_tokens and paren_spans:
        joined_paren = " ".join(paren_spans).lower()
        if any(k in joined_paren for k in role_keywords) or "physio" in joined_paren:
            role_tokens = [joined_paren]

    # join hyphenated parts and split
    name_part = " ".join(name_tokens)
    if "-" in name_part:
        name_part = name_part.split("-")[0]

    # remove inline parenthesis in name_part
    name_part = re.sub(r"\([^)]*\)", "", name_part).strip().strip(",.")

    raw_tokens = [nt.strip(",.") for nt in name_part.split() if nt]

    # handle dotted initials like A.B.Smith -> split to tokens
    ref_name: List[str] = []
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

        # attempt to detect role inside name tokens
        if not role and any(t.lower() in role_keywords for t in ref_name):
            idx = next((i for i, t in enumerate(ref_name) if t.lower() in role_keywords), None)
            if idx is not None:
                role = " ".join(ref_name[idx:])
                ref_name = ref_name[:idx]

        # remove post nominals
        valid_tokens = [t for t in ref_name if t.lower() not in post_nominals]
        if len(valid_tokens) > 1:
            surname = valid_tokens[-1]
            first_name = " ".join(valid_tokens[:-1])
        elif len(valid_tokens) == 1:
            first_name = valid_tokens[0]

    if role_tokens:
        role = " ".join(role_tokens)

    if role:
        normalized_role = role.strip(" ,.-")
        if normalized_role.lower().startswith("doctor") or normalized_role.lower().startswith("dr"):
            normalized_role = "Doctor"
        else:
            normalized_role = "Other Health Professional"
        role = normalized_role

    # Swap heuristic preserved
    if first_name.isupper() and len(first_name) > 1 and surname and not surname.isupper():
        first_name, surname = surname, first_name

    result["RF_FirstName"] = first_name.title().replace(",", "") if first_name else ""
    result["RF_Surname"] = surname.title().replace(",", "") if surname else ""
    result["RF_Role"] = role or ""

    return result


# ----------------------------- Transform extracted data --------------------

def transform_extracted_data(extracted_data: Dict[str, str]) -> Dict[str, str]:
    """Map extracted keys to Excel/CSV column keys and perform light cleaning.

    Attempt to preserve original mapping intent while simplifying flow.
    """
    try:
        out: Dict[str, str] = {}

        p_information_parts: List[str] = []

        for key, value in extracted_data.items():
            if not _safe_strip(value):
                continue

            if key == "Name":
                # Basic tokenization and assignment into P_Title, P_FirstName, P_MiddleNames, P_Surname
                val = re.sub(r"[()]", "", value)
                parts = [p.replace('.', '') for p in val.split() if p]

                if len(parts) == 4:
                    out["P_Title"] = parts[0]
                    out["P_FirstName"] = parts[1]
                    out["P_MiddleNames"] = parts[2]
                    out["P_Surname"] = parts[3]
                elif len(parts) == 3:
                    if any(p in titles for p in parts):
                        t_idx = next((i for i, w in enumerate(parts) if w in titles), 0)
                        if t_idx == 2:
                            out["P_Title"] = parts[2]
                            out["P_FirstName"] = parts[1]
                            out["P_Surname"] = parts[0]
                        else:
                            out["P_Title"] = parts[0]
                            out["P_FirstName"] = parts[1]
                            out["P_Surname"] = parts[2]
                    else:
                        out["P_FirstName"] = parts[0]
                        out["P_MiddleNames"] = parts[1]
                        out["P_Surname"] = parts[2]
                elif len(parts) == 2:
                    out["P_FirstName"] = parts[0]
                    out["P_Surname"] = parts[1]

                # fix cases where tokens included commas in an uppercase token
                if out.get("P_FirstName", "") and "," in out.get("P_FirstName", "") and out["P_FirstName"].isupper():
                    out["P_FirstName"], out["P_Surname"] = out.get("P_Surname", ""), out["P_FirstName"].replace(",", "").title()

            elif key == "DOB":
                out["P_DateOfBirth"] = format_date(value)
            elif key == "Ethnicity":
                out["P_Ethnicity"] = value
            elif key == "Gender":
                out["P_Gender"] = modify_gender_string(value)
            elif key == "Address":
                address_lines = value.splitlines() if value.splitlines() else [v.strip() for v in value.split(",")]
                if address_lines and address_lines[0].strip().lower() == "home address":
                    address_lines = address_lines[1:]
                address_lines = [a.strip() for a in address_lines if a.strip()]
                for idx, a in enumerate(address_lines, start=1):
                    out[f"P_HomeAddress{idx}"] = a
                if address_lines and re.search(r"\d", address_lines[-1]):
                    out["P_HomePostcode"] = address_lines[-1].upper()
            elif key == "Postcode":
                out["P_HomePostcode"] = value.upper()
            elif key == "P_HomeTelephone":
                out["P_HomeTelephone"] = value
            elif key == "P_EmailAddress":
                out["P_EmailAddress"] = clean_text(value)
            elif key == "P_Mobile":
                out["P_Mobile"] = value
            elif key in ("R_StatType_Height_Value", "R_StatType_Weight_Value"):
                out[key] = value
            elif key in ("R_StatType_Height_Date", "R_StatType_Weight_Date"):
                out[key] = format_date(value)
            elif key in ("R_StatType_BloodPressure_Date", "R_StatType_BloodPressure_Value"):
                out[key] = value

            elif key in ("Referral Agent details", "Referrer Agent details"):
                # Parse a token-string which may contain Name, Organisation, Contact, Date details
                tokens = value.split()

                def _norm_token(t: str) -> str:
                    return re.sub(r"[\s:;,.-]+$", "", t.strip().lower())

                def _get_field(tokens_list: List[str], keyword: str, stop_words: List[str]) -> str:
                    norm_kw = _norm_token(keyword)
                    idx = next((i for i, t in enumerate(tokens_list) if _norm_token(t) == norm_kw), None)
                    if idx is None:
                        return ""
                    collected: List[str] = []
                    for tkn in tokens_list[idx + 1 :]:
                        if _norm_token(tkn) in [ _norm_token(s) for s in stop_words]:
                            break
                        collected.append(tkn)
                    return " ".join(collected).strip()

                name_val = _get_field(tokens, "Name", ["Organisation", "Contact", "Date"])
                org_val = _get_field(tokens, "Organisation", ["Name", "Contact", "Date"])
                contact_val = _get_field(tokens, "Contact", ["Name", "Organisation", "Date"])

                # date of referral naive extraction
                ref_date = ""
                try:
                    date_idx = next(i for i, t in enumerate(tokens) if t.lower() == "date")
                    if tokens[date_idx:date_idx+3] == ["Date","of","referral"]:
                        ref_date = tokens[date_idx + 3] if date_idx + 3 < len(tokens) else ""
                except StopIteration:
                    ref_date = ""

                if name_val:
                    parsed = parse_referral_name(name_val)
                    out.update(parsed)
                if org_val:
                    out["RO_Name"] = org_val
                if contact_val:
                    out["RF_Contact"] = contact_val

                out["R_DateOfReferral"] = format_date(ref_date) if ref_date else "NA"

            # Collecting information fields
            if key in ("Reason_For_Referral", "Relevant_Medical_Conditions", "Related_Information"):
                out[key] = value
                p_information_parts.append(value)

        # Combine collected information into P_Information
        out["P_Information"] = ", ".join(p_information_parts).replace("Select from drop down ", "")

        # post-cleanups similar to original
        if out.get("P_HomeAddress3") and re.search(r"\d", out.get("P_HomeAddress3", "")):
            out["P_HomeAddress3"] = ""

        # If birth year equals current year mark invalid
        if "P_DateOfBirth" in out and re.search(r"\b\d{4}\b", out["P_DateOfBirth"]):
            birth_year = int(re.search(r"\b\d{4}\b", out["P_DateOfBirth"]).group())
            if birth_year == datetime.now().year:
                out["P_DateOfBirth"] += " Invalid date"

        # Capitalize name fields
        if "P_Surname" in out:
            out["P_Surname"] = out["P_Surname"].capitalize().replace(',', '').replace('"', '')
        for fn in ("P_FirstName", "P_MiddleNames"):
            if fn in out and out[fn]:
                out[fn] = out[fn].capitalize().replace(',', '').replace('"', '')

        out["R_ReasonForReferral"] = out.get("P_Information", "")

        if not out.get("RF_Role"):
            out["RF_Role"] = "Other Health Professional"
        if not out.get("RO_Name"):
            out["RO_Name"] = "NA"
        if not out.get("RF_FirstName"):
            out["RF_FirstName"] = "NA"

        return out
    except Exception as exc:
        logger.exception("transform_extracted_data failed: %s", exc)
        return {}


# ----------------------------- CSV output helpers ---------------------------

def create_data_row(json_for_csv: Dict[str, str]) -> Dict[str, str]:
    """Create a full row dict for all columns defined in column_names.

    Default fallbacks are preserved from original code.
    """
    row: Dict[str, str] = {}
    for col in column_names:
        val = json_for_csv.get(col, "")
        if col == "P_HomeTelephone" and val in ("Landline:", ""):
            row[col] = "01234 567890"
        elif col == "P_Mobile" and val in ("Mobile:", ""):
            row[col] = "07939 064047"
        elif col == "RF_Surname" and val == "":
            row[col] = "RFSNN"
        elif col == "RF_SchemeID":
            ro = json_for_csv.get("RO_Name", "")
            row[col] = "5527" if ro.startswith("Cardiac") else ("5411" if ro else "")
        else:
            row[col] = val
    return row


def save_to_csv(data_rows: List[Dict[str, str]], folder_path: str, email: str) -> Dict[str, Any]:
    """Save rows to CSV inside folder_path and return result dict with file path or error."""
    try:
        df = pd.DataFrame(data_rows).astype(str)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_email = email.replace("@", "_").replace(".", "_")
        csv_filename = f"output_{sanitized_email}_{timestamp}.csv"
        csv_file_path = os.path.join(folder_path, csv_filename)

        # remove last 3 columns if they exist (preserved from original behaviour)
        if df.shape[1] > 3:
            df = df.iloc[:, :-3]

        df.to_csv(csv_file_path, index=False)
        logger.info("Saved CSV to %s", csv_file_path)
        return {"success": True, "message": f"CSV file saved to {csv_file_path}", "fileName": csv_file_path}
    except Exception as exc:
        logger.exception("save_to_csv failed: %s", exc)
        return {"success": False, "message": str(exc), "fileName": ""}


# ----------------------------- Public entrypoint ----------------------------

def process_files_in_folder(folder_path: str, email: str = "check") -> Dict[str, Any]:
    """Process RTF and PDF files in folder_path and export CSV.

    Returns a dict with success status, message and fileName path if successful.

    NOTE: Function name kept unchanged to preserve compatibility.
    """
    try:
        if not os.path.isdir(folder_path):
            return {"success": False, "message": "Invalid folder path", "fileName": ""}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_email = email.replace("@", "_").replace(".", "_")
        output_folder = os.path.join(os.path.dirname(folder_path), f"{sanitized_email}_{timestamp}")
        os.makedirs(output_folder, exist_ok=True)

        data_rows: List[Dict[str, str]] = []
        failed_files: List[str] = []

        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isdir(file_path):
                continue

            file_type = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''

            if file_type == 'pdf':
                text = read_pdf_text(file_path)
            else:
                text = read_rtf_file(file_path)

            if not text:
                failed_files.append(filename)
                continue

            extracted = extract_data_from_text(text, file_type)
            if not extracted:
                failed_files.append(filename)
                continue

            transformed = transform_extracted_data(extracted)
            if not transformed:
                failed_files.append(filename)
                continue

            row = create_data_row(transformed)
            data_rows.append(row)

        if not data_rows:
            return {"success": False, "message": "No valid files processed", "fileName": ""}

        result = save_to_csv(data_rows, output_folder, email)
        if result.get("success") and failed_files:
            result["message"] += f"\nFailed to process: {', '.join(failed_files)}"
        return result

    except Exception as exc:
        logger.exception("Unexpected error in process_files_in_folder: %s", exc)
        return {"success": False, "message": str(exc), "fileName": ""}
