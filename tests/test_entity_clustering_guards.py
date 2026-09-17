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
    """Verify that sister brands with disjoint entities merge ONLY if explicit joint signals exist."""
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    # 1. Without explicit joint signal: sister brands MUST NOT merge
    a_vw_alone = Article(
        title="Volkswagen announces major European manufacturing restructuring",
        url="https://reuters.com/vw-restructure-europe",
        source="Reuters",
        published_at=dt,
        entities=["Volkswagen"],
    )
    a_audi_alone = Article(
        title="Audi announces major European manufacturing restructuring",
        url="https://autonews.com/audi-restructure-europe",
        source="Automotive News",
        published_at=dt,
        entities=["Audi"],
    )
    is_same_alone, sim_alone = are_articles_same_event(a_vw_alone, a_audi_alone)
    assert not is_same_alone
    assert sim_alone == 0.0

    # 2. With explicit joint signal: sister brands merge
    a_vw_joint = Article(
        title="Volkswagen and Audi announce joint European manufacturing restructuring program",
        url="https://reuters.com/vw-audi-joint",
        source="Reuters",
        published_at=dt,
        entities=["Volkswagen", "Audi"],
    )
    a_audi_joint = Article(
        title="Audi and Volkswagen confirm same restructuring program across European plants",
        url="https://autonews.com/audi-vw-joint",
        source="Automotive News",
        published_at=dt,
        entities=["Audi", "Volkswagen"],
    )

    is_same, sim = are_articles_same_event(a_vw_joint, a_audi_joint)
    assert is_same
    assert sim >= 0.65

    events, _, _ = cluster_articles([a_vw_joint, a_audi_joint])
    assert len(events) == 1


def test_ambiguous_entity_regression_benchmarks():
    """Verify exact news-style sentences for ambiguous entities (SEAT, Ford, Lotus, GM, ZF)."""
    # 1. SEAT
    art_seat_neg = Article(title="The driver adjusted the seat before departure", url="https://example.com/1", source="AutoBlog")
    assert "seat" not in extract_canonical_entities(art_seat_neg)

    art_seat_pos = Article(title="SEAT announces new EV strategy", url="https://example.com/2", source="Reuters")
    assert "seat" in extract_canonical_entities(art_seat_pos)

    # 2. Ford
    art_ford_neg = Article(title="Harrison Ford stars in a new film", url="https://example.com/3", source="Variety")
    assert "ford" not in extract_canonical_entities(art_ford_neg)

    art_ford_pos = Article(title="Ford announces new EV investment", url="https://example.com/4", source="Reuters")
    assert "ford" in extract_canonical_entities(art_ford_pos)

    # 3. Lotus
    art_lotus_neg = Article(title="The sacred lotus flower blooms across the pond", url="https://example.com/5", source="Nature")
    assert "lotus" not in extract_canonical_entities(art_lotus_neg)

    art_lotus_pos = Article(title="Lotus Cars unveils new EV", url="https://example.com/6", source="Automotive News")
    assert "lotus" in extract_canonical_entities(art_lotus_pos)

    # 4. GM
    art_gm_pos = Article(title="GM announces new electric vehicle strategy", url="https://example.com/7", source="Bloomberg")
    assert "gm" in extract_canonical_entities(art_gm_pos)

    art_gm_neg = Article(title="10 gm of material was added during test", url="https://example.com/8", source="LabDaily")
    assert "gm" not in extract_canonical_entities(art_gm_neg)

    # 5. ZF
    art_zf_pos = Article(title="ZF announces new automotive transmission", url="https://example.com/9", source="Reuters")
    assert "zf" in extract_canonical_entities(art_zf_pos)

    art_zf_neg = Article(title="Nikon Zf camera with retro dial design reviewed", url="https://example.com/10", source="DPR")
    assert "zf" not in extract_canonical_entities(art_zf_neg)


