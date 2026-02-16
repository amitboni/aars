#!/usr/bin/env bash
# Render build script — install dependencies only
# Migrations and seeding happen at startup (render-start.sh)
set -o errexit

pip install --no-cache-dir .
