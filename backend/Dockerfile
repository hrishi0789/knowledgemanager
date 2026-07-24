FROM python:3.11-slim

# System dependencies: Tesseract OCR + libmagic + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libmagic1 \
    libpq-dev \
    gcc \
    g++ \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifest first for layer caching
COPY pyproject.toml ./

# Install Python dependencies (CPU torch wheel to keep image lean)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -e "."

# Download spaCy model at build time so workers start immediately
RUN python -m spacy download en_core_web_sm

COPY . .

# Create data directories
RUN mkdir -p /app/data/chroma /app/data/documents

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

CMD ["supervisord", "-c", "/app/supervisord.conf"]
