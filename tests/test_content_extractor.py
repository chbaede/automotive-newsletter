from __future__ import annotations

from unittest.mock import MagicMock, patch

from automotive_newsletter.collector import should_allow_page_fetch
from automotive_newsletter.config import Settings
from automotive_newsletter.content_extractor import (
    ExtractedContent,
    RobotsTxtPolicy,
    _is_intermediary,
    extract_text_from_html,
    extract_usable_article_text,
    fetch_article_page_text,
)
from automotive_newsletter.sources import SourceFeed


def test_extract_text_from_html_strips_scripts_and_boilerplate():
    html = """
    <html>
      <head><title>Test Title</title><script>var x = 1;</script></head>
      <body>
        <nav><a href="/">Home</a></nav>
        <article>
          <p>Bosch announced a major expansion of its vehicle software development division today.</p>
          <p>The company plans to invest in zonal compute platforms for upcoming automaker architectures.</p>
          <p>Cookie policy: We use cookies to analyze traffic.</p>
        </article>
        <footer><p>All rights reserved 2026.</p></footer>
      </body>
    </html>
    """
    text = extract_text_from_html(html)
    assert "Bosch announced a major expansion" in text
    assert "zonal compute platforms" in text
    assert "var x = 1" not in text
    assert "Cookie policy" not in text
    assert "All rights reserved" not in text


# Requirement 11.1: RSS content available => RSS content is used
def test_rss_content_available_uses_rss_content():
    long_content = "<p>" + "Automotive software architecture is evolving rapidly. " * 15 + "</p>"
    raw_entry = {
        "content": [{"value": long_content}],
        "summary": "Short summary that should not override full content",
    }
    with patch("automotive_newsletter.content_extractor.fetch_article_page_text") as mock_page_fetch:
        extracted = extract_usable_article_text(
            raw_entry=raw_entry,
            url="https://example.com/article1",
            title="Software Architecture",
            allow_page_fetch=True,
        )
        assert extracted.source_type == "rss_content"
        assert "Automotive software architecture" in extracted.text
        assert not extracted.is_short_excerpt
        mock_page_fetch.assert_not_called()


# Requirement 11.2: RSS content unavailable but summary available => summary is used
def test_rss_content_unavailable_but_summary_available_uses_summary():
    summary_text = "<p>" + "Hyundai and Kia are rolling out new over-the-air updates across Europe. " * 5 + "</p>"
    raw_entry = {
        "summary": summary_text,
    }
    with patch("automotive_newsletter.content_extractor.fetch_article_page_text") as mock_page_fetch:
        extracted = extract_usable_article_text(
            raw_entry=raw_entry,
            url="https://example.com/article2",
            title="Hyundai OTA Updates",
            allow_page_fetch=True,
        )
        assert extracted.source_type == "rss_summary"
        assert "over-the-air updates" in extracted.text
        mock_page_fetch.assert_not_called()


# Requirement 11.3: RSS content/summary unavailable => page extraction is attempted
def test_rss_content_and_summary_unavailable_attempts_page_extraction():
    raw_entry = {}  # Neither content nor summary available
    with patch("automotive_newsletter.content_extractor.fetch_article_page_text") as mock_page_fetch:
        mock_page_fetch.return_value = (
            "Volkswagen announced major restructuring plans for its German plants today in Wolfsburg."
        )
        extracted = extract_usable_article_text(
            raw_entry=raw_entry,
            url="https://example.com/vw-restructure",
            title="VW Restructuring",
            excerpt="",
            allow_page_fetch=True,
        )
        mock_page_fetch.assert_called_once()
        assert extracted.source_type == "page_extraction"
        assert "Volkswagen announced major restructuring plans" in extracted.text


# Requirement 11.4: robots.txt blocks page => no page fetch
def test_robots_txt_blocks_page_prevents_page_fetch():
    mock_policy = MagicMock(spec=RobotsTxtPolicy)
    mock_policy.can_fetch.return_value = False

    raw_entry = {}
    with patch("httpx.Client.get") as mock_http_get:
        extracted = extract_usable_article_text(
            raw_entry=raw_entry,
            url="https://disallowed.com/news/123",
            title="Disallowed Article",
            excerpt="Fallback excerpt from feed",
            allow_page_fetch=True,
            robots_policy=mock_policy,
        )
        # HTTP client must not be called to fetch page when robots.txt disallows
        mock_http_get.assert_not_called()
        assert extracted.source_type == "fallback"
        assert extracted.text == "Fallback excerpt from feed"


# Requirement 11.5: page fetch fails => fallback
def test_page_fetch_fails_uses_fallback():
    raw_entry = {}
    with patch("automotive_newsletter.content_extractor.fetch_article_page_text") as mock_page_fetch:
        mock_page_fetch.return_value = ""  # Empty or failed fetch

        extracted = extract_usable_article_text(
            raw_entry=raw_entry,
            url="https://example.com/failed-page",
            title="Failed Page Title",
            excerpt="Fallback excerpt text",
            allow_page_fetch=True,
        )
        mock_page_fetch.assert_called_once()
        assert extracted.source_type == "fallback"
        assert extracted.text == "Fallback excerpt text"


