from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from automotive_newsletter.collector import collect_and_store
from automotive_newsletter.config import Settings
from automotive_newsletter.sources import SourceFeed
from automotive_newsletter.store import NewsletterStore
from automotive_newsletter.web import create_app
from tests.fixtures.offline_feeds import (
    SAMPLE_AUTONEWS_RSS,
    SAMPLE_BMW_OFFICIAL_RSS,
    SAMPLE_REUTERS_RSS,
    SAMPLE_UNECE_REGULATOR_RSS,
)


def test_end_to_end_pipeline_integration(tmp_path):
    """End-to-end integration test covering:

    RSS XML Fixtures
    -> Collection
    -> Publisher Detection
    -> Classification & Topic Extraction
    -> Canonicalization & Deduplication
    -> Event Clustering & Source Agreement
    -> Multi-dimensional Scoring
    -> SQLite Persistence (Issue, Articles, Events, Metrics)
    -> Web Rendering & Verification (HTML sections, Badges, Why It Matters, Filters, /health)
    """
    db_file = tmp_path / "e2e_newsletter.db"
    settings = Settings(
        db_path=db_file,
        newsletter_timezone="Europe/Berlin",
        admin_key="e2e-secret-key",
    )
    store = NewsletterStore(db_file)

    # 1. Define offline feeds
    test_feeds = [
        SourceFeed(
            id="reuters_test",
            name="Reuters Automotive",
            bucket="big",
            url="mock://reuters.com/rss",
            source_type="media",
            authority_score=95,
            region="global",
            language="en",
            enabled=True,
        ),
        SourceFeed(
            id="autonews_test",
            name="Automotive News Europe",
            bucket="oem",
            url="mock://europe.autonews.com/rss",
            source_type="media",
            authority_score=90,
            region="europe",
            language="en",
            enabled=True,
        ),
        SourceFeed(
            id="bmw_test",
            name="BMW Group PressClub",
            bucket="oem",
            url="mock://press.bmwgroup.com/rss",
            source_type="official",
            authority_score=70,
            region="europe",
            language="en",
            enabled=True,
        ),
        SourceFeed(
            id="unece_test",
            name="UNECE WP.29",
            bucket="regulation",
            url="mock://unece.org/rss",
            source_type="regulator",
            authority_score=100,
            region="global",
            language="en",
            enabled=True,
        ),
    ]

    feed_responses = {
        "mock://reuters.com/rss": SAMPLE_REUTERS_RSS.encode("utf-8"),
        "mock://europe.autonews.com/rss": SAMPLE_AUTONEWS_RSS.encode("utf-8"),
        "mock://press.bmwgroup.com/rss": SAMPLE_BMW_OFFICIAL_RSS.encode("utf-8"),
        "mock://unece.org/rss": SAMPLE_UNECE_REGULATOR_RSS.encode("utf-8"),
    }

    # 2. Mock HTTP fetching deterministically with offline fixtures
    def fake_get_with_tls_fallback(url, settings, client, insecure_client):
        content = feed_responses.get(url, b"")
        resp = MagicMock()
        resp.status_code = 200
        resp.content = content
        resp.text = content.decode("utf-8")
        resp.raise_for_status = MagicMock()
        return resp, False

    issue_date = "2026-09-17"
    with patch(
        "automotive_newsletter.collector._get_with_tls_fallback",
        side_effect=fake_get_with_tls_fallback,
    ):
        issue = collect_and_store(
            store=store,
            settings=settings,
            issue_date=issue_date,
            feeds=test_feeds,
        )

    # 3. Verify SQLite Issue Persistence
    assert issue is not None
    assert issue.issue_date == issue_date
    assert len(issue.articles) > 0

    # 4. Verify Publisher Detection & Canonical URLs
    reuters_article = next(
        (a for a in issue.articles if "restructuring" in a.title.lower() and "reuters" in (a.publisher or "").lower()),
        None,
    )
    assert reuters_article is not None
    assert "reuters" in reuters_article.publisher.lower()
    # Tracking parameters stripped
    assert "utm_source" not in (reuters_article.canonical_url or "")

    # 5. Verify Classification & Topics
    unece_article = next(
        (a for a in issue.articles if "un regulation no. 155" in a.title.lower()), None
    )
    assert unece_article is not None
    assert unece_article.source_type == "regulator"
    assert unece_article.source_authority == 100
    assert any("cybersecurity" in t.lower() for t in unece_article.topics + unece_article.tags)

    # 6. Verify Event Clustering & Multi-Source Agreement
    # Reuters & AutoNews both reported on VW restructuring
    vw_articles = [a for a in issue.articles if "restructuring" in a.title.lower() or "vw" in a.title.lower() or "volkswagen" in a.title.lower()]
    assert len(vw_articles) >= 1
    clustered = [a for a in issue.articles if a.event_id is not None]
    assert len(clustered) >= 1

    # 7. Verify Metrics Stored in SQLite
    metrics = store.get_latest_collection_metrics()
    assert metrics is not None
    assert metrics["feeds_total"] == 4
    assert metrics["feeds_ok"] == 4
    assert metrics["feeds_failed"] == 0
    assert metrics["articles_collected"] >= 4
    assert metrics["collection_duration"] >= 0

    # 8. Verify Web Rendering via FastAPI TestClient
    app = create_app(store=store, settings=settings)
    client = TestClient(app)

    # Home page
    home_resp = client.get("/")
    assert home_resp.status_code == 200
    html = home_resp.text

    # Verify intelligence sections in HTML
    assert "OEM" in html
    assert "Regulation" in html or "규제" in html
    assert "Tier 1" in html or "공급망" in html

    # Verify Why It Matters executive callout rendered
    assert "why-it-matters-box" in html or "Why it matters" in html

    # Verify filter controls rendered
    assert 'data-region-filter' in html
    assert 'data-topic-filter' in html
    assert 'data-source-type-filter' in html

    # Issue page
    issue_resp = client.get(f"/issues/{issue_date}")
    assert issue_resp.status_code == 200
    assert issue_date in issue_resp.text

    # Health API
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "healthy"
    assert health_data["metrics"]["feeds_total"] == 4
    assert health_data["metrics"]["feeds_ok"] == 4
    assert health_data["metrics"]["feeds_failed"] == 0
