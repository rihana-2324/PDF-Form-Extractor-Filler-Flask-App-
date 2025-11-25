import fitz  # PyMuPDF
import re
import json

# Month mapping
MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text("text")
    return text

def extract_residences(text):
    residence_pattern = re.compile(
        r"(?P<country>[A-Z\s]+)\s+"
        r"(?P<address>[A-Z0-9\s,\-]+?)\s+"
        r"(?P<from_year>\d{4})\s+"
        r"(?P<to_year>\d{4})",
        re.IGNORECASE
    )
    matches = residence_pattern.findall(text)
    residences = []
    for match in matches:
        country, address, from_year, to_year = match
        country_clean = country.replace("Place\nAddress\nPeriod of Stay\nFrom\nTo\n", "").strip()
        residences.append({
            "CountryPlace": country_clean,
            "Address": address.strip(),
            "From": from_year,
            "To": to_year
        })
    return residences

def extract_field(text, pattern, flags=0):
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ""

def extract_checkbox(text, label):
    return "On" if re.search(rf"{label}.*(YES|ON|TRUE|CHECKED)", text, re.IGNORECASE) else "Off"

def extract_date(text, label):
    pattern = rf"{label}\s*\n(\d{{1,2}})\s+([A-Za-z]{{3}})\s+(\d{{4}})"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        day, month_text, year = match.groups()
        month = MONTHS.get(month_text, "")
    else:
        day, month, year = "", "", ""
    return day, month, year

def extract_dob(text):
    pattern = r"Date Of Birth\s*\n(\d{1,2})/(\d{1,2})/(\d{4})"
    match = re.search(pattern, text)
    if match:
        return match.groups()
    return "", "", ""

def extract_travel_document_type(text):
    travel_type = extract_field(text, r"Type\s*\n([^\n]+)").upper()
    travel_types = {
        "INTERNATIONAL PASSPORT": "International Passport",
        "DIPLOMATIC PASSPORT": "Diplomatic Passport",
        "SERVICE PASSPORT": "Service Passport",
        "OFFICIAL PASSPORT": "Official Passport",
        "DOCUMENT OF IDENTITY": "Document of Identity",
        "CERTIFICATE OF IDENTITY": "Certificate of Identity"
    }
    travel_document_data = {
        "International Passport": "Off",
        "Diplomatic Passport": "Off",
        "Service Passport": "Off",
        "Official Passport": "Off",
        "Document of Identity": "Off",
        "Certificate of Identity": "Off",
        "Others please specify": "Off",
        "undefined_8": ""
    }
    if travel_type in travel_types:
        travel_document_data[travel_types[travel_type]] = "On"
    else:
        travel_document_data["Others please specify"] = "On"
        travel_document_data["undefined_8"] = travel_type
    return travel_document_data

def extract_stay_location_type(text):
    text_upper = text.upper()
    stay_location_data = {
        "Next of Kins Place": "Off",
        "Relatives Place": "Off",
        "Friends Place": "Off",
        "Hotel": "Off",
        "Others Please specify": "",
        "undefined_15": "Off",
    }
    stay_mappings = [
        (["FRIEND'S PLACE", "FRIENDS PLACE", "FRIEND PLACE"], "Friends Place"),
        (["HOTEL"], "Hotel"),
        (["RELATIVE'S PLACE", "RELATIVES PLACE", "RELATIVE PLACE"], "Relatives Place"),
        (["NEXT OF KIN'S PLACE", "NEXT OF KIN PLACE", "KIN'S PLACE"], "Next of Kins Place")
    ]
    matched = False
    for patterns, field_name in stay_mappings:
        for pattern in patterns:
            if pattern in text_upper:
                stay_location_data[field_name] = "On"
                for others_field in ["Others Please Specify", "Others", "Other", "undefined", "undefined_15"]:
                    if others_field in stay_location_data:
                        stay_location_data[others_field] = "Off"
                matched = True
                break
        if matched:
            break
    if not matched:
        stay_location_data["Others Please Specify"] = "On"
        stay_location_data["Others Please specify"] = "Others"
    return stay_location_data

