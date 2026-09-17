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


def test_clustering_test_a_real_similarity():
    """Test A — real similarity:

    Verify that articles in the same event do not have hardcoded 0.85 similarity,
    compute real distinct values, and primary has similarity == 1.0.
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_reuters = Article(
        title="Toyota and Nvidia announce software-defined vehicle partnership",
        url="https://reuters.com/toyota-nvidia-partnership",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Toyota"],
    )
    art_an = Article(
        title="Toyota teams up with Nvidia on SDV computing platform",
        url="https://autonews.com/toyota-nvidia-platform",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["Toyota"],
    )
    art_official = Article(
        title="Toyota Motor Corporation and NVIDIA Expand Strategic SDV Collaboration",
        url="https://toyota.com/newsroom/nvidia-sdv",
        source="Toyota Newsroom",
        publisher="Toyota Newsroom",
        source_type="official",
        is_official=True,
        is_primary_source=True,
        published_at=dt,
        entities=["Toyota"],
    )

    events, event_articles, all_articles = cluster_articles([art_reuters, art_an, art_official])

    assert len(events) == 1
    assert len(all_articles) == 3
    assert len(event_articles) == 3

    # Map article_id to similarity
    sim_map = {ea.article_id: ea.similarity for ea in event_articles}
    rel_map = {ea.article_id: ea.relationship for ea in event_articles}

    primary_id = events[0].primary_article_id
    assert primary_id is not None
    assert sim_map[primary_id] == 1.0
    assert rel_map[primary_id] == "primary"

    # Non-primary articles must NOT be hardcoded 0.85
    non_primaries = [ea for ea in event_articles if ea.article_id != primary_id]
    for ea in non_primaries:
        assert ea.similarity != 0.85, f"Similarity for {ea.article_id} must not be hardcoded 0.85"
        assert 0.60 <= ea.similarity < 1.0

    # Similarities of different articles should reflect actual pairwise values
    assert len(non_primaries) == 2
    assert non_primaries[0].similarity != non_primaries[1].similarity


def test_clustering_test_b_transitive_merge_prevention():
    """Test B — transitive merge prevention:

    A ~ B, B ~ C, but A !~ C (e.g. A is platform architecture, C is recall).
    Connected components must NOT merge A and C into the same event.
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_a = Article(
        title="Volkswagen announces new EV platform architecture",
        url="https://example.com/vw-ev-platform",
        source="Reuters",
        published_at=dt,
        entities=["Volkswagen"],
    )
    art_b = Article(
        title="Volkswagen platform software update details",
        url="https://example.com/vw-platform-update",
        source="Automotive News",
        published_at=dt,
        entities=["Volkswagen"],
    )
    art_c = Article(
        title="Volkswagen recalls 120,000 vehicles over brake defect",
        url="https://example.com/vw-brake-recall",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
        entities=["Volkswagen"],
    )

    events, event_articles, all_articles = cluster_articles([art_a, art_b, art_c])

    # Must NOT all be merged into 1 event
    assert len(events) >= 2, "Transitive merge must be prevented: Platform and Recall must not be in 1 event"
    assert len(all_articles) == 3, "All articles must be preserved"
    assert len(event_articles) == 3

    # Art A (Platform) and Art C (Recall) must belong to different events
    assert art_a.event_id != art_c.event_id


def test_clustering_test_c_model_separation():
    """Test C — model separation:

    Tesla Model 3 vs Tesla Model Y must remain separate events even for same OEM and same theme.
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_m3 = Article(
        title="Tesla rolls out FSD software update to Model 3 fleet",
        url="https://example.com/tesla-m3-fsd",
        source="Electrek",
        published_at=dt,
        entities=["Tesla"],
    )
    art_my = Article(
        title="Tesla rolls out FSD software update to Model Y fleet",
        url="https://example.com/tesla-my-fsd",
        source="Electrek",
        published_at=dt,
        entities=["Tesla"],
    )

    events, _, all_articles = cluster_articles([art_m3, art_my])
    assert len(events) == 2, "Model 3 and Model Y must remain separate events"
    assert len(all_articles) == 2
    assert events[0].event_id != events[1].event_id


def test_clustering_test_d_recall_separation():
    """Test D — recall separation:

    Different recalls by the same OEM must not be merged into one event.
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_recall1 = Article(
        title="Ford recalls 300,000 F-150 trucks over brake defect",
        url="https://example.com/ford-brake-recall",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
        entities=["Ford"],
    )
    art_recall2 = Article(
        title="Ford recalls 250,000 Explorer SUVs over airbag inflator risk",
        url="https://example.com/ford-airbag-recall",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
        entities=["Ford"],
    )

    events, _, all_articles = cluster_articles([art_recall1, art_recall2])
    assert len(events) == 2, "Different recalls must remain separate events"
    assert len(all_articles) == 2
    assert events[0].event_id != events[1].event_id


def test_clustering_test_e_parent_group_separation_and_joint_merging():
    """Test E — parent group:

    Hyundai and Kia are not merged solely on sharing parent group.
    However, genuine joint announcements with strong evidence must be merged.
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    # 1. Distinct events by sister brands -> must NOT merge
    art_hyundai = Article(
        title="Hyundai announces dedicated electric vehicle platform architecture",
        url="https://example.com/hyundai-ev",
        source="Automotive News",
        published_at=dt,
        entities=["Hyundai"],
    )
    art_kia = Article(
        title="Kia announces dedicated electric vehicle platform architecture",
        url="https://example.com/kia-ev",
        source="Automotive News",
        published_at=dt,
        entities=["Kia"],
    )

    events_sep, _, _ = cluster_articles([art_hyundai, art_kia])
    assert len(events_sep) == 2, "Hyundai and Kia must not merge solely due to parent group"

    # 2. Genuine joint announcement with strong joint evidence -> MUST merge
    art_joint1 = Article(
        title="Hyundai and Kia announce joint $3 billion battery facility in Georgia",
        url="https://reuters.com/hyundai-kia-battery-georgia",
        source="Reuters",
        published_at=dt,
        entities=["Hyundai", "Kia"],
    )
    art_joint2 = Article(
        title="Kia and Hyundai partner on joint $3 billion Georgia battery investment",
        url="https://autonews.com/kia-hyundai-battery-georgia",
        source="Automotive News",
        published_at=dt,
        entities=["Kia", "Hyundai"],
    )

    events_joint, _, all_joint = cluster_articles([art_joint1, art_joint2])
    assert len(events_joint) == 1, "Joint announcement across sister brands with strong evidence must merge"
    assert len(all_joint) == 2

