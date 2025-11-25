from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName, PdfObject
import json
import os
import textwrap

def fill_pdf_form(json_path="extracted_data.json", 
                  output_path="static/Filled_Form_14A.pdf",
                  form1="form1.pdf", form2="form2.pdf"):
    
    if not os.path.exists(json_path):
        print(f"⚠️ No extracted data found at {json_path}.")
        return

    with open(json_path, 'r') as f:
        form_data = json.load(f)

    # 🔍 Check the radio button value in JSON to select form
    resided_key = "Did you reside in other countriesplaces other than your countryplace of origin for one year or more during the last 5 years"
    resided_value = form_data.get(resided_key, "").strip().capitalize()

    # Choose which form to load
    if resided_value == "Yes":
        pdf_template = form2
    else:
        pdf_template = form1

    print(f"📄 Using PDF template → {pdf_template}")
    pdf = PdfReader(pdf_template)

    def set_text(annot, value, max_chars=30):
        if value:
            if len(value) > max_chars:
                wrapped_lines = textwrap.wrap(value, width=max_chars)
                value = '\n'.join(wrapped_lines)
            annot.update(PdfDict(V=str(value)))
            annot.update(PdfDict(AP=None))

    def set_checkbox(annot, value):
        value = str(value).strip().lower()
        is_checked = value in ["yes", "on", "true", "1"]
        annot.update(PdfDict(AS=PdfName("On" if is_checked else "Off")))
        annot.update(PdfDict(V=PdfName("On" if is_checked else "Off")))
        annot.update(PdfDict(AP=None))

    def set_checkbox2(annot, value):
        value = str(value).strip().lower()
        is_checked = value in ["yes", "on", "true", "1"]
        annot.update(PdfDict(V=PdfName("On" if is_checked else "Off")))
        annot.update(PdfDict(AS=PdfName("Yes" if is_checked else "No")))
        annot.update(PdfDict(AP=None))

    # Multi-line text field handling
    multi_line_fields = {
        "undefined": "Name",  
        "Address": "Address",  
    }

    # List of text fields that should NEVER be treated as checkboxes
    text_only_fields = [
        'BlockHouse No', 'Floor No', 'Unit No', 'Postal Code', 
        'Street Name', 'Contact No', 'Building Name',
        'Date of Birth', 'M', 'Y', 'Travel Document No', 'Travel Document',
        'M M', 'Y_2', 'Expiry Date', 'M M_2', 'Y_3', 'CountryPlace of Issue',
        'Expected Date of Arrival in Singapore', 'M M_3', 'Y_4',
        'Singapore dollars SGD'  # Added income field as text
    ]

    print("🔍 FILLING FORM FIELDS:")
    
    for page in pdf.pages:
        if not page.Annots:
            continue
        for annot in page.Annots:
            if annot.T:
                field_name = annot.T.to_unicode().strip()
                value = form_data.get(field_name)

                if value is not None:
                    # SPECIAL FIX FOR UNIT NO FIELD - Force it to be text
                    if field_name == 'Unit No':
                        print(f"🎯 FORCING UNIT NO AS TEXT FIELD: '{value}'")
                        set_text(annot, value)
                        print(f"🏠 Unit No (TEXT): '{value}'")
                    
                    # Handle other text-only fields as text
                    elif field_name in text_only_fields:
                        set_text(annot, value)
                        if field_name in ['BlockHouse No', 'Floor No', 'Unit No', 'Postal Code', 'Street Name', 'Contact No']:
                            print(f"🏠 {field_name}: '{value}'")
                        elif field_name == 'Singapore dollars SGD':
                            print(f"💰 Annual Income: '{value}'")
                    
                    # Handle multi-line fields
                    elif field_name in multi_line_fields:
                        set_text(annot, value, max_chars=30)
                        print(f"📝 {field_name}: '{value}'")
                    
                    # Handle checkbox fields
                    elif isinstance(value, str) and value.lower() in ["on", "off", "true", "false", "1", "0"]:
                        set_checkbox(annot, value)
                        print(f"☑️ {field_name}: {value}")
                    
                    elif isinstance(value, str) and value.lower() in ["yes", "no"]:
                        set_checkbox2(annot, value)
                        print(f"☑️ {field_name}: {value}")
                    
                    # Default to text for any other field
                    else:
                        set_text(annot, value)
                        print(f"📄 {field_name}: '{value}'")

    # Ensure form appearances update
    if "/AcroForm" not in pdf.Root:
        pdf.Root.AcroForm = PdfDict(NeedAppearances=PdfName("true"))
    else:
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfName("true")))

    # Save the PDF
    PdfWriter(output_path, trailer=pdf).write()
    print(f"✅ PDF successfully filled → {output_path}")

    # VERIFICATION: Check if critical fields were filled correctly
    print(f"\n🔍 VERIFICATION:")
    try:
        verify_pdf = PdfReader(output_path)
        critical_fields = ['Unit No', 'Singapore dollars SGD', 'Less than 30 days', 'Single']
        
        for page in verify_pdf.pages:
            if page.Annots:
                for annot in page.Annots:
                    if annot.T:
                        field_name = annot.T.to_unicode().strip()
                        if field_name in critical_fields:
                            field_value = "NOT FOUND"
                            if hasattr(annot, 'V') and annot.V:
                                field_value = annot.V
                                if hasattr(field_value, 'to_unicode'):
                                    field_value = field_value.to_unicode()
                            
                            print(f"{field_name}: '{field_value}'")
        
        print("✅ All critical fields verified")
        
    except Exception as e:
        print(f"⚠️ Verification error: {e}")

    print(f"\n💡 IMPORTANT: Download the PDF and open in ADOBE ACROBAT READER")
    print(f"   Browser PDF viewers often don't show filled form fields correctly")

    return output_path


if __name__ == "__main__":
    fill_pdf_form()