from pdfrw import PdfReader

pdf_path = "Form 14A - APPLICATION FORM.pdf"  # Update with your actual PDF path
pdf_reader = PdfReader(pdf_path)

print("\n📋 List of Fillable Fields in the PDF:\n")

for page in pdf_reader.pages:
    if not page.Annots:
        continue
    for annot in page.Annots:
        if annot.T:
            print(f"➡️ {annot.T[1:-1]}")  # Removes brackets around field names
