from __future__ import annotations

from datetime import datetime, timezone

import pytest

from automotive_newsletter.clustering import (
    are_articles_same_event,
    canonical_entity,
    cluster_articles,
    extract_canonical_entities,
    extract_parent_groups,
    parent_group,
)
from automotive_newsletter.models import Article


def test_canonical_entity_mapping():
    """Verify canonical entity resolution for brands and aliases."""
    assert canonical_entity("Kia") == "kia"
    assert canonical_entity("기아") == "kia"
    assert canonical_entity("Hyundai") == "hyundai"
    assert canonical_entity("현대차") == "hyundai"
    assert canonical_entity("Audi") == "audi"
    assert canonical_entity("Volkswagen") == "volkswagen"
    assert canonical_entity("VW") == "volkswagen"
    assert canonical_entity("Porsche") == "porsche"
    assert canonical_entity("Toyota") == "toyota"
    assert canonical_entity("Lexus") == "lexus"
    assert canonical_entity("Volvo") == "volvo"
    assert canonical_entity("Polestar") == "polestar"
    assert canonical_entity("Geely") == "geely"
    assert canonical_entity("GM") == "gm"
    assert canonical_entity("Chevrolet") == "chevrolet"
    assert canonical_entity("Stellantis") == "stellantis"
    assert canonical_entity("Jeep") == "jeep"

    # None and empty
    assert canonical_entity("") is None
    assert canonical_entity(None) is None  # type: ignore[arg-type]


def test_parent_group_mapping():
    """Verify parent corporate group resolution as a weak contextual signal."""
    # Hyundai Motor Group
    assert parent_group("kia") == "Hyundai Motor Group"
    assert parent_group("hyundai") == "Hyundai Motor Group"
    assert parent_group("genesis") == "Hyundai Motor Group"

    # Volkswagen Group
    assert parent_group("volkswagen") == "Volkswagen Group"
    assert parent_group("audi") == "Volkswagen Group"
    assert parent_group("porsche") == "Volkswagen Group"
    assert parent_group("skoda") == "Volkswagen Group"

    # Toyota Group
    assert parent_group("toyota") == "Toyota Group"
    assert parent_group("lexus") == "Toyota Group"

    # Geely Holding Group
    assert parent_group("volvo") == "Geely Holding Group"
    assert parent_group("polestar") == "Geely Holding Group"
    assert parent_group("geely") == "Geely Holding Group"

    # General Motors
    assert parent_group("gm") == "General Motors"
    assert parent_group("chevrolet") == "General Motors"
    assert parent_group("cadillac") == "General Motors"

    # Stellantis
    assert parent_group("stellantis") == "Stellantis"
    assert parent_group("jeep") == "Stellantis"
    assert parent_group("peugeot") == "Stellantis"

    # Unknown
    assert parent_group("unknown_brand") is None
    assert parent_group("") is None


