import fitz  # PyMuPDF
import re
import json

# Month mapping for conversion
MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

def extract_text_from_pdf(pdf_path):
    """Extracts all text from a PDF file"""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text("text")
    return text

def extract_field(text, pattern, flags=0):  # Add flags as an optional argument
    match = re.search(pattern, text, flags)  
    return match.group(1).strip() if match else ""

def extract_checkbox(text, label):
    """Extracts checkbox value: 'On' if checked, otherwise 'Off'"""
    return "On" if re.search(rf"{label}.*(YES|ON|TRUE|CHECKED)", text, re.IGNORECASE) else "Off"

def extract_date(text, label):
    """Extracts dates in 'DD MMM YYYY' format and converts to numeric format"""
    pattern = rf"{label}\s*\n(\d{{1,2}})\s+([A-Za-z]{{3}})\s+(\d{{4}})"
    match = re.search(pattern, text, re.IGNORECASE)

    month_text = ""  # Ensure variable is always defined
    if match:
        day, month_text, year = match.groups()
        month = MONTHS.get(month_text, "")  # Convert month name to number
    else:
        day, month, year = "", "", ""

    print(f"📌 Extracted Date: {label} → Full: {day} {month_text} {year} → Split: Day={day}, Month={month}, Year={year}")  # Debugging
    return day, month, year

def extract_dob(text):
    """Extracts Date of Birth in 'DD/MM/YYYY' format and splits it"""
    pattern = r"Date Of Birth\s*\n(\d{1,2})/(\d{1,2})/(\d{4})"
    match = re.search(pattern, text)

    if match:
        day, month, year = match.groups()
        print(f"📌 Extracted Date of Birth: {day}/{month}/{year}")  # Debugging
    else:
        day, month, year = "", "", ""

    return day, month, year

def extract_travel_document_type(text):
    """Extracts Travel Document Type and maps it to checkboxes"""
    travel_type = extract_field(text, r"Type\s*\n([^\n]+)").upper()  # Extract and convert to uppercase

    # Define valid travel document types and their checkbox mapping
    travel_types = {
        "INTERNATIONAL PASSPORT": "International Passport",
        "DIPLOMATIC PASSPORT": "Diplomatic Passport",
        "SERVICE PASSPORT": "Service Passport",
        "OFFICIAL PASSPORT": "Official Passport",
        "DOCUMENT OF IDENTITY": "Document of Identity",
        "CERTIFICATE OF IDENTITY": "Certificate of Identity"
    }

    # Initialize checkboxes as "Off" for all options
    travel_document_data = {
        "International Passport": "Off",
        "Diplomatic Passport": "Off",
        "Service Passport": "Off",
        "Official Passport": "Off",
        "Document of Identity": "Off",
        "Certificate of Identity": "Off",
        "Others please specify": "Off",
        "undefined_8": ""  # Store "Other" type value here
    }

    # Set only the matched checkbox to "On"
    if travel_type in travel_types:
        travel_document_data[travel_types[travel_type]] = "On"
    else:
        # If type is not in the predefined list, mark "Others please specify" as "On" and store the value
        travel_document_data["Others please specify"] = "On"
        travel_document_data["undefined_8"] = travel_type  # Store the actual "Other" type

    print(f"📌 Extracted Travel Document Type: {travel_type} → {travel_document_data}")  # Debugging
    return travel_document_data

