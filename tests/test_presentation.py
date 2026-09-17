from automotive_newsletter.models import Article
from automotive_newsletter.presentation import (
    filter_upcoming_conferences,
    display_summary_ko,
    display_title_ko,
    display_url,
    region_counts,
    regions_for_article,
    sort_articles_for_section,
    sort_articles_by_priority,
    visible_tags,
)


def test_display_title_ko_uses_korean_headline_without_original_english_title():
    article = Article(
        title="Hyundai Mobis joins S-Core project to advance SDV software platform development",
        url="https://example.com/mobis-sdv",
        source="Automotive World",
        category="sdv",
        tags=["Hyundai Mobis", "SDV"],
        score=76,
    )

    title = display_title_ko(article)

    assert "Hyundai Mobis" in title
    assert "SDV" in title
    assert "software platform development" not in title
    assert any(token in title for token in ["전략", "소프트웨어", "플랫폼"])


def test_display_summary_ko_strips_legacy_original_title_suffix():
    article = Article(
        title="Rivian software chief talks UX",
        url="https://example.com/rivian",
        source="The Verge",
        category="sdv",
        summary_ko="Rivian 관련 SDV 뉴스입니다. 핵심 신호는 차량 소프트웨어 경쟁력 강화입니다. 원문 제목: Rivian software chief talks UX",
    )

    assert display_summary_ko(article).endswith("경쟁력 강화입니다.")
    assert "원문 제목" not in display_summary_ko(article)


def test_display_url_hides_google_intermediary_links():
    article = Article(
        title="Supplier story",
        url="https://consent.google.com/ml?continue=https%3A%2F%2Fnews.google.com%2Frss%2Farticles%2Fabc",
        source="Google News",
        category="tier1",
    )

    assert display_url(article) is None
    assert display_url(Article(title="Direct", url="https://example.com/direct", source="Wire")) == "https://example.com/direct"


def test_sort_articles_by_priority_puts_largest_issue_first():
    low = Article(
        title="Supplier newsletter index",
        url="https://example.com/index",
        source="Official newsroom",
        category="institution",
        score=15,
    )
    high = Article(
        title="OEM recall investigation expands after regulator probe",
        url="https://example.com/recall",
        source="Reuters",
        category="oem",
        tags=["GM"],
        score=82,
    )

    assert sort_articles_by_priority([low, high])[0] == high


def test_regions_for_article_classifies_us_europe_asia_and_global():
    us = Article(
        title="GM expands software team in Detroit",
        url="https://example.com/gm",
        source="Reuters",
        category="sdv",
        tags=["GM", "SDV"],
    )
    europe = Article(
        title="Volkswagen and Bosch deepen SDV platform work in Germany",
        url="https://example.com/vw",
        source="Auto Wire",
        category="sdv",
        tags=["Volkswagen", "Bosch"],
    )
    asia = Article(
        title="Toyota and Hyundai Mobis show new vehicle software in Tokyo",
        url="https://example.com/tokyo",
        source="Auto Wire",
        category="conference",
        tags=["Toyota", "Hyundai Mobis"],
    )
    global_article = Article(
        title="Automotive supplier quality outlook",
        url="https://example.com/outlook",
        source="Industry Index",
        category="institution",
    )

    assert [region.key for region in regions_for_article(us)] == ["us"]
    assert [region.key for region in regions_for_article(europe)] == ["europe"]
    assert [region.key for region in regions_for_article(asia)] == ["asia"]
    assert [region.key for region in regions_for_article(global_article)] == ["global"]


def test_region_counts_counts_articles_per_filter():
    articles = [
        Article(title="GM Detroit update", url="https://example.com/gm", source="Wire"),
        Article(title="Volkswagen Germany update", url="https://example.com/vw", source="Wire"),
        Article(title="Toyota Tokyo update", url="https://example.com/toyota", source="Wire"),
        Article(title="General automotive outlook", url="https://example.com/global", source="Wire"),
    ]

    counts = region_counts(articles)

    assert counts["all"] == 4
    assert counts["us"] == 1
    assert counts["europe"] == 1
    assert counts["asia"] == 1
    assert counts["global"] == 1


def test_conference_display_hides_past_events_and_sorts_by_event_date():
    past = Article(
        title="Past Event | 2026년 6월 2-4일 · Novi",
        url="https://example.com/past",
        source="공식 사이트",
        category="conference",
        tags=["event_start:2026-06-02", "event_end:2026-06-04"],
        score=99,
    )
    later = Article(
        title="Later Event | 2026년 9월 15-20일 · Hannover",
        url="https://example.com/later",
        source="공식 사이트",
        category="conference",
        tags=["event_start:2026-09-15", "event_end:2026-09-20"],
        score=99,
    )
    earlier = Article(
        title="Earlier Event | 2026년 6월 9-11일 · Stuttgart",
        url="https://example.com/earlier",
        source="공식 사이트",
        category="conference",
        tags=["event_start:2026-06-09", "event_end:2026-06-11"],
        score=50,
    )

    upcoming = filter_upcoming_conferences([past, later, earlier], "2026-06-08")
    sorted_conferences = sort_articles_for_section("conference", [past, later, earlier], "2026-06-08")

    assert past not in upcoming
    assert [article.title for article in sorted_conferences] == [earlier.title, later.title]
    assert visible_tags(earlier) == []


def test_display_event_coverage():
    from automotive_newsletter.presentation import display_event_coverage

    art_single = Article(title="Standalone news", url="https://example.com/1", source="Wire")
    assert display_event_coverage(art_single) is None

    art_clustered = Article(
        title="Major news",
        url="https://example.com/2",
        source="Wire",
        related_article_ids=["art_3", "art_4", "art_5"],
    )
    cov = display_event_coverage(art_clustered)
    assert cov is not None
    assert cov["count"] == 4
    assert cov["label_ko"] == "4개 매체 보도 중"
    assert cov["label_en"] == "4 sources covering this event"
