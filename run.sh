#!/usr/bin/env bash
set -e
if [ ! -d ".venv" ]; then python -m venv .venv; fi
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
