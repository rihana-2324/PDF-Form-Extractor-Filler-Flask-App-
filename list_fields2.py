from PyPDF2 import PdfReader

reader = PdfReader("Form 14A - APPLICATION FORM.pdf")
fields = reader.get_fields()

if fields:
    for key in fields.keys():
        print(f"Field: {key}")
else:
    print("⚠️ No AcroForm fields found in this PDF")


