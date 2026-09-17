from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from automotive_newsletter.clustering import (
    are_articles_same_event,
    calculate_event_similarity,
    cluster_articles,
    compute_event_coherence_metrics,
    extract_canonical_entities,
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


def test_relative_similarity_ordering():
    """Verify deterministic relative ordering of event similarity:

    sim(A, B) > sim(A, C) > sim(A, D)
    where:
    A: Same event candidate 1 (Toyota + Nvidia partnership)
    B: Same event candidate 2 (Nvidia + Toyota partnership)
    C: Related event (Toyota autonomous road tests in Tokyo)
    D: Different event (Honda steering recall)
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_a = Article(
        title="Toyota and Nvidia announce autonomous driving chip partnership",
        url="https://reuters.com/toyota-nvidia-announcement",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Toyota", "Nvidia"],
    )
    art_b = Article(
        title="Nvidia and Toyota partner on autonomous vehicle computing",
        url="https://autonews.com/nvidia-toyota-computing",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["Toyota", "Nvidia"],
    )
    art_c = Article(
        title="Toyota expands autonomous driving road tests in Tokyo",
        url="https://bloomberg.com/toyota-tokyo-tests",
        source="Bloomberg",
        publisher="Bloomberg",
        published_at=dt,
        entities=["Toyota"],
    )
    art_d = Article(
        title="Honda recalls 500,000 vehicles over steering defect",
        url="https://nhtsa.gov/honda-steering-recall",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
        entities=["Honda"],
    )

    sim_ab = calculate_event_similarity(art_a, art_b)
    sim_ac = calculate_event_similarity(art_a, art_c)
    sim_ad = calculate_event_similarity(art_a, art_d)

    # 1. Strict relative ordering
    assert sim_ab > sim_ac > sim_ad, f"Expected sim(A,B) > sim(A,C) > sim(A,D), got {sim_ab} > {sim_ac} > {sim_ad}"

    # 2. Strict calibrated ranges
    assert sim_ab >= 0.75, f"Same event similarity must be >= 0.75, got {sim_ab}"
    assert 0.35 <= sim_ac <= 0.65, f"Related event similarity must be within [0.35, 0.65], got {sim_ac}"
    assert sim_ad <= 0.20, f"Unrelated event similarity must be <= 0.20, got {sim_ad}"

    # 3. Decision boundaries
    is_same_ab, _ = are_articles_same_event(art_a, art_b)
    is_same_ac, _ = are_articles_same_event(art_a, art_c)
    is_same_ad, _ = are_articles_same_event(art_a, art_d)

    assert is_same_ab is True
    assert is_same_ac is False
    assert is_same_ad is False


def test_strict_transitive_clustering_verification():
    """Verify transitive false-merge prevention:

    A ~ B, B ~ C, but A !~ C.
    Clustering must partition into Event 1: {A, B} and Event 2: {C}.
    All articles must remain available with full metadata.
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_a = Article(
        title="Volkswagen announces new EV platform architecture",
        url="https://reuters.com/vw-ev-platform-2026",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Volkswagen"],
        priority_score=85,
    )
    art_b = Article(
        title="Volkswagen platform software update details",
        url="https://autonews.com/vw-platform-software-update",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["Volkswagen"],
        priority_score=80,
    )
    art_c = Article(
        title="Volkswagen recalls 120,000 vehicles over brake defect",
        url="https://nhtsa.gov/vw-brake-recall-2026",
        source="NHTSA",
        publisher="NHTSA",
        source_type="regulator",
        published_at=dt,
        entities=["Volkswagen"],
        priority_score=95,
    )

    events, event_articles, all_articles = cluster_articles([art_a, art_b, art_c])

    assert len(all_articles) == 3, "Clustering must NEVER remove articles"
    assert len(event_articles) == 3
    assert len(events) == 2, "Platform announcement and Brake recall must not merge"

    # Verify article cluster membership
    assert art_a.event_id is not None
    assert art_b.event_id is not None
    assert art_c.event_id is not None

    assert art_a.event_id == art_b.event_id, "Platform articles A and B should be in the same event"
    assert art_a.event_id != art_c.event_id, "Recall article C must NOT be in the platform event"


def test_false_positive_matrix():
    """Verify false-positive separation across 5 critical dimensions:

    1. Same company, different theme
    2. Same company, different model
    3. Different company, same theme
    4. Sister brand, different event
    5. Generic domain news vs specific brand announcement
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    # 1. Same company, different theme (Battery plant vs CEO change)
    a1 = Article(title="Volkswagen builds new solid-state battery gigafactory", url="https://ex.com/1", source="Reuters", published_at=dt, entities=["Volkswagen"])
    a2 = Article(title="Volkswagen CEO resigns unexpectedly after supervisory board meeting", url="https://ex.com/2", source="Reuters", published_at=dt, entities=["Volkswagen"])
    is_same_1, sim_1 = are_articles_same_event(a1, a2)
    assert not is_same_1
    assert sim_1 == 0.0

    # 2. Same company, different model (BMW i4 vs BMW iX3)
    b1 = Article(title="BMW rolls out software update for i4 electric sedan", url="https://ex.com/3", source="Automotive News", published_at=dt, entities=["BMW"])
    b2 = Article(title="BMW rolls out software update for iX3 electric SUV", url="https://ex.com/4", source="Automotive News", published_at=dt, entities=["BMW"])
    events_b, _, _ = cluster_articles([b1, b2])
    assert len(events_b) == 2

    # 3. Different company, same theme (Hyundai vs GM labor agreements)
    c1 = Article(title="Hyundai reaches tentative wage agreement with labor union", url="https://ex.com/5", source="Reuters", published_at=dt, entities=["Hyundai"])
    c2 = Article(title="General Motors reaches tentative wage agreement with labor union", url="https://ex.com/6", source="Reuters", published_at=dt, entities=["GM"])
    is_same_3, sim_3 = are_articles_same_event(c1, c2)
    assert not is_same_3
    assert sim_3 == 0.0

    # 4. Sister brand, different event (Porsche Taycan vs Audi e-tron)
    d1 = Article(title="Porsche reveals next-generation Taycan battery platform", url="https://ex.com/7", source="Automotive News", published_at=dt, entities=["Porsche"])
    d2 = Article(title="Audi reveals next-generation e-tron electric platform", url="https://ex.com/8", source="Automotive News", published_at=dt, entities=["Audi"])
    is_same_4, sim_4 = are_articles_same_event(d1, d2)
    assert not is_same_4
    assert sim_4 == 0.0

    # 5. Generic domain news vs specific brand announcement
    e1 = Article(title="Global automakers face rising vehicle software complexity", url="https://ex.com/9", source="Bloomberg", published_at=dt)
    e2 = Article(title="Mercedes-Benz unveils MB.OS software architecture in Stuttgart", url="https://ex.com/10", source="Reuters", published_at=dt, entities=["Mercedes"])
    is_same_5, sim_5 = are_articles_same_event(e1, e2)
    assert not is_same_5
    assert sim_5 <= 0.20


def test_cross_company_partnership_clustering():
    """Verify cross-company joint announcements:

    - Toyota x Nvidia joint announcement merges across multi-source reports
    - Toyota x Nvidia vs Mercedes x Nvidia remain strictly separated
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    art_toyota_nvidia_wire = Article(
        title="Toyota and Nvidia announce autonomous driving chip partnership",
        url="https://reuters.com/toyota-nvidia-1",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Toyota", "Nvidia"],
    )
    art_toyota_nvidia_trade = Article(
        title="Nvidia and Toyota partner on autonomous vehicle computing",
        url="https://autonews.com/toyota-nvidia-2",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["Toyota", "Nvidia"],
    )
    art_toyota_nvidia_official = Article(
        title="Toyota and NVIDIA Expand Strategic SDV Collaboration",
        url="https://toyota.com/press/nvidia-partnership",
        source="Toyota Newsroom",
        publisher="Toyota Newsroom",
        source_type="official",
        is_official=True,
        published_at=dt,
        entities=["Toyota", "Nvidia"],
    )
    art_mercedes_nvidia = Article(
        title="Mercedes-Benz and Nvidia expand automated driving computing deal",
        url="https://reuters.com/mercedes-nvidia-1",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Mercedes", "Nvidia"],
    )

    # 1. Toyota x Nvidia reports merge into 1 event
    events_tn, _, arts_tn = cluster_articles([art_toyota_nvidia_wire, art_toyota_nvidia_trade, art_toyota_nvidia_official])
    assert len(events_tn) == 1
    assert len(arts_tn) == 3
    assert events_tn[0].source_count == 3
    assert events_tn[0].has_official_source is True

    # 2. Toyota x Nvidia vs Mercedes x Nvidia must be strictly 2 separate events
    events_both, _, _ = cluster_articles([art_toyota_nvidia_wire, art_mercedes_nvidia])
    assert len(events_both) == 2, "Toyota x Nvidia and Mercedes x Nvidia must remain separate events"
    assert events_both[0].event_id != events_both[1].event_id

    is_same, sim = are_articles_same_event(art_toyota_nvidia_wire, art_mercedes_nvidia)
    assert not is_same
    assert sim == 0.0


def test_common_word_entity_collisions():
    """Verify common/short word disambiguation:

    - 'seat' as car seat vs SEAT automaker
    - 'ram' as computer memory / verb vs RAM trucks
    - 'mini' as adjective vs MINI brand
    - 'ford' person name vs Ford automaker
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    # 1. 'seat' disambiguation
    art_seat_interior = Article(
        title="Tesla recalls 10,000 vehicles over heated driver seat failure",
        url="https://ex.com/tesla-seat",
        source="Electrek",
        published_at=dt,
    )
    entities_seat_interior = extract_canonical_entities(art_seat_interior)
    assert "seat" not in entities_seat_interior, "Vehicle seat defect must not trigger SEAT automaker entity"
    assert "tesla" in entities_seat_interior

    art_seat_brand = Article(
        title="SEAT unveils new urban electric car concept in Martorell",
        url="https://ex.com/seat-martorell",
        source="Automotive News Europe",
        published_at=dt,
    )
    entities_seat_brand = extract_canonical_entities(art_seat_brand)
    assert "seat" in entities_seat_brand

    # 2. 'ram' disambiguation
    art_ram_tech = Article(
        title="Ford driver rams into guardrail with 16GB RAM in-dash infotainment",
        url="https://ex.com/ford-ram",
        source="The Verge",
        published_at=dt,
    )
    entities_ram_tech = extract_canonical_entities(art_ram_tech)
    assert "ram" not in entities_ram_tech, "Verb 'rams' or '16GB RAM' must not trigger RAM brand"
    assert "ford" in entities_ram_tech

    art_ram_truck = Article(
        title="Stellantis launches RAM 1500 electric pickup truck",
        url="https://ex.com/ram-1500",
        source="Reuters",
        published_at=dt,
    )
    entities_ram_truck = extract_canonical_entities(art_ram_truck)
    assert "ram" in entities_ram_truck
    assert "stellantis" in entities_ram_truck

    # 3. 'mini' disambiguation
    art_mini_adjective = Article(
        title="Mini excavator halts construction at new BMW battery factory",
        url="https://ex.com/bmw-excavator",
        source="Automotive News",
        published_at=dt,
    )
    entities_mini_adj = extract_canonical_entities(art_mini_adjective)
    assert "mini" not in entities_mini_adj, "Mini excavator must not trigger MINI brand"
    assert "bmw" in entities_mini_adj

    art_mini_cooper = Article(
        title="BMW Mini Cooper electric debuts at Munich auto show",
        url="https://ex.com/mini-cooper",
        source="Automotive News",
        published_at=dt,
    )
    entities_mini_brand = extract_canonical_entities(art_mini_cooper)
    assert "mini" in entities_mini_brand
    assert "bmw" in entities_mini_brand


def test_recall_clustering_precision():
    """Verify strict recall clustering precision:

    - Multi-source reports of the same recall merge into 1 event
    - Different defect types on same model remain separated
    - Same defect on different OEMs remain separated
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    # 1. Multi-source reports of same recall -> Merge into 1
    r_nhtsa = Article(
        title="Ford recalls 500,000 trucks over brake defect",
        url="https://nhtsa.gov/ford-brake",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
        entities=["Ford"],
        priority_score=95,
    )
    r_reuters = Article(
        title="Ford issues recall for 500,000 pickup trucks due to brake line issues",
        url="https://reuters.com/ford-brake-recall",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Ford"],
        priority_score=85,
    )
    r_an = Article(
        title="Brake defect prompts Ford recall of 500,000 trucks",
        url="https://autonews.com/ford-brake-trucks",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["Ford"],
        priority_score=80,
    )

    events_same, _, _ = cluster_articles([r_nhtsa, r_reuters, r_an])
    assert len(events_same) == 1, "Same recall reported by regulator and media must merge"
    assert events_same[0].primary_article_id == r_nhtsa.article_id
    assert events_same[0].source_count == 3
    assert events_same[0].has_regulatory_source is True

    # 2. Different defect types on same OEM -> Separate events
    r_airbag = Article(
        title="Ford recalls 100,000 SUVs over airbag inflator risk",
        url="https://nhtsa.gov/ford-airbag",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
        entities=["Ford"],
        priority_score=90,
    )
    events_diff_defects, _, _ = cluster_articles([r_nhtsa, r_airbag])
    assert len(events_diff_defects) == 2, "Brake recall and Airbag recall must not merge"

    # 3. Same defect on different OEMs -> Separate events
    r_gm_brake = Article(
        title="General Motors recalls 500,000 trucks over brake defect",
        url="https://nhtsa.gov/gm-brake",
        source="NHTSA",
        source_type="regulator",
        published_at=dt,
        entities=["GM"],
        priority_score=95,
    )
    events_diff_oems, _, _ = cluster_articles([r_nhtsa, r_gm_brake])
    assert len(events_diff_oems) == 2, "Ford brake recall and GM brake recall must not merge"


def test_coherence_metrics_calculation():
    """Verify EventCoherenceMetrics computes accurate diagnostic properties."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    a1 = Article(
        title="Volkswagen announces major restructuring",
        url="https://reuters.com/vw1",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Volkswagen"],
        priority_score=90,
    )
    a2 = Article(
        title="VW restructuring plans accelerate",
        url="https://autonews.com/vw2",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["Volkswagen"],
        priority_score=80,
    )

    metrics = compute_event_coherence_metrics([a1, a2], primary=a1)

    assert metrics.member_count == 2
    assert metrics.min_similarity >= 0.65
    assert metrics.avg_similarity >= 0.65
    assert "volkswagen" in metrics.entity_overlap
    assert "restructuring" in metrics.theme_overlap
    assert metrics.source_count == 2
    assert metrics.independent_source_count == 2
    assert metrics.is_suspicious is False


def test_cli_diagnose_clustering():
    """Verify diagnose-clustering CLI command runs and reports diagnostic summary."""
    from automotive_newsletter.cli import main

    # Running with sample fixture returns 0 (all healthy)
    code = main(["diagnose-clustering"])
    assert code == 0

    # Running with --strict flag on healthy synthetic fixture returns 0
    code_strict = main(["diagnose-clustering", "--strict"])
    assert code_strict == 0


def test_disjoint_tech_partner_guard():
    """Verify same automaker with disjoint tech partners strictly NEVER merges."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    # BMW + Qualcomm
    bmw_qualcomm_1 = Article(
        title="BMW and Qualcomm collaborate on automated driving compute platform",
        url="https://reuters.com/bmw-qualcomm",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["BMW", "Qualcomm"],
    )
    bmw_qualcomm_2 = Article(
        title="BMW selects Qualcomm Snapdragon Ride for automated driving systems",
        url="https://autonews.com/bmw-qualcomm-2",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["BMW", "Qualcomm"],
    )

    # BMW + Nvidia
    bmw_nvidia_1 = Article(
        title="BMW partners with Nvidia on next-generation cockpit AI assistant",
        url="https://reuters.com/bmw-nvidia",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["BMW", "Nvidia"],
    )
    bmw_nvidia_2 = Article(
        title="BMW taps Nvidia for in-vehicle generative AI cockpit platform",
        url="https://autonews.com/bmw-nvidia-2",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["BMW", "Nvidia"],
    )

    # 1. Same partner: must cluster together
    sim_qq = calculate_event_similarity(bmw_qualcomm_1, bmw_qualcomm_2)
    assert sim_qq >= 0.70, f"Expected high similarity for same partner, got {sim_qq}"

    sim_nn = calculate_event_similarity(bmw_nvidia_1, bmw_nvidia_2)
    assert sim_nn >= 0.70, f"Expected high similarity for same partner, got {sim_nn}"

    # 2. Disjoint partner (Qualcomm vs Nvidia): Guard D2 must reject with 0.0
    sim_qn = calculate_event_similarity(bmw_qualcomm_1, bmw_nvidia_1)
    assert sim_qn == 0.0, f"Disjoint partner guard failed: expected 0.0, got {sim_qn}"

    sim_qn_cross = calculate_event_similarity(bmw_qualcomm_2, bmw_nvidia_2)
    assert sim_qn_cross == 0.0, f"Disjoint partner guard failed: expected 0.0, got {sim_qn_cross}"

    # 3. Full clustering: BMW+Qualcomm and BMW+Nvidia must form two completely distinct events
    articles = [bmw_qualcomm_1, bmw_qualcomm_2, bmw_nvidia_1, bmw_nvidia_2]
    events, event_articles, all_arts = cluster_articles(articles)

    assert len(events) == 2, f"Expected 2 separate events, got {len(events)}"
    ev_ids = {a.event_id for a in all_arts}
    assert len(ev_ids) == 2

    # Verify event membership
    q_events = {a.event_id for a in all_arts if "qualcomm" in a.url}
    n_events = {a.event_id for a in all_arts if "nvidia" in a.url}
    assert q_events.isdisjoint(n_events), "Qualcomm articles and Nvidia articles were improperly merged!"


def test_supplier_disjoint_partner_guard():
    """Verify Mercedes with Bosch vs Continental remain separate events."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    mb_bosch = Article(
        title="Mercedes-Benz teams up with Bosch on automated valet parking",
        url="https://reuters.com/mb-bosch",
        source="Reuters",
        publisher="Reuters",
        published_at=dt,
        entities=["Mercedes-Benz", "Bosch"],
    )
    mb_continental = Article(
        title="Mercedes-Benz partners with Continental on brake-by-wire system",
        url="https://autonews.com/mb-conti",
        source="Automotive News",
        publisher="Automotive News",
        published_at=dt,
        entities=["Mercedes-Benz", "Continental"],
    )

    sim = calculate_event_similarity(mb_bosch, mb_continental)
    assert sim == 0.0, f"Expected 0.0 for disjoint suppliers, got {sim}"



