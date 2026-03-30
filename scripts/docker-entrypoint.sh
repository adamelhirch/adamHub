#!/bin/sh
set -eu

RETRIES="${ADAMHUB_MIGRATION_RETRIES:-30}"
DELAY="${ADAMHUB_MIGRATION_DELAY:-2}"
ATTEMPT=1

while :; do
  if python -m alembic upgrade head; then
    break
  fi

  if [ "$ATTEMPT" -ge "$RETRIES" ]; then
    echo "AdamHUB migrations failed after ${RETRIES} attempts" >&2
    exit 1
  fi

  echo "Migration attempt ${ATTEMPT}/${RETRIES} failed, retrying in ${DELAY}s..." >&2
  ATTEMPT=$((ATTEMPT + 1))
  sleep "$DELAY"
done

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
