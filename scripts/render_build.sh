#!/usr/bin/env bash
set -euo pipefail

# This script is intentionally portable: it must work in Render's build
# environment without assuming apt/root access. Native PDF dependencies are
# installed by Dockerfile when the service uses the Docker runtime.

python - <<'PY'
import sys
assert sys.version_info[:2] == (3, 13), f"Expected Python 3.13, got {sys.version}"
print("Python runtime:", sys.version)
PY

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Verify the supported PDF APIs. Do not use the deprecated `fitz` import.
python - <<'PY'
import pymupdf
import pdftotext
import pypdf

print(f"PyMuPDF OK: {pymupdf.__doc__.splitlines()[0] if pymupdf.__doc__ else 'loaded'}")
print(f"pdftotext OK: {pdftotext.__file__}")
print(f"pypdf OK: {pypdf.__version__}")
PY

python -m compileall -q app
python -m pytest -q
