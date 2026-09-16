# syntax=docker/dockerfile:1.7

# Build native wheels and the virtual environment away from the runtime image.
FROM python:3.11-alpine3.24 AS dependency-builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache build-base libffi-dev

WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes --no-cache-dir -r requirements.txt \
    && /opt/venv/bin/pip uninstall -y pip setuptools wheel

# The final image contains runtime libraries and application code only. OCR is
# opt-in and is intentionally installed here because its executables are needed
# while jobs run, not while Python dependencies build.
FROM python:3.11-alpine3.24 AS runtime

ARG INSTALL_OCR=false

ENV PATH=/opt/venv/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates libffi \
    && if [ "$INSTALL_OCR" = "true" ]; then \
         apk add --no-cache poppler-utils tesseract-ocr tesseract-ocr-data-eng font-liberation; \
       fi

# Dependency installation is finished. Remove base-image build tools and their
# vendored libraries; application execution does not need a package installer.
RUN /usr/local/bin/python -m pip uninstall -y pip setuptools wheel

RUN addgroup -S -g 10001 app \
    && adduser -S -u 10001 -G app -h /nonexistent -H app

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
