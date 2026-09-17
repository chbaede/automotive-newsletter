from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from automotive_newsletter.clustering import (
    are_articles_same_event,
    cluster_articles,
    select_primary_article,
)
from automotive_newsletter.collector import (
    build_issue_articles,
    collect_and_store,
    select_presentation_articles,
)
from automotive_newsletter.config import Settings
from automotive_newsletter.models import Article, Event, EventArticle, FeedEntry
from automotive_newsletter.presentation import build_intelligence_sections
from automotive_newsletter.sources import SourceFeed
from automotive_newsletter.store import NewsletterStore


def test_case_a_multi_publisher_one_event_four_stored_articles(tmp_path: Path):
    """Case A: Reuters + Automotive News + Bloomberg + OEM official

    = 1 event, 4 stored articles.
    All articles must be stored in SQLite, and source_count/independent_source_count
    must be calculated from the complete cluster.
    """
    store = NewsletterStore(tmp_path / "case_a.db")
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    a_reuters = Article(
        title="Volkswagen announces major restructuring of European manufacturing",
        url="https://reuters.com/business/autos/volkswagen-restructure-europe",
        source="Reuters",
        publisher="Reuters",
        source_type="media",
        source_authority=95,
        published_at=dt,
        entities=["Volkswagen"],
    )
    a_autonews = Article(
        title="VW restructuring plans accelerate across European plants",
        url="https://autonews.com/oem/vw-restructure-europe-plans",
        source="Automotive News",
        publisher="Automotive News",
        source_type="media",
        source_authority=90,
        published_at=dt,
        entities=["VW"],
    )
    a_bloomberg = Article(
        title="Volkswagen cuts European operations in sweeping restructuring move",
        url="https://bloomberg.com/news/volkswagen-cuts-european-operations",
        source="Bloomberg",
        publisher="Bloomberg",
        source_type="media",
        source_authority=95,
        published_at=dt,
        entities=["Volkswagen"],
    )
    a_official = Article(
        title="Volkswagen announces restructuring measures for European plants",
        url="https://volkswagen-newsroom.com/en/press-releases/restructuring-europe-2026",
        source="Volkswagen Newsroom",
        publisher="Volkswagen Newsroom",
        source_type="official",
        source_authority=70,
        is_official=True,
        is_primary_source=True,
        published_at=dt,
        entities=["Volkswagen"],
    )

    all_input_articles = [a_reuters, a_autonews, a_bloomberg, a_official]

    # 1. Clustering never removes articles
    events, event_articles, all_articles = cluster_articles(all_input_articles)

    assert len(events) == 1
    assert len(all_articles) == 4, "Clustering must not remove non-primary articles"
    assert len(event_articles) == 4, "Every article in the event must be in event_articles"

    event = events[0]
    assert event.source_count == 4
    # Reuters, Automotive News, Bloomberg, VW Newsroom -> 4 independent publishers
    assert event.independent_source_count == 4
    assert event.has_official_source is True
    assert event.has_major_media_source is True
    # Official newsroom preferred as primary article
    assert event.primary_article_id == a_official.article_id

    # 2. Store all collected articles and events
    saved_issue = store.save_issue(
        "2026-09-16",
        articles=all_articles,
        events=events,
        event_articles=event_articles,
    )

    # 3. Verify SQLite persistence: 4 stored articles
    loaded_issue = store.get_issue("2026-09-16")
    assert loaded_issue is not None
    assert len(loaded_issue.articles) == 4, "All 4 articles must be preserved in the database"
    assert len(loaded_issue.events) == 1
    assert loaded_issue.events[0].source_count == 4

    # 4. Presentation time: newsletter displays only ONE primary article for the cluster
    sections = build_intelligence_sections(loaded_issue)
    all_presented_urls = [a.url for sec in sections for a in sec["articles"]]
    # The primary article URL must be displayed
    assert a_official.url in all_presented_urls
    # The 3 non-primary coverage URLs must NOT be displayed as duplicate cards
    assert a_reuters.url not in all_presented_urls
    assert a_autonews.url not in all_presented_urls
    assert a_bloomberg.url not in all_presented_urls


