#!/usr/bin/env bash
# Render start script — run migrations, seed, then start server
set -o errexit

echo "Running database migrations..."
alembic upgrade head

echo "Seeding platform defaults..."
python scripts/seed_db.py

echo "Seeding demo data..."
python scripts/seed_db.py --demo

echo "Starting server..."
exec uvicorn api.app:create_app --factory --host 0.0.0.0 --port "$PORT"
