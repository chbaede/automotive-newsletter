from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from automotive_newsletter.clustering import (
    are_articles_same_event,
    cluster_articles,
    select_primary_article,
)
from automotive_newsletter.models import Article
from automotive_newsletter.store import NewsletterStore


def test_same_event_clustered_across_multiple_publishers():
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    a1 = Article(
        title="Volkswagen announces major restructuring",
        url="https://reuters.com/volkswagen-restructure",
        source="Reuters",
        publisher="Reuters",
        source_type="media",
        source_authority=90,
        published_at=dt,
        entities=["Volkswagen"],
    )
    a2 = Article(
        title="VW restructuring plans accelerate",
        url="https://autonews.com/vw-restructure-plans",
        source="Automotive News",
        publisher="Automotive News",
        source_type="media",
        source_authority=80,
        published_at=dt,
        entities=["VW"],
    )
    a3 = Article(
        title="Volkswagen cuts European operations",
        url="https://bloomberg.com/volkswagen-cuts",
        source="Bloomberg",
        publisher="Bloomberg",
        source_type="media",
        source_authority=90,
        published_at=dt,
        entities=["Volkswagen"],
    )
    a4 = Article(
        title="Volkswagen announces restructuring measures",
        url="https://volkswagen-newsroom.com/en/press-releases/restructuring-2026",
        source="Volkswagen Newsroom",
        publisher="Volkswagen Newsroom",
        source_type="official",
        source_authority=85,
        is_official=True,
        is_primary_source=True,
        published_at=dt,
        entities=["Volkswagen"],
    )

    events, event_articles, all_articles = cluster_articles([a1, a2, a3, a4])

    assert len(events) == 1
    assert len(all_articles) == 4
    primary = next(a for a in all_articles if a.article_id == events[0].primary_article_id)

    # VW official newsroom should be selected as preferred primary reference
    assert primary.source == "Volkswagen Newsroom"
    assert primary.event_id == events[0].event_id

    # The primary article should have all other 3 articles in related_article_ids
    assert len(primary.related_article_ids) == 3
    assert len(event_articles) == 4


def test_primary_source_preference_hierarchy():
    dt = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)
    regulator_art = Article(
        title="NHTSA opens probe into Tesla autonomous software",
        url="https://nhtsa.gov/tesla-probe",
        source="NHTSA",
        publisher="NHTSA",
        source_type="regulator",
        source_authority=95,
        published_at=dt,
    )
    official_art = Article(
        title="Tesla issues statement on NHTSA inquiry",
        url="https://tesla.com/blog/nhtsa-inquiry",
        source="Tesla",
        publisher="Tesla",
        source_type="official",
        source_authority=85,
        published_at=dt,
    )
    wire_art = Article(
        title="NHTSA investigates Tesla autonomous driving software",
        url="https://reuters.com/tesla-probe",
        source="Reuters",
        publisher="Reuters",
        source_type="media",
        source_authority=90,
        published_at=dt,
    )
    trade_art = Article(
        title="Federal regulators investigate Tesla self-driving system",
        url="https://autonews.com/tesla-probe",
        source="Automotive News",
        publisher="Automotive News",
        source_type="media",
        source_authority=80,
        published_at=dt,
    )

    # Hierarchy check: Regulator > Official > Wire > Trade
    assert select_primary_article([trade_art, wire_art, official_art, regulator_art]) == regulator_art
    assert select_primary_article([trade_art, wire_art, official_art]) == official_art
    assert select_primary_article([trade_art, wire_art]) == wire_art


def test_different_model_numbers_not_merged():
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_m3 = Article(
        title="Tesla Model 3 production update in Shanghai factory",
        url="https://electrek.co/model-3-update",
        source="Electrek",
        published_at=dt,
    )
    art_my = Article(
        title="Tesla Model Y production update in Shanghai factory",
        url="https://electrek.co/model-y-update",
        source="Electrek",
        published_at=dt,
    )

    same_event, _ = are_articles_same_event(art_m3, art_my)
    assert not same_event

    events, _, primaries = cluster_articles([art_m3, art_my])
    assert len(events) == 2
    assert len(primaries) == 2


def test_different_generations_not_merged():
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_e6 = Article(
        title="European Commission updates Euro 6 emissions monitoring",
        url="https://eur-lex.europa.eu/euro6",
        source="European Commission",
        source_type="regulator",
        published_at=dt,
    )
    art_e7 = Article(
        title="European Commission finalizes Euro 7 emissions standards",
        url="https://eur-lex.europa.eu/euro7",
        source="European Commission",
        source_type="regulator",
        published_at=dt,
    )

    same_event, _ = are_articles_same_event(art_e6, art_e7)
    assert not same_event

    events, _, _ = cluster_articles([art_e6, art_e7])
    assert len(events) == 2


def test_same_company_different_events_not_merged():
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_restruct = Article(
        title="Volkswagen announces major restructuring plans",
        url="https://reuters.com/vw-restructure",
        source="Reuters",
        published_at=dt,
        entities=["Volkswagen"],
    )
    art_battery_jv = Article(
        title="Volkswagen announces solid-state battery joint venture with QuantumScape",
        url="https://reuters.com/vw-battery-jv",
        source="Reuters",
        published_at=dt,
        entities=["Volkswagen", "QuantumScape"],
    )

    same_event, _ = are_articles_same_event(art_restruct, art_battery_jv)
    assert not same_event

    events, _, primaries = cluster_articles([art_restruct, art_battery_jv])
    assert len(events) == 2
    assert len(primaries) == 2


def test_different_recalls_not_merged():
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_brake = Article(
        title="Ford recalls 500,000 trucks over brake defect",
        url="https://nhtsa.gov/ford-brake-recall",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
    )
    art_airbag = Article(
        title="Ford recalls 100,000 SUVs over airbag inflator risk",
        url="https://nhtsa.gov/ford-airbag-recall",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
    )

    same_event, _ = are_articles_same_event(art_brake, art_airbag)
    assert not same_event

    events, _, primaries = cluster_articles([art_brake, art_airbag])
    assert len(events) == 2


def test_store_persistence_of_events(tmp_path: Path):
    store = NewsletterStore(tmp_path / "test_newsletter.db")
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    a1 = Article(
        title="Volkswagen announces major restructuring",
        url="https://reuters.com/vw-restructure",
        source="Reuters",
        published_at=dt,
        entities=["Volkswagen"],
    )
    a2 = Article(
        title="VW restructuring plans accelerate",
        url="https://autonews.com/vw-restructure",
        source="Automotive News",
        published_at=dt,
        entities=["VW"],
    )

    events, event_articles, primary_articles = cluster_articles([a1, a2])

    saved_issue = store.save_issue(
        "2026-09-16",
        articles=[a1, a2],
        events=events,
        event_articles=event_articles,
    )

    assert len(saved_issue.events) == 1
    assert saved_issue.events[0].event_id == events[0].event_id
    assert saved_issue.events[0].title == events[0].title

    # Test reading back via get_issue
    loaded_issue = store.get_issue("2026-09-16")
    assert loaded_issue is not None
    assert len(loaded_issue.events) == 1
    assert loaded_issue.events[0].event_id == events[0].event_id

    # Test reading back event_articles
    ea_list = store.get_event_articles(events[0].event_id)
    assert len(ea_list) == 2
    assert {ea.article_id for ea in ea_list} == {a1.article_id, a2.article_id}
