from app.models import Group, GiftList, Message, PrivateItem, User, db

VIEW_ONLY_FLASH = 'You’ve archived this group, so it’s view-only for you.'


def text(response):
    return response.get_data(as_text=True)


def squash(html):
    return ' '.join(html.split())


def dashboard_sections(client):
    """(active part, archived part) of the dashboard HTML"""
    page = text(client.get('/dashboard'))
    active, _, archived = page.partition('class="archived-groups"')
    return active, archived


def archive(client, group):
    """Archive as this client, following the redirect so the confirmation flash is used up"""
    return client.post(f'/group/{group.id}/archive', follow_redirects=True)


def assert_controls_vanish(client, url, controls, group):
    """Each control must be on the page before archiving (so the check can fail) and gone after"""
    before = text(client.get(url))
    for control in controls:
        assert control in before, f'{control} missing before archiving'
    archive(client, group)
    after = text(client.get(url))
    for control in controls:
        assert control not in after, f'{control} still offered after archiving'
    return after


# Archiving and unarchiving

def test_archiving_moves_the_group_to_my_archived_section(family, login):
    alice = login(family.alice)
    archive(alice, family.group)

    active, archived_part = dashboard_sections(alice)
    assert 'Family Christmas' not in active
    assert 'Family Christmas' in archived_part
    assert 'Archived groups (1)' in archived_part
    assert f'action="/group/{family.group.id}/unarchive"' in archived_part


def test_archiving_only_affects_me(family, login):
    archive(login(family.alice), family.group)

    ben = login(family.ben)
    active, archived_part = dashboard_sections(ben)
    assert 'Family Christmas' in active
    assert archived_part == ''
    assert 'You archived this group' not in text(ben.get(f'/group/{family.group.id}'))


def test_unarchiving_brings_it_back_and_allows_changes_again(family, login):
    bens = GiftList.create(family.group.id, family.ben.id, 'Bike lights')
    alice = login(family.alice)
    archive(alice, family.group)

    response = alice.post(f'/group/{family.group.id}/unarchive', follow_redirects=True)
    assert 'Family Christmas is back on your dashboard.' in text(response)
    active, archived_part = dashboard_sections(alice)
    assert 'Family Christmas' in active and archived_part == ''

    alice.post(f'/claim-item/{family.group.id}/{bens.id}')
    assert GiftList.get(family.group.id, bens.id).claimer_id == family.alice.id


def test_banners_offer_unarchiving(family, login):
    alice = login(family.alice)
    archive(alice, family.group)

    for url in [f'/group/{family.group.id}', f'/my-list/{family.group.id}']:
        page = text(alice.get(url))
        assert 'You archived this group on' in page, url
        assert f'action="/group/{family.group.id}/unarchive"' in page, url


def test_non_members_cannot_archive_or_unarchive(family, login):
    outsider = login(User.create('Olive', 'Other', 'olive@example.com', 'password123'))

    for action in ['archive', 'unarchive']:
        response = outsider.post(f'/group/{family.group.id}/{action}')
        assert response.status_code == 302 and response.headers['Location'] == '/dashboard', action
        assert 'Group not found' in text(outsider.get('/dashboard')), action


def test_rejoining_with_the_code_unarchives(family, login):
    alice = login(family.alice)
    archive(alice, family.group)

    response = alice.post('/join-group', data={'join_code': family.group.join_code}, follow_redirects=True)
    assert 'out of your archived groups' in text(response)
    assert not Group.is_archived_for(family.group.id, family.alice.id)


def test_empty_state_when_everything_is_archived(family, login):
    alice = login(family.alice)
    archive(alice, family.group)

    active, _ = dashboard_sections(alice)
    assert 'No active groups' in active
    assert 'No groups yet' not in active
    assert '<details class="archived-groups" open>' in text(alice.get('/dashboard'))


def test_archived_groups_skip_dashboard_alerts(family, login):
    gift = GiftList.create(family.group.id, family.ben.id, 'Bike lights')
    gift.claim(family.alice.id)
    gift.edit('Brighter bike lights', '', '')
    alice = login(family.alice)
    assert 'gift you claimed has been updated' in squash(text(alice.get('/dashboard')))

    archive(alice, family.group)
    assert 'gift you claimed has been updated' not in squash(text(alice.get('/dashboard')))


# Viewing an archived group

def test_archived_group_is_still_readable(family, login):
    gift = GiftList.create(family.group.id, family.ben.id, 'Bike lights')
    gift.claim(family.alice.id)
    Message.create(family.group.id, gift.id, family.carol.id, 'comment', 'Nice choice')
    alice = login(family.alice)
    archive(alice, family.group)

    page = text(alice.get(f'/group/{family.group.id}'))
    assert 'Bike lights' in page and 'Claimed by you' in page and 'Nice choice' in page


def test_group_page_controls_disappear_when_archived(family, login):
    GiftList.create(family.group.id, family.ben.id, 'Bike lights')               # Claim
    puzzle = GiftList.create(family.group.id, family.carol.id, 'Puzzle')
    puzzle.claim(family.alice.id)                                                # Unclaim
    puzzle.edit('Bigger puzzle', '', '')                                         # Got it
    Message.create(family.group.id, puzzle.id, family.alice.id, 'comment', 'Mine')  # Delete message
    alice = login(family.alice)   # Alice created the group, so she'd see Start gift exchange

    controls = ['/claim-item/', '/unclaim-item/', '/dismiss-edit-alert/', '/message/', '/delete-message/',
                '/start-gift-exchange', f'action="/group/{family.group.id}/archive"']
    page = assert_controls_vanish(alice, f'/group/{family.group.id}', controls, family.group)
    assert 'View my list' in page


