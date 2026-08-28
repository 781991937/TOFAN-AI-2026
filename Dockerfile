FROM python:3.13.5-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Native dependencies required by pdftotext.
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

# Validate the PDF stack and application before Render starts the service.
RUN python -c "import pdftotext, pymupdf, pypdf; print('PDF stack OK')" \
    && python -m compileall -q app \
    && python -m pytest -q tests/test_runtime_smoke.py

CMD ["python", "-m", "app.bot.main"]