def test_source_and_publisher_contamination_prevention():
    """Verify that journalistic media sources/publishers do not contaminate article entities."""
    # Automotive News as publisher
    art_an = Article(
        title="New battery technology discovered for long-range commercial vehicles",
        url="https://autonews.com/battery-breakthrough",
        source="Automotive News",
        publisher="Automotive News",
        source_type="media",
    )
    entities_an = extract_canonical_entities(art_an)
    assert "automotive_news" not in entities_an

    # WardsAuto as publisher
    art_wards = Article(
        title="Rivian CEO announces production ramp for R2 platform",
        url="https://wardsauto.com/rivian-ramp",
        source="WardsAuto",
        publisher="WardsAuto",
        source_type="media",
    )
    entities_wards = extract_canonical_entities(art_wards)
    assert "rivian" in entities_wards
    assert "wardsauto" not in entities_wards

    # Reuters as source
    art_reuters = Article(
        title="Global auto sales rebound in August following supply chain recovery",
        url="https://reuters.com/sales-rebound",
        source="Reuters",
        publisher="Reuters",
        source_type="media",
    )
    entities_reuters = extract_canonical_entities(art_reuters)
    assert "reuters" not in entities_reuters

    # Official OEM newsroom (e.g. Volkswagen Newsroom) properly attributes company even if title omits brand
    art_official = Article(
        title="Next-generation scalable EV architecture unveiled for 2027",
        url="https://volkswagen-newsroom.com/release-123",
        source="Volkswagen Newsroom",
        publisher="Volkswagen Newsroom",
        source_type="official",
        is_official=True,
    )
    entities_official = extract_canonical_entities(art_official)
    assert "volkswagen" in entities_official


def test_entity_matches_provenance_and_confidence():
    """Verify EntityMatch accurately tracks match provenance (title, rss_summary, content, official attribution)."""
    from automotive_newsletter.entity_registry import extract_entity_matches

    # 1. Title provenance
    art_title = Article(
        title="BMW announces solid-state battery testing program",
        url="https://example.com/bmw",
        source="TechMedia",
    )
    matches_title = extract_entity_matches(art_title)
    assert any(m.entity == "bmw" and m.source == "title" and m.confidence == 1.0 for m in matches_title)

    # 2. RSS summary / excerpt provenance
    art_excerpt = Article(
        title="Massive breakthrough in solid-state cells reported",
        url="https://example.com/excerpt",
        source="TechMedia",
        excerpt="Toyota researchers confirmed laboratory milestones for 2027.",
    )
    matches_excerpt = extract_entity_matches(art_excerpt)
    assert any(m.entity == "toyota" and m.source == "rss_summary" and m.confidence == 0.9 for m in matches_excerpt)

    # 3. Content provenance
    art_content = Article(
        title="Electric vehicle manufacturing investments ramp up in North America",
        url="https://example.com/content",
        source="TechMedia",
        content="Hyundai Motor Group is constructing a dedicated megasite for electric vehicles and batteries.",
    )
    matches_content = extract_entity_matches(art_content)
    assert any(m.entity == "hyundai" and m.source == "content" and m.confidence == 0.8 for m in matches_content)

    # 4. Publisher attribution for official newsroom
    art_official = Article(
        title="Quarterly delivery numbers and financial outlook for investors",
        url="https://press.bmwgroup.com/release-q3",
        source="BMW Group PressClub",
        publisher="BMW Group PressClub",
        source_type="official",
        is_official=True,
    )
    matches_official = extract_entity_matches(art_official)
    assert any(m.entity == "bmw" and m.source == "publisher_attribution" and m.confidence == 0.95 for m in matches_official)


