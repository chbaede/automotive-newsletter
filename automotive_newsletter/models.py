from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class FeedEntry:
    title: str
    url: str
    source: str
    bucket: str
    published_at: datetime | None = None
    excerpt: str = ""
    discovered_via: str | None = None
    publisher: str | None = None
    source_id: str | None = None
    authority_score: int | None = None
    source_type: str = "media"
    source_authority: int | None = None
    canonical_url: str | None = None
    collected_at: datetime | None = None
    content: str = ""
    content_source_type: str = "fallback"

    def __post_init__(self) -> None:
        if self.source_authority is None:
            self.source_authority = (
                self.authority_score if self.authority_score is not None else 70
            )
        if self.authority_score is None:
            self.authority_score = self.source_authority
        if self.publisher is None:
            self.publisher = self.source
        if self.canonical_url is None:
            self.canonical_url = self.url
        if self.collected_at is None:
            self.collected_at = datetime.now(timezone.utc)


@dataclass(slots=True)
class Article:
    # Basic / Positional compatibility
    title: str
    url: str
    source: str
    category: str = "big"
    published_at: datetime | None = None
    summary_ko: str = ""
    excerpt: str = ""
    tags: list[str] = field(default_factory=list)
    score: float = 0.0

    # Source & Provenance
    discovered_via: str | None = None
    source_id: str | None = None
    authority_score: int | None = None
    source_type: str = "media"
    source_authority: int | None = None
    publisher: str | None = None

    # Identity
    article_id: str | None = None
    canonical_url: str | None = None
    original_url: str | None = None

    # Content & Summarization
    summary_en: str = ""
    why_it_matters_ko: str = ""
    content: str = ""
    content_source_type: str = "fallback"
    key_points: list[str] = field(default_factory=list)
    summary_model: str | None = None
    summary_version: str | None = None
    summary_created_at: datetime | None = None

    # Classification
    primary_category: str | None = None
    secondary_categories: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)

    # Scoring
    source_score: float = 0.0
    relevance_score: float = 0.0
    impact_score: float = 0.0
    novelty_score: float = 0.0
    recency_score: float = 0.0
    priority_score: float = 0.0

    # Relationships & Event Metadata
    event_id: str | None = None
    event_title: str | None = None
    related_article_ids: list[str] = field(default_factory=list)
    event_source_count: int = 1
    event_independent_source_count: int = 1
    event_has_official_source: bool = False
    event_has_regulatory_source: bool = False
    event_has_major_media_source: bool = False
    event_official_source_url: str | None = None
    event_official_source_name: str | None = None
    event_reference_source_name: str | None = None
    event_related_sources: list[str] = field(default_factory=list)

    # Flags
    is_official: bool = False
    is_reference: bool = False
    is_primary_source: bool = False

    # Timing
    collected_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.canonical_url is None:
            self.canonical_url = self.url
        if self.original_url is None:
            self.original_url = self.url
        if self.article_id is None:
            target = (self.canonical_url or self.url).strip()
            self.article_id = f"art_{hashlib.sha256(target.encode()).hexdigest()[:16]}"
        if self.publisher is None:
            self.publisher = self.source
        if self.primary_category is None:
            self.primary_category = self.category
        elif self.category == "big" and self.primary_category != "big":
            self.category = self.primary_category

        if self.source_authority is None:
            self.source_authority = (
                self.authority_score if self.authority_score is not None else 70
            )
        if self.authority_score is None:
            self.authority_score = self.source_authority

        if self.source_score == 0.0 and self.source_authority is not None:
            self.source_score = float(self.source_authority)
        if self.priority_score == 0.0 and self.score > 0.0:
            self.priority_score = self.score
        elif self.score == 0.0 and self.priority_score > 0.0:
            self.score = self.priority_score

        if not self.is_official and self.source_type == "official":
            self.is_official = True
        if not self.is_primary_source and self.source_type in {"official", "regulator", "press_release"}:
            self.is_primary_source = True
        if not self.is_reference and self.source_type in {"regulator", "institution", "research"}:
            self.is_reference = True

        if self.collected_at is None:
            self.collected_at = datetime.now(timezone.utc)


@dataclass(slots=True)
class Event:
    event_id: str
    title: str
    category: str = "big"
    created_at: datetime | None = None
    importance: float = 0.0
    primary_article_id: str | None = None
    source_count: int = 1
    independent_source_count: int = 1
    has_official_source: bool = False
    has_regulatory_source: bool = False
    has_major_media_source: bool = False
    official_source_url: str | None = None
    official_source_name: str | None = None
    reference_source_name: str | None = None
    related_sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


@dataclass(slots=True)
class EventArticle:
    event_id: str
    article_id: str
    relationship: str = "coverage"
    similarity: float = 1.0


@dataclass(slots=True)
class CollectionMetrics:
    feeds_total: int = 0
    feeds_ok: int = 0
    feeds_failed: int = 0
    articles_collected: int = 0
    articles_after_dedupe: int = 0
    articles_selected: int = 0
    collection_duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "feeds_total": self.feeds_total,
            "feeds_ok": self.feeds_ok,
            "feeds_failed": self.feeds_failed,
            "articles_collected": self.articles_collected,
            "articles_after_dedupe": self.articles_after_dedupe,
            "articles_selected": self.articles_selected,
            "collection_duration": round(self.collection_duration, 4),
        }


@dataclass(slots=True)
class NewsletterIssue:
    issue_date: str
    articles: list[Article] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    title: str = "Automotive Newsletter"
    created_at: datetime | None = None
    sent_at: datetime | None = None
    events: list[Event] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

