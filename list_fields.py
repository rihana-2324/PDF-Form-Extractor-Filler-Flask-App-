from pdfrw import PdfReader

pdf_path = "Form 14A - APPLICATION FORM.pdf"
pdf = PdfReader(pdf_path)

print("🔍 Listing all form fields:")
for page in pdf.pages:
    if not page.Annots:
        continue
    for annot in page.Annots:
        if annot.T:
            print(annot.T)
