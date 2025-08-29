import webview
import threading
from app import app  # Import your Flask app

# Start Flask server in a separate thread
def start_flask():
    app.run(debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start Flask in a background thread
    flask_thread = threading.Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Start desktop window using PyWebView
    webview.create_window("PDF Form Filler", "http://127.0.0.1:5000", width=1000, height=800)
