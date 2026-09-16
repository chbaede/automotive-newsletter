from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


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

    def __post_init__(self) -> None:
        if self.source_authority is None:
            self.source_authority = (
                self.authority_score if self.authority_score is not None else 70
            )
        if self.authority_score is None:
            self.authority_score = self.source_authority


@dataclass(slots=True)
class Article:
    title: str
    url: str
    source: str
    category: str = "big"
    published_at: datetime | None = None
    summary_ko: str = ""
    excerpt: str = ""
    tags: list[str] = field(default_factory=list)
    score: float = 0
    discovered_via: str | None = None
    source_id: str | None = None
    authority_score: int | None = None
    source_type: str = "media"
    source_authority: int | None = None

    def __post_init__(self) -> None:
        if self.source_authority is None:
            self.source_authority = (
                self.authority_score if self.authority_score is not None else 70
            )
        if self.authority_score is None:
            self.authority_score = self.source_authority


@dataclass(slots=True)
class NewsletterIssue:
    issue_date: str
    articles: list[Article] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    title: str = "Automotive Newsletter"
    created_at: datetime | None = None
    sent_at: datetime | None = None