def clean_extracted_value(values):
    """Clean extracted values to avoid field label contamination"""
    if not values:
        return ""
    
    values = values.strip()
    
    # List of field labels that might be incorrectly extracted
    field_labels = [
        "Unit Number", "Floor Number", "Contact Number", "Postal Code", 
        "Street Name", "Block/House Number", "Hotel/Building Name"
    ]
    
    # If the value matches a field label, return empty string
    for label in field_labels:
        if values.lower() == label.lower():
            return ""
    return values

# -------------------- New helpers for proximity matching --------------------
def find_field_occurrences_with_pos(text, pattern):
    """Return list of (value, start_pos, end_pos) for all group(1) occurrences."""
    occurrences = []
    for m in re.finditer(pattern, text, re.IGNORECASE):
        val = m.group(1).strip()
        occurrences.append((val, m.start(1), m.end(1)))
    return occurrences

def pick_nearest_index(occurrences, text, label_patterns, max_dist=1000):
    """
    occurrences: list of (value, start, end)
    label_patterns: list of regex patterns to search for label location.
    Returns index into occurrences or None if none close enough.
    """
    label_pos = None
    for lp in label_patterns:
        m = re.search(lp, text, re.IGNORECASE)
        if m:
            label_pos = m.start()
            break
    if label_pos is None:
        return None
    candidates = []
    for i, (_, start, end) in enumerate(occurrences):
        # distance measured by start; you can tweak metric
        dist = abs(start - label_pos)
        if dist <= max_dist:
            candidates.append((dist, i))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]

def pick_nearest_value_from_occurrences(occ_list, text, label_patterns, max_dist=1200):
    """Pick nearest value from a list of (val, start, end) based on label position"""
    label_pos = None
    for lp in label_patterns:
        m = re.search(lp, text, re.IGNORECASE)
        if m:
            label_pos = m.start()
            break
    if label_pos is None:
        return ""
    candidates = []
    for (val, start, end) in occ_list:
        dist = abs(start - label_pos)
        if dist <= max_dist:
            candidates.append((dist, val))
    if not candidates:
        return ""
    candidates.sort()
    return candidates[0][1]
# ---------------------------------------------------------------------------

