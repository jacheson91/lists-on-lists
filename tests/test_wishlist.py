from app.models import Group, GiftList, PrivateItem


def text(response):
    return response.get_data(as_text=True)


def test_add_edit_and_delete_wishlist_items(family, login):
    alice = login(family.alice)
    alice.post('/wishlist', data={'item_name': 'Headphones', 'description': 'Noise cancelling', 'link': ''})
    [item] = PrivateItem.get_by_user(family.alice.id)
    assert 'Headphones' in text(alice.get('/wishlist'))

    alice.post(f'/wishlist/{item.id}/edit', data={'item_name': 'Headphones', 'description': 'Over-ear', 'link': ''})
    assert PrivateItem.get(family.alice.id, item.id).description == 'Over-ear'

    alice.post(f'/wishlist/{item.id}/delete')
    assert PrivateItem.get_by_user(family.alice.id) == []


def test_wishlist_is_private(family, login):
    PrivateItem.create(family.alice.id, 'Secret wish')

    assert 'Secret wish' not in text(login(family.ben).get('/wishlist'))
    assert 'Secret wish' not in text(login(family.ben).get(f'/group/{family.group.id}'))


def test_others_cannot_edit_or_delete_my_wishlist_items(family, login):
    item = PrivateItem.create(family.alice.id, 'Headphones')
    ben = login(family.ben)
    ben.post(f'/wishlist/{item.id}/edit', data={'item_name': 'Hacked', 'description': '', 'link': ''})
    ben.post(f'/wishlist/{item.id}/delete')

    assert PrivateItem.get(family.alice.id, item.id).item_name == 'Headphones'


def test_copy_to_group_shares_an_independent_copy(family, login):
    item = PrivateItem.create(family.alice.id, 'Headphones', 'Over-ear', 'https://example.com/h')
    alice = login(family.alice)
    response = alice.post('/wishlist/copy', data={'group_id': family.group.id, 'item_ids': [item.id]},
                          follow_redirects=True)
    assert 'Added 1 item to your list for Family Christmas.' in text(response)

    [gift] = GiftList.get_by_user(family.group.id, family.alice.id)
    assert (gift.item_name, gift.description, gift.link) == ('Headphones', 'Over-ear', 'https://example.com/h')
    assert 'Headphones' in text(login(family.ben).get(f'/group/{family.group.id}'))

    # Later changes to the wishlist item don't touch the copy
    alice.post(f'/wishlist/{item.id}/edit', data={'item_name': 'Earbuds', 'description': '', 'link': ''})
    assert GiftList.get(family.group.id, gift.id).item_name == 'Headphones'


def test_copying_twice_does_not_duplicate(family, login):
    item = PrivateItem.create(family.alice.id, 'Headphones')
    alice = login(family.alice)
    alice.post('/wishlist/copy', data={'group_id': family.group.id, 'item_ids': [item.id]})
    response = alice.post('/wishlist/copy', data={'group_id': family.group.id, 'item_ids': [item.id]},
                          follow_redirects=True)

    assert '1 was already there' in text(response)
    assert len(GiftList.get_by_user(family.group.id, family.alice.id)) == 1


def test_cannot_copy_into_a_group_you_are_not_in(family, login):
    item = PrivateItem.create(family.alice.id, 'Headphones')
    other_group = Group.create('Work Secret Santa', '', family.ben.id)

    login(family.alice).post('/wishlist/copy', data={'group_id': other_group.id, 'item_ids': [item.id]})
    assert GiftList.get_by_user(other_group.id, family.alice.id) == []


def test_wishlist_shows_where_items_were_copied(family, login):
    PrivateItem.create(family.alice.id, 'Headphones').copy_to_group(family.group.id)
    PrivateItem.create(family.alice.id, 'Pottery class')

    page = text(login(family.alice).get('/wishlist'))
    assert page.count('On your list for Family Christmas') == 1


def test_group_lists_keep_the_order_items_were_added(family, login):
    for name in ['First', 'Second', 'Third', 'Fourth']:
        GiftList.create(family.group.id, family.alice.id, name)

    names = [gift.item_name for gift in GiftList.get_by_user(family.group.id, family.alice.id)]
    assert names == ['First', 'Second', 'Third', 'Fourth']


def test_my_list_offers_only_uncopied_wishlist_items(family, login):
    headphones = PrivateItem.create(family.alice.id, 'Headphones')
    PrivateItem.create(family.alice.id, 'Pottery class')
    headphones.copy_to_group(family.group.id)

    page = text(login(family.alice).get(f'/my-list/{family.group.id}'))
    picker = page.split('Add from my wishlist')[1].split('</details>')[0]
    assert 'Pottery class' in picker
    assert 'Headphones' not in picker
