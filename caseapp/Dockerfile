# Multi-stage build for Python backend
FROM python:3.11-slim AS backend-base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and clean up in single layer
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libfontconfig1 \
    libxrender1 \
    libgl1-mesa-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy backend code to the app root (not in a subdirectory)
COPY backend/ ./

# Ensure __init__.py files exist in all packages (critical for Python imports)
RUN touch ./services/__init__.py ./core/__init__.py || true

# Create shared directory if it doesn't exist
RUN mkdir -p ./shared

# Create non-root user for security (after file operations)
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

# Command to run the application (now main.py is directly in /app)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Frontend build stage
FROM nginx:alpine AS frontend

# Create a minimal frontend
RUN echo '<!DOCTYPE html>' > /usr/share/nginx/html/index.html && \
    echo '<html><head><title>Court Case Management</title></head>' >> /usr/share/nginx/html/index.html && \
    echo '<body><h1>Court Case Management System</h1>' >> /usr/share/nginx/html/index.html && \
    echo '<p>Backend API available at <a href="/api/v1/">/api/v1/</a></p>' >> /usr/share/nginx/html/index.html && \
    echo '<p>API Documentation at <a href="/docs">/docs</a></p>' >> /usr/share/nginx/html/index.html && \
    echo '</body></html>' >> /usr/share/nginx/html/index.html

COPY nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

# Media processing service
FROM python:3.11-slim AS media-processor

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install FFmpeg and media processing tools
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavcodec-extra \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install BOTH core dependencies and media processing dependencies
# Core dependencies needed for models, schemas, services, core modules
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Media-specific dependencies
COPY requirements-media.txt .
RUN pip install --no-cache-dir -r requirements-media.txt

# Copy required modules maintaining proper structure
COPY backend/services/ ./services/
COPY backend/core/ ./core/
COPY backend/models/ ./models/
COPY backend/schemas/ ./schemas/

# Ensure __init__.py files exist in all packages
RUN touch ./services/__init__.py ./core/__init__.py ./models/__init__.py ./schemas/__init__.py || true

CMD ["python", "-m", "services.media_processing_service"]