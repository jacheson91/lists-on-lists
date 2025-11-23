from flask import Flask
from flask_login import LoginManager
import os
import resend

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')

# Initialize Resend API Key
resend.api_key = os.environ.get('RESEND_API_KEY')

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Import routes to register them
from app import routes