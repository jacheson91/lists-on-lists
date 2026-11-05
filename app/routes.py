from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import app, login_manager
from app.models import User, Group, GiftList, PrivateItem, Message, get_user_groups
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
        
        # Update password using the model method
        user = User.get_by_email(email)
        if user:
            user.update_password(password)
            flash('Your password has been reset successfully!', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'danger')
            return redirect(url_for('forgot_password'))
    
    return render_template('reset_password.html', token=token)

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    # Get all groups the user is a member of; ones they've archived are listed separately
    user_groups = get_user_groups(current_user.id)
    active_groups = [group for group in user_groups if not group.archived_at]
    archived_groups = sorted((group for group in user_groups if group.archived_at),
                             key=lambda group: group.archived_at, reverse=True)

    groups_data = []
    for group in active_groups:
        # Get all members of this group
        members = group.get_members()
        
        # Count how many people the current user still needs to buy for, and how many of
        # the gifts they've claimed have been edited since
        needs_gift = 0
        updated_claims = 0
        for member in members:
            if member.id != current_user.id:
                # Get gifts for this member in this group
                member_gifts = GiftList.get_by_user(group.id, member.id)
                # Check if current user has claimed any
                claimed_by_me = [g for g in member_gifts if g.claimer_id == current_user.id]
                if not claimed_by_me:
                    needs_gift += 1
                updated_claims += sum(1 for g in claimed_by_me if g.edited_since_claim)

        groups_data.append({
            'group': group,
            'member_count': len(members),
            'needs_gift_count': needs_gift,
            'updated_claims_count': updated_claims
        })
    
    return render_template('dashboard.html', groups_data=groups_data, archived_groups=archived_groups)

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
            membership = group.get_membership(current_user.id)
            if membership and membership.get('archived_at'):
                # Entering the code again for a group you archived means you want it back
                group.unarchive_for(current_user.id)
                flash(f'Welcome back! {group.name} is out of your archived groups.', 'success')
                return redirect(url_for('group_detail', group_id=group.id))
            elif membership:
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
    membership = group.get_membership(current_user.id)
    if membership is None:
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

    # Message threads on everyone else's items, filtered to what this user may see
    all_gifts = [gift for entry in member_gifts for gift in entry['gifts']]
    threads = Message.threads_for(group.id, current_user.id, all_gifts)

    return render_template('group_detail.html',
                         group=group,
                         member_gifts=member_gifts,
                         is_creator=is_creator,
                         member_count=len(members),
                         gift_exchange_assignment=gift_exchange_assignment,
                         threads=threads,
                         names={member.id: member.first_name for member in members},
                         open_thread=request.args.get('thread'),
                         archived_at=membership.get('archived_at'))

@app.route('/group/<group_id>/start-gift-exchange', methods=['POST'])
@login_required
def start_gift_exchange(group_id):
    blocked = view_only_redirect(group_id)
    if blocked:
        return blocked

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
    membership = group.get_membership(current_user.id)
    if membership is None:
        flash('You are not a member of this group', 'danger')
        return redirect(url_for('dashboard'))
    archived_at = membership.get('archived_at')

    if request.method == 'POST':
        if archived_at:
            return view_only_redirect(group_id)
        item_name = request.form['item_name']
        description = request.form.get('description', '')
        link = request.form.get('link', '')
        
        GiftList.create(group_id, current_user.id, item_name, description, link)
        return redirect(url_for('my_list', group_id=group_id))
    
    gifts = GiftList.get_by_user(group_id, current_user.id)

    # Private wishlist items that haven't been copied into this group yet
    wishlist = PrivateItem.get_by_user(current_user.id)
    already_copied = {gift.source_private_id for gift in gifts}
    wishlist_to_add = [item for item in wishlist if item.id not in already_copied]

    # The owner's view of their items' threads: anonymous messages and replies, never comments
    threads = Message.threads_for(group_id, current_user.id, gifts)

    return render_template('my_list.html', gifts=gifts, group=group,
                           has_wishlist=bool(wishlist), wishlist_to_add=wishlist_to_add,
                           threads=threads, open_thread=request.args.get('thread'),
                           archived_at=archived_at)

@app.route('/delete-item/<group_id>/<gift_id>', methods=['POST'])
@login_required
def delete_item(group_id, gift_id):
    blocked = view_only_redirect(group_id)
    if blocked:
        return blocked

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

