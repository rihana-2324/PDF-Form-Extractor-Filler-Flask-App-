from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName
import json
import os
import textwrap

def fill_pdf_form(pdf_template="Form 14A - APPLICATION FORM.pdf", 
                 json_path="extracted_data.json", 
                 output_path="static/Filled_Form_14A.pdf"):
    """Fills the interactive form with proper handling of long text fields."""
    
    if not os.path.exists(json_path):
        print(f"⚠️ No extracted data found at {json_path}.")
        return

    pdf = PdfReader(pdf_template)
    with open(json_path, 'r') as f:
        form_data = json.load(f)

    def set_text(annot, value, max_chars=30):
        if value:
            # Split long text into multiple lines if needed
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

    # Field mapping for multi-line fields
    multi_line_fields = {
        "undefined": "Name",  # Main name field
        "Address": "Address",  # Address field
        # Add other fields that might need wrapping
    }

    for page in pdf.pages:
        if not page.Annots:
            continue
            
        for annot in page.Annots:
            if annot.T:
                field_name = annot.T.to_unicode().strip()
                value = form_data.get(field_name)

                if value is not None:
                    # Handle text fields that might need wrapping
                    if field_name in multi_line_fields:
                        set_text(annot, value, max_chars=30)
                    elif isinstance(value, str) and value.lower() in ["on", "off", "true", "false", "1", "0"]:
                        set_checkbox(annot, value)
                    elif isinstance(value, str) and value.lower() in ["yes", "no"]:
                        set_checkbox2(annot, value)
                    else:
                        set_text(annot, value)

    # Ensure form appearance is updated
    if "/AcroForm" not in pdf.Root:
        pdf.Root.AcroForm = PdfDict(NeedAppearances=PdfName("true"))
    else:
        pdf.Root.AcroForm.update(PdfDict(NeedAppearances=PdfName("true")))

    # Save the filled PDF
    PdfWriter(output_path, trailer=pdf).write()
    print(f"✅ PDF successfully filled → {output_path}")

if __name__ == "__main__":
    fill_pdf_form()