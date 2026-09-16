# syntax=docker/dockerfile:1.7

# Build native wheels and the virtual environment away from the runtime image.
FROM python:3.11-slim-bookworm AS dependency-builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes --no-cache-dir -r requirements.txt

# The final image contains runtime libraries and application code only. OCR is
# opt-in and is intentionally installed here because its executables are needed
# while jobs run, not while Python dependencies build.
FROM python:3.11-slim-bookworm AS runtime

ARG INSTALL_OCR=false

ENV PATH=/opt/venv/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && if [ "$INSTALL_OCR" = "true" ]; then \
         apt-get install -y --no-install-recommends poppler-utils tesseract-ocr; \
       fi \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /nonexistent --no-create-home app

COPY --from=dependency-builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app

USER app
EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=5 \
    CMD python -m app.healthcheck || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
