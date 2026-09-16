from datetime import datetime, timezone

from automotive_newsletter.collector import (
    canonicalize_url,
    check_feed_health,
    collect_from_entries,
    extract_source_and_publisher,
    fetch_feed_entries,
    unwrap_google_redirect,
)
from automotive_newsletter.models import Article, FeedEntry
from automotive_newsletter.sources import (
    AUTHORITY_HIERARCHY,
    DEFAULT_FEEDS,
    SourceFeed,
    classify_source_type,
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


def test_google_news_redirect_resolution():
    # 1. Google consent redirect
    consent_url = "https://consent.google.com/m?continue=https://www.reuters.com/business/autos/article-1"
    assert unwrap_google_redirect(consent_url) == "https://www.reuters.com/business/autos/article-1"

    # 2. Google search redirect parameter
    google_url = "https://www.google.com/url?q=https://www.reuters.com/business/autos/tesla-update?utm_source=twitter&sa=D"
    assert unwrap_google_redirect(google_url) == "https://www.reuters.com/business/autos/tesla-update?utm_source=twitter"

    # 3. Google News base64 encoded token
    base64_url = "https://news.google.com/rss/articles/CBMiTWh0dHBzOi8vd3d3LnJldXRlcnMuY29tL2J1c2luZXNzL2F1dG9zLXRyYW5zcG9ydGF0aW9uL3Rlc2xhLXJlY2FsbC0yMDI0LTAxLTI1L9IBAA?oc=5"
    unwrapped = unwrap_google_redirect(base64_url)
    assert unwrapped == "https://www.reuters.com/business/autos-transportation/tesla-recall-2024-01-25/"

    # 4. Canonicalize unwraps and removes tracking params
    canon = canonicalize_url(google_url)
    assert canon == "https://www.reuters.com/business/autos/tesla-update"


def test_publisher_identification_for_reuters():
    google_feed = SourceFeed(
        name="Google News Automotive",
        bucket="big",
        url="https://news.google.com/rss/search?q=automotive",
        id="google_news_automotive",
        source_type="aggregator",
        authority_score=40,
    )

    # 1. Identified via explicit source tag
    class RawSource:
        title = "Tesla reports quarterly deliveries"
        source = {"title": "Reuters"}
        link = "https://news.google.com/articles/123"

    pub1, disc1, auth1 = extract_source_and_publisher(RawSource(), google_feed)
    assert pub1 == "Reuters"
    assert disc1 == "Google News"
    assert auth1 == 95

    # 2. Identified via title suffix
    class RawSuffix:
        title = "Global automakers pivot toward hybrids - Reuters"
        source = None
        link = "https://news.google.com/articles/456"

    pub2, disc2, auth2 = extract_source_and_publisher(RawSuffix(), google_feed)
    assert pub2 == "Reuters"
    assert disc2 == "Google News"
    assert auth2 == 95

    # 3. Identified via destination link domain
    class RawDomain:
        title = "Chip supply stabilizes across major suppliers"
        source = None
        link = "https://www.google.com/url?q=https://www.reuters.com/technology/chips-auto-2026"

    pub3, disc3, auth3 = extract_source_and_publisher(RawDomain(), google_feed)
    assert pub3 == "Reuters"
    assert disc3 == "Google News"
    assert auth3 == 95


def test_tracking_parameter_removal_and_canonicalization():
    url = "HTTPS://WWW.Reuters.COM:443/business/autos/?utm_source=twitter&utm_medium=social&fbclid=abc123&page=2&sort=desc#section"
    canon = canonicalize_url(url)
    # Scheme and host lowercased, default port 443 removed, trailing slash normalized, tracking params stripped, query sorted
    assert canon == "https://www.reuters.com/business/autos?page=2&sort=desc"

    # Root trailing slash preserved
    assert canonicalize_url("http://example.com:80/") == "http://example.com/"

    # Avoid incorrectly merging different articles
    url1 = "https://example.com/article/100?ref=home"
    url2 = "https://example.com/article/200?ref=home"
    assert canonicalize_url(url1) != canonicalize_url(url2)

    url3 = "https://example.com/view?id=1"
    url4 = "https://example.com/view?id=2"
    assert canonicalize_url(url3) != canonicalize_url(url4)


def test_unknown_publisher_warning_and_resilience():
    google_feed = SourceFeed(
        name="Google News Aggregator",
        bucket="big",
        url="https://news.google.com/rss/search?q=test",
        id="google_news_agg",
        source_type="aggregator",
        authority_score=40,
    )

    class RawUnknown:
        title = "Autonomous vehicle breakthrough announced today"
        source = None
        link = "https://some-obscure-domain-xyz.net/post/456"

    pub, disc, auth = extract_source_and_publisher(RawUnknown(), google_feed)
    assert pub == "Unknown"
    assert disc == "Google News"
    assert auth == 40  # fallback to feed authority score

    class FakeParsed:
        bozo = False
        entries = [
            {
                "title": "Autonomous vehicle breakthrough announced today",
                "link": "https://some-obscure-domain-xyz.net/post/456",
                "summary": "Sample summary",
            }
        ]

    class FakeResponse:
        status_code = 200
        content = b"<rss></rss>"
        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return None
        def get(self, url):
            return FakeResponse()

    import automotive_newsletter.collector as collector_module
    old_client = collector_module._feed_client
    import feedparser
    old_parse = feedparser.parse
    try:
        collector_module._feed_client = FakeClient
        feedparser.parse = lambda c: FakeParsed()

        entries, warnings = fetch_feed_entries([google_feed])
        assert len(entries) == 1
        assert entries[0].publisher == "Unknown"
        assert entries[0].source == "Unknown"
        assert any("출처(publisher) 식별 실패" in w for w in warnings)
    finally:
        collector_module._feed_client = old_client
        feedparser.parse = old_parse


def test_source_classification_and_authority_fallback():
    # Classification across categories
    assert classify_source_type("NHTSA") == "regulator"
    assert classify_source_type("ACEA") == "regulator"
    assert classify_source_type("IEEE Standards") == "institution"
    assert classify_source_type("한국자동차모빌리티산업협회") == "institution"
    assert classify_source_type("McKinsey Mobility") == "research"
    assert classify_source_type("SAE International") == "research"
    assert classify_source_type("PR Newswire") == "press_release"
    assert classify_source_type("Linux Foundation AGL") == "open_source"
    assert classify_source_type("Hyundai Motor Group Newsroom") == "official"
    assert classify_source_type("Google News Automotive") == "aggregator"

    # Fallback to media for unknown
    assert classify_source_type("Unrecognized Indie Car Blog") == "media"

    # Fallback using feed metadata when provided
    research_feed = SourceFeed(
        name="Auto Research Hub",
        bucket="technology",
        url="https://example.com/research",
        id="auto_research_hub",
        source_type="research",
        authority_score=85,
    )
    assert classify_source_type("Custom Lab", research_feed) == "research"

    # Source authority property / fallback
    entry = FeedEntry(
        title="Sample Entry",
        url="https://example.com/article",
        source="Custom Lab",
        bucket="technology",
        authority_score=research_feed.authority_score,
        source_type=research_feed.source_type,
    )
    assert entry.source_authority == 85
    assert entry.source_type == "research"

    articles, _ = collect_from_entries([entry])
    assert articles[0].source_authority == 85
    assert articles[0].source_type == "research"


def test_collector_diagnostics_format():
    feed_direct = SourceFeed(
        name="Reuters",
        bucket="big",
        url="https://reuters.com/feed",
        id="reuters",
        source_type="media",
        authority_score=95,
    )
    feed_agg = SourceFeed(
        name="Google News",
        bucket="big",
        url="https://news.google.com/rss",
        id="google_news",
        source_type="aggregator",
        authority_score=40,
    )
    feed_fail = SourceFeed(
        name="ACEA",
        bucket="policy",
        url="https://acea.auto/feed",
        id="acea",
        source_type="regulator",
        authority_score=95,
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return None
        def get(self, url):
            class FakeResponse:
                def __init__(self, url):
                    self.status_code = 500 if "acea" in url else 200
                    self.content = b"<rss></rss>"
                def raise_for_status(self):
                    if self.status_code >= 400:
                        raise Exception("HTTP 500")
            return FakeResponse(url)

    class FakeParsed:
        def __init__(self, url):
            self.bozo = False
            if "google" in url:
                self.entries = [
                    {
                        "title": "Tesla updates autonomy roadmap - Reuters",
                        "link": "https://news.google.com/articles/123",
                    }
                ]
            elif "reuters" in url:
                self.entries = [
                    {
                        "title": "Automakers report record profits",
                        "link": "https://reuters.com/123",
                    }
                ]
            else:
                self.entries = []

    import automotive_newsletter.collector as collector_module
    old_client = collector_module._feed_client
    import feedparser
    old_parse = feedparser.parse
    try:
        collector_module._feed_client = FakeClient
        feedparser.parse = lambda c: FakeParsed("google" if b"google" in c else ("acea" if b"acea" in c else "reuters"))
        # We also need get() to return url-specific content:
        class DynamicResponse:
            def __init__(self, url):
                self.url = url
                self.status_code = 500 if "acea" in url else 200
                self.content = url.encode()
            def raise_for_status(self):
                if self.status_code >= 400:
                    raise Exception("HTTP 500")
        class DynamicClient:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return None
            def get(self, url): return DynamicResponse(url)
        collector_module._feed_client = DynamicClient

        rows = check_feed_health(feeds=[feed_direct, feed_agg, feed_fail])
        assert rows[0]["diagnostic"] == "OK  Reuters"
        assert rows[1]["diagnostic"] == "OK  Google News → Reuters"
        assert rows[2]["diagnostic"] == "FAIL ACEA"
    finally:
        collector_module._feed_client = old_client
        feedparser.parse = old_parse


