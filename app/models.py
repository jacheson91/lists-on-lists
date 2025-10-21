from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import secrets

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# New Group model
class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    join_code = db.Column(db.String(8), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def generate_join_code(self):
        """Generate a unique 6-character join code"""
        while True:
            code = secrets.token_urlsafe(6)[:6].upper()
            if not Group.query.filter_by(join_code=code).first():
                return code

# Association table for many-to-many relationship between users and groups
group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=db.func.current_timestamp())
)

class GiftList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)  # NEW: Link to group
    item_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    link = db.Column(db.String(500), nullable=True)
    is_claimed = db.Column(db.Boolean, default=False, nullable=False)
    claimer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def __repr__(self):
        return f'<GiftList Item: {self.item_name} Claimed: {self.is_claimed}>'