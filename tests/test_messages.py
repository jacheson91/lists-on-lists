import pytest

from app.models import Group, GiftList, Message, User


def text(response):
    return response.get_data(as_text=True)


@pytest.fixture
def scarf(family):
    return GiftList.create(family.group.id, family.alice.id, 'Wool scarf')


def post(client, family, gift, message, kind=None):
    data = {'text': message}
    if kind:
        data['kind'] = kind
    return client.post(f'/message/{family.group.id}/{gift.id}', data=data, follow_redirects=True)


def owner_page(login, family):
    return text(login(family.alice).get(f'/my-list/{family.group.id}'))


def member_page(login, family, user):
    return text(login(user).get(f'/group/{family.group.id}'))


# Hidden comments

def test_hidden_comment_is_seen_signed_by_other_members(family, login, scarf):
    post(login(family.ben), family, scarf, 'Carol, want to go halves?', 'comment')

    page = member_page(login, family, family.carol)
    assert 'Carol, want to go halves?' in page
    assert '<strong>Ben</strong>' in page
    assert 'hidden from Alice' in page


def test_hidden_comment_never_reaches_the_owner(family, login, scarf):
    post(login(family.ben), family, scarf, 'Carol, want to go halves?', 'comment')

    page = owner_page(login, family)
    assert 'go halves' not in page
    assert 'Add a note' in page          # thread shows as empty, so not even the count leaks
    assert 'hidden from' not in page


# Anonymous messages

def test_anonymous_message_is_seen_by_the_owner_without_a_name(family, login, scarf):
    post(login(family.ben), family, scarf, 'Long or short?', 'anonymous')

    page = owner_page(login, family)
    assert 'Long or short?' in page
    assert '<strong>Anonymous</strong>' in page
    assert 'Ben' not in page and family.ben.id not in page


def test_anonymous_message_is_unsigned_for_other_members_too(family, login, scarf):
    post(login(family.ben), family, scarf, 'Long or short?', 'anonymous')

    page = member_page(login, family, family.carol)
    assert 'Long or short?' in page
    assert '<strong>Anonymous</strong>' in page
    thread = page.split('Long or short?')[0].rsplit('<li class="message', 1)[1]
    assert 'Ben' not in thread


def test_anonymous_author_sees_it_is_theirs(family, login, scarf):
    post(login(family.ben), family, scarf, 'Long or short?', 'anonymous')
    assert 'Anonymous (you)' in member_page(login, family, family.ben)


# Owner replies

def test_owner_reply_is_seen_signed_by_everyone(family, login, scarf):
    post(login(family.alice), family, scarf, 'Long please!')

    assert 'Long please!' in owner_page(login, family)
    page = member_page(login, family, family.ben)
    assert 'Long please!' in page
    assert '<strong>Alice</strong>' in page and 'list owner' in page


def test_owner_can_only_reply_on_their_own_items(family, login, scarf):
    post(login(family.alice), family, scarf, 'Sneaky', 'comment')
    [message] = Message.threads_for(family.group.id, family.ben.id, [scarf])[scarf.id]
    assert message.kind == 'reply'


def test_members_cannot_post_replies(family, login, scarf):
    response = post(login(family.ben), family, scarf, 'Pretending to be Alice', 'reply')
    assert 'Choose who can see your message.' in text(response)
    assert Message.threads_for(family.group.id, family.ben.id, [scarf])[scarf.id] == []


def test_non_members_cannot_post(family, login, scarf):
    outsider = User.create('Olive', 'Other', 'olive@example.com', 'password123')
    Group.create('Elsewhere', '', outsider.id)

    post(login(outsider), family, scarf, 'Hello', 'comment')
    assert Message.threads_for(family.group.id, family.ben.id, [scarf])[scarf.id] == []


def test_empty_messages_are_ignored(family, login, scarf):
    post(login(family.ben), family, scarf, '   ', 'comment')
    assert Message.threads_for(family.group.id, family.ben.id, [scarf])[scarf.id] == []


# Deleting

def test_authors_can_delete_their_messages(family, login, scarf):
    message = Message.create(family.group.id, scarf.id, family.ben.id, 'comment', 'Oops')
    login(family.ben).post(f'/delete-message/{family.group.id}/{message.id}')
    assert Message.get(family.group.id, message.id) is None


def test_others_cannot_delete_messages(family, login, scarf):
    message = Message.create(family.group.id, scarf.id, family.ben.id, 'anonymous', 'Mine')
    login(family.alice).post(f'/delete-message/{family.group.id}/{message.id}')
    login(family.carol).post(f'/delete-message/{family.group.id}/{message.id}')
    assert Message.get(family.group.id, message.id) is not None


def test_deleting_an_item_deletes_its_messages(family, login, scarf):
    message = Message.create(family.group.id, scarf.id, family.ben.id, 'comment', 'Halves?')
    login(family.alice).post(f'/delete-item/{family.group.id}/{scarf.id}')
    assert Message.get(family.group.id, message.id) is None


# Threads

def test_thread_opens_after_posting(family, login, scarf):
    response = post(login(family.ben), family, scarf, 'Hi', 'comment')
    assert '<details class="thread" open>' in text(response)


def test_messages_are_shown_oldest_first(family, login, scarf):
    for message in ['First', 'Second', 'Third']:
        Message.create(family.group.id, scarf.id, family.ben.id, 'comment', message)

    page = member_page(login, family, family.carol)
    assert page.index('First') < page.index('Second') < page.index('Third')


def test_messages_stay_on_their_own_item(family, login, scarf):
    socks = GiftList.create(family.group.id, family.ben.id, 'Socks')
    Message.create(family.group.id, socks.id, family.carol.id, 'anonymous', 'What size?')

    assert 'What size?' not in owner_page(login, family)
