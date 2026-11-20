import pytest

import app.routes
from app import app as flask_app
from app.models import User, db
from app.utils import get_serializer


@pytest.fixture
def outbox(monkeypatch):
    """Capture reset emails instead of sending them"""
    sent = []
    monkeypatch.setattr(app.routes, 'send_reset_email', lambda to, url: sent.append((to, url)))
    return sent


@pytest.fixture
def admin(family):
    db.collection('users').document(family.alice.id).update({'is_admin': True})
    return family.alice


def token_email(url):
    with flask_app.app_context():
        return get_serializer().loads(url.rsplit('/', 1)[1], salt='password-reset-salt', max_age=3600)


def flash_after(client, response):
    return client.get(response.headers['Location']).get_data(as_text=True)


# The normal "Forgot password?" flow, which now shares the link helper

def test_forgot_password_emails_a_working_link(family, outbox):
    flask_app.test_client().post('/forgot-password', data={'email': 'ben@example.com'})

    [(to, url)] = outbox
    assert to == 'ben@example.com'
    assert '/reset-password/' in url and token_email(url) == 'ben@example.com'


def test_forgot_password_for_unknown_email_sends_nothing(family, outbox):
    response = flask_app.test_client().post('/forgot-password', data={'email': 'nobody@example.com'},
                                            follow_redirects=True)
    assert outbox == []
    assert 'If that email exists' in response.get_data(as_text=True)


# The admin button

def test_admin_can_send_someone_a_reset_email(family, login, admin, outbox):
    client = login(family.alice)
    response = client.post('/admin/send-reset', data={'email': 'ben@example.com'})

    [(to, url)] = outbox
    assert to == 'ben@example.com' and token_email(url) == 'ben@example.com'
    assert response.headers['Location'].endswith('/admin/stats#send-reset')
    assert 'Sent a password reset email to ben@example.com' in flash_after(client, response)


def test_admin_lookup_ignores_capitals_and_spaces(family, login, admin, outbox):
    User.create('Mum', 'Smith', 'Mum.Smith@Example.com', 'password123')
    login(family.alice).post('/admin/send-reset', data={'email': '  mum.smith@example.com '})

    [(to, url)] = outbox
    assert to == 'Mum.Smith@Example.com'   # sent to the address on the account, as stored
    assert token_email(url) == 'Mum.Smith@Example.com'


def test_admin_is_told_when_no_account_matches(family, login, admin, outbox):
    client = login(family.alice)
    response = client.post('/admin/send-reset', data={'email': 'nobody@example.com'})

    assert outbox == []
    assert 'No account uses nobody@example.com.' in flash_after(client, response)


def test_non_admins_cannot_send_reset_emails(family, login, outbox):
    response = login(family.ben).post('/admin/send-reset', data={'email': 'carol@example.com'})
    assert response.status_code == 404
    assert outbox == []


def test_stats_page_shows_the_reset_form_to_admins(family, login, admin):
    page = login(family.alice).get('/admin/stats').get_data(as_text=True)
    assert 'action="/admin/send-reset"' in page
