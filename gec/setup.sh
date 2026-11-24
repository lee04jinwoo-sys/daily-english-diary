#!/bin/bash
# One-time setup of the GECToR server venv (Python 3.12 via uv; about 1 GB with torch).
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null || { echo "uv is needed (brew install uv)"; exit 1; }
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
[[ -f verb-form-vocab.txt ]] || curl -fsSL -o verb-form-vocab.txt \
  https://raw.githubusercontent.com/grammarly/gector/master/data/verb-form-vocab.txt
echo "done: start with  gec/.venv/bin/python gec/server.py  (start.sh does it when gec/.venv exists)"
