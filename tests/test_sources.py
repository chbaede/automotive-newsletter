from datetime import datetime, timezone

from automotive_newsletter.collector import (
    collect_from_entries,
    extract_source_and_publisher,
    fetch_feed_entries,
)
from automotive_newsletter.models import Article, FeedEntry
from automotive_newsletter.sources import (
    AUTHORITY_HIERARCHY,
    DEFAULT_FEEDS,
    SourceFeed,
    get_enabled_sources,
    get_source,
    source_authority,
    source_metadata,
)


def test_source_feed_metadata_and_hierarchy():
    # Verify all DEFAULT_FEEDS have complete metadata
    for feed in DEFAULT_FEEDS:
        assert feed.id
        assert feed.name
        assert feed.bucket
        assert feed.url
        assert feed.source_type in AUTHORITY_HIERARCHY
        assert 0 <= feed.authority_score <= 100
        assert feed.region in {"global", "us", "europe", "asia", "kr"}
        assert feed.language in {"en", "ko"}
        assert isinstance(feed.paywalled, bool)
        assert isinstance(feed.enabled, bool)

    # Authority hierarchy values
    assert AUTHORITY_HIERARCHY["regulator"] == 100
    assert AUTHORITY_HIERARCHY["news_agency"] == 95
    assert AUTHORITY_HIERARCHY["industry_media"] == 90
    assert AUTHORITY_HIERARCHY["specialist_media"] == 85
    assert AUTHORITY_HIERARCHY["research"] == 80
    assert AUTHORITY_HIERARCHY["tech_media"] == 75
    assert AUTHORITY_HIERARCHY["official"] == 70
    assert AUTHORITY_HIERARCHY["press_release"] == 60
    assert AUTHORITY_HIERARCHY["aggregator"] == 40

    # Source metadata helper
    meta = source_metadata("automotive_news")
    assert meta is not None
    assert meta["id"] == "automotive_news"
    assert meta["name"] == "Automotive News"
    assert meta["authority_score"] == 90
    assert meta["source_type"] == "media"
    assert meta["enabled"] is True

    assert source_metadata("non_existent_source") is None


def test_source_authority_lookup():
    # Source IDs
    assert source_authority("reuters") == 95
    assert source_authority("acea") == 100
    assert source_authority("unece") == 100
    assert source_authority("automotive_news") == 90
    assert source_authority("wardsauto") == 90
    assert source_authority("eclipse_sdv") == 85
    assert source_authority("global_automotive_big_news") == 40

    # Publisher names from aggregator results
    assert source_authority("Reuters") == 95
    assert source_authority("Bloomberg") == 95
    assert source_authority("NHTSA") == 100
    assert source_authority("PR Newswire") == 60

    # Source types
    assert source_authority("regulator") == 100
    assert source_authority("aggregator") == 40


def test_source_lookup_by_id_and_name():
    # Explicit slugs requested
    assert get_source("reuters") is not None
    assert get_source("reuters").id == "reuters"
    assert get_source("automotive_news") is not None
    assert get_source("automotive_world") is not None
    assert get_source("wardsauto") is not None
    assert get_source("acea") is not None
    assert get_source("unece") is not None
    assert get_source("eclipse_sdv") is not None

    # Lookup by display name
    assert get_source("Automotive News") is not None
    assert get_source("Automotive News").id == "automotive_news"

    # Non-existent
    assert get_source("unknown_xyz") is None