def test_expanded_publisher_contamination_regression():
    """Verify exhaustive list of journalistic publishers never contaminate entities, while official newsrooms attribute OEMs."""
    from automotive_newsletter.entity_registry import extract_canonical_entities

    media_publishers = [
        ("Reuters", "https://reuters.com/article-1"),
        ("Bloomberg", "https://bloomberg.com/article-2"),
        ("AP", "https://apnews.com/article-3"),
        ("Automotive News", "https://autonews.com/article-4"),
        ("WardsAuto", "https://wardsauto.com/article-5"),
        ("Autocar", "https://autocar.co.uk/article-6"),
        ("MotorTrend", "https://motortrend.com/article-7"),
        ("Car and Driver", "https://caranddriver.com/article-8"),
        ("Electrek", "https://electrek.co/article-9"),
        ("The Verge", "https://theverge.com/article-10"),
        ("TechCrunch", "https://techcrunch.com/article-11"),
    ]

    for pub_name, pub_url in media_publishers:
        art = Article(
            title="Battery supply chain challenges emerge amid increasing EV adoption",
            url=pub_url,
            source=pub_name,
            publisher=pub_name,
            source_type="media",
        )
        entities = extract_canonical_entities(art)
        assert len(entities) == 0, f"Media publisher {pub_name} contaminated article entities: {entities}"

    # Official newsrooms
    official_newsrooms = [
        ("Volkswagen Newsroom", "volkswagen"),
        ("BMW Group PressClub", "bmw"),
        ("Mercedes-Benz Media", "mercedes"),
        ("Toyota Newsroom", "toyota"),
        ("Hyundai Newsroom", "hyundai"),
    ]

    for source_name, expected_oem in official_newsrooms:
        art_oem = Article(
            title="Strategic electrification roadmap revealed for global markets",
            url=f"https://press.{expected_oem}.com/release",
            source=source_name,
            publisher=source_name,
            source_type="official",
            is_official=True,
        )
        entities = extract_canonical_entities(art_oem)
        assert expected_oem in entities, f"Expected {expected_oem} from {source_name}, got {entities}"


def test_explicit_article_entities_additive_evidence():
    """Verify that structured article.entities contribute additive canonical entities safely."""
    from automotive_newsletter.entity_registry import (
        extract_canonical_entities,
        extract_entity_matches,
    )

    # 1. Title BMW + structured Qualcomm/Nvidia entities both survive
    art_additive = Article(
        title="BMW announces new automated driving platform",
        url="https://example.com/bmw-platform",
        source="Reuters",
        publisher="Reuters",
        entities=["BMW", "Qualcomm", "Nvidia"],
    )
    entities = extract_canonical_entities(art_additive)
    assert entities == {"bmw", "qualcomm", "nvidia"}

    # Provenance and confidence check
    matches = extract_entity_matches(art_additive)
    bmw_m = next(m for m in matches if m.entity == "bmw")
    assert bmw_m.source == "title"
    assert bmw_m.confidence == 1.0

    qc_m = next(m for m in matches if m.entity == "qualcomm")
    assert qc_m.source == "explicit_article_entity"
    assert qc_m.confidence == 0.95

    nv_m = next(m for m in matches if m.entity == "nvidia")
    assert nv_m.source == "explicit_article_entity"
    assert nv_m.confidence == 0.95

    # 2. Media publisher entities in structured entities are filtered
    art_media = Article(
        title="BMW announces new automated driving platform",
        url="https://example.com/bmw-media",
        source="Reuters",
        publisher="Reuters",
        entities=["BMW", "Reuters", "Bloomberg", "WardsAuto"],
    )
    assert extract_canonical_entities(art_media) == {"bmw"}

    # 3. Arbitrary non-canonical entity strings are safely ignored
    art_arbitrary = Article(
        title="BMW announces new automated driving platform",
        url="https://example.com/bmw-arbitrary",
        source="Reuters",
        publisher="Reuters",
        entities=["BMW", "NonExistentCompanyXYZ", "some_random_string"],
    )
    assert extract_canonical_entities(art_arbitrary) == {"bmw"}

    # 4. Existing title/excerpt behavior remains unchanged when article.entities is empty
    art_plain = Article(
        title="Toyota announces new battery factory in North Carolina",
        url="https://example.com/toyota-plain",
        source="Reuters",
        publisher="Reuters",
        excerpt="The Japanese automaker invests heavily in battery cells.",
    )
    assert extract_canonical_entities(art_plain) == {"toyota"}


