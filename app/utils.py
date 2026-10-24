import resend
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

# Helper functions
def send_reset_email(user_email, reset_url):
    # Local dev has no Resend key, so print the link instead of emailing it
    if not resend.api_key:
        print(f'Password reset link for {user_email}: {reset_url}', flush=True)
        return
    resend.Emails.send({
        "from": "Giftster <noreply@mail.giftster.app>",
        "to": user_email,
        "subject": "Reset Your Giftster Password",
        "html": f'''<p>Click <a href="{reset_url}">here</a> to reset your password.</p>'''
    })

def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])