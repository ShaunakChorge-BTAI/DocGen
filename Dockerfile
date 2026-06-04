# =============================================================================
#  DBAnalyser — Dockerfile
# =============================================================================
#  Multi-stage build:
#    builder — installs Python dependencies in a virtual environment
#    runtime — lean production image with the pre-built venv
#
#  Build:
#    docker build -t dbanalyser:2.0.0 .
#
#  Run API server:
#    docker run -p 8000:8000 \
#      -e DBANALYSER_POSTGRES_HOST=postgres \
#      -e DBANALYSER_POSTGRES_PASSWORD=secret \
#      dbanalyser:2.0.0
#
#  Run dashboard:
#    docker run -p 8501:8501 dbanalyser:2.0.0 dashboard --port 8501 --no-browser
# =============================================================================

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System packages required for psycopg2 + pyodbc headers
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first (Docker cache layer)
COPY pyproject.toml ./
COPY dbanalyser/__init__.py ./dbanalyser/__init__.py

# Create virtual environment and install
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install -e ".[auth]" --no-cache-dir || \
    pip install -e "." --no-cache-dir


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="LTFS Technology <tech@ltfs.com>"
LABEL version="2.0.0"
LABEL description="DBAnalyser — Enterprise SQL Server code quality analyser"

# Runtime system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        unixodbc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
WORKDIR /app
COPY . /app

# Create non-root user
RUN useradd -m -u 1000 dbanalyser && chown -R dbanalyser:dbanalyser /app
USER dbanalyser

# Output directory
RUN mkdir -p /app/output /app/custom_rules

# ── Runtime configuration ─────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default config path (can be overridden with -e DBANALYSER_CONFIG_PATH=...)
ENV DBANALYSER_CONFIG_PATH=/app/analysis_config.yaml

# PostgreSQL credentials (override via -e or docker-compose environment)
ENV DBANALYSER_POSTGRES_HOST=postgres
ENV DBANALYSER_POSTGRES_PORT=5432
ENV DBANALYSER_POSTGRES_DATABASE=dbanalyser
ENV DBANALYSER_POSTGRES_USER=dbanalyser_user
ENV DBANALYSER_POSTGRES_PASSWORD=""
ENV DBANALYSER_API_API_KEY=""

# ── Ports ─────────────────────────────────────────────────────────────────────
EXPOSE 8000
# API server
EXPOSE 8501
# Streamlit dashboard

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Default command: API server ───────────────────────────────────────────────
CMD ["dbanalyser", "api", "--host", "0.0.0.0", "--port", "8000"]
