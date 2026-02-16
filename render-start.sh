#!/usr/bin/env bash
# Render start script — run migrations, seed, then start server

echo "=== Starting AARS API ==="
echo "DATABASE_URL is set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'NO')"
echo "PORT: $PORT"

echo "--- Running database migrations ---"
python -m alembic upgrade head
MIGRATE_EXIT=$?
if [ $MIGRATE_EXIT -ne 0 ]; then
  echo "!!! MIGRATIONS FAILED with exit code $MIGRATE_EXIT !!!"
  python -m alembic current || true
else
  echo "--- Migrations completed successfully ---"
  python -m alembic current || true
fi

echo "--- Seeding platform defaults ---"
python scripts/seed_db.py || echo "WARNING: Default seeding failed, continuing..."

echo "--- Seeding demo data ---"
python scripts/seed_db.py --demo || echo "WARNING: Demo seeding failed, continuing..."

echo "--- Starting uvicorn ---"
exec uvicorn api.app:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}"
