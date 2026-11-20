from flask import Flask
from flask_login import LoginManager
import os
import resend

# Initialize Flask app
app = Flask(__name__)

# The secret key signs login cookies and password reset links, so the live app must have its own
# (from Secret Manager, see cloudrun.yaml). The public fallback is only for local dev and tests,
# which run against the Firestore emulator; anywhere else, refuse to start without a real key.
if os.environ.get('SECRET_KEY'):
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
elif os.environ.get('FIRESTORE_EMULATOR_HOST'):
    app.config['SECRET_KEY'] = 'local-dev-only-secret-key'
else:
    raise RuntimeError('SECRET_KEY is not set. In production it comes from Secret Manager (see cloudrun.yaml).')

# Initialize Resend API Key
resend.api_key = os.environ.get('RESEND_API_KEY')

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Import routes to register them
from app import routes