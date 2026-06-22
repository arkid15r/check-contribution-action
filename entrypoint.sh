#!/bin/sh
set -e

cd /action

source .venv/bin/activate
exec python src/check_contribution_action/main.py "$@"
