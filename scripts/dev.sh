#!/usr/bin/env bash
# Run the app locally against the Firestore emulator, loaded with fake family data.
# Emulator data lives in memory, so every run starts from a fresh seed.
set -euo pipefail
cd "$(dirname "$0")/.."

export FIRESTORE_EMULATOR_HOST=127.0.0.1:8180
export GOOGLE_CLOUD_PROJECT=demo-giftster

# The emulator needs Java 21+. Fall back to one unpacked under ~/.jdks (see README).
if ! java -version >/dev/null 2>&1; then
  for java_home in ~/.jdks/*/Contents/Home ~/.jdks/*; do
    if [ -x "$java_home/bin/java" ]; then export PATH="$java_home/bin:$PATH"; break; fi
  done
fi

firebase emulators:start --only firestore --project "$GOOGLE_CLOUD_PROJECT" &
EMULATOR_PID=$!
trap 'kill $EMULATOR_PID 2>/dev/null' EXIT

echo "Waiting for the Firestore emulator..."
until curl -s "http://$FIRESTORE_EMULATOR_HOST" >/dev/null; do sleep 1; done

.venv/bin/python scripts/seed_local.py
.venv/bin/python run.py
