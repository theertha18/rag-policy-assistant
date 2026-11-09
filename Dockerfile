FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FASTEMBED_CACHE_PATH=/models

WORKDIR /app

# 0. Security patches: Debian updates (fixes zlib) and current Python packaging tools
#    (a newer setuptools also replaces its bundled copies of wheel and jaraco.context)
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 1. Libraries first: this layer is cached and only rebuilt when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Models next: also cached, rebuilt only if the model names in config.py change
COPY app/__init__.py app/config.py app/
COPY scripts/download_models.py scripts/
RUN python scripts/download_models.py

# 3. Application code and data last: these change most often
COPY app ./app
COPY data ./data

# 4. Run as a normal user, not as root
RUN useradd --create-home appuser && chown -R appuser /app /models
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]