def test_entity_extraction_does_not_pollute_brand_with_parent():
    """Verify taxonomy entity groupings do not pollute article canonical entity."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    # Article has Audi in title, but taxonomy might set entities to ["Volkswagen"]
    audi_art = Article(
        title="Audi announces new EV architecture for luxury models",
        url="https://example.com/audi-ev",
        source="Automotive News",
        published_at=dt,
        entities=["Volkswagen"],  # OEM taxonomy group
    )

    entities = extract_canonical_entities(audi_art)
    assert "audi" in entities
    assert "volkswagen" not in entities

    groups = extract_parent_groups(audi_art)
    assert "Volkswagen Group" in groups


@pytest.mark.parametrize(
    ("title1", "source1", "title2", "source2", "brand1", "brand2"),
    [
        # Pair 1: Hyundai vs Kia
        (
            "Hyundai announces new SDV platform",
            "Reuters",
            "Kia announces new infotainment platform",
            "Automotive News",
            "hyundai",
            "kia",
        ),
        # Pair 2: Volvo vs Polestar
        (
            "Volvo announces major restructuring and cost cuts",
            "Reuters",
            "Polestar reveals new sports car concept",
            "Autocar",
            "volvo",
            "polestar",
        ),
        # Pair 3: Volvo vs Geely
        (
            "Volvo expands electric SUV lineup in Europe",
            "Automotive News",
            "Geely launches new satellite communication network",
            "Bloomberg",
            "volvo",
            "geely",
        ),
        # Pair 4: Volkswagen vs Audi
        (
            "Volkswagen announces restructuring measures for plants",
            "Reuters",
            "Audi unveils new Q6 e-tron electric SUV",
            "Automotive News",
            "volkswagen",
            "audi",
        ),
        # Pair 5: Volkswagen vs Porsche
        (
            "Volkswagen cuts European operations amid cost review",
            "Bloomberg",
            "Porsche reports record Q3 operating profit",
            "Reuters",
            "volkswagen",
            "porsche",
        ),
        # Pair 6: Toyota vs Lexus
        (
            "Toyota recalls 500,000 vehicles over steering defect",
            "NHTSA",
            "Lexus unveils next-gen luxury EV sedan",
            "Automotive News",
            "toyota",
            "lexus",
        ),
        # Pair 7: GM vs Chevrolet
        (
            "General Motors signs strategic battery raw materials deal",
            "Reuters",
            "Chevrolet Corvette ZR1 breaks production speed record",
            "MotorTrend",
            "gm",
            "chevrolet",
        ),
        # Pair 8: Stellantis vs Jeep
        (
            "Stellantis announces executive leadership changes",
            "Automotive News",
            "Jeep introduces hybrid Wrangler in North America",
            "Car and Driver",
            "stellantis",
            "jeep",
        ),
    ],
)
def test_distinct_brands_under_same_parent_group_not_merged(
    title1: str,
    source1: str,
    title2: str,
    source2: str,
    brand1: str,
    brand2: str,
):
    """Verify that distinct brands under the same parent group are NOT merged."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    a1 = Article(
        title=title1,
        url=f"https://example.com/art1-{brand1}",
        source=source1,
        published_at=dt,
    )
    a2 = Article(
        title=title2,
        url=f"https://example.com/art2-{brand2}",
        source=source2,
        published_at=dt,
    )

    # 1. are_articles_same_event must return False
    is_same, sim = are_articles_same_event(a1, a2)
    assert not is_same, f"Articles for {brand1} and {brand2} should not be merged: {title1} vs {title2}"
    assert sim == 0.0

    # 2. cluster_articles must produce 2 distinct events
    events, event_articles, all_articles = cluster_articles([a1, a2])
    assert len(events) == 2
    assert len(all_articles) == 2
    assert events[0].event_id != events[1].event_id


def test_same_brand_across_publishers_merges_successfully():
    """Verify that the same brand across different sources still clusters correctly."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    a1 = Article(
        title="Volkswagen announces major restructuring plans",
        url="https://reuters.com/vw-restruct",
        source="Reuters",
        published_at=dt,
    )
    a2 = Article(
        title="VW restructuring plans accelerate across plants",
        url="https://autonews.com/vw-restruct-plans",
        source="Automotive News",
        published_at=dt,
    )

    is_same, sim = are_articles_same_event(a1, a2)
    assert is_same
    assert sim > 0.4

    events, event_articles, all_articles = cluster_articles([a1, a2])
    assert len(events) == 1
    assert len(all_articles) == 2


def test_joint_parent_group_initiative_with_strong_signals_merges():
    """Verify that when sister brands share strong joint signals, they merge."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    a1 = Article(
        title="Hyundai and Kia announce joint next-generation SDV software platform",
        url="https://reuters.com/hyundai-kia-sdv",
        source="Reuters",
        published_at=dt,
    )
    a2 = Article(
        title="Kia and Hyundai unveil new joint SDV software platform",
        url="https://autonews.com/kia-hyundai-unified-sdv",
        source="Automotive News",
        published_at=dt,
    )

    is_same, sim = are_articles_same_event(a1, a2)
    assert is_same
    assert sim > 0.0

    events, event_articles, all_articles = cluster_articles([a1, a2])
    assert len(events) == 1
    assert len(all_articles) == 2


def test_disjoint_brands_with_strong_joint_event_merges():
    """Verify that sister brands with disjoint entities merge if strong joint signals exist."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    # Volkswagen announces European manufacturing restructuring
    # Audi announces European manufacturing restructuring (part of same group initiative)
    a_vw = Article(
        title="Volkswagen announces major European manufacturing restructuring",
        url="https://reuters.com/vw-restructure-europe",
        source="Reuters",
        published_at=dt,
    )
    a_audi = Article(
        title="Audi announces major European manufacturing restructuring",
        url="https://autonews.com/audi-restructure-europe",
        source="Automotive News",
        published_at=dt,
    )

    # c1 is {'volkswagen'}, c2 is {'audi'} -> disjoint brands under same parent group
    # but tokens overlap strongly (5 tokens) and same restructuring theme
    is_same, sim = are_articles_same_event(a_vw, a_audi)
    assert is_same
    assert sim > 0.5

    events, _, _ = cluster_articles([a_vw, a_audi])
    assert len(events) == 1