def test_my_list_controls_disappear_when_archived(family, login):
    scarf = GiftList.create(family.group.id, family.alice.id, 'Wool scarf')
    Message.create(family.group.id, scarf.id, family.alice.id, 'reply', 'Long please')
    Message.create(family.group.id, scarf.id, family.ben.id, 'anonymous', 'Long or short?')
    Message.create(family.group.id, scarf.id, family.ben.id, 'comment', 'Secret halves plan')
    PrivateItem.create(family.alice.id, 'Headphones')   # so "Add from my wishlist" is offered
    alice = login(family.alice)

    controls = ['/edit-item/', '/delete-item/', '/message/', '/delete-message/', 'toggleGiftForm',
                '/wishlist/copy', 'Add from my wishlist']
    page = assert_controls_vanish(alice, f'/my-list/{family.group.id}', controls, family.group)
    assert 'Wool scarf' in page and 'Long or short?' in page and 'Long please' in page
    assert 'Secret halves plan' not in page   # archiving doesn't loosen message privacy


# Every change is refused for the person who archived it

def blocked_actions(group, alice, ben):
    """(description, request to make as Alice, check the data is unchanged)"""
    group_id = group.id
    bens = GiftList.create(group_id, ben.id, 'Bike lights')
    claimed = GiftList.create(group_id, ben.id, 'Socks')
    claimed.claim(alice.id)
    claimed.edit('Running socks', '', '')
    alices = GiftList.create(group_id, alice.id, 'Scarf')
    message = Message.create(group_id, bens.id, alice.id, 'comment', 'Mine')
    wish = PrivateItem.create(alice.id, 'Headphones')

    return [
        ('claim', f'/claim-item/{group_id}/{bens.id}', {},
         lambda: not GiftList.get(group_id, bens.id).is_claimed),
        ('unclaim', f'/unclaim-item/{group_id}/{claimed.id}', {},
         lambda: GiftList.get(group_id, claimed.id).claimer_id == alice.id),
        ('dismiss edit alert', f'/dismiss-edit-alert/{group_id}/{claimed.id}', {},
         lambda: GiftList.get(group_id, claimed.id).edited_since_claim),
        ('add item', f'/my-list/{group_id}', {'item_name': 'New thing', 'description': '', 'link': ''},
         lambda: len(GiftList.get_by_user(group_id, alice.id)) == 1),
        ('edit item', f'/edit-item/{group_id}/{alices.id}', {'item_name': 'Changed', 'description': '', 'link': ''},
         lambda: GiftList.get(group_id, alices.id).item_name == 'Scarf'),
        ('delete item', f'/delete-item/{group_id}/{alices.id}', {},
         lambda: GiftList.get(group_id, alices.id) is not None),
        ('post message', f'/message/{group_id}/{bens.id}', {'text': 'Hello', 'kind': 'comment'},
         lambda: len(Message.threads_for(group_id, alice.id, [bens])[bens.id]) == 1),
        ('delete message', f'/delete-message/{group_id}/{message.id}', {},
         lambda: Message.get(group_id, message.id) is not None),
        ('start gift exchange', f'/group/{group_id}/start-gift-exchange', {},
         lambda: not Group.get(group_id).has_gift_exchange),
        ('copy from wishlist', '/wishlist/copy', {'group_id': group_id, 'item_ids': [wish.id]},
         lambda: len(GiftList.get_by_user(group_id, alice.id)) == 1),
    ]


def test_every_change_is_refused_while_archived(family, login):
    actions = blocked_actions(family.group, family.alice, family.ben)
    alice = login(family.alice)
    archive(alice, family.group)

    for name, path, data, unchanged in actions:
        response = alice.post(path, data=data)
        assert response.status_code == 302, name
        assert response.headers['Location'] == f'/group/{family.group.id}', name
        assert VIEW_ONLY_FLASH in text(alice.get(response.headers['Location'])), name
        assert unchanged(), name


def test_everyone_else_can_still_use_my_items(family, login):
    scarf = GiftList.create(family.group.id, family.alice.id, 'Scarf')
    archive(login(family.alice), family.group)

    ben = login(family.ben)
    ben.post(f'/claim-item/{family.group.id}/{scarf.id}')
    ben.post(f'/message/{family.group.id}/{scarf.id}', data={'text': 'Got it!', 'kind': 'comment'})

    assert GiftList.get(family.group.id, scarf.id).claimer_id == family.ben.id
    assert len(Message.threads_for(family.group.id, family.ben.id, [scarf])[scarf.id]) == 1


# Wishlist

def test_wishlist_does_not_offer_archived_groups(family, login):
    Group.create('Cousins', '', family.alice.id)
    PrivateItem.create(family.alice.id, 'Headphones')
    alice = login(family.alice)
    archive(alice, family.group)

    page = text(alice.get('/wishlist'))
    select = page.split('<select')[1].split('</select>')[0]
    assert 'Cousins' in select and 'Family Christmas' not in select
    # The item card is captured with {% set %}; it must render as HTML, not escaped text
    assert '<div class="item-body">' in page and '&lt;div' not in page


def test_wishlist_when_all_groups_are_archived(family, login):
    PrivateItem.create(family.alice.id, 'Headphones').copy_to_group(family.group.id)
    alice = login(family.alice)
    archive(alice, family.group)

    page = text(alice.get('/wishlist'))
    assert 'All your groups are archived' in page
    assert 'form="copy-form"' not in page
    assert 'On your list for Family Christmas' in page   # still shown without the tick box
