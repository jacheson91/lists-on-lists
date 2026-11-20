import re

import pytest

from app.models import Group, GiftList, Message, PrivateItem, User, db


def text(response):
    return response.get_data(as_text=True)


def stat(page, label):
    """The number shown in the tile with this label"""
    match = re.search(r'<span class="stat-number[^"]*">(\d+(?:\.\d+)?)</span><span class="stat-label">'
                      + re.escape(label) + '</span>', page)
    assert match, f'no tile labelled {label!r}'
    return float(match.group(1)) if '.' in match.group(1) else int(match.group(1))


@pytest.fixture
def admin(family):
    db.collection('users').document(family.alice.id).update({'is_admin': True})
    return family.alice


def test_non_admins_get_a_404(family, login):
    assert login(family.ben).get('/admin/stats').status_code == 404


def test_logged_out_visitors_are_sent_to_login(family):
    from app import app
    response = app.test_client().get('/admin/stats')
    assert response.status_code == 302 and '/login' in response.headers['Location']


def test_only_admins_see_the_dashboard_link(family, login, admin):
    assert '/admin/stats' in text(login(family.alice).get('/dashboard'))
    assert '/admin/stats' not in text(login(family.ben).get('/dashboard'))


def test_stats_add_up(family, login, admin):
    # family: Alice, Ben and Carol in one group of 3. Add a loner and a second group.
    User.create('Lonely', 'Signup', 'lonely@example.com', 'password123')
    second = Group.create('Cousins', '', family.carol.id)
    second.start_gift_exchange([(family.carol.id, family.carol.id)])
    gift = GiftList.create(family.group.id, family.ben.id, 'Bike lights')
    GiftList.create(second.id, family.carol.id, 'Puzzle')
    Message.create(family.group.id, gift.id, family.carol.id, 'comment', 'Nice')
    PrivateItem.create(family.alice.id, 'Headphones')

    page = text(login(family.alice).get('/admin/stats'))
    assert stat(page, 'total') == 4                       # accounts tile comes first
    assert stat(page, 'in at least one group') == 3
    assert stat(page, 'not in any group') == 1
    assert stat(page, 'with a gift exchange') == 1
    assert stat(page, 'members per group, on average') == 2.0   # 3 + 1 members over 2 groups
    assert stat(page, 'gift list items') == 2
    assert stat(page, 'private wishlist items') == 1
    assert stat(page, 'messages') == 1


def test_recent_activity_is_counted_this_week(family, login, admin):
    page = text(login(family.alice).get('/admin/stats'))
    assert stat(page, 'new in the last 7 days') == 3      # first match is the accounts tile
    this_week = page.split('(this week)')[1].split('</tr>')[0]
    assert re.findall(r'</span>(\d+)</td>', this_week) == ['3', '1']
