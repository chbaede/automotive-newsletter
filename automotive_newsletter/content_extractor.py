from __future__ import annotations

import re
import urllib.robotparser
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlsplit

import httpx
from bs4 import BeautifulSoup


@dataclass(slots=True)
class ExtractedContent:
    text: str
    source_type: str  # "rss_content", "rss_summary", "page_extraction", "fallback"
    is_short_excerpt: bool


class RobotsTxtPolicy:
    """Polite and cached robots.txt compliance checker."""

    def __init__(self, timeout: float = 3.0, user_agent: str = "AutomotiveNewsletter/0.1"):
        self.timeout = timeout
        self.user_agent = user_agent
        self._parsers: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def can_fetch(self, url: str) -> bool:
        if not url or not url.startswith(("http://", "https://")):
            return False

        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self._parsers:
            self._parsers[origin] = self._load_robots(origin)

        parser = self._parsers[origin]
        if parser is None:
            # If robots.txt was missing (404) or failed to load, default to permissible
            return True

        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _load_robots(self, origin: str) -> urllib.robotparser.RobotFileParser | None:
        robots_url = f"{origin}/robots.txt"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(robots_url, headers={"User-Agent": self.user_agent})
                if resp.status_code == 200 and resp.text:
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(resp.text.splitlines())
                    return parser
                elif resp.status_code in (401, 403):
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(["User-agent: *", "Disallow: /"])
                    return parser
        except Exception:
            pass
        return None


# Global robots policy cache
_ROBOTS_POLICY = RobotsTxtPolicy()


def extract_text_from_html(html: str, max_chars: int = 6000) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-text and boilerplate elements
    for tag in soup(
        ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "button", "iframe"]
    ):
        tag.decompose()

    # Prioritize article / main body containers if available
    container = (
        soup.find("article")
        or soup.find("main")
        or soup.find(class_=re.compile(r"article[-_]?(content|body)|story[-_]?content|post[-_]?content", re.I))
        or soup.body
        or soup
    )

    paragraphs = container.find_all("p") if container else []
    if paragraphs:
        text_parts = [p.get_text(" ", strip=True) for p in paragraphs]
        # Filter out very short or cookie/copyright boilerplates
        valid_parts = [p for p in text_parts if len(p) > 25 and not _is_boilerplate(p)]
        cleaned = "\n\n".join(valid_parts)
    else:
        cleaned = container.get_text("\n", strip=True) if container else ""

    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0] + "…"

    return cleaned


def _is_boilerplate(text: str) -> bool:
    lowered = text.lower()
    return any(
        term in lowered
        for term in [
            "cookie policy",
            "terms of service",
            "privacy policy",
            "all rights reserved",
            "subscribe to read",
            "sign up for newsletter",
            "advertisement",
        ]
    )


def fetch_article_page_text(
    url: str,
    timeout: float = 6.0,
    user_agent: str = "AutomotiveNewsletter/0.1 (+local research app)",
    robots_policy: RobotsTxtPolicy | None = None,
) -> str:
    if not url or _is_intermediary(url):
        return ""
    policy = robots_policy or _ROBOTS_POLICY
    if not policy.can_fetch(url):
        return ""

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": user_agent})
            if resp.status_code == 200:
                return extract_text_from_html(resp.text)
    except Exception:
        pass
    return ""


def extract_usable_article_text(
    raw_entry: dict[str, Any] | None,
    url: str,
    title: str = "",
    excerpt: str = "",
    allow_page_fetch: bool = True,
    timeout: float = 6.0,
    robots_policy: RobotsTxtPolicy | None = None,
) -> ExtractedContent:
    """Extract usable article text in priority order:
    1. RSS content (<content:encoded> / content)
    2. RSS summary / description
    3. Article page extraction (respecting robots.txt & limits)
    4. Fallback to excerpt / title
    """
    # 1. Check RSS content field
    if raw_entry:
        content_items = raw_entry.get("content")
        if isinstance(content_items, list) and content_items:
            for item in content_items:
                if isinstance(item, dict) and "value" in item:
                    val = extract_text_from_html(item["value"])
                    if val.strip():
                        return ExtractedContent(
                            text=val,
                            source_type="rss_content",
                            is_short_excerpt=len(val) < 250,
                        )
                elif isinstance(item, str) and item.strip():
                    val = extract_text_from_html(item)
                    if val.strip():
                        return ExtractedContent(
                            text=val,
                            source_type="rss_content",
                            is_short_excerpt=len(val) < 250,
                        )
        elif isinstance(content_items, str) and content_items.strip():
            val = extract_text_from_html(content_items)
            if val.strip():
                return ExtractedContent(
                    text=val,
                    source_type="rss_content",
                    is_short_excerpt=len(val) < 250,
                )

        for k in ("content:encoded", "content_encoded"):
            val_raw = raw_entry.get(k)
            if isinstance(val_raw, str) and val_raw.strip():
                val = extract_text_from_html(val_raw)
                if val.strip():
                    return ExtractedContent(
                        text=val,
                        source_type="rss_content",
                        is_short_excerpt=len(val) < 250,
                    )

    # 2. Check RSS summary / description
    if raw_entry:
        summary_raw = raw_entry.get("summary") or raw_entry.get("description") or ""
        if summary_raw and str(summary_raw).strip():
            rss_summary = extract_text_from_html(str(summary_raw))
            if rss_summary.strip():
                return ExtractedContent(
                    text=rss_summary,
                    source_type="rss_summary",
                    is_short_excerpt=len(rss_summary) < 250,
                )

    # 3. Article page extraction (when RSS content/summary unavailable)
    if allow_page_fetch and url and not _is_intermediary(url):
        page_text = fetch_article_page_text(
            url, timeout=timeout, robots_policy=robots_policy
        )
        if page_text and len(page_text.strip()) >= 50:
            return ExtractedContent(
                text=page_text,
                source_type="page_extraction",
                is_short_excerpt=len(page_text) < 250,
            )

    # 4. Fallback: use excerpt or title
    fallback_text = (excerpt or "").strip() or title.strip()
    return ExtractedContent(
        text=fallback_text,
        source_type="fallback",
        is_short_excerpt=len(fallback_text) < 250,
    )


def _is_intermediary(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return (
        host == "google.com"
        or host.endswith(".google.com")
        or "news.google" in host
        or host.endswith("google.co.uk")
    )

