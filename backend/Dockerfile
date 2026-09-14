# ===========================================
# Dockerfile for Flashcard Generator Backend
# ===========================================
# This creates a production-ready container for the FastAPI backend.
#
# Build: docker build -t flashcard-backend .
# Run:   docker run -p 8000:8000 flashcard-backend

# Use Python 3.11 slim image (smaller than full image)
FROM python:3.11-slim

ARG INSTALL_OCR=false

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
# - gcc: Required for some Python packages
# - libpq-dev: Required for psycopg2/asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# OCR remains opt-in because Poppler and Tesseract increase image size and CPU
# requirements. Build with --build-arg INSTALL_OCR=true when PDF_OCR_ENABLED is
# enabled for the worker.
RUN if [ "$INSTALL_OCR" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr && \
      rm -rf /var/lib/apt/lists/*; \
    fi

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
# --host 0.0.0.0: Listen on all interfaces (required for Docker)
# --port 8000: Port to listen on
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