def test_enabled_and_disabled_sources():
    enabled = get_enabled_sources()
    assert all(feed.enabled for feed in enabled)
    assert len(enabled) == len(DEFAULT_FEEDS)

    # Test feed with enabled=False
    disabled_feed = SourceFeed(
        name="Disabled Feed",
        bucket="sdv",
        url="https://disabled.example.com/rss",
        id="disabled_feed",
        enabled=False,
    )
    active_feed = SourceFeed(
        name="Active Feed",
        bucket="sdv",
        url="https://active.example.com/rss",
        id="active_feed",
        enabled=True,
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.visited = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            pass

        def get(self, url):
            class FakeResponse:
                status_code = 200
                content = b"<rss><channel><title>Active</title></channel></rss>"
            return FakeResponse()

    # Verify fetch_feed_entries skips disabled feeds
    entries, _ = fetch_feed_entries([disabled_feed])
    assert len(entries) == 0


def test_google_news_discovery_vs_publisher():
    google_feed = SourceFeed(
        name="Global automotive big news",
        bucket="big",
        url="https://news.google.com/rss/search?q=test",
        id="global_automotive_big_news",
        source_type="aggregator",
        authority_score=40,
    )

    # 1. Entry with explicit source tag
    class FakeRawWithSource:
        title = "Tesla expands factory in Nevada - Reuters"
        source = {"title": "Reuters", "href": "https://reuters.com"}

    pub, disc, auth = extract_source_and_publisher(FakeRawWithSource(), google_feed)
    assert pub == "Reuters"
    assert disc == "Google News"
    assert auth == 95

    # 2. Entry with title suffix fallback
    class FakeRawWithSuffix:
        title = "GM reports record electric vehicle deliveries - Bloomberg"
        source = None

    pub2, disc2, auth2 = extract_source_and_publisher(FakeRawWithSuffix(), google_feed)
    assert pub2 == "Bloomberg"
    assert disc2 == "Google News"
    assert auth2 == 95

    # 3. Direct feed where publisher is the feed itself
    direct_feed = SourceFeed(
        name="Automotive News",
        bucket="big",
        url="https://www.autonews.com/feed",
        id="automotive_news",
        source_type="media",
        authority_score=90,
    )
    pub3, disc3, auth3 = extract_source_and_publisher(FakeRawWithSuffix(), direct_feed)
    assert pub3 == "Automotive News"
    assert disc3 == "Automotive News"
    assert auth3 == 90

    # 4. FeedEntry and Article propagation
    entry = FeedEntry(
        title="Hyundai Mobis unveils next-gen steer-by-wire",
        url="https://example.com/hyundai-mobis",
        source="Hyundai Mobis",
        bucket="tier1",
        discovered_via="Google News",
        publisher="Hyundai Mobis",
        source_id=google_feed.id,
        authority_score=70,
    )
    articles, _ = collect_from_entries([entry])
    assert len(articles) == 1
    assert articles[0].source == "Hyundai Mobis"
    assert articles[0].discovered_via == "Google News"
    assert articles[0].source != "Google News"


def test_backward_compatibility():
    # 3 positional arguments without id or metadata
    legacy_feed = SourceFeed("Legacy Outlet", "oem", "https://example.com/feed.xml")
    assert legacy_feed.name == "Legacy Outlet"
    assert legacy_feed.bucket == "oem"
    assert legacy_feed.url == "https://example.com/feed.xml"
    assert legacy_feed.id == "legacy_outlet"
    assert legacy_feed.source_type == "media"
    assert legacy_feed.authority_score == 70
    assert legacy_feed.enabled is True
    assert legacy_feed.paywalled is False

    # 4 positional arguments for FeedEntry
    legacy_entry = FeedEntry("Title", "https://example.com", "Legacy Source", "big")
    assert legacy_entry.title == "Title"
    assert legacy_entry.source == "Legacy Source"
    assert legacy_entry.discovered_via is None

    # Article positional arguments
    legacy_article = Article("Title", "https://example.com", "Legacy Source")
    assert legacy_article.title == "Title"
    assert legacy_article.source == "Legacy Source"
    assert legacy_article.discovered_via is None

    # All DEFAULT_FEEDS still present
    feed_names = {feed.name for feed in DEFAULT_FEEDS}
    assert "Automotive World" in feed_names
    assert "WardsAuto" in feed_names
    assert "Electrek" in feed_names
    assert "InsideEVs" in feed_names
    assert "The Verge Transportation" in feed_names
