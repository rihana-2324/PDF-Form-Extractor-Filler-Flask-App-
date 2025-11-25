from PyPDF2 import PdfReader

# pdf = PdfReader("Form 14A - APPLICATION FORM.pdf")


pdf = PdfReader("Form 14A - APPLICATION FORM.pdf")


fields = pdf.get_fields()

for field_name, field_info in fields.items():
    value = field_info.get("/V")         # The filled value
    field_type = field_info.get("/FT")  # Field type (e.g., /Tx for text, /Btn for button, /Ch for choice)
    
    # Optional: Convert PDF field type codes to readable names
    field_type_readable = {
        "/Btn": "Button (Checkbox/Radio)",
        "/Tx": "Text",
        "/Ch": "Choice (Dropdown/List)",
        "/Sig": "Signature"
    }.get(field_type, str(field_type))
    
    print(f"Name: {field_name}, Type: {field_type_readable}, Value: {value}")