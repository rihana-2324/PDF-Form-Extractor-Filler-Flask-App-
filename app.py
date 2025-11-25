from flask import Flask, render_template, request, url_for, send_from_directory, send_file, redirect, session
import os
from extract_fields import extract_and_save_data
from fill_pdf import fill_pdf_form
import uuid
import shutil
import io
import zipfile
import json
import datetime as dt
import threading
import time
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['STATIC_FOLDER'] = 'static'
app.config['COUNTER_FILE'] = 'download_counter.json'
app.config['CLEANUP_FILE'] = 'cleanup_tracker.json'
app.config['CREDENTIALS_FILE'] = 'credentials.json'
app.secret_key = "supersecretkey"

# Default credentials (will be loaded from file)
DEFAULT_USERNAME = "admin@gmail.com"
DEFAULT_PASSWORD = "ad@12#"

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['STATIC_FOLDER'], exist_ok=True)

# -------------------- CREDENTIALS MANAGEMENT --------------------
def load_credentials():
    """Load credentials from file or create default"""
    if os.path.exists(app.config['CREDENTIALS_FILE']):
        try:
            with open(app.config['CREDENTIALS_FILE'], 'r') as f:
                return json.load(f)
        except:
            pass
    
    # Create default credentials
    default_creds = {
        "username": DEFAULT_USERNAME,
        "password": DEFAULT_PASSWORD
    }
    save_credentials(default_creds)
    return default_creds

def save_credentials(credentials):
    """Save credentials to file"""
    with open(app.config['CREDENTIALS_FILE'], 'w') as f:
        json.dump(credentials, f, indent=2)

def get_current_credentials():
    """Get current username and password"""
    return load_credentials()

def update_credentials(current_username, current_password, new_username, new_password):
    """Update credentials after verification"""
    creds = get_current_credentials()
    
    # Verify current credentials
    if creds["username"] != current_username or creds["password"] != current_password:
        return False, "Current username or password is incorrect"
    
    # Update credentials
    updated_creds = {
        "username": new_username,
        "password": new_password
    }
    save_credentials(updated_creds)
    return True, "Credentials updated successfully"

# -------------------- CLEANUP SYSTEM (DELETE UPLOADS EVERY 2 DAYS) --------------------
def init_cleanup_tracker():
    """Initialize the cleanup tracker file"""
    if not os.path.exists(app.config['CLEANUP_FILE']):
        cleanup_data = {
            "last_cleanup_date": datetime.now().isoformat(),
            "cleanup_history": []
        }
        with open(app.config['CLEANUP_FILE'], 'w') as f:
            json.dump(cleanup_data, f, indent=2)

def should_run_cleanup():
    """Check if cleanup should run (every 2 days)"""
    if not os.path.exists(app.config['CLEANUP_FILE']):
        return True
    
    with open(app.config['CLEANUP_FILE'], 'r') as f:
        cleanup_data = json.load(f)
    
    last_cleanup = datetime.fromisoformat(cleanup_data["last_cleanup_date"])
    return datetime.now() - last_cleanup >= timedelta(days=2)

