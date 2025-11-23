from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import app, login_manager
from app.models import User, Group, GiftList, get_user_groups
from app.utils import send_reset_email, get_serializer
import random

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        
        # Check if email already exists
        if User.get_by_email(email):
            flash('Email is already registered', 'danger')
        else:
            User.create(first_name, last_name, email, password)
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.get_by_email(email)
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form['email']
        user = User.get_by_email(email)
        
        if user:
            # Generate reset token
            serializer = get_serializer()
            token = serializer.dumps(email, salt='password-reset-salt')
            
            # Create reset URL
            reset_url = url_for('reset_password', token=token, _external=True)
            
            # Send email (for now just prints to console)
            send_reset_email(email, reset_url)
            
        # Always show success message (don't reveal if email exists)
        flash('If that email exists, a password reset link has been sent.', 'info')
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    try:
        # Verify token (valid for 1 hour)
        serializer = get_serializer()
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('reset_password.html', token=token)
        
        # Update password in Firestore
        user = User.get_by_email(email)
        if user:
            from google.cloud import firestore
            from werkzeug.security import generate_password_hash
            
            db = firestore.Client()
            db.collection('users').document(user.id).update({
                'password_hash': generate_password_hash(password)
            })
            
            flash('Your password has been reset successfully!', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'danger')
            return redirect(url_for('forgot_password'))
    
    return render_template('reset_password.html', token=token)

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    # Get all groups the user is a member of
    user_groups = get_user_groups(current_user.id)
    
    groups_data = []
    for group in user_groups:
        # Get all members of this group
        members = group.get_members()
        
        # Count how many people the current user still needs to buy for
        needs_gift = 0
        for member in members:
            if member.id != current_user.id:
                # Get gifts for this member in this group
                member_gifts = GiftList.get_by_user(group.id, member.id)
                # Check if current user has claimed any
                claimed_by_me = sum(1 for g in member_gifts if g.claimer_id == current_user.id)
                if claimed_by_me == 0:
                    needs_gift += 1
        
        groups_data.append({
            'group': group,
            'member_count': len(members),
            'needs_gift_count': needs_gift
        })
    
    return render_template('dashboard.html', groups_data=groups_data)

