from __future__ import annotations

import smtplib
import sqlite3
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from automotive_newsletter.collector import collect_and_store, fetch_feed_entries
from automotive_newsletter.config import Settings
from automotive_newsletter.mailer import MailConfigError, send_issue
from automotive_newsletter.models import Article
from automotive_newsletter.sources import SourceFeed
from automotive_newsletter.store import NewsletterStore
from automotive_newsletter.summarizer import FallbackSummarizer, OllamaSummarizer, TemplateSummarizer, get_summarizer
from automotive_newsletter.web import create_app
from tests.fixtures.offline_feeds import (
    SAMPLE_EMPTY_RSS,
    SAMPLE_INVALID_XML,
    SAMPLE_MALFORMED_ARTICLES_RSS,
)


def test_feed_timeout_handled_gracefully(tmp_path):
    store = NewsletterStore(tmp_path / "timeout.db")
    settings = Settings(db_path=tmp_path / "timeout.db")
    timeout_feed = SourceFeed(
        id="timeout_feed",
        name="Timeout Feed",
        url="mock://timeout",
        bucket="sdv",
        enabled=True,
    )

    def fake_get_timeout(*args, **kwargs):
        raise httpx.TimeoutException("Read timed out after 8.0 seconds")

    with patch("automotive_newsletter.collector._get_with_tls_fallback", side_effect=fake_get_timeout):
        issue = collect_and_store(store=store, settings=settings, issue_date="2026-09-17", feeds=[timeout_feed])

    assert issue is not None
    assert any("Read timed out" in w for w in issue.warnings)
    metrics = store.get_latest_collection_metrics()
    assert metrics is not None
    assert metrics["feeds_failed"] == 1
    assert metrics["feeds_ok"] == 0


def test_invalid_xml_handled_gracefully(tmp_path):
    store = NewsletterStore(tmp_path / "invalid_xml.db")
    settings = Settings(db_path=tmp_path / "invalid_xml.db")
    broken_feed = SourceFeed(
        id="broken_feed",
        name="Broken Feed",
        url="mock://broken",
        bucket="sdv",
        enabled=True,
    )

    resp = MagicMock()
    resp.status_code = 200
    resp.content = SAMPLE_INVALID_XML.encode("utf-8")
    resp.text = SAMPLE_INVALID_XML
    resp.raise_for_status = MagicMock()

    with patch("automotive_newsletter.collector._get_with_tls_fallback", return_value=(resp, False)):
        entries, warnings, stats = fetch_feed_entries([broken_feed], settings=settings, return_stats=True)

    assert entries == []
    assert stats["feeds_failed"] == 1
    assert stats["feeds_ok"] == 0
    assert any("피드 파싱 실패" in w for w in warnings)


def test_dns_failure_handled_gracefully(tmp_path):
    store = NewsletterStore(tmp_path / "dns.db")
    settings = Settings(db_path=tmp_path / "dns.db")
    dns_feed = SourceFeed(
        id="dns_feed",
        name="DNS Feed",
        url="mock://unresolvable.invalid",
        bucket="oem",
        enabled=True,
    )

    def fake_dns_error(*args, **kwargs):
        raise httpx.ConnectError("[Errno 8] nodename nor servname provided, or not known")

    with patch("automotive_newsletter.collector._get_with_tls_fallback", side_effect=fake_dns_error):
        issue = collect_and_store(store=store, settings=settings, issue_date="2026-09-17", feeds=[dns_feed])

    assert issue is not None
    assert any("nodename nor servname" in w for w in issue.warnings)
    metrics = store.get_latest_collection_metrics()
    assert metrics["feeds_failed"] == 1


def test_tls_failure_handled_gracefully(tmp_path):
    store = NewsletterStore(tmp_path / "tls.db")
    settings = Settings(db_path=tmp_path / "tls.db")
    tls_feed = SourceFeed(
        id="tls_feed",
        name="TLS Feed",
        url="mock://bad-cert.invalid",
        bucket="oem",
        enabled=True,
    )

    def fake_tls_error(*args, **kwargs):
        raise httpx.ConnectError("CERTIFICATE_VERIFY_FAILED: certificate verify failed")

    with patch("automotive_newsletter.collector._get_with_tls_fallback", side_effect=fake_tls_error):
        entries, warnings = fetch_feed_entries([tls_feed], settings=settings)

    assert entries == []
    assert any("CERTIFICATE_VERIFY_FAILED" in w for w in warnings)


