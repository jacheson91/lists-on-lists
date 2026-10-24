# lists-on-lists (Giftster)

A gift registry for the family. Create or join a group with a 6-character code, keep a wishlist for each group, and claim the gifts you're buying. List owners never see what's been claimed. Group creators can also draw a Secret Santa–style gift exchange.

Flask + Flask-Login, Firestore, deployed to Cloud Run. Password reset emails go through Resend.

## Running locally

You need Python 3.11, Node (for `firebase-tools`) and Java 21+ (for the Firestore emulator).

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
npm install -g firebase-tools
```

For Java, any JDK/JRE 21+ on your `PATH` works. Alternatively, unpack a [Temurin](https://adoptium.net/temurin/releases/?version=21) build into `~/.jdks/` and `dev.sh` will find it. (On older macOS versions, Homebrew's `openjdk` builds from source, so the download is much quicker.)

Then:

```bash
scripts/dev.sh
```

This starts the Firestore emulator (browse the data at http://127.0.0.1:4000), loads a fake family from [scripts/seed_local.py](scripts/seed_local.py) (the logins are listed at the top of that file), and runs the app at http://localhost:8080 with auto-reload.

- Emulator data lives in memory, so every run starts from a fresh seed.
- Password reset links are printed to the terminal instead of emailed.
- Nothing here can touch production. The seed script refuses to run without `FIRESTORE_EMULATOR_HOST`.

## Tests

With the emulator running (from `scripts/dev.sh`, or `firebase emulators:start --only firestore`):

```bash
.venv/bin/pytest
```

Tests use their own emulator project and wipe it before each test, so they don't disturb the dev seed data.

## Deploying

[cloudbuild.yaml](cloudbuild.yaml) builds the image and deploys [cloudrun.yaml](cloudrun.yaml) to Cloud Run (project `list-app-475800`, region `us-central1`). Production uses the Firestore database `giftster-db` and reads `RESEND_API_KEY` from Secret Manager.

## Code map

| Path | What's there |
|---|---|
| `app/routes.py` | Every page and form handler |
| `app/models.py` | Thin classes over Firestore (`User`, `Group`, `GiftList`) |
| `app/templates/` | Jinja templates; every page extends `base.html`, partials start with `_` |
| `app/static/styles.css` | All styles, including the mobile layout |
| `scripts/` | Local dev runner and seed data |
| `tests/` | pytest suite (runs against the emulator) |

## Data model (Firestore)

```
users/{uid}               first_name, last_name, email, password_hash
groups/{gid}              name, description, join_code, created_by, created_at, has_gift_exchange
  members/{uid}           joined_at
  gift_lists/{id}         user_id, item_name, description, link, is_claimed, claimer_id
  gift_exchanges/{id}     giver_id, receiver_id, created_at
```
