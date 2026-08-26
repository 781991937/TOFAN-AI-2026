#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# pdftotext is a native Poppler binding, so Render needs its Linux build
# dependencies before pip installs the Python package.
apt-get update
apt-get install -y --no-install-recommends \
  build-essential \
  libpoppler-cpp-dev \
  pkg-config \
  python3-dev
rm -rf /var/lib/apt/lists/*

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Fail the deploy during build if the native PDF stack is unavailable.
python - <<'PY'
import fitz
import pdftotext
import pypdf

print(f"PyMuPDF OK: {fitz.__doc__.splitlines()[0] if fitz.__doc__ else 'loaded'}")
print(f"pdftotext OK: {pdftotext.__file__}")
print(f"pypdf OK: {pypdf.__version__}")
PY

# Catch syntax/import problems before Render starts the service.
python -m compileall -q app
python -m pytest -q tests/test_runtime_smoke.py
