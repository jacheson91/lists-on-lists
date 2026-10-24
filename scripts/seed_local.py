"""Wipe the local Firestore emulator and load a fake family into it.

Refuses to run unless FIRESTORE_EMULATOR_HOST is set, so it can never touch production.

Every account's password is SEED_PASSWORD:
    alice@example.com  Alice Smith  - created "Smith Family Christmas"
    ben@example.com    Ben Smith
    carol@example.com  Carol Jones  - created "Cousins Secret Santa" (exchange already drawn)
    dan@example.com    Dan Jones
    erin@example.com   Erin Smith
"""
import os
import sys
import urllib.request

if not os.environ.get('FIRESTORE_EMULATOR_HOST'):
    sys.exit('FIRESTORE_EMULATOR_HOST is not set; refusing to seed (this would write to production).')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app.models import db, User, Group, GiftList, PrivateItem, Message  # noqa: E402

SEED_PASSWORD = 'password123'


def clear_emulator():
    database = os.environ.get('FIRESTORE_DATABASE', 'giftster-db')
    url = (f"http://{os.environ['FIRESTORE_EMULATOR_HOST']}/emulator/v1/projects/"
           f"{db.project}/databases/{database}/documents")
    urllib.request.urlopen(urllib.request.Request(url, method='DELETE'))


def seed():
    clear_emulator()

    users = {}
    for first, last in [('Alice', 'Smith'), ('Ben', 'Smith'), ('Carol', 'Jones'),
                        ('Dan', 'Jones'), ('Erin', 'Smith')]:
        users[first] = User.create(first, last, f'{first.lower()}@example.com', SEED_PASSWORD)

    # Dan is left blank to show how a member without likes/dislikes looks
    users['Alice'].update_likes('Earl Grey, mystery novels, anything green', 'Glitter')
    users['Ben'].update_likes('Coffee, cycling gear, hot sauce', 'Novelty socks')
    users['Carol'].update_likes('Dark chocolate, crosswords, anything lavender', 'Mugs, scented candles')
    users['Erin'].update_likes('Cats, watercolours, cosy things', '')

    family = Group.create('Smith Family Christmas', 'Presents under the tree at Grandma\'s',
                          users['Alice'].id)
    for name in ['Ben', 'Carol', 'Dan', 'Erin']:
        family.add_member(users[name].id)

    # (owner, item name, description, link, claimed by)
    family_items = [
        ('Alice', 'Wool scarf', 'Dark green or navy, nothing itchy', 'https://example.com/scarf', 'Ben'),
        ('Alice', 'The Thursday Murder Club', 'Paperback is fine', '', None),
        ('Ben', 'Bike lights', 'USB rechargeable, front and back', 'https://example.com/lights', 'Alice'),
        ('Ben', 'Hot sauce sampler', '', '', 'Erin'),
        ('Ben', 'Running socks', 'Size L', '', None),
        ('Carol', 'Jigsaw puzzle', '1000 pieces, landscapes please', '', None),
        ('Carol', 'Herb garden kit', '', 'https://example.com/herbs', 'Alice'),
        ('Dan', 'Board game: Wingspan', '', 'https://example.com/wingspan', None),
        ('Erin', 'Fuzzy slippers', 'Size 6', '', 'Dan'),
        ('Erin', 'Watercolour set', 'For a beginner', 'https://example.com/paints', None),
    ]
    gifts = {}
    for owner, name, description, link, claimer in family_items:
        gift = GiftList.create(family.id, users[owner].id, name, description, link)
        if claimer:
            gift.claim(users[claimer].id)
        gifts[name] = gift

    # Alice's private wishlist; one item has already been copied into the family group
    wishlist = {name: PrivateItem.create(users['Alice'].id, name, description, link)
                for name, description, link in [
                    ('Pottery class voucher', '', 'https://example.com/pottery'),
                    ('Noise-cancelling headphones', 'Over-ear, not earbuds', 'https://example.com/headphones'),
                    ('Cast iron skillet', '10 inch', ''),
                    ('Kindle gift card', '', ''),
                ]}
    wishlist['Pottery class voucher'].copy_to_group(family.id)

    # Ben changes something Alice already claimed, so Alice sees the "updated" notice
    gifts['Bike lights'].edit('Bike lights', 'USB-C rechargeable, front and back, 100+ lumens',
                              'https://example.com/brighter-lights')

    # Message threads showing all three kinds. Logged in as Alice you'll see her anonymous
    # question to Ben and the comments on Carol's puzzle, plus Erin's anonymous question and
    # your reply on the scarf, but never Ben and Carol's comments about going halves on it.
    for item, author, kind, text in [
        ('Wool scarf', 'Ben', 'comment', "I've claimed this. Carol, want to go halves?"),
        ('Wool scarf', 'Carol', 'comment', "Yes! I'll send you £15"),
        ('Wool scarf', 'Erin', 'anonymous', 'Do you prefer long or short scarves?'),
        ('Wool scarf', 'Alice', 'reply', 'Long please, the longer the better!'),
        ('Running socks', 'Alice', 'anonymous', 'Any brand you like best?'),
        ('Running socks', 'Ben', 'reply', 'Anything cushioned, thanks!'),
        ('Jigsaw puzzle', 'Dan', 'comment', 'There was a great Lake District one at the market'),
    ]:
        Message.create(family.id, gifts[item].id, users[author].id, kind, text)

    cousins = Group.create('Cousins Secret Santa', '£20 limit', users['Carol'].id)
    for name in ['Dan', 'Erin', 'Alice']:
        cousins.add_member(users[name].id)
    for owner, name in [('Alice', 'Fancy tea'), ('Dan', 'Socks with dogs on'),
                        ('Erin', 'Bath bombs'), ('Carol', 'Sourdough starter kit')]:
        GiftList.create(cousins.id, users[owner].id, name)
    draw = [('Carol', 'Dan'), ('Dan', 'Erin'), ('Erin', 'Alice'), ('Alice', 'Carol')]
    cousins.start_gift_exchange([(users[g].id, users[r].id) for g, r in draw])

    print(f'Seeded {len(users)} users and 2 groups. Log in as alice@example.com (password in this file).')


if __name__ == '__main__':
    seed()
