from app.models import GiftList


def test_dashboard_lists_my_groups(family, login):
    page = login(family.ben).get('/dashboard').get_data(as_text=True)
    assert 'Family Christmas' in page


def test_list_owner_never_sees_claims(family, login):
    gift = GiftList.create(family.group.id, family.alice.id, 'Wool scarf')
    ben = login(family.ben)
    ben.post(f'/claim-item/{family.group.id}/{gift.id}')

    assert 'Claimed by you' in ben.get(f'/group/{family.group.id}').get_data(as_text=True)
    owner_page = login(family.alice).get(f'/my-list/{family.group.id}').get_data(as_text=True)
    assert 'Wool scarf' in owner_page
    assert 'Claimed' not in owner_page


def test_other_members_see_item_as_claimed(family, login):
    gift = GiftList.create(family.group.id, family.alice.id, 'Wool scarf')
    login(family.ben).post(f'/claim-item/{family.group.id}/{gift.id}')

    page = login(family.carol).get(f'/group/{family.group.id}').get_data(as_text=True)
    assert 'Claimed' in page
    assert 'Claimed by you' not in page
