#!/usr/bin/env bash
# Render build script — runs migrations and seeds platform defaults
set -o errexit

pip install --no-cache-dir .

# Run database migrations
alembic upgrade head

# Seed platform defaults (idempotent)
python scripts/seed_db.py

# Seed demo data for testing (idempotent)
python scripts/seed_db.py --demo
