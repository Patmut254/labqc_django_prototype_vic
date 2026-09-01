#!/bin/bash
# Vercel build step — set this as the project's "Build Command" (Project
# Settings > Build & Development Settings), or it runs automatically if
# Vercel detects it. It only prepares static files; it does NOT touch the
# database (see the SQLite note in README.md before deploying).
set -e
pip install -r requirements.txt
python manage.py collectstatic --noinput
