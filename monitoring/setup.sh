#!/usr/bin/env bash
# Create (or update) the counters and the "Giftster" dashboard in Google Cloud Monitoring.
# Safe to rerun. The counters are built from Cloud Run's request logs, so they only count from
# the moment they're created; the app's /admin/stats page has all-time totals.
set -euo pipefail
cd "$(dirname "$0")"

PROJECT=list-app-475800
SERVICE='resource.type="cloud_run_revision" AND resource.labels.service_name="lists-on-lists"'

# name | description | which requests count (a successful sign-up or group creation redirects, so 302)
metric() {
  if gcloud logging metrics describe "$1" --project "$PROJECT" >/dev/null 2>&1; then
    gcloud logging metrics update "$1" --project "$PROJECT" --description "$2" --log-filter "$3"
  else
    gcloud logging metrics create "$1" --project "$PROJECT" --description "$2" --log-filter "$3"
  fi
}
metric giftster_signups "Successful sign-ups" \
  "$SERVICE AND httpRequest.requestMethod=\"POST\" AND httpRequest.requestUrl:\"/register\" AND httpRequest.status=302"
metric giftster_groups_created "Groups created" \
  "$SERVICE AND httpRequest.requestMethod=\"POST\" AND httpRequest.requestUrl:\"/create-group\" AND httpRequest.status=302"
metric giftster_password_reset_requests "Password reset emails requested" \
  "$SERVICE AND httpRequest.requestMethod=\"POST\" AND httpRequest.requestUrl:\"/forgot-password\""

existing=$(gcloud monitoring dashboards list --project "$PROJECT" --filter='displayName="Giftster"' --format='value(name)')
if [ -n "$existing" ]; then
  echo "Dashboard already exists: $existing (delete it in the console to recreate from dashboard.json)"
else
  gcloud monitoring dashboards create --project "$PROJECT" --config-from-file=dashboard.json
fi
