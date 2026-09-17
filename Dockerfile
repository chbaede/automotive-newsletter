FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=Europe/Berlin \
    NEWSLETTER_TIMEZONE=Europe/Berlin \
    FORWARDED_ALLOW_IPS=127.0.0.1,::1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn==23.0.0

COPY automotive_newsletter ./automotive_newsletter

RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/data \
    && useradd -u 10001 -r -s /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app/data /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["sh", "-c", "exec gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 1 --timeout 120 --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1,::1}\" 'automotive_newsletter.web:create_app()'"]
