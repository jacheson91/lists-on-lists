import pytest

from app.models import GiftList


@pytest.fixture
def scarf(family):
    return GiftList.create(family.group.id, family.alice.id, 'Wool scarf', 'Navy', 'https://example.com/navy')


def edit(client, family, gift, **fields):
    data = {'item_name': gift.item_name, 'description': gift.description, 'link': gift.link}
    data.update(fields)
    return client.post(f'/edit-item/{family.group.id}/{gift.id}', data=data, follow_redirects=True)


def group_page(client, family):
    return client.get(f'/group/{family.group.id}').get_data(as_text=True)


def test_owner_can_edit_unclaimed_item(family, login, scarf):
    edit(login(family.alice), family, scarf, item_name='Cashmere scarf', description='Grey')

    gift = GiftList.get(family.group.id, scarf.id)
    assert (gift.item_name, gift.description) == ('Cashmere scarf', 'Grey')
    assert not gift.edited_since_claim


def test_only_owner_can_edit(family, login, scarf):
    edit(login(family.ben), family, scarf, item_name='Hacked')
    assert GiftList.get(family.group.id, scarf.id).item_name == 'Wool scarf'


def test_claimer_is_told_what_changed(family, login, scarf):
    ben = login(family.ben)
    ben.post(f'/claim-item/{family.group.id}/{scarf.id}')
    edit(login(family.alice), family, scarf, description='Grey', link='https://example.com/grey')

    page = group_page(ben, family)
    assert 'Updated since you claimed it' in page
    assert '<s>Navy</s> → Grey' in page
    assert 'https://example.com/grey' in page
    dashboard = ' '.join(ben.get('/dashboard').get_data(as_text=True).split())
    assert '1 gift you claimed has been updated' in dashboard


def test_owner_and_other_members_never_see_the_alert(family, login, scarf):
    login(family.ben).post(f'/claim-item/{family.group.id}/{scarf.id}')
    alice = login(family.alice)
    owner_response = edit(alice, family, scarf, item_name='Red scarf').get_data(as_text=True)

    assert 'Gift item updated.' in owner_response
    assert 'claimed' not in owner_response.lower()
    assert 'Updated since you claimed it' not in group_page(login(family.carol), family)


def test_owner_sees_same_response_whether_or_not_claimed(family, login, scarf):
    alice = login(family.alice)
    unclaimed = edit(alice, family, scarf, item_name='Red scarf').get_data(as_text=True)
    login(family.ben).post(f'/claim-item/{family.group.id}/{scarf.id}')
    claimed = edit(alice, family, GiftList.get(family.group.id, scarf.id), item_name='Blue scarf').get_data(as_text=True)

    assert unclaimed.replace('Red scarf', 'X') == claimed.replace('Blue scarf', 'X')


def test_dismissing_clears_the_alert(family, login, scarf):
    ben = login(family.ben)
    ben.post(f'/claim-item/{family.group.id}/{scarf.id}')
    edit(login(family.alice), family, scarf, item_name='Red scarf')

    ben.post(f'/dismiss-edit-alert/{family.group.id}/{scarf.id}')
    assert 'Updated since you claimed it' not in group_page(ben, family)


def test_only_the_claimer_can_dismiss(family, login, scarf):
    login(family.ben).post(f'/claim-item/{family.group.id}/{scarf.id}')
    edit(login(family.alice), family, scarf, item_name='Red scarf')

    login(family.carol).post(f'/dismiss-edit-alert/{family.group.id}/{scarf.id}')
    assert GiftList.get(family.group.id, scarf.id).edited_since_claim


def test_unclaiming_clears_the_alert(family, login, scarf):
    ben = login(family.ben)
    ben.post(f'/claim-item/{family.group.id}/{scarf.id}')
    edit(login(family.alice), family, scarf, item_name='Red scarf')
    ben.post(f'/unclaim-item/{family.group.id}/{scarf.id}')

    gift = GiftList.get(family.group.id, scarf.id)
    assert not gift.edited_since_claim and gift.edit_changes == []


def test_saving_without_changes_does_not_alert(family, login, scarf):
    login(family.ben).post(f'/claim-item/{family.group.id}/{scarf.id}')
    edit(login(family.alice), family, scarf, description='Navy\r\n')

    assert not GiftList.get(family.group.id, scarf.id).edited_since_claim


def test_repeated_edits_keep_the_original_value(family, login, scarf):
    login(family.ben).post(f'/claim-item/{family.group.id}/{scarf.id}')
    alice = login(family.alice)
    edit(alice, family, scarf, item_name='Red scarf')
    edit(alice, family, GiftList.get(family.group.id, scarf.id), item_name='Blue scarf')

    changes = GiftList.get(family.group.id, scarf.id).edit_changes
    assert changes == [{'field': 'item_name', 'old': 'Wool scarf', 'new': 'Blue scarf'}]


def test_changing_back_clears_the_alert(family, login, scarf):
    login(family.ben).post(f'/claim-item/{family.group.id}/{scarf.id}')
    alice = login(family.alice)
    edit(alice, family, scarf, item_name='Red scarf')
    edit(alice, family, GiftList.get(family.group.id, scarf.id), item_name='Wool scarf')

    gift = GiftList.get(family.group.id, scarf.id)
    assert not gift.edited_since_claim and gift.edit_changes == []
