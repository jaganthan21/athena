from datetime import datetime
# Get the current timestamp in "mm_dd_yyyy_hh_mm" format
timestamp = datetime.now().strftime("%m_%d_%Y_%H_%M")
excel_file_name=f"processed_data_{timestamp}.xlsx"
titles = ["Ms", "Mrs","Mrs.","Ms.","Miss", "Mr","(Mrs)","(Mrs.)","(Ms)","(Miss)","MRS"]
# Column names for the Excel file
column_names = [
    "P_Title", "P_FirstName", "P_MiddleNames", "P_Surname", "P_DateOfBirth", "P_Gender",
    "P_NHSNumber", "P_HomeAddress1", "P_HomeAddress2", "P_HomeAddress3", "P_HomePostcode",
    "P_HomeTelephone", "P_Mobile", "P_EmailAddress", "P_Ethnic_Group", "P_Ethnicity",
    "P_Information", "RO_Name", "RO_Address1", "RO_Address2", "RO_Address3", "RO_GMPC",
    "RO_Postcode", "RO_Email", "RF_FirstName", "RF_Surname", "RF_Role", "RF_SchemeID",
    "RF_SchemeName", "R_DateOfReferral", "R_ReasonForReferral", "R_StatType_Height_Date",
    "R_StatType_Height_Value", "R_StatType_Weight_Date", "R_StatType_Weight_Value",
    "R_StatType_StatedBMI_Date", "R_StatType_StatedBMI_Value", "R_StatType_BloodPressure_Date",
    "R_StatType_BloodPressure_Value", "R_PatientConsent","Reason_For_Referral","Relevant_Medical_Conditions","Related_Information"
]

# Keywords for data extraction
keywords = ["Name", "Address", "Postcode", "Landline:", "Mobile:", "Email", "DOB", "Age", "Gender", "Ethnicity",
            "Interpreter", "required language", "Disability", "disability details", "Height", "Weight",
            "BMI", "Blood Pressure", "Information relevant to referral", "Relevant medical conditions",
            "Problems", "Active", "Referral Agent details", "Referrer Agent details","O/E- blood pressure reading"]
