from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
from google.cloud import storage
import atexit
import threading
import time

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')

# Database configuration
DB_FILE = 'gift_registry.db'
BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'giftster-db-backup')
SYNC_INTERVAL = 3600  # Sync every hour (3600 seconds)

# Download database from Cloud Storage if running on Cloud Run
if os.environ.get('K_SERVICE'):  # K_SERVICE is set on Cloud Run
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(DB_FILE)
        
        if blob.exists():
            print(f"Downloading database from gs://{BUCKET_NAME}/{DB_FILE}")
            blob.download_to_filename(DB_FILE)
            print("Database downloaded successfully")
        else:
            print(f"No existing database found in bucket, starting fresh")
    except Exception as e:
        print(f"Error downloading database: {e}")
        print("Starting with fresh database")

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_FILE}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Function to upload database to Cloud Storage
def upload_db_to_gcs():
    if os.environ.get('K_SERVICE'):  # Only upload on Cloud Run
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(DB_FILE)
            
            print(f"Uploading database to gs://{BUCKET_NAME}/{DB_FILE}")
            blob.upload_from_filename(DB_FILE)
            print("Database uploaded successfully")
        except Exception as e:
            print(f"Error uploading database: {e}")

# Background thread for periodic syncing
def periodic_sync():
    while True:
        time.sleep(SYNC_INTERVAL)
        print("Periodic sync triggered")
        upload_db_to_gcs()

# Start background sync thread if on Cloud Run
if os.environ.get('K_SERVICE'):
    sync_thread = threading.Thread(target=periodic_sync, daemon=True)
    sync_thread.start()
    print(f"Started periodic sync thread (every {SYNC_INTERVAL} seconds)")

# Register cleanup function to run on shutdown
atexit.register(upload_db_to_gcs)

# Import routes to register them
from app import routes