from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from automotive_newsletter.clustering import (
    calculate_event_source_agreement,
    cluster_articles,
    resolve_originating_publisher,
)
from automotive_newsletter.mailer import build_email_html, build_email_text
from automotive_newsletter.models import Article, NewsletterIssue
from automotive_newsletter.presentation import display_event_coverage
from automotive_newsletter.store import NewsletterStore


def test_independent_source_count_detects_syndication():
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    # Article 1: Original Reuters wire
    art_reuters = Article(
        title="Volkswagen announces major European plant restructuring",
        url="https://reuters.com/vw-restructuring",
        source="Reuters",
        publisher="Reuters",
        source_type="media",
        published_at=dt,
        excerpt="Volkswagen announced today major European plant restructuring.",
    )
    # Article 2: Yahoo republishing Reuters with attribution
    art_yahoo = Article(
        title="Volkswagen announces major European plant restructuring via Reuters",
        url="https://yahoo.com/news/vw-restructuring",
        source="Yahoo News",
        publisher="Yahoo News",
        source_type="aggregator",
        published_at=dt,
        excerpt="(Reuters) - Volkswagen announced today major European plant restructuring.",
    )
    # Article 3: Automotive News independent trade reporting
    art_autonews = Article(
        title="VW restructuring accelerates across German manufacturing sites",
        url="https://autonews.com/vw-restructure",
        source="Automotive News",
        publisher="Automotive News",
        source_type="media",
        published_at=dt,
        excerpt="Automotive News analysis of Volkswagen's restructuring measures.",
    )
    # Article 4: Tech blog copying Automotive News
    art_blog = Article(
        title="VW restructuring plans according to Automotive News",
        url="https://techblog.com/vw-plans",
        source="TechBlog",
        publisher="TechBlog",
        source_type="media",
        published_at=dt,
        excerpt="According to Automotive News, VW restructuring accelerates.",
    )

    # Test individual originating publisher detection
    assert resolve_originating_publisher(art_reuters) == "Reuters"
    assert resolve_originating_publisher(art_yahoo) == "Reuters"
    assert resolve_originating_publisher(art_autonews) == "Automotive News"
    assert resolve_originating_publisher(art_blog) == "Automotive News"

    # Test agreement calculation
    agreement = calculate_event_source_agreement(
        [art_reuters, art_yahoo, art_autonews, art_blog],
        primary=art_reuters,
    )

    assert agreement["source_count"] == 4
    # Even though there are 4 articles, only 2 independent reporting publishers exist (Reuters & Automotive News)
    assert agreement["independent_source_count"] == 2
    assert agreement["has_major_media_source"] is True


def test_official_and_regulatory_source_detection():
    dt = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)
    art_nhtsa = Article(
        title="NHTSA opens investigation into Tesla autonomous steering defect",
        url="https://nhtsa.gov/recalls/probe-123",
        source="NHTSA",
        publisher="NHTSA",
        source_type="regulator",
        is_reference=True,
        published_at=dt,
        entities=["Tesla", "NHTSA"],
    )
    art_official = Article(
        title="Tesla issues statement addressing NHTSA safety inquiry",
        url="https://tesla.com/press/inquiry-response",
        source="Tesla",
        publisher="Tesla",
        source_type="official",
        is_official=True,
        is_primary_source=True,
        published_at=dt,
        entities=["Tesla"],
    )
    art_wire = Article(
        title="NHTSA probes Tesla over autonomous steering defect",
        url="https://bloomberg.com/nhtsa-probe",
        source="Bloomberg",
        publisher="Bloomberg",
        source_type="media",
        published_at=dt,
        entities=["Tesla", "NHTSA"],
    )

    events, event_articles, primaries = cluster_articles([art_nhtsa, art_official, art_wire])
    assert len(events) == 1
    event = events[0]

    assert event.source_count == 3
    assert event.independent_source_count == 3
    assert event.has_official_source is True
    assert event.has_regulatory_source is True
    assert event.has_major_media_source is True
    assert event.official_source_url == "https://tesla.com/press/inquiry-response"
    assert event.official_source_name == "Tesla"
    assert event.reference_source_name == "NHTSA"
    assert "NHTSA" in event.related_sources
    assert "Tesla" in event.related_sources
    assert "Bloomberg" in event.related_sources


