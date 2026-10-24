from app.models import Group, User


def text(response):
    return response.get_data(as_text=True)


def test_saving_likes_and_dislikes(family, login):
    response = login(family.alice).post('/likes', data={'likes': ' Earl Grey ', 'dislikes': 'Glitter\r\n',
                                                        'next': '/wishlist'}, follow_redirects=True)

    assert 'Your likes and dislikes have been saved.' in text(response)
    alice = User.get(family.alice.id)
    assert (alice.likes, alice.dislikes) == ('Earl Grey', 'Glitter')


def test_group_members_see_likes(family, login):
    family.alice.update_likes('Earl Grey', 'Glitter')

    page = text(login(family.ben).get(f'/group/{family.group.id}'))
    assert 'Earl Grey' in page and 'Glitter' in page


def test_likes_show_in_every_group(family, login):
    family.alice.update_likes('Earl Grey', '')
    other = Group.create('Cousins', '', family.carol.id)
    other.add_member(family.alice.id)

    assert 'Earl Grey' in text(login(family.carol).get(f'/group/{other.id}'))


def test_gift_exchange_banner_shows_your_match_likes(family, login):
    family.ben.update_likes('Cycling gear', 'Novelty socks')
    family.group.start_gift_exchange([(family.alice.id, family.ben.id),
                                      (family.ben.id, family.carol.id),
                                      (family.carol.id, family.alice.id)])

    page = text(login(family.alice).get(f'/group/{family.group.id}'))
    banner = page.split('gift-exchange-banner')[1].split('Member Gift Lists')[0]
    assert 'Cycling gear' in banner and 'Novelty socks' in banner


def test_owner_sees_what_the_group_sees(family, login):
    family.alice.update_likes('Earl Grey', '')
    assert 'Earl Grey' in text(login(family.alice).get(f'/my-list/{family.group.id}'))


def test_no_likes_box_when_empty(family, login):
    page = text(login(family.ben).get(f'/group/{family.group.id}'))
    assert 'likes-box' not in page


def test_redirect_stays_on_site(family, login):
    response = login(family.alice).post('/likes', data={'likes': '', 'dislikes': '',
                                                        'next': 'https://example.com/'})
    assert response.headers['Location'] == '/wishlist'
