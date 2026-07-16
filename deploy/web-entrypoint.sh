#!/usr/bin/env sh
set -eu

python3 /app/deploy/validate_env.py --current-environment
python3 -m flask --app web/wsgi.py db-init

exec gunicorn \
  --config /app/web/gunicorn.conf.py \
  --chdir /app/web \
  wsgi:app