def test_case_b_three_different_events_all_preserved(tmp_path: Path):
    """Case B: 3 different events = 3 events, all articles preserved."""
    store = NewsletterStore(tmp_path / "case_b.db")
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    a1 = Article(
        title="BMW announces new solid-state battery gigafactory in Munich",
        url="https://press.bmwgroup.com/battery-gigafactory",
        source="BMW",
        category="ev_battery",
        published_at=dt,
        entities=["BMW"],
    )
    a2 = Article(
        title="Tesla recalls 200,000 vehicles over rearview camera blank screen",
        url="https://nhtsa.gov/tesla-camera-recall",
        source="NHTSA",
        category="regulation",
        source_type="regulator",
        published_at=dt,
        entities=["Tesla"],
    )
    a3 = Article(
        title="UNECE WP.29 adopts new vehicle cybersecurity regulations for trucks",
        url="https://unece.org/regulations/wp29-truck-cybersecurity",
        source="UNECE",
        category="regulation",
        source_type="regulator",
        published_at=dt,
        entities=["UNECE"],
    )

    events, event_articles, all_articles = cluster_articles([a1, a2, a3])

    assert len(events) == 3, "3 distinct events must produce 3 separate events"
    assert len(all_articles) == 3, "All articles must be preserved"
    assert len(event_articles) == 3

    # Store in database
    store.save_issue("2026-09-16", articles=all_articles, events=events, event_articles=event_articles)
    loaded = store.get_issue("2026-09-16")
    assert loaded is not None
    assert len(loaded.articles) == 3
    assert len(loaded.events) == 3


def test_case_c_same_event_with_one_primary_source(tmp_path: Path):
    """Case C: same event with one primary source = 1 event, 1 article."""
    store = NewsletterStore(tmp_path / "case_c.db")
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    a1 = Article(
        title="Mercedes-Benz unveils next-generation MB.OS architecture at tech summit",
        url="https://group.mercedes-benz.com/mb-os-unveil",
        source="Mercedes-Benz",
        source_type="official",
        category="sdv",
        published_at=dt,
        entities=["Mercedes-Benz"],
    )

    events, event_articles, all_articles = cluster_articles([a1])

    assert len(events) == 1
    assert len(all_articles) == 1
    assert len(event_articles) == 1
    assert events[0].source_count == 1
    assert events[0].independent_source_count == 1
    assert events[0].primary_article_id == a1.article_id
    assert all_articles[0].event_id == events[0].event_id
    assert all_articles[0].related_article_ids == []

    store.save_issue("2026-09-16", articles=all_articles, events=events, event_articles=event_articles)
    loaded = store.get_issue("2026-09-16")
    assert loaded is not None
    assert len(loaded.articles) == 1
    assert len(loaded.events) == 1


def test_case_d_same_company_different_events_must_not_merge():
    """Case D: same company but different events = must not merge."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    art_restruct = Article(
        title="Volkswagen announces major workforce restructuring and European plant cuts",
        url="https://reuters.com/vw-restruct-workforce",
        source="Reuters",
        published_at=dt,
        entities=["Volkswagen"],
    )
    art_battery_jv = Article(
        title="Volkswagen and QuantumScape form joint venture for solid-state battery gigafactory",
        url="https://reuters.com/vw-battery-gigafactory-jv",
        source="Reuters",
        published_at=dt,
        entities=["Volkswagen"],
    )

    same_event, _ = are_articles_same_event(art_restruct, art_battery_jv)
    assert not same_event, "Restructuring and Battery JV must not be merged"

    events, _, all_articles = cluster_articles([art_restruct, art_battery_jv])
    assert len(events) == 2
    assert len(all_articles) == 2


def test_case_e_model_3_vs_model_y_must_not_merge():
    """Case E: Model 3 vs Model Y = must not merge."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    art_m3 = Article(
        title="Tesla cuts Model 3 price in North America ahead of refresh",
        url="https://electrek.co/tesla-model-3-price-cut",
        source="Electrek",
        published_at=dt,
    )
    art_my = Article(
        title="Tesla cuts Model Y price in North America amid demand shift",
        url="https://electrek.co/tesla-model-y-price-cut",
        source="Electrek",
        published_at=dt,
    )

    same_event, _ = are_articles_same_event(art_m3, art_my)
    assert not same_event, "Model 3 and Model Y price cuts must not be merged"

    events, _, all_articles = cluster_articles([art_m3, art_my])
    assert len(events) == 2
    assert len(all_articles) == 2


