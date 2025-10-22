from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db, login_manager
from app.models import User, GiftList, Group, group_members

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
        if User.query.filter_by(email=email).first():
            flash('Email is already registered', 'danger')
        else:
            user = User(first_name=first_name, last_name=last_name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
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
        user = User.query.filter_by(email=email).first()
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

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    # Get all groups the user is a member of
    user_groups = db.session.query(Group).join(group_members).filter(
        group_members.c.user_id == current_user.id
    ).all()
    
    groups_data = []
    for group in user_groups:
        # Get all members of this group except current user
        members = db.session.query(User).join(group_members).filter(
            group_members.c.group_id == group.id,
            User.id != current_user.id
        ).all()
        
        # Count how many people the current user still needs to buy for
        needs_gift = 0
        for member in members:
            claimed_by_me = GiftList.query.filter_by(
                user_id=member.id,
                group_id=group.id,
                claimer_id=current_user.id
            ).count()
            if claimed_by_me == 0:
                needs_gift += 1
        
        groups_data.append({
            'group': group,
            'member_count': len(members) + 1,  # +1 for current user
            'needs_gift_count': needs_gift
        })
    
    return render_template('dashboard.html', groups_data=groups_data)

@app.route('/create-group', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        
        group = Group(name=name, description=description, created_by=current_user.id)
        group.join_code = group.generate_join_code()
        
        db.session.add(group)
        db.session.commit()
        
        # Add creator to the group
        db.session.execute(group_members.insert().values(
            user_id=current_user.id,
            group_id=group.id
        ))
        db.session.commit()
        
        flash(f'Group created! Join code: {group.join_code}', 'success')
        return redirect(url_for('group_detail', group_id=group.id))
    
    return render_template('create_group.html')

@app.route('/join-group', methods=['GET', 'POST'])
@login_required
def join_group():
    if request.method == 'POST':
        join_code = request.form['join_code'].upper().strip()
        group = Group.query.filter_by(join_code=join_code).first()
        
        if not group:
            flash('Invalid join code', 'danger')
        else:
            # Check if already a member
            is_member = db.session.query(group_members).filter_by(
                user_id=current_user.id,
                group_id=group.id
            ).first()
            
            if is_member:
                flash('You are already a member of this group', 'info')
            else:
                db.session.execute(group_members.insert().values(
                    user_id=current_user.id,
                    group_id=group.id
                ))
                db.session.commit()
                flash(f'Successfully joined {group.name}!', 'success')
                return redirect(url_for('group_detail', group_id=group.id))
    
    return render_template('join_group.html')

@app.route('/group/<int:group_id>')
@login_required
def group_detail(group_id):
    group = Group.query.get_or_404(group_id)
    
    # Check if user is a member
    is_member = db.session.query(group_members).filter_by(
        user_id=current_user.id,
        group_id=group_id
    ).first()
    
    if not is_member:
        flash('You are not a member of this group', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get all members and their gifts
    members = db.session.query(User).join(group_members).filter(
        group_members.c.group_id == group_id
    ).all()
    
    member_gifts = []
    for member in members:
        if member.id != current_user.id:
            gifts = GiftList.query.filter_by(user_id=member.id, group_id=group_id).all()
            claimed_count = sum(1 for g in gifts if g.is_claimed and g.claimer_id == current_user.id)
            member_gifts.append({
                'user': member,
                'gifts': gifts,
                'claimed_by_me': claimed_count
            })
    
    return render_template('group_detail.html', group=group, member_gifts=member_gifts)

@app.route('/my-list/<int:group_id>', methods=['GET', 'POST'])
@login_required
def my_list(group_id):
    group = Group.query.get_or_404(group_id)
    
    # Check if user is a member
    is_member = db.session.query(group_members).filter_by(
        user_id=current_user.id,
        group_id=group_id
    ).first()
    
    if not is_member:
        flash('You are not a member of this group', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        item_name = request.form['item_name']
        description = request.form.get('description', '')
        link = request.form.get('link', None)
        gift = GiftList(
            user_id=current_user.id,
            group_id=group_id,
            item_name=item_name,
            description=description,
            link=link
        )
        db.session.add(gift)
        db.session.commit()
        flash('Gift item added successfully!', 'success')
        return redirect(url_for('my_list', group_id=group_id))

    gifts = GiftList.query.filter_by(user_id=current_user.id, group_id=group_id).all()
    return render_template('my_list.html', gifts=gifts, group=group)

@app.route('/delete-item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    gift = GiftList.query.get_or_404(item_id)
    if gift.user_id != current_user.id:
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('dashboard'))

    group_id = gift.group_id
    db.session.delete(gift)
    db.session.commit()
    flash('Gift item deleted successfully.', 'success')
    return redirect(url_for('my_list', group_id=group_id))

@app.route('/claim-item/<int:item_id>', methods=['POST'])
@login_required
def claim_item(item_id):
    gift = GiftList.query.get_or_404(item_id)
    if gift.user_id == current_user.id:
        flash('You cannot claim your own item.', 'danger')
        return redirect(url_for('group_detail', group_id=gift.group_id))
    if gift.is_claimed:
        flash('This item has already been claimed.', 'danger')
        return redirect(url_for('group_detail', group_id=gift.group_id))

    gift.is_claimed = True
    gift.claimer_id = current_user.id
    db.session.commit()
    flash('Gift item claimed successfully!', 'success')
    return redirect(url_for('group_detail', group_id=gift.group_id))

@app.route('/unclaim-item/<int:item_id>', methods=['POST'])
@login_required
def unclaim_item(item_id):
    gift = GiftList.query.get_or_404(item_id)
    if gift.claimer_id != current_user.id:
        flash('You did not claim this item.', 'danger')
        return redirect(url_for('group_detail', group_id=gift.group_id))

    gift.is_claimed = False
    gift.claimer_id = None
    db.session.commit()
    flash('Gift item unclaimed successfully!', 'success')
    return redirect(url_for('group_detail', group_id=gift.group_id))