def extract_and_save_data(pdf_path):
    text = extract_text_from_pdf(pdf_path)

    # ✅ Handle Name Splitting BEFORE dictionary
    name_value = extract_field(text, r"Name\s*\n([^\n]+)")

    if len(name_value) > 25:
        name_field = name_value[:25]     # first 25 chars → first row
        name_field_2 = name_value[25:]   # remaining chars → second row
    else:
        name_field = name_value
        name_field_2 = ""

    # ✅ Now continue with the rest of your extractions
    dob_d, dob_m, dob_y = extract_dob(text)  
    issue_d, issue_m, issue_y = extract_date(text, "Issue Date")  # Extract Other Dates (DD MMM YYYY)
    expiry_d, expiry_m, expiry_y = extract_date(text, "Expiry Date")
    arrival_d, arrival_m, arrival_y = extract_date(text, "Expected Date of Arrival")


     # ✅ Extract Sex and Convert to "On"/"Off"
    sex = extract_field(text, r"Sex\s*\n([^\n]+)")
    male_checkbox = "On" if sex.upper() == "MALE" else "Off"
    female_checkbox = "On" if sex.upper() == "FEMALE" else "Off"


     # ✅ Extract Travel Document Type and Checkbox Values
    travel_document_checkboxes = extract_travel_document_type(text)




    # ✅ Extract "Country/Place of Issue" (For Reference Only)
    country_of_issue = extract_field(text, r"Country/Place of Issue\s*\n([^\n]+)")

    # ✅ Extract "Place of Issue" Strictly (Ensuring it does not match "Country/Place of Issue")
    place_of_issue = extract_field(text, r"\bPlace of Issue\b\s*\n([^\n]+)")

    # Debugging Log
    print(f"📌 Extracted 'Country/Place of Issue' (Reference Only): {country_of_issue}")
    print(f"📌 Extracted 'Place of Issue' → Mapped to 'CountryPlace of Issue': {place_of_issue}")

    qualification = extract_field(
    text,
    r"Highest\s+Academic\s*/?\s*Professional\s+Qualifications?\s+Attained\s*\n([^\n]+)",
    re.IGNORECASE).strip().upper()
    print("📌 Extracted Qualification FIXED →", repr(qualification))

    
    # Extract values properly
    typeofvisa = extract_field(text, r"Type Of Visa\s*\n([^\n]+)").strip()
    purpose_of_visit = extract_field(text, r"Purpose of visit\s*\n([^\n]+)").strip()

    # Ensure extracted values are correct by printing (debugging)
    print(f"Extracted Type of Visa: {typeofvisa}")
    print(f"Extracted Purpose of Visit: {purpose_of_visit}")

    # Assign checkbox values dynamically
    visa_types = ["Single Journey", "Double Journey", "Triple Journey", "Multiple Journey"]
    purpose_types = ["Social", "Business"]

    visa_checkboxes = {visa: "On" if typeofvisa.lower() == visa.lower() else "Off" for visa in visa_types}
    purpose_checkboxes = {purpose: "On" if purpose_of_visit.lower() == purpose.lower() else "Off" for purpose in purpose_types}

    # Print extracted results (debugging)
    print(f"Visa Checkboxes: {visa_checkboxes}")
    print(f"Purpose Checkboxes: {purpose_checkboxes}")


    how_long_stay = extract_field(
    text,
    r"How long does the applicant intend to stay in\s*Singapore\?\s*\n([^\n]+)",
    re.IGNORECASE | re.DOTALL).strip().upper()
    stay_checkboxes = {
    "Less than 30 days": "On" if "LESS THAN 30 DAYS" in how_long_stay else "Off",
    "More than 30 days": "On" if "MORE THAN 30 DAYS" in how_long_stay else "Off"
    }




    print(f"Stay Checkboxes: {stay_checkboxes}")


  # Extract the value where the applicant will stay
    stay_in_singapore = extract_field(text, r"Where will the applicant be staying in Singapore\?\s*\n([^\n]+)").strip().lower()


    # Debugging
    print(f"Extracted Stay Location: {stay_in_singapore}")

    

    # Assign checkbox values based on the extracted text
    address_checkboxes = {
        "Next of Kins Place": "On" if stay_in_singapore == "next of kin’s place" else "Off",
        "Relatives Place": "On" if stay_in_singapore == "relatives place" else "Off",
        "Friends Place": "On" if stay_in_singapore == "friend’s place" else "Off",
        "Hotel": "On" if stay_in_singapore == "hotel" else "Off",
        "Others Please specify": "On" if stay_in_singapore not in ["next of kin’s place", "relatives place", "friend’s place", "hotel"] else "Off"
    }

    # Extract text fields
    block_house_no = extract_field(text, r"Block/House Number\s*\n([^\n]+)").strip()
    floor_no = extract_field(text, r"Floor Number\s*\n([^\n]*)").strip()
    unit_no = extract_field(text, r"Unit Number\s*\n([^\n]*)").strip()
    postal_code = extract_field(text, r"Postal Code\s*\n([^\n]+)").strip()
    street_name = extract_field(text, r"Street Name\s*\n([^\n]+)").strip()
    contact_no = extract_field(text, r"Contact Number\s*\n([^\n]+)").strip()
    building_name = extract_field(text, r"Hotel/Building Name\s*\n([^\n]+)").strip()

    # Assign extracted text values
    address_details = {
        "BlockHouse No": block_house_no,
        # "Floor No": floor_no,
        # "Unit No": unit_no,
        "Postal Code": postal_code,
        "Street Name": street_name,
        "Contact No": contact_no,
        "Building Name": building_name
    }

    # Debugging Output
    print(f"Address Checkboxes: {address_checkboxes}")
    print(f"Extracted Address Details: {address_details}")
        # ✅ Extract "Did you reside in other countries…" Yes/No
   # ✅ Extract "Did you reside in other countries…" Yes/No
    resided_other_countries = extract_field(
    text,
    r"Has the applicant resided in other countries/places.*?\?\s*(Yes|No)",
    re.IGNORECASE).strip().lower()
    # Map to checkbox style
    resided_other_countries_checkbox = {
    "undefined_15": "On" if resided_other_countries == "yes" else "Off"
    }
    print("📌 Extracted Resided Other Countries:", repr(resided_other_countries))









    # ✅ Extract Antecedents (Yes/No Questions)
    refused_entry = extract_field(text, r"Has the applicant ever been refused entry.*?\?\s*\n*([^\n]+)").strip().lower()

    convicted = extract_field(text, r"Has the applicant ever been convicted.*?\n([^\n]+)").strip().lower()
    prohibited_entry = extract_field(text, r"Has the applicant ever been prohibited.*?\n([^\n]+)").strip().lower()
    different_passport = extract_field(text, r"Has the applicant ever entered Singapore using a different passport.*?\n([^\n]+)").strip().lower()

    # ✅ Extract additional details if any of the above is "YES"
    different_passport_details = extract_field(text, r"If any of the answer is 'YES', please furnish details below:\s*\n(.+)").strip()
  
    # ✅ Assign checkbox values based on extracted text
    antecedents_checkboxes = {

        "Check Box3": "Yes" if refused_entry == "yes" else "No",
        "Check Box4": "Yes" if convicted == "yes" else "No",
        "Check Box5": "Yes" if prohibited_entry == "yes" else "No",
        "Check Box6": "Yes" if different_passport == "yes" else "No",


        # "Check Box7": "Yes" if refused_entry == "no" else "No",

        "Check Box7": "Yes",
        "Check Box8": "Yes" ,
        "Check Box9": "Yes" if prohibited_entry == "no" else "No",
        "Check Box10": "Yes" if different_passport == "no" else "No",


        
    }



    # 🛠 Debugging Output
    print(f"Extracted Antecedent Responses: Refused Entry={refused_entry}, Convicted={convicted}, Prohibited={prohibited_entry}, Different Passport={different_passport}")
    print(f"Antecedent Checkboxes: {antecedents_checkboxes}")
    print(f"Additional Details: {different_passport_details}")

        # ✅ Extract Local Contact Information
    local_contact_name_value = extract_field(text, r"Name of Company/Firm\s*\n([^\n]+)")

    # Split into multiple 25-character fields
    if len(local_contact_name_value) > 25:
        local_contact_name_field = local_contact_name_value[:25]   # first row
        local_contact_name_field_2 = local_contact_name_value[25:] # next row
    else:
        local_contact_name_field = local_contact_name_value
        local_contact_name_field_2 = ""
    
    relationship_to_contact = extract_field(text, r"Relationship of Applicant to Local Contact\s*\n([^\n]+)")
    local_contact_number = extract_field(text, r"Contact Number\s*\n([^\n]+)")
    local_contact_email = extract_field(text, r"Email Address\s*\n([^\n]+)")














    data = {
        # ✅ Personal Information
        
        "undefined": name_field,
        "undefined_2": name_field_2,
        "Date of Birth": dob_d,
        "M": dob_m,
        "Y": dob_y,

        "undefined_5": male_checkbox,  
        "undefined_6": female_checkbox,  

        "Single": "On" if extract_field(text, r"Marital Status\s*\n([^\n]+)") == "SINGLE" else "Off",
        "Married": "On" if extract_field(text, r"Marital Status\s*\n([^\n]+)") == "MARRIED" else "Off",
        "Separated": "On" if extract_field(text, r"Marital Status\s*\n([^\n]+)") == "SEPARATED" else "Off",
        "Divorced": "On" if extract_field(text, r"Marital Status\s*\n([^\n]+)") == "DIVORCED" else "Off",
        "Widowed": "On" if extract_field(text, r"Marital Status\s*\n([^\n]+)") == "WIDOWED" else "Off",
        "Cohabited": "Off",
        "Customary": "Off",
        "Singapore Citizen": "Off",
        "Singapore Permanent Resident": "Off",
        "Others Please Specify": "On",
        "NRIC No": "",
        "NRIC No_2": "",
        "undefined_7": extract_field(text, r"Race\s*\n([^\n]+)"),
        "CountryPlace of Birth": extract_field(text, r"Country/Place of Birth\s*\n([^\n]+)"),
        "StateProvince of Birth": extract_field(text, r"State/Province of Birth\s*\n([^\n]+)"),
        "Chinese Caucasian etc": extract_field(text, r"Race\s*\n([^\n]+)"),
        "NationalityCitizenship": extract_field(text, r"Nationality/Citizenship\s*\n([^\n]+)"),

        # ✅ Travel Document Information
        "Travel Document": issue_d,
        "M M": issue_m,
        "Y_2": issue_y,
        "Expiry Date": expiry_d,
        "M M_2": expiry_m,
        "Y_3": expiry_y,
        "Expected Date of Arrival in Singapore": arrival_d,
        "M M_3": arrival_m,
        "Y_4": arrival_y,



        "Travel Document No": extract_field(text, r"Travel Document Number\s*\n([^\n]+)"),
         # ✅ Store the extracted value in the correct JSON key
        "CountryPlace of Issue": place_of_issue,
        **travel_document_checkboxes,  # Merge checkbox values into data dictionary,

        "CountryPlace of Origin": "INDIA",
        "DivisionStateProvince": extract_field(text, r"Province/State of Origin/Residence\s*\n([^\n]+)"),
        "Prefecture of Origin": "INDIA",
        # ✅ Extract Multi-Line Address Correctly (Stops at next field label)
        "Address" : extract_field(text, r"Address\s*\n(.*?)(?=\b(?:Province/State|Applicant's Email Address|Contact Information|Occupation)\b)", re.DOTALL),
        "CountyDistrict of Origin": "INDIA",


        "undefined_11" : extract_field(text, r"Applicant's Email Address\s*\n([^\n]+)"),
        "Contact Number" : extract_field(text, r"Applicant's Contact Number\s*\n([^\n]+)"),
        "undefined_12" : extract_field(text, r"Occupation\s*\n([^\n]+)"),

        "Diploma": "On" if "DIPLOMA" in qualification else "Off",
        "University": "On" if "UNIVERSITY" in qualification else "Off",
        "PostGraduate": "On" if "POSTGRADUATE" in qualification else "Off",



        "Singapore dollars SGD": extract_field(text, r"Annual Income \(Singapore Dollars - in numbers only\)\s*\n([\d,]+)"),

        "undefined_13" : extract_field(text, r"Religion\s*\n([^\n]+)"),

        
        




         # ✅ Include Visa Checkboxes
        **visa_checkboxes,  

        # ✅ Include Purpose Checkboxes
        **purpose_checkboxes,

        "undefined_14" : extract_field(text, r"Choose a purpose\s*\n([^\n]+)"),
        "undefined_15": "On" if resided_other_countries == "yes" else "",

                # ✅ Local Contact Information
                # ✅ Local Contact Information
        "Name of Local Contact": local_contact_name_field,
        "CompanyHotel": local_contact_name_field_2,  # spillover row if >25 chars
        "Local ContactCompany": relationship_to_contact,
        "Contact No_2": local_contact_number,
        "Email Address": local_contact_email,


       

        **stay_checkboxes,  # ✅ Expands stay checkboxes into JSON


        **address_checkboxes,  # ✅ Expands address checkboxes into JSON
        **address_details,  # ✅ Expands address details into JSON
        **resided_other_countries_checkbox,  # ✅ Adds undefined_15 field



        **antecedents_checkboxes,  # ✅ Expands antecedents checkboxes into JSON

        "If any of the answer is YES please furnish details below 1": different_passport_details,  # ✅ Extracted details for antecedents




    }

    # Save extracted data to JSON
    with open("extracted_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print("✅ Extracted data saved to extracted_data.json")
    
    return data  # Return the complete data dictionary
 

