from google.cloud import firestore
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import secrets
from datetime import datetime

db = firestore.Client(database='giftster-db')

class User(UserMixin):
    def __init__(self, user_id, data=None):
        self.id = user_id
        if data:
            self.first_name = data.get('first_name', '')
            self.last_name = data.get('last_name', '')
            self.email = data.get('email', '')
            self.password_hash = data.get('password_hash', '')
    
    @staticmethod
    def get(user_id):
        """Get user by ID"""
        doc = db.collection('users').document(user_id).get()
        if doc.exists:
            return User(doc.id, doc.to_dict())
        return None
    
    @staticmethod
    def get_by_email(email):
        """Get user by email"""
        users = db.collection('users').where('email', '==', email).limit(1).stream()
        for user in users:
            return User(user.id, user.to_dict())
        return None
    
    @staticmethod
    def create(first_name, last_name, email, password):
        """Create a new user"""
        user_ref = db.collection('users').document()
        user_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password_hash': generate_password_hash(password)
        }
        user_ref.set(user_data)
        return User(user_ref.id, user_data)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Group:
    def __init__(self, group_id, data=None):
        self.id = group_id
        if data:
            self.name = data.get('name', '')
            self.description = data.get('description', '')
            self.join_code = data.get('join_code', '')
            self.created_by = data.get('created_by', '')
            self.created_at = data.get('created_at')
            self.has_gift_exchange = data.get('has_gift_exchange', False)
    
    @staticmethod
    def get(group_id):
        """Get group by ID"""
        doc = db.collection('groups').document(group_id).get()
        if doc.exists:
            return Group(doc.id, doc.to_dict())
        return None
    
    @staticmethod
    def get_by_join_code(join_code):
        """Get group by join code"""
        groups = db.collection('groups').where('join_code', '==', join_code).limit(1).stream()
        for group in groups:
            return Group(group.id, group.to_dict())
        return None
    
    @staticmethod
    def create(name, description, created_by):
        """Create a new group"""
        group_ref = db.collection('groups').document()
        join_code = Group.generate_join_code()
        group_data = {
            'name': name,
            'description': description,
            'join_code': join_code,
            'created_by': created_by,
            'created_at': firestore.SERVER_TIMESTAMP,
            'has_gift_exchange': False
        }
        group_ref.set(group_data)
        
        # Add creator as member
        group_ref.collection('members').document(created_by).set({
            'joined_at': firestore.SERVER_TIMESTAMP
        })
        
        return Group(group_ref.id, group_data)
    
    @staticmethod
    def generate_join_code():
        """Generate a unique 6-character join code"""
        while True:
            code = secrets.token_urlsafe(6)[:6].upper()
            # Check if code exists
            existing = db.collection('groups').where('join_code', '==', code).limit(1).get()
            if not list(existing):
                return code
    
    def add_member(self, user_id):
        """Add a member to the group"""
        db.collection('groups').document(self.id).collection('members').document(user_id).set({
            'joined_at': firestore.SERVER_TIMESTAMP
        })
    
    def is_member(self, user_id):
        """Check if user is a member"""
        doc = db.collection('groups').document(self.id).collection('members').document(user_id).get()
        return doc.exists
    
    def get_members(self):
        """Get all members of the group"""
        members_docs = db.collection('groups').document(self.id).collection('members').stream()
        member_ids = [doc.id for doc in members_docs]
        members = []
        for user_id in member_ids:
            user = User.get(user_id)
            if user:
                members.append(user)
        return members
    
    def start_gift_exchange(self, assignments):
        """Start gift exchange with assignments list of (giver_id, receiver_id) tuples"""
        batch = db.batch()
        
        # Add all assignments
        for giver_id, receiver_id in assignments:
            exchange_ref = db.collection('groups').document(self.id).collection('gift_exchanges').document()
            batch.set(exchange_ref, {
                'giver_id': giver_id,
                'receiver_id': receiver_id,
                'created_at': firestore.SERVER_TIMESTAMP
            })
        
        # Mark group as having gift exchange
        group_ref = db.collection('groups').document(self.id)
        batch.update(group_ref, {'has_gift_exchange': True})
        
        batch.commit()
        self.has_gift_exchange = True
    
    def get_gift_exchange_assignment(self, giver_id):
        """Get the receiver for a giver"""
        assignments = db.collection('groups').document(self.id).collection('gift_exchanges').where('giver_id', '==', giver_id).limit(1).stream()
        for assignment in assignments:
            data = assignment.to_dict()
            return User.get(data['receiver_id'])
        return None


class GiftList:
    def __init__(self, gift_id, group_id, data=None):
        self.id = gift_id
        self.group_id = group_id
        if data:
            self.user_id = data.get('user_id', '')
            self.item_name = data.get('item_name', '')
            self.description = data.get('description', '')
            self.link = data.get('link', '')
            self.is_claimed = data.get('is_claimed', False)
            self.claimer_id = data.get('claimer_id')
    
    @staticmethod
    def create(group_id, user_id, item_name, description='', link=''):
        """Create a new gift list item"""
        gift_ref = db.collection('groups').document(group_id).collection('gift_lists').document()
        gift_data = {
            'user_id': user_id,
            'item_name': item_name,
            'description': description,
            'link': link,
            'is_claimed': False,
            'claimer_id': None
        }
        gift_ref.set(gift_data)
        return GiftList(gift_ref.id, group_id, gift_data)
    
    @staticmethod
    def get(group_id, gift_id):
        """Get a specific gift item"""
        doc = db.collection('groups').document(group_id).collection('gift_lists').document(gift_id).get()
        if doc.exists:
            return GiftList(doc.id, group_id, doc.to_dict())
        return None
    
    @staticmethod
    def get_by_user(group_id, user_id):
        """Get all gifts for a user in a group"""
        gifts_docs = db.collection('groups').document(group_id).collection('gift_lists').where('user_id', '==', user_id).stream()
        return [GiftList(doc.id, group_id, doc.to_dict()) for doc in gifts_docs]
    
    @staticmethod
    def get_all_in_group(group_id):
        """Get all gifts in a group"""
        gifts_docs = db.collection('groups').document(group_id).collection('gift_lists').stream()
        return [GiftList(doc.id, group_id, doc.to_dict()) for doc in gifts_docs]
    
    def update(self, **kwargs):
        """Update gift item fields"""
        db.collection('groups').document(self.group_id).collection('gift_lists').document(self.id).update(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def delete(self):
        """Delete gift item"""
        db.collection('groups').document(self.group_id).collection('gift_lists').document(self.id).delete()
    
    def claim(self, claimer_id):
        """Claim this gift"""
        self.update(is_claimed=True, claimer_id=claimer_id)
    
    def unclaim(self):
        """Unclaim this gift"""
        self.update(is_claimed=False, claimer_id=None)


def get_user_groups(user_id):
    """Get all groups a user is a member of"""
    # Query all groups where user is in members subcollection
    all_groups = db.collection('groups').stream()
    user_groups = []
    
    for group_doc in all_groups:
        member_doc = group_doc.reference.collection('members').document(user_id).get()
        if member_doc.exists:
            user_groups.append(Group(group_doc.id, group_doc.to_dict()))
    
    return user_groups