def test_empty_feed_handled_gracefully(tmp_path):
    store = NewsletterStore(tmp_path / "empty.db")
    settings = Settings(db_path=tmp_path / "empty.db")
    empty_feed = SourceFeed(
        id="empty_feed",
        name="Empty Feed",
        url="mock://empty",
        bucket="oem",
        enabled=True,
    )

    resp = MagicMock()
    resp.status_code = 200
    resp.content = SAMPLE_EMPTY_RSS.encode("utf-8")
    resp.text = SAMPLE_EMPTY_RSS
    resp.raise_for_status = MagicMock()

    with patch("automotive_newsletter.collector._get_with_tls_fallback", return_value=(resp, False)):
        entries, warnings, stats = fetch_feed_entries([empty_feed], settings=settings, return_stats=True)

    assert entries == []
    assert stats["feeds_ok"] == 1
    assert stats["feeds_failed"] == 0


def test_malformed_article_handled_gracefully(tmp_path):
    store = NewsletterStore(tmp_path / "malformed.db")
    settings = Settings(db_path=tmp_path / "malformed.db")
    malformed_feed = SourceFeed(
        id="malformed_feed",
        name="Malformed Feed",
        url="mock://malformed",
        bucket="sdv",
        enabled=True,
    )

    resp = MagicMock()
    resp.status_code = 200
    resp.content = SAMPLE_MALFORMED_ARTICLES_RSS.encode("utf-8")
    resp.text = SAMPLE_MALFORMED_ARTICLES_RSS
    resp.raise_for_status = MagicMock()

    with patch("automotive_newsletter.collector._get_with_tls_fallback", return_value=(resp, False)):
        entries, warnings = fetch_feed_entries([malformed_feed], settings=settings)

    # Empty titles or links should be skipped safely; unparseable date should not crash
    assert len(entries) == 1
    assert entries[0].title == "Article with corrupted pubDate"
    assert entries[0].published_at is None  # Safe None fallback


def test_ai_summarizer_failure_falls_back_to_template():
    article = Article(
        title="Hyundai expands SDV software R&D center in Europe",
        url="https://example.com/hyundai-sdv",
        source="Auto Wire",
        category="sdv",
        summary_ko="",
        excerpt="Hyundai Motor announced a new vehicle software development hub.",
    )

    # Primary Ollama summarizer raises network connection error
    mock_ollama = MagicMock(spec=OllamaSummarizer)
    mock_ollama.summarize.side_effect = httpx.ConnectError("Ollama connection refused on http://localhost:11434")

    template = TemplateSummarizer()
    fallback_summarizer = FallbackSummarizer(primary=mock_ollama, fallback=template)

    result = fallback_summarizer.summarize(article)
    assert result is not None
    assert result.summary_ko != ""
    assert result.why_it_matters_ko != ""
    assert result.summary_model == "template"


def test_database_failure_reported_by_health(tmp_path):
    store = NewsletterStore(tmp_path / "healthy.db")
    settings = Settings(db_path=tmp_path / "healthy.db")
    app = create_app(store=store, settings=settings)
    client = TestClient(app)

    # When database list_issues throws an OperationalError (e.g. locked/corrupted)
    with patch.object(store, "list_issues", side_effect=sqlite3.OperationalError("database is locked")):
        resp = client.get("/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["components"]["database"] == "unhealthy"


def test_smtp_failure_returns_clean_error(tmp_path):
    store = NewsletterStore(tmp_path / "smtp.db")
    store.save_issue(
        "2026-09-17",
        [
            Article(
                title="Test article",
                url="https://example.com/test",
                source="Wire",
                category="oem",
                summary_ko="요약",
            )
        ],
    )
    settings = Settings(
        db_path=tmp_path / "smtp.db",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_from="sender@example.com",
        newsletter_to="reader@example.com",
        admin_key="test-key",
    )
    app = create_app(store=store, settings=settings)
    client = TestClient(app)

    # When SMTP server throws a connection error
    with patch("automotive_newsletter.mailer.smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = smtplib.SMTPConnectError(421, b"Service unavailable, closing transmission channel")
        resp = client.post("/api/issues/2026-09-17/send", headers={"X-Admin-Key": "test-key"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["ok"] is False
        assert "메일 발송에 실패했습니다" in data["message"] or "Service unavailable" in data["message"]
