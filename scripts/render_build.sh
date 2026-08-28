#!/usr/bin/env bash
set -euo pipefail

# Render uses the Dockerfile for this service. Keep this script dependency-light
# for local/legacy use as well; PDF extraction is handled by PyMuPDF/pypdf.
python - <<'PY'
import sys
assert sys.version_info[:2] == (3, 13), f"Expected Python 3.13, got {sys.version}"
print("Python runtime:", sys.version)
PY

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python - <<'PY'
import pymupdf
import pypdf
print("PyMuPDF OK")
print(f"pypdf OK: {pypdf.__version__}")
PY
python -m compileall -q app
