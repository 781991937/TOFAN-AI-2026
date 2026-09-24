# Deployment Guide

TOFAN Smart Academy is a FastAPI application that serves the web application from the same process. The project is designed to run on any hosting provider that can run Docker or Python and expose an HTTP port.

## 1. Docker deployment

Build and run:

```bash
docker build -t tofan-smart-academy .
docker run --rm -p 8000:8000 --env-file .env tofan-smart-academy
```

The container listens on `0.0.0.0` and uses `PORT` when supplied by the hosting provider.

## 2. Python deployment

Use Python 3.12+.

```bash
python -m pip install -r requirements.txt
python -m compileall -q app
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

For a managed platform, configure its start command to run the same Uvicorn command and expose the provider-assigned port.

## 3. Production database

Set:

```text
TOFAN_ENV=production
DATABASE_URL=postgresql+psycopg://...
```

Production does not permit SQLite.

## 4. Object storage

Set:

```text
TOFAN_STORAGE_BACKEND=s3
TOFAN_S3_BUCKET=...
TOFAN_S3_REGION=...
TOFAN_S3_ENDPOINT_URL=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

The S3-compatible layer supports AWS S3, Cloudflare R2, MinIO, and compatible providers. Keep credentials in the hosting provider's secret/environment-variable store.

## 5. Authentication and Passkeys

Set a strong secret:

```text
AUTH_OTP_PEPPER=...
```

Production WebAuthn configuration is explicit and provider-neutral:

```text
WEBAUTHN_RP_ID=academy.example.com
WEBAUTHN_ORIGIN=https://academy.example.com
```

Both variables are required when `TOFAN_ENV=production`. Do not rely on provider-specific hostname variables.

## 6. AI provider

Keep the OpenAI API key server-side:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

Never put the key in frontend JavaScript or commit it to Git.

## 7. Health check

Configure the hosting provider's HTTP health check to:

```text
GET /health
```

The endpoint verifies application/database connectivity.

## 8. HTTPS and domain

Passkeys require the deployment's public origin to match `WEBAUTHN_ORIGIN`. In production, use the public HTTPS origin and set `WEBAUTHN_RP_ID` to its hostname.

## 9. Render

`render.yaml` is retained only as an optional Render deployment adapter. The application itself does not depend on Render-specific environment variables. On Render, configure the required production WebAuthn variables explicitly.

## 10. Other hosting providers

For any Docker/Python provider, the essential contract is:

- build/install dependencies from `requirements.txt`
- start `uvicorn app.main:app --host 0.0.0.0 --port <provider-port>`
- provide PostgreSQL in production
- provide S3-compatible storage in production
- provide the required secrets through environment variables
- expose `/health` as the health check

No provider-specific SDK or deployment service is required by the application runtime.
