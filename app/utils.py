import resend
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

# Helper functions
def send_reset_email(user_email, reset_url):
    resend.Emails.send({
        "from": "Giftster <noreply@mail.giftster.app>",
        "to": user_email,
        "subject": "Reset Your Giftster Password",
        "html": f'''<p>Click <a href="{reset_url}">here</a> to reset your password.</p>'''
    })

def get_serializer():
    from itsdangerous import URLSafeTimedSerializer
    from flask import current_app
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])