FROM python:3.13.5-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

# Keep image validation lightweight. Runtime dependencies are validated by
# Python compilation; tests are not part of the production image build.
RUN python -m compileall -q app

CMD ["python", "-m", "app.bot.main"]
