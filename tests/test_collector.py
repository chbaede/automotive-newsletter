from datetime import date, datetime, timezone

from automotive_newsletter.collector import (
    build_issue_articles,
    check_feed_health,
    collect_from_entries,
    conference_fallback_articles,
    ensure_required_fallbacks,
    resolve_original_url,
)
from automotive_newsletter.models import Article
from automotive_newsletter.models import FeedEntry
from automotive_newsletter.sources import DEFAULT_FEEDS


def test_collect_from_entries_deduplicates_and_groups_relevant_articles():
    entries = [
        FeedEntry(
            title="Hyundai Mobis unveils SDV platform for global OEMs",
            url="https://example.com/hyundai-mobis-sdv",
            source="Mobility Wire",
            bucket="tier1",
            published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
            excerpt="Supplier software platform for automakers.",
        ),
        FeedEntry(
            title="Hyundai Mobis unveils SDV platform for global OEMs",
            url="https://example.com/hyundai-mobis-sdv?utm=feed",
            source="Mobility Wire",
            bucket="tier1",
            published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
            excerpt="Duplicate.",
        ),
        FeedEntry(
            title="IAA Mobility announces software vehicle conference program",
            url="https://example.com/iaa-sdv",
            source="Event News",
            bucket="conference",
            published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
            excerpt="Conference agenda includes SDV and suppliers.",
        ),
    ]

    articles, warnings = collect_from_entries(entries)

    assert warnings == []
    assert len(articles) == 2
    assert articles[0].score >= articles[1].score
    assert {article.category for article in articles} == {"sdv", "conference"}


def test_build_issue_articles_keeps_each_section_under_limit():
    articles = [
        FeedEntry(
            title=f"Toyota SDV update {index}",
            url=f"https://example.com/{index}",
            source="Wire",
            bucket="sdv",
        )
        for index in range(10)
    ]

    issue_articles = build_issue_articles(articles, per_section=3)

    assert len(issue_articles) == 3


def test_build_issue_articles_prefers_direct_source_links_over_google_intermediaries():
    direct_entries = [
        FeedEntry(
            title=f"Bosch supplier software update {index}",
            url=f"https://supplier.example.com/news/{index}",
            source="Supplier News",
            bucket="tier1",
        )
        for index in range(8)
    ]
    google_entry = FeedEntry(
        title="Bosch supplier software update from Google",
        url="https://consent.google.com/ml?continue=https%3A%2F%2Fnews.google.com%2Frss%2Farticles%2Fabc",
        source="Google News",
        bucket="tier1",
    )

    issue_articles = build_issue_articles([*direct_entries, google_entry], per_section=10)

    assert issue_articles
    assert all("google.com" not in article.url for article in issue_articles)


def test_ensure_conference_fallback_adds_official_event_links():
    issue_articles = ensure_required_fallbacks([], issue_date="2026-01-01")

    conferences = [article for article in issue_articles if article.category == "conference"]
    assert len(conferences) >= 12
    assert any("ces.tech" in article.url for article in conferences)
    assert any("iaa-transportation.com" in article.url for article in conferences)
    assert all("google.com" not in article.url for article in conferences)


def test_ensure_required_fallbacks_adds_supplier_newsroom_links():
    issue_articles = ensure_required_fallbacks([])

    assert any(article.category == "tier1" for article in issue_articles)
    assert any("bosch" in article.url for article in issue_articles)


def test_conference_fallback_hides_past_events_and_sorts_by_date():
    conferences = conference_fallback_articles(on_date=date(2026, 6, 8))

    titles = [article.title for article in conferences]

    assert "2026 CES" not in " ".join(titles)
    assert "AutoTech Detroit" not in " ".join(titles)
    assert titles[0].startswith("The Battery Show Europe 2026 | 2026년 6월 9-11일")
    assert titles[1].startswith("Autonomous Vehicle Technology Expo Europe | 2026년 6월 23-25일")
    assert all("2026년" in title for title in titles)
    assert all("종료" not in article.tags for article in conferences)


def test_ensure_required_fallbacks_replaces_institution_google_links_with_direct_sources():
    issue_articles = ensure_required_fallbacks(
        [
            Article(
                title="McKinsey automotive report via Google",
                url="https://consent.google.com/ml?continue=https%3A%2F%2Fnews.google.com%2Frss%2Farticles%2Fabc",
                source="Google News",
                category="institution",
                score=72,
            )
        ]
    )

    institutions = [article for article in issue_articles if article.category == "institution"]

    assert institutions
    assert all("google.com" not in article.url for article in institutions)
    assert any("jdpower.com/pr-id/" in article.url for article in institutions)


def test_fallback_articles_use_specific_articles_not_newsroom_landing_pages():
    issue_articles = ensure_required_fallbacks([])
    fallback_urls = {article.url for article in issue_articles if article.category in {"tier1", "institution"}}

    assert "https://www.continental.com/en/press/" not in fallback_urls
    assert "https://www.magna.com/company/newsroom/releases" not in fallback_urls
    assert "https://www.autonews.com/" not in fallback_urls
    assert "https://www.jdpower.com/business/automotive" not in fallback_urls
    assert "https://www.sae.org/publications/magazines/content/momag" not in fallback_urls
    assert "https://www.wardsauto.com/" not in fallback_urls
    assert any("/press/press-releases/" in url for url in fallback_urls)
    assert any("/stories/news-press-release/" in url for url in fallback_urls)


def test_resolve_original_url_unwraps_google_consent_continue_parameter():
    url = "https://consent.google.com/ml?continue=https%3A%2F%2Fexample.com%2Farticle%3Futm_source%3Dgoogle"

    assert resolve_original_url(url) == "https://example.com/article?utm_source=google"


def test_default_feeds_include_verified_industry_sources():
    names = {feed.name for feed in DEFAULT_FEEDS}

    assert "WardsAuto" in names
    assert "PR Newswire Automotive" in names
    assert "Car and Driver News" in names
    assert "Motor1 News" in names


def test_check_feed_health_reports_parse_failures(monkeypatch):
    class FakeResponse:
        status_code = 200
        content = b"not xml"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def get(self, url):
            return FakeResponse()

    monkeypatch.setattr("automotive_newsletter.collector._feed_client", FakeClient)

    rows = check_feed_health(feeds=[DEFAULT_FEEDS[0]])

    assert rows[0]["name"] == DEFAULT_FEEDS[0].name
    assert rows[0]["ok"] is False
    assert rows[0]["entries"] == 0
    assert rows[0]["error"] == "피드 파싱 실패"