def extract_and_save_data(pdf_path):
    text = extract_text_from_pdf(pdf_path)

    # -------------------- Basic applicant fields --------------------
    name_value = extract_field(text, r"Name\s*\n([^\n]+)")
    if len(name_value) > 25:
        name_field, name_field_2 = name_value[:25], name_value[25:]
    else:
        name_field, name_field_2 = name_value, ""

    dob_d, dob_m, dob_y = extract_dob(text)
    issue_d, issue_m, issue_y = extract_date(text, "Issue Date")
    expiry_d, expiry_m, expiry_y = extract_date(text, "Expiry Date")
    arrival_d, arrival_m, arrival_y = extract_date(text, "Expected Date of Arrival")

    sex = extract_field(text, r"Sex\s*\n([^\n]+)")
    # Applicant sex checkboxes
    male_checkbox = "On" if sex.upper() == "MALE" else "Off"
    female_checkbox = "On" if sex.upper() == "FEMALE" else "Off"

    travel_document_checkboxes = extract_travel_document_type(text)
    place_of_issue = extract_field(text, r"(?<!Country/)Place of Issue\s*\n([^\n]+)")

    qualification = extract_field(
        text,
        r"Highest\s+Academic\s*/?\s*Professional\s+Qualifications?\s+Attained\s*\n([^\n]+)",
        re.IGNORECASE
    ).strip().upper()

    typeofvisa = extract_field(text, r"Type Of Visa\s*\n([^\n]+)").strip()
    purpose_of_visit = extract_field(text, r"Purpose of visit\s*\n([^\n]+)").strip()
    choose_a_purpose = extract_field(text, r"Choose a purpose\s*\n([^\n]+)").strip().upper()
    visa_types = ["Single Journey", "Double Journey", "Triple Journey", "Multiple Journey"]
    purpose_types = ["Social", "Business"]
    visa_checkboxes = {v: "On" if typeofvisa.lower() == v.lower() else "Off" for v in visa_types}
    purpose_checkboxes = {p: "On" if purpose_of_visit.lower() == p.lower() else "Off" for p in purpose_types}

    how_long_stay = extract_field(
        text, r"How long does the applicant intend to stay in\s*Singapore\?\s*\n([^\n]+)",
        re.IGNORECASE | re.DOTALL
    ).strip().upper()
    stay_checkboxes = {
        "Less than 30 days": "On" if "LESS THAN 30 DAYS" in how_long_stay else "Off",
        "More than 30 days": "On" if "MORE THAN 30 DAYS" in how_long_stay else "Off"
    }

    address_checkboxes = extract_stay_location_type(text)

    # -------------------- FIX: Extract Hotel Contact Number separately --------------------
    # First extract applicant contact number
    applicant_contact = clean_extracted_value(extract_field(text, r"Applicant's Contact Number\s*\n([^\n]+)"))
    
    # Now extract hotel contact number - look for patterns near hotel address fields
    hotel_contact_patterns = [
        r"Hotel Contact Number\s*\n([^\n]+)",
        r"Contact Number\s*\n(\+?65\s?\d{8})",  # Singapore number pattern
        r"Contact\s*\n(\+?65\s?\d{8})",
        r"Phone\s*\n(\+?65\s?\d{8})",
        r"Tel\s*\n(\+?65\s?\d{8})"
    ]
    
    hotel_contact = ""
    for pattern in hotel_contact_patterns:
        hotel_contact = extract_field(text, pattern)
        if hotel_contact:
            break
    
    # If no specific hotel contact found, use a default Singapore hotel number
    if not hotel_contact:
        hotel_contact = ""  # Default hotel contact number
    
    # Address details with proper cleaning
    address_details = {
        "BlockHouse No": clean_extracted_value(extract_field(text, r"Block/House Number\s*\n([^\n]+)")),
        "Postal Code": clean_extracted_value(extract_field(text, r"Postal Code\s*\n([^\n]+)")),
        "Street Name": clean_extracted_value(extract_field(text, r"Street Name\s*\n([^\n]+)")),
        "Contact No": hotel_contact,  # FIXED: Use hotel contact number, not applicant's
        "Building Name": clean_extracted_value(extract_field(text, r"Hotel/Building Name\s*\n([^\n]+)")),
        "Unit No": clean_extracted_value(extract_field(text, r"Unit Number\s*\n([^\n]+)")),
        "Floor No": clean_extracted_value(extract_field(text, r"Floor Number\s*\n([^\n]+)")),
    }

    resided_other_countries = extract_field(
        text,
        r"Has the applicant resided in other countries/places[\s\S]*?last\s*5\s*years\?\s*(?:\n)?\s*(YES|NO)",
        re.IGNORECASE
    ).lower()

    residence_entries = extract_residences(text)
    data_residences = {}
    if residence_entries:
        for i, entry in enumerate(residence_entries, start=1):
            data_residences[f"CountryPlaceRow{i}"] = entry["CountryPlace"]
            data_residences[f"AddressRow{i}"] = entry["Address"]
            data_residences[f"FromRow{i}"] = entry["From"]
            data_residences[f"ToRow{i}"] = entry["To"]

    if resided_other_countries == "yes":
        resided_data = {
            "Did you reside in other countriesplaces other than your countryplace of origin for one year or more during the last 5 years": "Yes",
            "CountryPlaceRow1": data_residences.get("CountryPlaceRow1", ""),
            "AddressRow1": data_residences.get("AddressRow1", ""),
            "FromRow1": data_residences.get("FromRow1", ""),
            "ToRow1": data_residences.get("ToRow1", "")
        }
    else:
        resided_data = {"Did you reside in other countriesplaces other than your countryplace of origin for one year or more during the last 5 years": "No"}

    refused_entry = extract_field(text, r"Has the applicant ever been refused entry.*?\?\s*\n*([^\n]+)").strip().lower()
    convicted = extract_field(text, r"Has the applicant ever been convicted.*?\n([^\n]+)").strip().lower()
    prohibited_entry = extract_field(text, r"Has the applicant ever been prohibited.*?\n([^\n]+)").strip().lower()
    different_passport = extract_field(text, r"Has the applicant ever entered Singapore using a different passport.*?\n([^\n]+)").strip().lower()
    different_passport_details = extract_field(text, r"If any of the answer is 'YES', please furnish details below:\s*\n(.+)").strip()
    antecedents_checkboxes = {
        "Check Box3": "Yes" if refused_entry == "yes" else "No",
        "Check Box4": "Yes" if convicted == "yes" else "No",
        "Check Box5": "Yes" if prohibited_entry == "yes" else "No",
        "Check Box6": "Yes" if different_passport == "yes" else "No",
        "Check Box7": "Yes",
        "Check Box8": "Yes",
        "Check Box9": "Yes" if prohibited_entry == "no" else "No",
        "Check Box10": "Yes" if different_passport == "no" else "No",
    }

    # -------------------- Local contact --------------------
    local_contact_name_value = extract_field(text, r"Name\s*\n([^\n]+)")
    if len(local_contact_name_value) > 25:
        local_contact_name_field, local_contact_name_field_2 = local_contact_name_value[:25], local_contact_name_value[25:]
    else:
        local_contact_name_field, local_contact_name_field_2 = local_contact_name_value, ""
    relationship_to_contact = extract_field(text, r"Relationship of Applicant to Local Contact\s*\n([^\n]+)")
    local_contact_number = extract_field(text, r"Contact Number\s*\n([^\n]+)")
    local_contact_email = extract_field(text, r"Email Address\s*\n([^\n]+)")

    local_contact_fields = {
        "Travel Document_2": None,
        "Name of Local Contact": None,
        "CompanyHotel": None,
        "Local ContactCompany": None,
        "Contact No_2": None,
        "Email Address": None,
    }

    # -------------------- Gather all travel document occurrences with positions --------------------
    travel_doc_occurrences = find_field_occurrences_with_pos(text, r"Travel Document Number\s*\n([^\n]+)")

    used_doc_indices = set()

    # -------------------- Travel companion (proximity-based) --------------------
    travel_companion_fields = {}
    # Try to find companion labels (prefer relationship label, fallback to name label)
    companion_label_patterns = [
        r"Relationship of Traveling Companion to Applicant\s*\n([^\n]+)",
        r"Name of Travelling Companion\s*\n([^\n]+)",
        r"Travelling Companion"
    ]
    companion_doc_index = pick_nearest_index(travel_doc_occurrences, text, companion_label_patterns, max_dist=1200)
    # If companion label exists at all (detect by label existence)
    companion_label_present = any(re.search(p, text, re.IGNORECASE) for p in companion_label_patterns)

    # Extract companion-specific fields using proximity when possible
    relationship_tc = extract_field(text, r"Relationship of Traveling Companion to Applicant\s*\n([^\n]+)")
    name_tc = extract_field(text, r"Name of Travelling Companion\s*\n([^\n]+)")

    # For companion DOB/nationality/sex, we'll pick nearest occurrences
    # DOB occurrences with pos
    dob_occurrences = []
    for m in re.finditer(r"Date of Birth\s*\n(\d{1,2})/(\d{1,2})/(\d{4})", text):
        dob_occurrences.append(((m.group(1), m.group(2), m.group(3)), m.start(1)))

    nationality_occurrences = find_field_occurrences_with_pos(text, r"Nationality/Citizenship\s*\n([^\n]+)")
    sex_occurrences = find_field_occurrences_with_pos(text, r"Sex\s*\n([^\n]+)")

    # Companion DOB (pick nearest DOB occurrence)
    dob_tc_d, dob_tc_m, dob_tc_y = "", "", ""
    if companion_label_present and dob_occurrences:
        # find nearest DOB by label
        label_pos = None
        for lp in companion_label_patterns:
            m = re.search(lp, text, re.IGNORECASE)
            if m:
                label_pos = m.start()
                break
        if label_pos is not None:
            candidates = []
            for i, (dobtuple, startpos) in enumerate(dob_occurrences):
                dist = abs(startpos - label_pos)
                candidates.append((dist, i, dobtuple))
            candidates.sort()
            if candidates and candidates[0][0] <= 1200:
                _, chosen_i, chosen_dob = candidates[0]
                dob_tc_d, dob_tc_m, dob_tc_y = chosen_dob
            else:
                dob_tc_d, dob_tc_m, dob_tc_y = "", "", ""
        else:
            dob_tc_d, dob_tc_m, dob_tc_y = "", "", ""
    else:
        dob_tc_d, dob_tc_m, dob_tc_y = "", "", ""

    # Companion nationality
    nationality_tc = pick_nearest_value_from_occurrences(nationality_occurrences, text, companion_label_patterns, max_dist=1200)

    # Companion sex
    sex_tc = pick_nearest_value_from_occurrences(sex_occurrences, text, companion_label_patterns, max_dist=1200)

    # If we picked a companion travel-doc index, use it
    travel_doc_tc = ""
    if companion_doc_index is not None:
        travel_doc_tc = travel_doc_occurrences[companion_doc_index][0]
        used_doc_indices.add(companion_doc_index)

    # -------------------- Local contact travel doc (proximity-based) --------------------
    local_contact_doc_index = pick_nearest_index(travel_doc_occurrences, text,
                                                [r"Relationship of Applicant to Local Contact\s*\n([^\n]+)",
                                                 r"Name of Local Contact\s*\n([^\n]+)"], max_dist=1200)
    travel_doc_local_contact = ""
    if local_contact_doc_index is not None and local_contact_doc_index not in used_doc_indices:
        travel_doc_local_contact = travel_doc_occurrences[local_contact_doc_index][0]
        used_doc_indices.add(local_contact_doc_index)

    # -------------------- Applicant travel doc (first unused or first overall) --------------------
    travel_doc_applicant = ""
    if travel_doc_occurrences:
        # pick the first occurrence that is not used by companion/local
        for idx, (val, start, end) in enumerate(travel_doc_occurrences):
            if idx not in used_doc_indices:
                travel_doc_applicant = val
                used_doc_indices.add(idx)
                break
        # if everything was used and none left, fallback to first occurrence
        if not travel_doc_applicant and travel_doc_occurrences:
            travel_doc_applicant = travel_doc_occurrences[0][0]

    # -------------------- Prepare local_contact_fields if condition holds --------------------
    if purpose_of_visit.upper() == "SOCIAL" and "VISITING FAMILY/RELATIVES" in choose_a_purpose:
        local_contact_fields = {
            "Travel Document_2": travel_doc_local_contact if travel_doc_local_contact else None,
            "Name of Local Contact": local_contact_name_field,
            "CompanyHotel": local_contact_name_field_2,
            "Local ContactCompany": relationship_to_contact,
            "Contact No_2": local_contact_number,
            "Email Address": local_contact_email,
        }
    else:
        local_contact_fields = {
            "Travel Document_2": None,
            "Name of Local Contact": None,
            "CompanyHotel": None,
            "Local ContactCompany": None,
            "Contact No_2": None,
            "Email Address": None,
        }

    # -------------------- Compose travel_companion_fields only if companion present --------------------
    # Define companion "present" as: companion label exists AND (relationship/name/sex/any field) present
    companion_present = False
    if companion_label_present or relationship_tc or name_tc or nationality_tc or sex_tc or travel_doc_tc:
        companion_present = True

    # Build companion checkboxes for sex (defaults to No)
    male_tc_checkbox = "Yes" if sex_tc and sex_tc.upper() == "MALE" else "No"
    female_tc_checkbox = "Yes" if sex_tc and sex_tc.upper() == "FEMALE" else "No"

    if companion_present:
        travel_companion_fields = {
            "undefined_16": relationship_tc,
            "undefined_17": name_tc,
            "D": dob_tc_d,
            "M_2": dob_tc_m,
            "Y_5": dob_tc_y,
            "D_2": nationality_tc,
            "Travel Document_2": travel_doc_tc if travel_doc_tc else None
        }
    else:
        travel_companion_fields = {}

    # -------------------- FIX 1: CORRECT Marital Status Handling --------------------
    marital_status = extract_field(text, r"Marital Status\s*\n([^\n]+)").upper()
    
    # Initialize all marital status checkboxes to Off
    marital_checkboxes = {
        "Single": "Off",
        "Married": "Off",
        "Separated": "Off", 
        "Divorced": "Off",
        "Widowed": "Off",
        "Cohabited": "Off",
        "Customary": "Off"
    }
    
    # Set the correct marital status to On based on extracted value
    if marital_status == "SINGLE":
        marital_checkboxes["Single"] = "On"
    elif marital_status == "MARRIED":
        marital_checkboxes["Married"] = "On"
    elif marital_status == "SEPARATED":
        marital_checkboxes["Separated"] = "On"
    elif marital_status == "DIVORCED":
        marital_checkboxes["Divorced"] = "On"
    elif marital_status == "WIDOWED":
        marital_checkboxes["Widowed"] = "On"
    elif marital_status == "COHABITED":
        marital_checkboxes["Cohabited"] = "On"
    elif marital_status == "CUSTOMARY":
        marital_checkboxes["Customary"] = "On"
    
    # FIXED: Spouse nationality logic based on marital status
    # Extract spouse nationality from the input form
    spouse_nationality = extract_field(text, r"Nationality/Citizenship of Spouse\s*\n([^\n]+)")
    
    # Initialize spouse nationality fields - ALL EMPTY for single/divorced/widowed
    spouse_nationality_fields = {
        "Singapore Citizen": "Off",
        "Singapore Permanent Resident": "Off", 
        "Others Please Specify": "Off",
        "NRIC No": "",
        "NRIC No_2": "",
        "undefined_7": ""  # This is the text field for "Others Please Specify"
    }
    
    # Fill spouse nationality ONLY for statuses that require it
    if marital_status in ["MARRIED", "SEPARATED", "COHABITED", "CUSTOMARY"]:
        if spouse_nationality:
            if spouse_nationality.upper() == "SINGAPORE CITIZEN":
                spouse_nationality_fields["Singapore Citizen"] = "On"
            elif spouse_nationality.upper() == "SINGAPORE PERMANENT RESIDENT":
                spouse_nationality_fields["Singapore Permanent Resident"] = "On"
            else:
                spouse_nationality_fields["Others Please Specify"] = "On"
                spouse_nationality_fields["undefined_7"] = spouse_nationality  # Fill the text field ONLY when Others is On
    # For SINGLE, DIVORCED, WIDOWED - leave all spouse fields empty/Off (including undefined_9)

    # -------------------- FIX 2: Annual Income for Students --------------------
    annual_income = extract_field(text, r"Annual Income \(Singapore Dollars - in numbers only\)\s*\n([\d,]+)")
    if not annual_income or annual_income == "0":
        annual_income = "0"  # Explicitly set to 0 for students

    # -------------------- FIX 3: Stay Duration Selection --------------------
    stay_duration = extract_field(
        text, 
        r"How long does the applicant intend to stay in Singapore\?\s*\n([^\n]+)",
        re.IGNORECASE
    ).strip().upper()
    
    stay_duration_checkboxes = {
        "Less than 30 days": "On" if "LESS THAN 30 DAYS" in stay_duration else "Off",
        "More than 30 days": "On" if "MORE THAN 30 DAYS" in stay_duration else "Off"
    }

    # -------------------- FIX 4: RACE FIELD - NEVER CLEAR IT --------------------
    # Extract race value - DO NOT CLEAR IT regardless of marital status
    race_value = extract_field(text, r"Race\s*\n([^\n]+)")
    
    # IMPORTANT FIX: Always keep the race value, never clear it
    # Race should be filled regardless of marital status

    # -------------------- Final data dict (all original fields restored) --------------------
    data = {
        # Companion sex checkbox mapping
        "Check Box2": male_tc_checkbox,
        "Male": female_tc_checkbox,

        # Applicant name parts
        "undefined": name_field,
        "undefined_2": name_field_2,

        # Applicant DOB
        "Date of Birth": dob_d,
        "M": dob_m,
        "Y": dob_y,

        # Applicant sex checkboxes
        "undefined_5": male_checkbox,
        "undefined_6": female_checkbox,

        # FIXED: Correct marital status handling
        **marital_checkboxes,

        # FIXED: Spouse nationality - filled only when required
        # CRITICAL FIX: undefined_9 is now properly managed - only filled when "Others Please Specify" is On
        **spouse_nationality_fields,

        # FIXED: Race fields - ALWAYS filled (never cleared)
    
        "CountryPlace of Birth": extract_field(text, r"Country/Place of Birth\s*\n([^\n]+)"),
        "StateProvince of Birth": extract_field(text, r"State/Province of Birth\s*\n([^\n]+)"),
        "Chinese Caucasian etc": race_value,  # Same race value (ALWAYS filled)

        # Applicant nationality/citizenship
        "NationalityCitizenship": extract_field(text, r"Nationality/Citizenship\s*\n([^\n]+)"),

        # Passport / travel doc date pieces
        "Travel Document": issue_d,
        "M M": issue_m,
        "Y_2": issue_y,
        "Expiry Date": expiry_d,
        "M M_2": expiry_m,
        "Y_3": expiry_y,

        # Expected arrival
        "Expected Date of Arrival in Singapore": arrival_d,
        "M M_3": arrival_m,
        "Y_4": arrival_y,

        # Applicant travel document (now assigned by proximity/usage logic)
        "Travel Document No": travel_doc_applicant if travel_doc_applicant else None,

        "CountryPlace of Issue": place_of_issue,

        # travel doc checkboxes (International/Diplomatic etc.)
        **travel_document_checkboxes,

        # Origin fields
        "CountryPlace of Origin": "INDIA",
        "DivisionStateProvince": extract_field(text, r"Province/State of Origin/Residence\s*\n([^\n]+)"),
        "Prefecture of Origin": "INDIA",

        # Address (multi-line capture)
        "Address": extract_field(text, r"Address\s*\n(.*?)(?=\b(?:Province/State|Applicant's Email Address|Contact Information|Occupation)\b)", re.DOTALL),

        "CountyDistrict of Origin": "INDIA",

        # Contact / occupation / religion / income
        "undefined_11": extract_field(text, r"Applicant's Email Address\s*\n([^\n]+)"),
        "Contact Number": applicant_contact,  # Use extracted applicant contact number
        "undefined_12": extract_field(text, r"Occupation\s*\n([^\n]+)"),

        "Diploma": "On" if "DIPLOMA" in qualification else "Off",
        "University": "On" if "UNIVERSITY" in qualification else "Off",
        "PostGraduate": "On" if "POSTGRADUATE" in qualification else "Off",

        # FIXED: Annual income for students
        "Singapore dollars SGD": annual_income,

        "undefined_13": extract_field(text, r"Religion\s*\n([^\n]+)"),

        # Residences
        **resided_data,

        # Visa & purpose
        **visa_checkboxes,
        **purpose_checkboxes,
        "undefined_14": choose_a_purpose,
        "undefined_15": "On" if resided_other_countries == "yes" else "",

        # Local contact fields
        **local_contact_fields,

        # FIXED: Duration / stay location / address details
        **stay_duration_checkboxes,
        **address_checkboxes,
        **address_details,

        # Antecedents and details
        **antecedents_checkboxes,
        "If any of the answer is YES please furnish details below 1": different_passport_details,

        # All travelling companion fields (if present)
        **travel_companion_fields,
    }

    # Save JSON
    with open("extracted_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return address_details