# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Faster, quieter, no .pyc clutter
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching
COPY pyproject.toml README.md LICENSE ./
COPY marktplaats_monitor ./marktplaats_monitor
RUN pip install --no-cache-dir .

# Run as a non-root user; /app/data is the SQLite/state volume
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

ENV CONFIG_FILE=/app/config.yaml \
    DB_PATH=/app/data/monitor.sqlite3

# Default: poll forever. Override with: docker run ... once|test|stats
ENTRYPOINT ["python", "-m", "marktplaats_monitor"]
CMD ["run"]