def test_case_f_hyundai_vs_kia_must_not_merge_same_parent_group():
    """Case F: Hyundai vs Kia = must not merge merely because they belong to the same parent group."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    art_hyundai = Article(
        title="Hyundai announces dedicated electric vehicle platform architecture",
        url="https://autonews.com/hyundai-ev-platform",
        source="Automotive News",
        published_at=dt,
        entities=["Hyundai"],
    )
    art_kia = Article(
        title="Kia announces dedicated electric vehicle platform architecture",
        url="https://autonews.com/kia-ev-platform",
        source="Automotive News",
        published_at=dt,
        entities=["Kia"],
    )

    same_event, _ = are_articles_same_event(art_hyundai, art_kia)
    assert not same_event, "Hyundai and Kia are distinct OEM brands and must not merge"

    events, _, all_articles = cluster_articles([art_hyundai, art_kia])
    assert len(events) == 2
    assert len(all_articles) == 2


def test_source_count_and_independent_count_calculated_from_all_event_articles():
    """Verify source_count and independent_source_count are calculated from all event articles,

    including syndicated wire republication detection.
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    # 1. Original Reuters report
    art_orig = Article(
        title="Stellantis halts European production due to supply chain dispute",
        url="https://reuters.com/stellantis-halt",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Stellantis"],
    )
    # 2. Syndicated copy via Yahoo News
    art_syndicated = Article(
        title="Stellantis halts European production due to supply chain dispute",
        url="https://finance.yahoo.com/stellantis-halt-reuters",
        source="Yahoo News",
        publisher="Yahoo News",
        excerpt="(Reuters) - Automaker Stellantis halted European production.",
        published_at=dt,
        entities=["Stellantis"],
    )
    # 3. Independent report from Automotive News Europe
    art_independent = Article(
        title="Stellantis stops European plant lines over supplier contract row",
        url="https://europe.autonews.com/stellantis-stops-lines",
        source="Automotive News Europe",
        publisher="Automotive News Europe",
        published_at=dt,
        entities=["Stellantis"],
    )

    events, event_articles, all_articles = cluster_articles([art_orig, art_syndicated, art_independent])

    assert len(events) == 1
    event = events[0]
    # Total source count from all 3 articles
    assert event.source_count == 3
    # Independent count correctly recognizes Yahoo News is syndicated from Reuters
    assert event.independent_source_count == 2
    assert len(all_articles) == 3
    assert len(event_articles) == 3


def test_collect_and_store_runs_clustering_once_and_retains_all_articles(tmp_path: Path):
    """Verify collect_and_store pipeline:

    fetch -> canonicalize -> deduplicate -> classify -> score -> add fallbacks
    -> cluster ONCE -> select presentation articles -> store ALL collected articles and events.
    """
    db_file = tmp_path / "pipeline.db"
    store = NewsletterStore(db_file)
    settings = Settings(db_path=db_file)

    feed = SourceFeed(
        id="mock_feed",
        name="Mock Feed",
        bucket="sdv",
        url="mock://test/rss",
        source_type="media",
        authority_score=90,
        enabled=True,
    )

    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    # 2 articles belonging to the same event
    entries = [
        FeedEntry(
            title="Bosch unveils vehicle computer software for SDV platforms",
            url="https://bosch.com/vehicle-computer-sdv",
            source="Bosch",
            bucket="tier1",
            published_at=dt,
            source_type="official",
        ),
        FeedEntry(
            title="Auto supplier Bosch expands vehicle computer lineup for SDVs",
            url="https://autonews.com/bosch-vehicle-computer",
            source="Automotive News",
            bucket="tier1",
            published_at=dt,
            source_type="media",
        ),
    ]

    cluster_call_count = 0
    real_cluster_articles = cluster_articles

    def counting_cluster_articles(*args, **kwargs):
        nonlocal cluster_call_count
        cluster_call_count += 1
        return real_cluster_articles(*args, **kwargs)

    with patch("automotive_newsletter.collector.fetch_feed_entries", return_value=(entries, [], {"feeds_total": 1, "feeds_ok": 1, "feeds_failed": 0})), \
         patch("automotive_newsletter.collector.cluster_articles", side_effect=counting_cluster_articles):

        issue = collect_and_store(
            store=store,
            settings=settings,
            issue_date="2026-09-16",
            feeds=[feed],
        )

    # 1. Cluster called exactly once during the collection pipeline
    assert cluster_call_count == 1, "Clustering must run exactly ONCE during collect_and_store"

    # 2. Both articles are stored in SQLite
    loaded = store.get_issue("2026-09-16")
    assert loaded is not None
    # Verify both Bosch articles are preserved in the database
    bosch_articles = [a for a in loaded.articles if "vehicle computer" in a.title.lower()]
    assert len(bosch_articles) == 2, "Both articles must be retained in the database"

    # 3. Only the primary article is presented in the newsletter sections
    sections = build_intelligence_sections(loaded)
    presented_bosch = [a for sec in sections for a in sec["articles"] if "vehicle computer" in a.title.lower()]
    assert len(presented_bosch) == 1, "Only primary article should be presented across newsletter sections"
    assert presented_bosch[0].is_official is True