@app.route('/edit-item/<group_id>/<gift_id>', methods=['POST'])
@login_required
def edit_item(group_id, gift_id):
    blocked = view_only_redirect(group_id)
    if blocked:
        return blocked

    gift = GiftList.get(group_id, gift_id)
    if not gift:
        flash('Gift item not found', 'danger')
        return redirect(url_for('dashboard'))

    if gift.user_id != current_user.id:
        flash('You can only edit items on your own list.', 'danger')
        return redirect(url_for('dashboard'))

    if not request.form['item_name'].strip():
        flash('Item name is required.', 'danger')
        return redirect(url_for('my_list', group_id=group_id))

    # Same response whether or not it's claimed, so the owner can't tell
    gift.edit(request.form['item_name'], request.form.get('description', ''), request.form.get('link', ''))
    flash('Gift item updated.', 'success')
    return redirect(url_for('my_list', group_id=group_id, _anchor=f'item-{gift_id}'))

@app.route('/dismiss-edit-alert/<group_id>/<gift_id>', methods=['POST'])
@login_required
def dismiss_edit_alert(group_id, gift_id):
    blocked = view_only_redirect(group_id)
    if blocked:
        return blocked

    gift = GiftList.get(group_id, gift_id)
    if gift and gift.claimer_id == current_user.id:
        gift.dismiss_edit_alert()
    return redirect(url_for('group_detail', group_id=group_id, _anchor=f'item-{gift_id}'))

@app.route('/claim-item/<group_id>/<gift_id>', methods=['POST'])
@login_required
def claim_item(group_id, gift_id):
    blocked = view_only_redirect(group_id)
    if blocked:
        return blocked

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
    blocked = view_only_redirect(group_id)
    if blocked:
        return blocked

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
@app.route('/wishlist', methods=['GET', 'POST'])
@login_required
def wishlist():
    """The user's private wishlist, kept outside any group"""
    if request.method == 'POST':
        if not request.form['item_name'].strip():
            flash('Item name is required.', 'danger')
        else:
            PrivateItem.create(current_user.id, request.form['item_name'],
                               request.form.get('description', ''), request.form.get('link', ''))
        return redirect(url_for('wishlist'))
    
    items = PrivateItem.get_by_user(current_user.id)
    groups = get_user_groups(current_user.id)

    # Names of the groups each wishlist item has already been copied into
    copied_to = {}
    for group in groups:
        for gift in GiftList.get_by_user(group.id, current_user.id):
            if gift.source_private_id:
                copied_to.setdefault(gift.source_private_id, []).append(group.name)

    # Items can only be copied into groups that aren't archived (archived ones are view-only)
    copy_groups = [group for group in groups if not group.archived_at]

    return render_template('wishlist.html', items=items, groups=groups, copy_groups=copy_groups,
                           copied_to=copied_to)

@app.route('/wishlist/<item_id>/edit', methods=['POST'])
@login_required
def edit_wishlist_item(item_id):
    item = PrivateItem.get(current_user.id, item_id)
    if not item:
        flash('Wishlist item not found', 'danger')
    elif not request.form['item_name'].strip():
        flash('Item name is required.', 'danger')
    else:
        item.update(request.form['item_name'], request.form.get('description', ''), request.form.get('link', ''))
        flash('Wishlist item updated.', 'success')
    return redirect(url_for('wishlist', _anchor=f'item-{item_id}'))

@app.route('/wishlist/<item_id>/delete', methods=['POST'])
@login_required
def delete_wishlist_item(item_id):
    item = PrivateItem.get(current_user.id, item_id)
    if item:
        item.delete()
        flash('Removed from your wishlist.', 'success')
    return redirect(url_for('wishlist'))

@app.route('/wishlist/copy', methods=['POST'])
@login_required
def copy_wishlist_items():
    """Copy selected private wishlist items into the user's list for a group"""
    group = Group.get(request.form.get('group_id', ''))
    if not group or not group.is_member(current_user.id):
        flash('Choose one of your groups to copy into.', 'danger')
        return redirect(url_for('wishlist'))
    blocked = view_only_redirect(group.id)
    if blocked:
        return blocked

    
    item_ids = request.form.getlist('item_ids')
    if not item_ids:
        flash('Tick the items you want to copy first.', 'info')
        if request.form.get('return_to') == 'my_list':
            return redirect(url_for('my_list', group_id=group.id))
        return redirect(url_for('wishlist'))
    
    # Skip anything already copied into this group
    already_copied = {gift.source_private_id for gift in GiftList.get_by_user(group.id, current_user.id)}
    copied = skipped = 0
    for item_id in item_ids:
        item = PrivateItem.get(current_user.id, item_id)
        if not item:
            continue
        if item.id in already_copied:
            skipped += 1
        else:
            item.copy_to_group(group.id)
            copied += 1
    
    message = f'Added {copied} item{"s" if copied != 1 else ""} to your list for {group.name}.'
    if skipped:
        message += f' {skipped} {"was" if skipped == 1 else "were"} already there.'
    flash(message, 'success')
    return redirect(url_for('my_list', group_id=group.id))

