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

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["sh", "-c", "exec gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 1 --timeout 120 --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1,::1}\" 'automotive_newsletter.web:create_app()'"]
