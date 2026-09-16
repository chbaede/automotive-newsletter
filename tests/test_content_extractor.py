from __future__ import annotations

from unittest.mock import MagicMock, patch

from automotive_newsletter.content_extractor import (
    ExtractedContent,
    RobotsTxtPolicy,
    extract_text_from_html,
    extract_usable_article_text,
    fetch_article_page_text,
)


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


def test_extract_usable_article_text_priority_rss_content():
    long_content = "<p>" + "Automotive software architecture is evolving rapidly. " * 15 + "</p>"
    raw_entry = {
        "content": [{"value": long_content}],
        "summary": "Short summary",
    }
    extracted = extract_usable_article_text(
        raw_entry=raw_entry,
        url="https://example.com/article1",
        title="Software Architecture",
        allow_page_fetch=False,
    )
    assert extracted.source_type == "rss_content"
    assert "Automotive software architecture" in extracted.text
    assert not extracted.is_short_excerpt


def test_extract_usable_article_text_priority_rss_summary():
    long_summary = "<p>" + "Hyundai and Kia are rolling out new over-the-air updates across Europe. " * 10 + "</p>"
    raw_entry = {
        "summary": long_summary,
    }
    extracted = extract_usable_article_text(
        raw_entry=raw_entry,
        url="https://example.com/article2",
        title="Hyundai OTA Updates",
        allow_page_fetch=False,
    )
    assert extracted.source_type == "rss_summary"
    assert "over-the-air updates" in extracted.text
    assert not extracted.is_short_excerpt


def test_robots_txt_disallowed_prevents_page_fetch():
    mock_policy = MagicMock(spec=RobotsTxtPolicy)
    mock_policy.can_fetch.return_value = False

    with patch("httpx.Client.get") as mock_get:
        text = fetch_article_page_text(
            "https://disallowed.com/news/123", robots_policy=mock_policy
        )
        assert text == ""
        mock_get.assert_not_called()


def test_extract_usable_article_text_fallback_on_short_summary():
    raw_entry = {
        "summary": "Brief 10-word teaser for subscribers only.",
    }
    mock_policy = MagicMock(spec=RobotsTxtPolicy)
    mock_policy.can_fetch.return_value = False

    extracted = extract_usable_article_text(
        raw_entry=raw_entry,
        url="https://example.com/teaser",
        title="Teaser Title",
        allow_page_fetch=True,
        robots_policy=mock_policy,
    )
    assert extracted.is_short_excerpt is True
    assert "Brief 10-word teaser" in extracted.text