def test_neutrality_of_display_labels_without_truth_claims():
    art = Article(
        title="Major industry development",
        url="https://example.com/1",
        source="Reuters",
        related_article_ids=["art_2", "art_3", "art_4"],
        event_source_count=4,
        event_independent_source_count=2,
        event_has_official_source=True,
        event_official_source_url="https://official.example.com",
    )

    cov = display_event_coverage(art)
    assert cov is not None

    # Check for neutral informational labels
    assert cov["source_label_en"] == "4 sources"
    assert cov["independent_label_en"] == "2 independent publishers"
    assert cov["official_label_en"] == "Official source available"
    assert cov["source_label_ko"] == "4개 매체"
    assert cov["independent_label_ko"] == "2개 독립 매체"

    # Strictly forbid non-neutral certainty or truth claims
    all_label_text = " ".join(
        str(v).lower() for v in cov.values() if isinstance(v, str)
    )
    for forbidden in ["confirmed", "100% reliable", "true", "verified"]:
        assert forbidden not in all_label_text


def test_email_presentation_includes_source_agreement_and_official_source():
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art = Article(
        title="Volkswagen announces restructuring",
        url="https://reuters.com/vw",
        source="Reuters",
        category="big",
        published_at=dt,
        event_source_count=4,
        event_independent_source_count=2,
        event_has_official_source=True,
        event_official_source_url="https://volkswagen-newsroom.com/en/releases/123",
        event_official_source_name="Volkswagen Newsroom",
        event_related_sources=["Reuters", "Volkswagen Newsroom", "Automotive News", "Bloomberg"],
    )
    issue = NewsletterIssue(
        issue_date="2026-09-16",
        articles=[art],
    )

    html_ko = build_email_html(issue, lang="ko")
    html_en = build_email_html(issue, lang="en")
    text_ko = build_email_text(issue, lang="ko")
    text_en = build_email_text(issue, lang="en")

    # HTML verification
    assert "4개 매체" in html_ko
    assert "2개 독립 매체" in html_ko
    assert "공식 출처 제공" in html_ko
    assert "https://volkswagen-newsroom.com/en/releases/123" in html_ko
    assert "공식 발표 보기" in html_ko

    assert "4 sources" in html_en
    assert "2 independent publishers" in html_en
    assert "Official source available" in html_en
    assert "Official Source" in html_en
    assert "Related Sources:" in html_en

    # Plain text verification
    assert "4 sources · 2 independent publishers · Official source available" in text_en
    assert "Related Sources: Reuters, Volkswagen Newsroom, Automotive News, Bloomberg" in text_en
    assert "Official Source: https://volkswagen-newsroom.com/en/releases/123" in text_en


def test_sqlite_persistence_of_event_source_agreement(tmp_path: Path):
    store = NewsletterStore(tmp_path / "test_agreement.db")
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    a1 = Article(
        title="NHTSA investigates Tesla autonomous steering software",
        url="https://nhtsa.gov/probe",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
    )
    a2 = Article(
        title="Tesla issues official response to NHTSA inquiry",
        url="https://tesla.com/press",
        source="Tesla Newsroom",
        source_type="official",
        is_official=True,
        published_at=dt,
    )
    a3 = Article(
        title="NHTSA investigates Tesla steering via Reuters",
        url="https://yahoo.com/reuters-tesla",
        source="Yahoo News",
        published_at=dt,
        excerpt="(Reuters) - Federal regulators opened a probe.",
    )

    events, event_articles, primaries = cluster_articles([a1, a2, a3])
    assert len(events) == 1

    saved = store.save_issue("2026-09-16", articles=[a1, a2, a3], events=events, event_articles=event_articles)
    assert len(saved.events) == 1
    assert saved.events[0].source_count == 3
    assert saved.events[0].has_official_source is True
    assert saved.events[0].has_regulatory_source is True
    assert saved.events[0].official_source_url == "https://tesla.com/press"

    # Reload from store
    loaded = store.get_issue("2026-09-16")
    assert loaded is not None
    assert len(loaded.events) == 1
    ev = loaded.events[0]
    assert ev.source_count == 3
    assert ev.has_official_source is True
    assert ev.has_regulatory_source is True
    assert ev.official_source_url == "https://tesla.com/press"
    assert ev.official_source_name == "Tesla Newsroom"
    assert "Tesla Newsroom" in ev.related_sources

    # Check that loaded articles have event metadata attached
    loaded_primary = next(a for a in loaded.articles if a.article_id == ev.primary_article_id)
    assert loaded_primary.event_source_count == 3
    assert loaded_primary.event_has_official_source is True
    assert loaded_primary.event_official_source_url == "https://tesla.com/press"
