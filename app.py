from flask import Flask, render_template, request, url_for, send_from_directory, send_file
import os
from extract_fields import extract_and_save_data
from fill_pdf import fill_pdf_form
import uuid
import shutil
import io
import zipfile
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['STATIC_FOLDER'] = 'static'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['STATIC_FOLDER'], exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        files = request.files.getlist("pdf_file")
        filled_files = []

        for file in files:
            if file and file.filename.endswith(".pdf"):
                try:
                    # Generate unique ID for this file
                    unique_id = str(uuid.uuid4())
                    input_filename = f"{unique_id}_{file.filename}"
                    input_filepath = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
                    file.save(input_filepath)

                    # Step 1: Extract fields
                    extract_and_save_data(input_filepath)
                    
                    # Get the extracted name from the JSON data
                    with open("extracted_data.json", 'r') as f:
                        extracted_data = json.load(f)
                    name = extracted_data.get("undefined", "").replace(" ", "_")[:30]  # Clean name for filename
                    
                    # Step 2: Fill the form with descriptive output filename
                    output_filename = f"Filled_Form_{name}_{unique_id}.pdf" if name else f"Filled_Form_14A_{unique_id}.pdf"
                    output_filepath = os.path.join(app.config['STATIC_FOLDER'], output_filename)
                    
                    # Fill the PDF form
                    fill_pdf_form()
                    
                    # Rename the filled PDF
                    original_filled_path = os.path.join(app.config['STATIC_FOLDER'], "Filled_Form_14A.pdf")
                    if os.path.exists(original_filled_path):
                        shutil.move(original_filled_path, output_filepath)
                    
                    # Store the URL for the filled PDF
                    filled_files.append({
                        'url': url_for('static', filename=output_filename),
                        'filename': output_filename
                    })

                except Exception as e:
                    print(f"Error processing file {file.filename}: {str(e)}")
                    continue

        return render_template("index.html", 
                            filled=True, 
                            filled_files=filled_files,
                            json_path=url_for('serve_json'))

    return render_template("index.html", filled=False)

@app.route("/data.json")
def serve_json():
    return send_from_directory(".", "extracted_data.json")

@app.route('/download-all', methods=['POST'])
def download_all():
    try:
        files = request.json.get('files', [])
        
        # Create a zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_info in files:
                filename = file_info['filename']
                file_path = os.path.join(app.config['STATIC_FOLDER'], filename)
                
                if os.path.exists(file_path):
                    zip_file.write(file_path, filename)
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='filled_forms.zip'
        )
    except Exception as e:
        print(f"Error creating zip file: {str(e)}")
        return "Error creating zip file", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)