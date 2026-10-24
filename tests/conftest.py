import os
import urllib.request
from types import SimpleNamespace

import pytest

# Always use the emulator, in a separate project from the dev seed data so tests never wipe it
os.environ.setdefault('FIRESTORE_EMULATOR_HOST', '127.0.0.1:8180')
os.environ['GOOGLE_CLOUD_PROJECT'] = 'demo-giftster-test'

from app import app as flask_app  # noqa: E402
from app.models import User, Group  # noqa: E402

EMULATOR = os.environ['FIRESTORE_EMULATOR_HOST']
DATABASE = os.environ.get('FIRESTORE_DATABASE', 'giftster-db')
PASSWORD = 'password123'

try:
    urllib.request.urlopen(f'http://{EMULATOR}', timeout=2)
except OSError:
    pytest.exit(f'Firestore emulator is not running on {EMULATOR}. Start it with scripts/dev.sh (see README).')


@pytest.fixture(autouse=True)
def clean_db():
    url = f'http://{EMULATOR}/emulator/v1/projects/demo-giftster-test/databases/{DATABASE}/documents'
    urllib.request.urlopen(urllib.request.Request(url, method='DELETE'))


@pytest.fixture
def login():
    """Return a test client logged in as the given user."""
    def _login(user):
        client = flask_app.test_client()
        client.post('/login', data={'email': user.email, 'password': PASSWORD})
        return client
    return _login


@pytest.fixture
def family():
    """Alice (group creator), Ben and Carol, all in one group."""
    alice = User.create('Alice', 'Smith', 'alice@example.com', PASSWORD)
    ben = User.create('Ben', 'Smith', 'ben@example.com', PASSWORD)
    carol = User.create('Carol', 'Jones', 'carol@example.com', PASSWORD)
    group = Group.create('Family Christmas', '', alice.id)
    group.add_member(ben.id)
    group.add_member(carol.id)
    return SimpleNamespace(alice=alice, ben=ben, carol=carol, group=group)
