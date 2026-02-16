#!/usr/bin/env bash
# Render start script — run migrations, seed, then start server

echo "=== Starting AARS API ==="
echo "DATABASE_URL is set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'NO')"
echo "PORT: $PORT"

echo "--- Running database migrations ---"
if ! python -m alembic upgrade head 2>&1; then
  echo "WARNING: Migrations failed, continuing anyway..."
fi

echo "--- Seeding platform defaults ---"
if ! python scripts/seed_db.py 2>&1; then
  echo "WARNING: Default seeding failed, continuing..."
fi

echo "--- Seeding demo data ---"
if ! python scripts/seed_db.py --demo 2>&1; then
  echo "WARNING: Demo seeding failed, continuing..."
fi

echo "--- Starting uvicorn ---"
exec uvicorn api.app:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}"