@app.route('/create-group', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        
        group = Group.create(name, description, current_user.id)
        
        flash(f'Group created! Join code: {group.join_code}', 'success')
        return redirect(url_for('group_detail', group_id=group.id))
    
    return render_template('create_group.html')

@app.route('/join-group', methods=['GET', 'POST'])
@login_required
def join_group():
    if request.method == 'POST':
        join_code = request.form['join_code'].upper().strip()
        group = Group.get_by_join_code(join_code)
        
        if not group:
            flash('Invalid join code', 'danger')
        else:
            # Check if already a member
            if group.is_member(current_user.id):
                flash('You are already a member of this group', 'info')
            else:
                group.add_member(current_user.id)
                flash(f'Successfully joined {group.name}!', 'success')
                return redirect(url_for('group_detail', group_id=group.id))
    
    return render_template('join_group.html')

@app.route('/group/<group_id>')
@login_required
def group_detail(group_id):
    group = Group.get(group_id)
    if not group:
        flash('Group not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if user is a member
    if not group.is_member(current_user.id):
        flash('You are not a member of this group', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if user is the creator
    is_creator = (group.created_by == current_user.id)
    
    # Get all members
    members = group.get_members()
    
    # Check if gift exchange is active and get assignment
    gift_exchange_assignment = None
    if group.has_gift_exchange:
        gift_exchange_assignment = group.get_gift_exchange_assignment(current_user.id)
    
    # Get all members and their gifts (excluding current user)
    member_gifts = []
    for member in members:
        if member.id != current_user.id:
            gifts = GiftList.get_by_user(group.id, member.id)
            claimed_by_me = sum(1 for g in gifts if g.claimer_id == current_user.id)
            member_gifts.append({
                'user': member,
                'gifts': gifts,
                'claimed_by_me': claimed_by_me
            })
    
    return render_template('group_detail.html', 
                         group=group, 
                         member_gifts=member_gifts,
                         is_creator=is_creator,
                         member_count=len(members),
                         gift_exchange_assignment=gift_exchange_assignment)

@app.route('/group/<group_id>/start-gift-exchange', methods=['POST'])
@login_required
def start_gift_exchange(group_id):
    group = Group.get(group_id)
    if not group:
        flash('Group not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if user is the creator
    if group.created_by != current_user.id:
        flash('Only the group creator can start a gift exchange', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    # Check if gift exchange already exists
    if group.has_gift_exchange:
        flash('Gift exchange has already been started for this group', 'info')
        return redirect(url_for('group_detail', group_id=group_id))
    
    # Get all members
    members = group.get_members()
    
    # Need at least 2 people for gift exchange
    if len(members) < 2:
        flash('You need at least 2 members to start a gift exchange', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    # Create random assignments (ensure no one gets themselves)
    givers = [m.id for m in members]
    receivers = givers.copy()
    
    # Shuffle until no one has themselves
    valid = False
    attempts = 0
    while not valid and attempts < 100:
        random.shuffle(receivers)
        valid = all(givers[i] != receivers[i] for i in range(len(givers)))
        attempts += 1
    
    if not valid:
        flash('Unable to create gift exchange assignments. Please try again.', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    # Create assignments list
    assignments = [(givers[i], receivers[i]) for i in range(len(givers))]
    
    # Save to Firestore
    group.start_gift_exchange(assignments)
    
    flash('Gift exchange started! Check who you got below.', 'success')
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/my-list/<group_id>', methods=['GET', 'POST'])
@login_required
def my_list(group_id):
    group = Group.get(group_id)
    if not group:
        flash('Group not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if user is a member
    if not group.is_member(current_user.id):
        flash('You are not a member of this group', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        item_name = request.form['item_name']
        description = request.form.get('description', '')
        link = request.form.get('link', '')
        
        GiftList.create(group_id, current_user.id, item_name, description, link)
        return redirect(url_for('my_list', group_id=group_id))
    
    gifts = GiftList.get_by_user(group_id, current_user.id)
    return render_template('my_list.html', gifts=gifts, group=group)

@app.route('/delete-item/<group_id>/<gift_id>', methods=['POST'])
@login_required
def delete_item(group_id, gift_id):
    gift = GiftList.get(group_id, gift_id)
    if not gift:
        flash('Gift item not found', 'danger')
        return redirect(url_for('dashboard'))
    
    if gift.user_id != current_user.id:
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('dashboard'))
    
    gift.delete()
    flash('Gift item deleted successfully.', 'success')
    return redirect(url_for('my_list', group_id=group_id))

@app.route('/claim-item/<group_id>/<gift_id>', methods=['POST'])
@login_required
def claim_item(group_id, gift_id):
    gift = GiftList.get(group_id, gift_id)
    if not gift:
        flash('Gift item not found', 'danger')
        return redirect(url_for('dashboard'))
    
    if gift.user_id == current_user.id:
        flash('You cannot claim your own item.', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    if gift.is_claimed:
        flash('This item has already been claimed.', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    gift.claim(current_user.id)
    flash('Gift item claimed successfully!', 'success')
    return redirect(url_for('group_detail', group_id=group_id))

@app.route('/unclaim-item/<group_id>/<gift_id>', methods=['POST'])
@login_required
def unclaim_item(group_id, gift_id):
    gift = GiftList.get(group_id, gift_id)
    if not gift:
        flash('Gift item not found', 'danger')
        return redirect(url_for('dashboard'))
    
    if gift.claimer_id != current_user.id:
        flash('You did not claim this item.', 'danger')
        return redirect(url_for('group_detail', group_id=group_id))
    
    gift.unclaim()
    flash('Gift item unclaimed successfully!', 'success')
    return redirect(url_for('group_detail', group_id=group_id))