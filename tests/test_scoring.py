from __future__ import annotations

from datetime import datetime, timedelta, timezone

from automotive_newsletter.models import Article
from automotive_newsletter.scoring import (
    compute_impact_score,
    compute_multi_dimensional_scores,
    compute_novelty_score,
    compute_recency_score,
    compute_relevance_score,
    compute_source_score,
)


def test_source_score_hierarchy():
    regulator_art = Article(
        title="NHTSA issues new guidance",
        url="https://nhtsa.gov/1",
        source="NHTSA",
        source_type="regulator",
    )
    reuters_art = Article(
        title="Automaker reports earnings",
        url="https://reuters.com/1",
        source="Reuters",
        source_type="media",
    )
    trade_press_art = Article(
        title="Supplier develops new radar",
        url="https://autonews.com/1",
        source="Automotive News",
        source_type="media",
    )
    oem_art = Article(
        title="Toyota unveils new EV battery line",
        url="https://toyota.com/pr",
        source="Toyota Newsroom",
        source_type="official",
    )
    aggregator_art = Article(
        title="Auto Roundup",
        url="https://news.google.com/1",
        source="Google News",
        source_type="aggregator",
    )

    reg_score = compute_source_score(regulator_art)
    reuters_score = compute_source_score(reuters_art)
    trade_score = compute_source_score(trade_press_art)
    oem_score = compute_source_score(oem_art)
    agg_score = compute_source_score(aggregator_art)

    assert reg_score >= 90.0
    assert reuters_score >= 88.0
    assert trade_score >= 85.0
    assert oem_score >= 80.0
    assert agg_score < 70.0
    assert reg_score > trade_score > agg_score


def test_relevance_score_prioritizes_sdv_and_vehicle_software():
    sdv_art = Article(
        title="BMW adopts Adaptive AUTOSAR and Zonal Architecture for new EV lineup",
        url="https://example.com/sdv",
        source="Auto Tech",
        category="sdv",
        topics=["SDV", "Adaptive AUTOSAR", "Zonal Architecture", "OTA"],
        excerpt="The architecture supports vehicle OS and over-the-air updates.",
    )
    linux_art = Article(
        title="Automaker migrates in-vehicle infotainment to Android Automotive and Embedded Linux with Yocto",
        url="https://example.com/linux",
        source="Linux Foundation",
        category="software",
        topics=["Vehicle OS", "Android Automotive", "Embedded Linux", "Yocto"],
        excerpt="The middleware stack leverages QNX for safety and Yocto for infotainment.",
    )
    generic_art = Article(
        title="Local dealership hosts annual summer discount event in Ohio",
        url="https://example.com/dealer",
        source="Local Media",
        category="market",
        excerpt="Customers can get discounts on selected compact cars.",
    )

    sdv_score = compute_relevance_score(sdv_art)
    linux_score = compute_relevance_score(linux_art)
    gen_score = compute_relevance_score(generic_art)

    assert sdv_score >= 80.0
    assert linux_score >= 80.0
    assert gen_score <= 40.0
    assert sdv_score > gen_score


def test_impact_score_detects_major_signals():
    # Test major investment and strategic partnership
    partner_art = Article(
        title="GM and LG Energy Solution announce $3 billion investment for new gigafactory joint venture",
        url="https://example.com/jv",
        source="Reuters",
        category="ev_battery",
        excerpt="The $3 billion capex expands battery cell production under a multi-year supply contract.",
    )
    # Test recall and regulator investigation
    recall_art = Article(
        title="Regulator opens safety probe into steering defect triggering 500,000 vehicle recall",
        url="https://example.com/recall",
        source="Reuters",
        category="regulation",
        excerpt="NHTSA investigation into potential safety defect and recall.",
    )
    minor_art = Article(
        title="Car designer shares sketches of concept vehicle",
        url="https://example.com/sketches",
        source="Design Blog",
        category="market",
        excerpt="The designer released stylistic sketches on personal social media.",
    )

    partner_score = compute_impact_score(partner_art)
    recall_score = compute_impact_score(recall_art)
    minor_score = compute_impact_score(minor_art)

    assert partner_score >= 70.0
    assert recall_score >= 70.0
    assert minor_score <= 40.0
    assert partner_score > minor_score


