import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from automotive_newsletter.config import Settings, _read_secret, load_settings
from automotive_newsletter.logging import StructuredLogger
from automotive_newsletter.models import Article, CollectionMetrics
from automotive_newsletter.store import NewsletterStore
from automotive_newsletter.web import create_app


def test_admin_auth_headers_and_query_param_rejection(tmp_path):
    store = NewsletterStore(tmp_path / "test.db")
    settings = Settings(db_path=tmp_path / "test.db", admin_key="prod-secret-999")
    app = create_app(store=store, settings=settings)
    client = TestClient(app)

    # 1. No auth -> 401
    assert client.get("/api/admin/verify").json()["admin"] is False
    assert client.post("/api/collect").status_code == 401

    # 2. X-Admin-Key header -> 200
    assert client.get("/api/admin/verify", headers={"X-Admin-Key": "prod-secret-999"}).json()["admin"] is True
    assert client.get("/api/settings/mail", headers={"X-Admin-Key": "prod-secret-999"}).status_code == 200

    # 3. Authorization: Bearer <key> -> 200
    assert (
        client.get("/api/admin/verify", headers={"Authorization": "Bearer prod-secret-999"}).json()["admin"]
        is True
    )
    assert (
        client.get("/api/settings/mail", headers={"Authorization": "Bearer prod-secret-999"}).status_code
        == 200
    )

    # 4. Query param ?admin_key=... or ?key=... MUST BE REJECTED (no query param secrets allowed!)
    assert (
        client.get("/api/admin/verify?admin_key=prod-secret-999").json()["admin"]
        is False
    )
    assert (
        client.get("/api/admin/verify?key=prod-secret-999").json()["admin"]
        is False
    )
    assert (
        client.post("/api/collect?admin_key=prod-secret-999").status_code
        == 401
    )


def test_health_endpoint_healthy_and_degraded_states(tmp_path):
    store = NewsletterStore(tmp_path / "test.db")
    settings = Settings(db_path=tmp_path / "test.db")
    app = create_app(store=store, settings=settings)
    client = TestClient(app)

    # Initially before collection -> status healthy
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["components"]["web"] == "healthy"
    assert data["components"]["database"] == "healthy"
    assert data["metrics"]["feeds_failed"] == 0

    # Simulate a successful collection run with 0 failed feeds
    good_metrics = CollectionMetrics(
        feeds_total=35,
        feeds_ok=35,
        feeds_failed=0,
        articles_collected=120,
        articles_after_dedupe=80,
        articles_selected=30,
        collection_duration=3.12,
    ).to_dict()
    store.finish_daily_run("2026-09-17", metrics=good_metrics)

    resp_good = client.get("/health")
    assert resp_good.status_code == 200
    good_data = resp_good.json()
    assert good_data["status"] == "healthy"
    assert good_data["metrics"]["feeds_total"] == 35
    assert good_data["metrics"]["feeds_ok"] == 35
    assert good_data["metrics"]["feeds_failed"] == 0
    assert good_data["metrics"]["collection_duration"] == 3.12

    # Simulate a collection run with 3 failed feeds -> status degraded
    degraded_metrics = CollectionMetrics(
        feeds_total=35,
        feeds_ok=32,
        feeds_failed=3,
        articles_collected=105,
        articles_after_dedupe=72,
        articles_selected=28,
        collection_duration=4.55,
    ).to_dict()
    store.finish_daily_run("2026-09-18", metrics=degraded_metrics)

    resp_deg = client.get("/health")
    assert resp_deg.status_code == 200
    deg_data = resp_deg.json()
    assert deg_data["status"] == "degraded"
    assert "3 feeds failed" in deg_data["details"]
    assert deg_data["metrics"]["feeds_failed"] == 3
    assert deg_data["metrics"]["articles_collected"] == 105
    assert "admin_key" not in deg_data
    assert "smtp_password" not in deg_data


def test_structured_logging():
    stream = io.StringIO()
    logger = StructuredLogger(name="test_logger", output=stream)

    record = logger.info(
        component="collector",
        event="feed_fetch_ok",
        source="reuters",
        duration=0.12345,
    )
    assert record.level == "INFO"
    assert record.component == "collector"
    assert record.source == "reuters"
    assert record.duration == 0.1235
    assert record.error is None

    line = stream.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["component"] == "collector"
    assert parsed["event"] == "feed_fetch_ok"
    assert parsed["source"] == "reuters"
    assert parsed["duration"] == 0.1235
    assert "timestamp" in parsed


def test_smtp_password_not_persisted_in_sqlite_if_in_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "env-secret-password")
    store = NewsletterStore(tmp_path / "test.db")

    # When save_mail_settings is called, it should NOT write smtp_password into sqlite
    store.save_mail_settings(
        {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "env-secret-password",
            "smtp_from": "user@example.com",
            "newsletter_to": "team@example.com",
            "smtp_tls": True,
        }
    )

    saved = store.mail_settings()
    assert "smtp_password" not in saved
    assert saved["smtp_host"] == "smtp.example.com"


def test_secret_loader_file_and_env(tmp_path, monkeypatch):
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("file-secret-value\n", encoding="utf-8")

    monkeypatch.setenv("MY_KEY_FILE", str(secret_file))
    monkeypatch.delenv("MY_KEY", raising=False)

    val = _read_secret("MY_KEY", "MY_KEY_FILE")
    assert val == "file-secret-value"

    # Direct env takes precedence
    monkeypatch.setenv("MY_KEY", "direct-env-value")
    val_direct = _read_secret("MY_KEY", "MY_KEY_FILE")
    assert val_direct == "direct-env-value"


def test_proxy_security_defaults():
    settings = load_settings()
    # By default, proxies should NOT be wildcard
    assert settings.trusted_proxies != "*"
    assert "127.0.0.1" in settings.trusted_proxies
    assert settings.forwarded_allow_ips != "*"