def perform_cleanup():
    """Delete all files in uploads folder and update cleanup tracker"""
    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        static_folder = app.config['STATIC_FOLDER']
        
        # Count files before cleanup
        upload_files_before = len([f for f in os.listdir(upload_folder) if os.path.isfile(os.path.join(upload_folder, f))])
        static_files_before = len([f for f in os.listdir(static_folder) if os.path.isfile(os.path.join(static_folder, f))])
        
        # Delete all files in uploads folder
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        
        # Delete all filled PDFs in static folder (keep other static files)
        for filename in os.listdir(static_folder):
            if filename.startswith("Filled_Form_") and filename.endswith(".pdf"):
                file_path = os.path.join(static_folder, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
        
        # Count files after cleanup
        upload_files_after = len([f for f in os.listdir(upload_folder) if os.path.isfile(os.path.join(upload_folder, f))])
        static_files_after = len([f for f in os.listdir(static_folder) if os.path.isfile(os.path.join(static_folder, f))])
        
        # Update cleanup tracker
        cleanup_data = {
            "last_cleanup_date": datetime.now().isoformat(),
            "cleanup_history": []
        }
        
        # Load existing history if file exists
        if os.path.exists(app.config['CLEANUP_FILE']):
            with open(app.config['CLEANUP_FILE'], 'r') as f:
                existing_data = json.load(f)
                cleanup_data["cleanup_history"] = existing_data.get("cleanup_history", [])
        
        # Add current cleanup to history
        cleanup_record = {
            "timestamp": datetime.now().isoformat(),
            "upload_files_deleted": upload_files_before - upload_files_after,
            "static_files_deleted": static_files_before - static_files_after,
            "upload_files_remaining": upload_files_after,
            "static_files_remaining": static_files_after
        }
        cleanup_data["cleanup_history"].append(cleanup_record)
        
        # Keep only last 30 cleanup records
        cleanup_data["cleanup_history"] = cleanup_data["cleanup_history"][-30:]
        
        with open(app.config['CLEANUP_FILE'], 'w') as f:
            json.dump(cleanup_data, f, indent=2)
        
        print(f"Cleanup completed: Deleted {upload_files_before - upload_files_after} upload files and {static_files_before - static_files_after} static files")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")

def cleanup_scheduler():
    """Background thread to run cleanup every 2 days"""
    while True:
        try:
            if should_run_cleanup():
                print("Running scheduled cleanup...")
                perform_cleanup()
            # Check every hour
            time.sleep(3600)  # 1 hour
        except Exception as e:
            print(f"Error in cleanup scheduler: {e}")
            time.sleep(3600)  # Wait 1 hour before retrying

# Start cleanup thread when app starts
cleanup_thread = threading.Thread(target=cleanup_scheduler, daemon=True)
cleanup_thread.start()

# Helper function to check if login is required (new day)
def is_login_required():
    """Check if login is required (new day since last login)"""
    if 'last_login_date' not in session:
        return True
    
    last_login = datetime.fromisoformat(session['last_login_date'])
    today = datetime.now().date()
    return last_login.date() < today

# Download counter functions (RESET DAILY)
def init_download_counter():
    """Initialize the download counter file if it doesn't exist or it's a new day"""
    today = datetime.today().date().isoformat()
    
    # Check if we need to reset counters for new day
    if os.path.exists(app.config['COUNTER_FILE']):
        with open(app.config['COUNTER_FILE'], 'r') as f:
            counter_data = json.load(f)
        
        # If last reset date is not today, reset the counters
        if counter_data.get('last_reset_date') != today:
            counter_data = {
                "total_downloads": 0,
                "daily_downloads": {today: 0},
                "file_downloads": {},
                "download_history": [],
                "last_reset_date": today
            }
    else:
        # Initialize fresh counters
        counter_data = {
            "total_downloads": 0,
            "daily_downloads": {today: 0},
            "file_downloads": {},
            "download_history": [],
            "last_reset_date": today
        }
    
    with open(app.config['COUNTER_FILE'], 'w') as f:
        json.dump(counter_data, f, indent=2)

def get_download_stats():
    """Get current download statistics"""
    init_download_counter()  # This will reset if new day
    try:
        with open(app.config['COUNTER_FILE'], 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading counter file: {e}")
        return {
            "total_downloads": 0,
            "daily_downloads": {},
            "file_downloads": {},
            "download_history": [],
            "last_reset_date": datetime.today().date().isoformat()
        }

def update_download_counter(filename, download_type="single"):
    """Update download counters for a file"""
    stats = get_download_stats()
    today = datetime.today().date().isoformat()
    now = datetime.now().isoformat()
    
    # Update total downloads (daily total only)
    stats["total_downloads"] += 1
    
    # Update daily downloads
    if today in stats["daily_downloads"]:
        stats["daily_downloads"][today] += 1
    else:
        stats["daily_downloads"][today] = 1
    
    # Update file-specific downloads (daily only)
    if filename:
        if filename in stats["file_downloads"]:
            stats["file_downloads"][filename] += 1
        else:
            stats["file_downloads"][filename] = 1
    
    # Add to download history
    stats["download_history"].append({
        "timestamp": now,
        "filename": filename,
        "type": download_type
    })
    
    # Keep only today's history entries to prevent file from growing too large
    stats["download_history"] = [entry for entry in stats["download_history"] 
                               if datetime.fromisoformat(entry["timestamp"]).date() == datetime.today().date()]
    
    # Save updated stats
    try:
        with open(app.config['COUNTER_FILE'], 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"Error writing counter file: {e}")
    
    return stats

def get_today_downloads():
    """Get downloads for today"""
    stats = get_download_stats()
    today = datetime.today().date().isoformat()
    return stats["daily_downloads"].get(today, 0)

def get_single_downloads():
    """Get count of single PDF downloads for today"""
    stats = get_download_stats()
    today = datetime.today().date().isoformat()
    # Count single downloads from today's history
    single_count = sum(1 for entry in stats["download_history"] 
                      if entry["type"] == "single" and 
                      datetime.fromisoformat(entry["timestamp"]).date() == datetime.today().date())
    return single_count

def get_zip_downloads():
    """Get count of ZIP downloads for today"""
    stats = get_download_stats()
    today = datetime.today().date().isoformat()
    # Count zip downloads from today's history
    zip_count = sum(1 for entry in stats["download_history"] 
                   if entry["type"] == "batch" and 
                   datetime.fromisoformat(entry["timestamp"]).date() == datetime.today().date())
    return zip_count

# -------------------- LOGIN SYSTEM (DAILY REQUIREMENT) --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in today, redirect to index
    if 'logged_in' in session and session['logged_in'] and not is_login_required():
        return redirect(url_for("index"))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Get current credentials
        current_creds = get_current_credentials()

        if username == current_creds["username"] and password == current_creds["password"]:
            session["logged_in"] = True
            session["last_login_date"] = datetime.now().isoformat()
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

@app.route("/change-credentials", methods=["GET", "POST"])
def change_credentials():
    """Route to change username and password - accessible without login"""
    if request.method == "POST":
        current_username = request.form.get("current_username")
        current_password = request.form.get("current_password")
        new_username = request.form.get("new_username")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        # Validate inputs
        if not all([current_username, current_password, new_username, new_password, confirm_password]):
            return render_template("change_credentials.html", error="All fields are required")
        
        if new_password != confirm_password:
            return render_template("change_credentials.html", error="New passwords do not match")
        
        # Update credentials
        success, message = update_credentials(current_username, current_password, new_username, new_password)
        
        if success:
            # Clear any existing session and redirect to login
            session.clear()
            return render_template("change_credentials.html", success=message + " Please login with your new credentials.")
        else:
            return render_template("change_credentials.html", error=message)
    
    return render_template("change_credentials.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
def index():
    # Check if login is required (new day)
    if is_login_required():
        session.clear()
        return redirect(url_for("login"))
    
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))

    # Get current statistics for display
    stats = get_download_stats()
    today_downloads = get_today_downloads()
    single_downloads = get_single_downloads()
    zip_downloads = get_zip_downloads()

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
                    
                    # Store the URL for the filled PDF - use static URL for preview
                    filled_files.append({
                        'url': url_for('static', filename=output_filename),  # For preview
                        'download_url': url_for('download_file', filename=output_filename),  # For download
                        'filename': output_filename
                    })

                except Exception as e:
                    print(f"Error processing file {file.filename}: {str(e)}")
                    continue

        # Get updated stats after processing
        updated_stats = get_download_stats()
        today_downloads = get_today_downloads()
        single_downloads = get_single_downloads()
        zip_downloads = get_zip_downloads()
        
        return render_template("index.html", 
                            filled=True, 
                            filled_files=filled_files,
                            total_downloads=updated_stats["total_downloads"],
                            today_downloads=today_downloads,
                            single_downloads=single_downloads,
                            zip_downloads=zip_downloads,
                            file_downloads=updated_stats["file_downloads"],
                            json_path=url_for('serve_json'))

    # For GET request, pass the stats
    return render_template("index.html", 
                         filled=False,
                         total_downloads=stats["total_downloads"],
                         today_downloads=today_downloads,
                         single_downloads=single_downloads,
                         zip_downloads=zip_downloads,
                         file_downloads=stats["file_downloads"])

@app.route("/data.json")
def serve_json():
    if is_login_required():
        return redirect(url_for("login"))
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))
    return send_from_directory(".", "extracted_data.json")