# Requirement 6: Do not fetch intermediary Google News pages
def test_intermediary_google_news_pages_never_fetched():
    assert _is_intermediary("https://news.google.com/rss/articles/CBMi...") is True
    assert _is_intermediary("https://google.com/url?q=https://example.com") is True
    assert _is_intermediary("https://reuters.com/business/autos/article") is False

    with patch("automotive_newsletter.content_extractor.fetch_article_page_text") as mock_page_fetch:
        extracted = extract_usable_article_text(
            raw_entry={},
            url="https://news.google.com/rss/articles/XYZ123",
            title="Google News Story",
            excerpt="Google News brief description",
            allow_page_fetch=True,
        )
        mock_page_fetch.assert_not_called()
        assert extracted.source_type == "fallback"
        assert extracted.text == "Google News brief description"


# Requirement 10: Do not fetch article pages unnecessarily for conference or reference entries
def test_should_allow_page_fetch_guards():
    settings_enabled = Settings(fetch_article_excerpts=True)
    settings_disabled = Settings(fetch_article_excerpts=False)

    conf_feed = SourceFeed(
        id="ces-conf",
        name="CES",
        url="https://ces.tech/rss",
        bucket="conference",
    )
    media_feed = SourceFeed(
        id="reuters-auto",
        name="Reuters",
        url="https://reuters.com/rss",
        bucket="media",
    )

    # Disabled globally
    assert should_allow_page_fetch(feed=media_feed, settings=settings_disabled) is False

    # Conference feed disallowed
    assert should_allow_page_fetch(feed=conf_feed, settings=settings_enabled) is False
    assert should_allow_page_fetch(entry_bucket="conference", settings=settings_enabled) is False

    # Reference / static source types disallowed
    assert should_allow_page_fetch(entry_source_type="reference", settings=settings_enabled) is False
    assert should_allow_page_fetch(entry_source_type="static", settings=settings_enabled) is False

    # Regular media allowed when enabled
    assert should_allow_page_fetch(feed=media_feed, entry_bucket="media", settings=settings_enabled) is True


def test_collect_from_entries_extracts_content_and_stores_source_type(tmp_path):
    from pathlib import Path
    from automotive_newsletter.collector import collect_from_entries
    from automotive_newsletter.models import FeedEntry
    from automotive_newsletter.store import NewsletterStore

    entry = FeedEntry(
        title="BMW reveals new Neue Klasse software architecture",
        url="https://example.com/bmw-software",
        source="Automotive News",
        bucket="media",
        excerpt="BMW announced zonal architecture details.",
        content="Full extracted body text of the BMW announcement regarding Neue Klasse SDV.",
        content_source_type="page_extraction",
    )

    articles, _ = collect_from_entries([entry])
    assert len(articles) == 1
    art = articles[0]
    assert art.content == "Full extracted body text of the BMW announcement regarding Neue Klasse SDV."
    assert art.content_source_type == "page_extraction"

    # Verify SQLite persistence of content_source_type
    store = NewsletterStore(tmp_path / "test_content.db")
    saved_issue = store.save_issue("2026-09-17", articles=[art])
    loaded_issue = store.get_issue("2026-09-17")
    assert loaded_issue is not None
    assert len(loaded_issue.articles) == 1
    loaded_art = loaded_issue.articles[0]
    assert loaded_art.content == art.content
    assert loaded_art.content_source_type == "page_extraction"


def test_ai_summarizer_receives_extracted_article_content():
    from unittest.mock import MagicMock
    from automotive_newsletter.collector import collect_from_entries
    from automotive_newsletter.models import FeedEntry
    from automotive_newsletter.summarizer import BaseSummarizer, SummaryResult

    mock_summarizer = MagicMock(spec=BaseSummarizer)
    mock_summarizer.summarize.return_value = SummaryResult(
        summary_ko="요약",
        summary_en="Summary",
        why_it_matters_ko="의의",
        key_points=["포인트"],
        summary_model="mock",
    )

    full_text = "Comprehensive technical analysis of AUTOSAR adaptive platform deployment across European OEMs."
    entry = FeedEntry(
        title="AUTOSAR Adaptive Platform in Production",
        url="https://example.com/autosar-adaptive",
        source="Automotive World",
        bucket="media",
        excerpt="Short teaser",
        content=full_text,
        content_source_type="rss_content",
    )

    articles, _ = collect_from_entries([entry], summarizer=mock_summarizer)
    assert len(articles) == 1

    # Verify summarizer received the extracted content
    mock_summarizer.summarize.assert_called_once()
    called_article, kwargs = mock_summarizer.summarize.call_args
    assert called_article[0].title == "AUTOSAR Adaptive Platform in Production"
    assert kwargs.get("content") == full_text

