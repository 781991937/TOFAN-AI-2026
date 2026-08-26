FROM python:3.13.5-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# pdftotext is a native Poppler binding. Install its OS dependencies
# inside the image so Render does not need apt access in its native runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpoppler-cpp-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

# Fail the image build before deployment if the Python/PDF stack is broken.
RUN python -c "import pdftotext, fitz, pypdf; print('PDF stack OK')" \
    && python -m compileall -q app \
    && python -m pytest -q tests/test_runtime_smoke.py

CMD ["python", "-m", "app.bot.main"]