def test_novelty_score_penalizes_duplicates_and_evergreen():
    past = [
        Article(
            title="Tesla launches Cybercab robotaxi in California",
            url="https://example.com/tesla-past",
            source="Reuters",
        )
    ]
    duplicate_art = Article(
        title="Tesla launches Cybercab robotaxi California event",
        url="https://example.com/tesla-dup",
        source="Bloomberg",
    )
    evergreen_art = Article(
        title="What is SDV? An Overview and Buyer's Guide to Software-Defined Vehicles",
        url="https://example.com/guide",
        source="Blog",
        excerpt="A guide to what is SDV and how to understand automotive software.",
    )
    fresh_art = Article(
        title="Qualcomm reveals Snapdragon Ride Flex multi-domain cockpit processor",
        url="https://example.com/qualcomm",
        source="Tech Auto",
        excerpt="New multi-domain SoC announced today at developer conference.",
    )

    dup_score = compute_novelty_score(duplicate_art, past_articles=past)
    evergreen_score = compute_novelty_score(evergreen_art)
    fresh_score = compute_novelty_score(fresh_art, past_articles=past)

    assert fresh_score >= 85.0
    assert dup_score < 70.0
    assert evergreen_score < 60.0
    assert fresh_score > dup_score
    assert fresh_score > evergreen_score


def test_recency_score_decay():
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    half_life = 36.0

    recent_art = Article(
        title="Just in",
        url="https://example.com/now",
        source="Wire",
        published_at=now - timedelta(hours=2),
    )
    day_old_art = Article(
        title="Yesterday",
        url="https://example.com/yesterday",
        source="Wire",
        published_at=now - timedelta(hours=36),  # 1 half-life
    )
    stale_art = Article(
        title="Last week",
        url="https://example.com/stale",
        source="Wire",
        published_at=now - timedelta(hours=144),  # 4 half-lives
    )
    undated_art = Article(
        title="No date",
        url="https://example.com/nodate",
        source="Wire",
        published_at=None,
    )

    rec_score = compute_recency_score(recent_art, ref_time=now, half_life_hours=half_life)
    day_score = compute_recency_score(day_old_art, ref_time=now, half_life_hours=half_life)
    stale_score = compute_recency_score(stale_art, ref_time=now, half_life_hours=half_life)
    undated_score = compute_recency_score(undated_art, ref_time=now, half_life_hours=half_life)

    assert rec_score >= 90.0
    assert 45.0 <= day_score <= 55.0  # Exactly 1 half-life = ~50%
    assert stale_score < 20.0
    assert undated_score == 50.0


def test_multi_dimensional_scores_and_explanation():
    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    article = Article(
        title="Mercedes-Benz and Bosch deploy level 3 autonomous driving with zonal architecture",
        url="https://example.com/mb-bosch",
        source="Reuters",
        source_type="media",
        category="sdv",
        topics=["SDV", "Zonal Architecture", "Autonomous Driving", "ADAS"],
        excerpt="The companies announced major commercial deployment and multi-year supply partnership.",
        published_at=now - timedelta(hours=4),
    )

    result = compute_multi_dimensional_scores(article, ref_time=now)

    assert result.source_score >= 85.0
    assert result.relevance_score >= 80.0
    assert result.impact_score >= 65.0
    assert result.novelty_score >= 80.0
    assert result.recency_score >= 85.0
    assert result.priority_score >= 80.0

    # Explainability checks
    exp = result.explanation
    assert any("소프트웨어" in r or "SDV" in r for r in exp.reasons_ko)
    assert any("High software & SDV relevance" in r for r in exp.reasons_en)
    assert any("이슈화" in r or "산업" in r for r in exp.reasons_ko)
    assert any("출처" in r for r in exp.reasons_ko)
    assert exp.summary_ko
    assert exp.summary_en