@app.route('/likes', methods=['POST'])
@login_required
def update_likes():
    """Save the user's likes/dislikes, shown to all their groups"""
    current_user.update_likes(request.form.get('likes', ''), request.form.get('dislikes', ''))
    flash('Your likes and dislikes have been saved.', 'success')
    
    # Only follow paths within this site
    next_url = request.form.get('next', '')
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = url_for('wishlist')
    return redirect(next_url)

@app.route('/message/<group_id>/<gift_id>', methods=['POST'])
@login_required
def post_message(group_id, gift_id):
    blocked = view_only_redirect(group_id)
    if blocked:
        return blocked

    group = Group.get(group_id)
    gift = GiftList.get(group_id, gift_id)
    if not group or not gift or not group.is_member(current_user.id):
        flash('Gift item not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Owners can only reply on their own items; everyone else picks hidden or anonymous
    is_owner = gift.user_id == current_user.id
    kind = 'reply' if is_owner else request.form.get('kind')
    text = request.form.get('text', '').strip()
    
    if not text:
        flash('Write a message first.', 'info')
    elif not is_owner and kind not in Message.MEMBER_KINDS:
        flash('Choose who can see your message.', 'danger')
    else:
        Message.create(group_id, gift_id, current_user.id, kind, text)
    
    return redirect(thread_url(gift, is_owner))

@app.route('/delete-message/<group_id>/<message_id>', methods=['POST'])
@login_required
def delete_message(group_id, message_id):
    blocked = view_only_redirect(group_id)
    if blocked:
        return blocked

    message = Message.get(group_id, message_id)
    if not message or message.author_id != current_user.id:
        flash('Message not found', 'danger')
        return redirect(url_for('dashboard'))
    
    message.delete()
    gift = GiftList.get(group_id, message.item_id)
    if not gift:
        return redirect(url_for('group_detail', group_id=group_id))
    return redirect(thread_url(gift, gift.user_id == current_user.id))

def thread_url(gift, is_owner):
    """Back to the page showing this item's thread, scrolled to it and opened"""
    page = 'my_list' if is_owner else 'group_detail'
    return url_for(page, group_id=gift.group_id, thread=gift.id, _anchor=f'item-{gift.id}')

@app.template_filter('short_date')
def short_date(value):
    """e.g. '3 Nov'. Server timestamps are only filled in after a write, so tolerate missing ones."""
    if not hasattr(value, 'strftime'):
        return ''
    return f'{value.day} {value.strftime("%b")}'

@app.route('/group/<group_id>/archive', methods=['POST'])
@login_required
def archive_group(group_id):
    """Archive a group for the current user only: it moves to the Archived section of their
    dashboard and becomes view-only for them. Nobody else in the group is affected."""
    group = Group.get(group_id)
    if not group or not group.is_member(current_user.id):
        flash('Group not found', 'danger')
        return redirect(url_for('dashboard'))
    
    group.archive_for(current_user.id)
    flash(f'{group.name} is archived. It’s at the bottom of your dashboard and view-only for you; '
          'nobody else is affected.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/group/<group_id>/unarchive', methods=['POST'])
@login_required
def unarchive_group(group_id):
    group = Group.get(group_id)
    if not group or not group.is_member(current_user.id):
        flash('Group not found', 'danger')
        return redirect(url_for('dashboard'))
    
    group.unarchive_for(current_user.id)
    flash(f'{group.name} is back on your dashboard.', 'success')
    return redirect(url_for('group_detail', group_id=group_id))

def view_only_redirect(group_id):
    """Groups a member has archived are view-only for them. If the current user has archived
    this one, explain and send them back to it; otherwise return None so the change can go ahead."""
    if Group.is_archived_for(group_id, current_user.id):
        flash('You’ve archived this group, so it’s view-only for you. Unarchive it to make changes.', 'info')
        return redirect(url_for('group_detail', group_id=group_id))
    return None

@app.template_filter('full_date')
def full_date(value):
    """e.g. '3 Nov 2026'"""
    if not hasattr(value, 'strftime'):
        return ''
    return f'{value.day} {value.strftime("%b %Y")}'
