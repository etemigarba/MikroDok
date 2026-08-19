# MikroDok Dockerfile
# Multi-stage build for development and production

# =============================================================================
# Base Stage - Common dependencies
# =============================================================================
FROM nvidia/cuda:12.1-devel-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    python3-pip \
    git \
    curl \
    wget \
    ca-certificates \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r mikrodok --gid=1000 && \
    useradd -r -g mikrodok --uid=1000 --home-dir=/home/mikrodok --create-home mikrodok

# Set up Python
RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# =============================================================================
# Development Stage
# =============================================================================
FROM base AS development

# Install development dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt && pip install -r requirements-dev.txt

# Install additional dev tools
RUN pip install ipython ipdb jupyter notebook

# Set workdir
WORKDIR /workspace

# Copy source code
COPY --chown=mikrodok:mikrodok . .

# Switch to non-root user
USER mikrodok

# Default command
CMD ["bash"]

# =============================================================================
# Build Stage - Compile wheels for faster installs
# =============================================================================
FROM base AS builder

# Install build dependencies
RUN pip install build

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Build wheel
RUN python -m build --wheel --no-isolation

# =============================================================================
# Production Stage
# =============================================================================
FROM base AS production

# Copy built wheel from builder
COPY --from=builder /dist/*.whl /tmp/wheels/

# Install application
RUN pip install /tmp/wheels/mikrodok-*.whl && \
    rm -rf /tmp/wheels

# Create directories for data
RUN mkdir -p /data/models /data/documents /data/logs /data/cache && \
    chown -R mikrodok:mikrodok /data

# Switch to non-root user
USER mikrodok

# Set workdir
WORKDIR /home/mikrodok

# Expose ports (if needed for future web interface)
# EXPOSE 8000 8550

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import mikrodok; print('OK')" || exit 1

# Default command
ENTRYPOINT ["mikrodok"]
CMD ["--help"]

# =============================================================================
# GPU-enabled Production Stage
# =============================================================================
FROM production AS production-gpu

# This stage inherits from production but ensures GPU access
# Runtime will need --gpus all flag

# =============================================================================
# CI Stage - For running tests in CI
# =============================================================================
FROM development AS ci

# Install test dependencies
RUN pip install pytest pytest-cov pytest-xdist pytest-asyncio

# Run tests by default
CMD ["pytest", "tests/", "-v", "--tb=short", "-m", "not slow and not gpu", "-n", "auto"]

# =============================================================================
# Documentation Stage
# =============================================================================
FROM development AS docs

# Install documentation dependencies
RUN pip install sphinx sphinx-rtd-theme myst-parser sphinx-autodoc-typehints sphinx-copybutton sphinx-design

WORKDIR /workspace/docs

CMD ["sphinx-autobuild", "-b", "html", "--port", "8000", "--host", "0.0.0.0", ".", "_build/html"]