@app.route('/download/<filename>')
def download_file(filename):
    if is_login_required():
        return redirect(url_for("login"))
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))
    
    # Update download counter for individual file download
    update_download_counter(filename, "single")
    
    return send_from_directory(app.config['STATIC_FOLDER'], filename, as_attachment=True)

@app.route('/download-all', methods=['POST'])
def download_all():
    if is_login_required():
        return redirect(url_for("login"))
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))

    try:
        files = request.json.get('files', [])
        
        # Update download counter for each file in the zip
        for file_info in files:
            update_download_counter(file_info['filename'], "batch")
        
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

@app.route('/stats')
def stats():
    if is_login_required():
        return redirect(url_for("login"))
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))
    
    stats_data = get_download_stats()
    return render_template("stats.html", stats=stats_data)

@app.route('/cleanup-info')
def cleanup_info():
    """Page to show cleanup information"""
    if is_login_required():
        return redirect(url_for("login"))
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))
    
    cleanup_data = {}
    if os.path.exists(app.config['CLEANUP_FILE']):
        with open(app.config['CLEANUP_FILE'], 'r') as f:
            cleanup_data = json.load(f)
    
    # Count current files
    upload_files_count = len([f for f in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], f))])
    static_files_count = len([f for f in os.listdir(app.config['STATIC_FOLDER']) if os.path.isfile(os.path.join(app.config['STATIC_FOLDER'], f))])
    
    return render_template("cleanup_info.html", 
                         cleanup_data=cleanup_data,
                         upload_files_count=upload_files_count,
                         static_files_count=static_files_count)

@app.route('/manual-cleanup', methods=['POST'])
def manual_cleanup():
    """Manual trigger for cleanup"""
    if is_login_required():
        return redirect(url_for("login"))
    if "logged_in" not in session or not session["logged_in"]:
        return redirect(url_for("login"))
    
    perform_cleanup()
    return redirect(url_for('cleanup_info'))

if __name__ == "__main__":
    # Initialize counter and cleanup files on startup
    init_download_counter()
    init_cleanup_tracker()
    
    # Perform initial cleanup if needed
    if should_run_cleanup():
        print("Running initial cleanup...")
        perform_cleanup()
    
    app.run(host="0.0.0.0", port=5000, debug=True)