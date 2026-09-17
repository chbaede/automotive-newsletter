from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import Article, Event, EventArticle, NewsletterIssue


class NewsletterStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save_issue(
        self,
        issue_date: str,
        articles: Iterable[Article],
        warnings: list[str] | None = None,
        events: Iterable[Event] | None = None,
        event_articles: Iterable[EventArticle] | None = None,
    ) -> NewsletterIssue:
        now = datetime.now(timezone.utc).isoformat()
        article_list = list(articles)
        event_list = list(events) if events is not None else []
        event_article_list = list(event_articles) if event_articles is not None else []
        with self._connect() as conn:
            existing = conn.execute(
                "select id from issues where issue_date = ?", (issue_date,)
            ).fetchone()
            if existing:
                issue_id = existing["id"]
                conn.execute(
                    "update issues set title = ?, warnings = ?, updated_at = ? where id = ?",
                    (
                        f"{issue_date} Automotive Newsletter",
                        json.dumps(warnings or [], ensure_ascii=False),
                        now,
                        issue_id,
                    ),
                )
                conn.execute(
                    "delete from event_articles where event_id in (select event_id from events where issue_id = ?)",
                    (issue_id,),
                )
                conn.execute("delete from events where issue_id = ?", (issue_id,))
                conn.execute("delete from articles where issue_id = ?", (issue_id,))
            else:
                cursor = conn.execute(
                    """
                    insert into issues (issue_date, title, warnings, created_at, updated_at)
                    values (?, ?, ?, ?, ?)
                    """,
                    (
                        issue_date,
                        f"{issue_date} Automotive Newsletter",
                        json.dumps(warnings or [], ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                issue_id = cursor.lastrowid

            for index, article in enumerate(article_list):
                conn.execute(
                    """
                    insert into articles (
                        issue_id, position, title, url, source, category, published_at,
                        summary_ko, excerpt, tags, score,
                        article_id, canonical_url, original_url, source_id, publisher,
                        discovered_via, source_type, source_authority, summary_en, why_it_matters_ko,
                        primary_category, secondary_categories, topics, entities,
                        source_score, relevance_score, impact_score, novelty_score, recency_score,
                        priority_score, event_id, event_title, related_article_ids,
                        is_official, is_reference, is_primary_source, collected_at,
                        content, key_points, summary_model, summary_version, summary_created_at
                    )
                    values (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        issue_id,
                        index,
                        article.title,
                        article.url,
                        article.source,
                        article.category,
                        article.published_at.isoformat() if article.published_at else None,
                        article.summary_ko,
                        article.excerpt,
                        json.dumps(article.tags, ensure_ascii=False),
                        article.score,
                        article.article_id,
                        article.canonical_url,
                        article.original_url,
                        article.source_id,
                        article.publisher,
                        article.discovered_via,
                        article.source_type,
                        article.source_authority,
                        article.summary_en,
                        article.why_it_matters_ko,
                        article.primary_category,
                        json.dumps(article.secondary_categories, ensure_ascii=False),
                        json.dumps(article.topics, ensure_ascii=False),
                        json.dumps(article.entities, ensure_ascii=False),
                        article.source_score,
                        article.relevance_score,
                        article.impact_score,
                        article.novelty_score,
                        article.recency_score,
                        article.priority_score,
                        article.event_id,
                        article.event_title,
                        json.dumps(article.related_article_ids, ensure_ascii=False),
                        1 if article.is_official else 0,
                        1 if article.is_reference else 0,
                        1 if article.is_primary_source else 0,
                        article.collected_at.isoformat() if article.collected_at else None,
                        article.content,
                        json.dumps(article.key_points, ensure_ascii=False),
                        article.summary_model,
                        article.summary_version,
                        article.summary_created_at.isoformat() if article.summary_created_at else None,
                    ),
                )

            for event in event_list:
                conn.execute(
                    """
                    insert into events (
                        event_id, issue_id, title, category, importance, primary_article_id, created_at,
                        source_count, independent_source_count, has_official_source, has_regulatory_source,
                        has_major_media_source, official_source_url, official_source_name,
                        reference_source_name, related_sources
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(event_id) do update set
                        title = excluded.title,
                        category = excluded.category,
                        importance = excluded.importance,
                        primary_article_id = excluded.primary_article_id,
                        source_count = excluded.source_count,
                        independent_source_count = excluded.independent_source_count,
                        has_official_source = excluded.has_official_source,
                        has_regulatory_source = excluded.has_regulatory_source,
                        has_major_media_source = excluded.has_major_media_source,
                        official_source_url = excluded.official_source_url,
                        official_source_name = excluded.official_source_name,
                        reference_source_name = excluded.reference_source_name,
                        related_sources = excluded.related_sources
                    """,
                    (
                        event.event_id,
                        issue_id,
                        event.title,
                        event.category,
                        event.importance,
                        event.primary_article_id,
                        event.created_at.isoformat() if event.created_at else now,
                        event.source_count,
                        event.independent_source_count,
                        1 if event.has_official_source else 0,
                        1 if event.has_regulatory_source else 0,
                        1 if event.has_major_media_source else 0,
                        event.official_source_url,
                        event.official_source_name,
                        event.reference_source_name,
                        json.dumps(event.related_sources, ensure_ascii=False),
                    ),
                )

            for ea in event_article_list:
                conn.execute(
                    """
                    insert into event_articles (event_id, article_id, relationship, similarity)
                    values (?, ?, ?, ?)
                    on conflict(event_id, article_id) do update set
                        relationship = excluded.relationship,
                        similarity = excluded.similarity
                    """,
                    (ea.event_id, ea.article_id, ea.relationship, ea.similarity),
                )

        issue = self.get_issue(issue_date)
        if issue is None:
            raise RuntimeError("failed to read issue after save")
        return issue

    def latest_issue(self) -> NewsletterIssue | None:
        with self._connect() as conn:
            row = conn.execute(
                "select issue_date from issues order by issue_date desc limit 1"
            ).fetchone()
        if row is None:
            return None
        return self.get_issue(row["issue_date"])

    def get_issue(self, issue_date: str) -> NewsletterIssue | None:
        with self._connect() as conn:
            issue_row = conn.execute(
                "select * from issues where issue_date = ?", (issue_date,)
            ).fetchone()
            if issue_row is None:
                return None
            article_rows = conn.execute(
                "select * from articles where issue_id = ? order by position asc",
                (issue_row["id"],),
            ).fetchall()
            event_rows = conn.execute(
                "select * from events where issue_id = ? order by importance desc, created_at desc",
                (issue_row["id"],),
            ).fetchall()

        articles = [self._row_to_article(row) for row in article_rows]
        events = []
        event_dict = {}
        for er in event_rows:
            keys = set(er.keys())

            def get_col(k: str, default: object = None) -> object:
                return er[k] if k in keys and er[k] is not None else default

            ev = Event(
                event_id=er["event_id"],
                title=er["title"],
                category=er["category"],
                created_at=_parse_datetime(er["created_at"]),
                importance=float(er["importance"]),
                primary_article_id=er["primary_article_id"],
                source_count=int(get_col("source_count", 1)),  # type: ignore[arg-type]
                independent_source_count=int(get_col("independent_source_count", 1)),  # type: ignore[arg-type]
                has_official_source=bool(get_col("has_official_source", 0)),
                has_regulatory_source=bool(get_col("has_regulatory_source", 0)),
                has_major_media_source=bool(get_col("has_major_media_source", 0)),
                official_source_url=str(get_col("official_source_url")) if get_col("official_source_url") is not None else None,
                official_source_name=str(get_col("official_source_name")) if get_col("official_source_name") is not None else None,
                reference_source_name=str(get_col("reference_source_name")) if get_col("reference_source_name") is not None else None,
                related_sources=json.loads(str(get_col("related_sources", "[]")) or "[]"),
            )
            event_dict[ev.event_id] = ev
            events.append(ev)

        # Attach event metadata to articles if article has event_id
        for art in articles:
            if art.event_id and art.event_id in event_dict:
                ev = event_dict[art.event_id]
                if not art.event_title:
                    art.event_title = ev.title
                art.event_source_count = ev.source_count
                art.event_independent_source_count = ev.independent_source_count
                art.event_has_official_source = ev.has_official_source
                art.event_has_regulatory_source = ev.has_regulatory_source
                art.event_has_major_media_source = ev.has_major_media_source
                art.event_official_source_url = ev.official_source_url
                art.event_official_source_name = ev.official_source_name
                art.event_reference_source_name = ev.reference_source_name
                art.event_related_sources = ev.related_sources

        created_at = _parse_datetime(issue_row["created_at"])
        sent_at = _parse_datetime(issue_row["sent_at"])
        return NewsletterIssue(
            issue_date=issue_row["issue_date"],
            title=issue_row["title"],
            articles=articles,
            warnings=json.loads(issue_row["warnings"] or "[]"),
            created_at=created_at,
            sent_at=sent_at,
            events=events,
        )

    def get_event_articles(self, event_id: str) -> list[EventArticle]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from event_articles where event_id = ? order by similarity desc",
                (event_id,),
            ).fetchall()
        return [
            EventArticle(
                event_id=r["event_id"],
                article_id=r["article_id"],
                relationship=r["relationship"],
                similarity=float(r["similarity"]),
            )
            for r in rows
        ]

    def list_issues(self) -> list[tuple[str, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select issues.issue_date, count(articles.id) as article_count
                from issues
                left join articles on articles.issue_id = issues.id
                group by issues.id
                order by issues.issue_date desc
                """
            ).fetchall()
        return [(row["issue_date"], row["article_count"]) for row in rows]

    def get_recent_articles(
        self, before_issue_date: str | None = None, days: int = 7
    ) -> list[Article]:
        with self._connect() as conn:
            if before_issue_date:
                rows = conn.execute(
                    """
                    select articles.*
                    from articles
                    join issues on articles.issue_id = issues.id
                    where issues.issue_date < ?
                      and date(issues.issue_date) >= date(?, '-' || ? || ' day')
                      and articles.category != 'conference'
                    order by issues.issue_date desc, articles.position asc
                    """,
                    (before_issue_date, before_issue_date, days),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    select articles.*
                    from articles
                    join issues on articles.issue_id = issues.id
                    where date(issues.issue_date) >= date('now', '-' || ? || ' day')
                      and articles.category != 'conference'
                    order by issues.issue_date desc, articles.position asc
                    """,
                    (days,),
                ).fetchall()
        return [self._row_to_article(row) for row in rows]

    def mark_sent(self, issue_date: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("update issues set sent_at = ? where issue_date = ?", (now, issue_date))

    def mail_settings(self) -> dict[str, object]:
        with self._connect() as conn:
            row = conn.execute(
                "select value from app_settings where key = ?", ("mail",)
            ).fetchone()
        if row is None:
            return {}
        return json.loads(row["value"] or "{}")

    def save_mail_settings(self, values: dict[str, object]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                insert into app_settings (key, value, updated_at)
                values (?, ?, ?)
                on conflict(key) do update set value = excluded.value, updated_at = excluded.updated_at
                """,
                ("mail", json.dumps(values, ensure_ascii=False), now),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists issues (
                    id integer primary key autoincrement,
                    issue_date text not null unique,
                    title text not null,
                    warnings text not null default '[]',
                    created_at text not null,
                    updated_at text not null,
                    sent_at text
                )
                """
            )
            conn.execute(
                """
                create table if not exists articles (
                    id integer primary key autoincrement,
                    issue_id integer not null references issues(id) on delete cascade,
                    position integer not null,
                    title text not null,
                    url text not null,
                    source text not null,
                    category text not null,
                    published_at text,
                    summary_ko text not null,
                    excerpt text not null,
                    tags text not null,
                    score real not null,
                    article_id text,
                    canonical_url text,
                    original_url text,
                    source_id text,
                    publisher text,
                    discovered_via text,
                    source_type text not null default 'media',
                    source_authority integer not null default 70,
                    summary_en text not null default '',
                    why_it_matters_ko text not null default '',
                    primary_category text,
                    secondary_categories text not null default '[]',
                    topics text not null default '[]',
                    entities text not null default '[]',
                    source_score real not null default 0,
                    relevance_score real not null default 0,
                    impact_score real not null default 0,
                    novelty_score real not null default 0,
                    recency_score real not null default 0,
                    priority_score real not null default 0,
                    event_id text,
                    event_title text,
                    related_article_ids text not null default '[]',
                    is_official integer not null default 0,
                    is_reference integer not null default 0,
                    is_primary_source integer not null default 0,
                    collected_at text,
                    content text not null default '',
                    key_points text not null default '[]',
                    summary_model text,
                    summary_version text,
                    summary_created_at text
                )
                """
            )

            # Lightweight schema migration for existing databases
            existing_columns = {
                row["name"]
                for row in conn.execute("pragma table_info(articles)").fetchall()
            }
            new_columns = [
                ("article_id", "text"),
                ("canonical_url", "text"),
                ("original_url", "text"),
                ("source_id", "text"),
                ("publisher", "text"),
                ("discovered_via", "text"),
                ("source_type", "text default 'media'"),
                ("source_authority", "integer default 70"),
                ("summary_en", "text default ''"),
                ("why_it_matters_ko", "text default ''"),
                ("primary_category", "text"),
                ("secondary_categories", "text default '[]'"),
                ("topics", "text default '[]'"),
                ("entities", "text default '[]'"),
                ("source_score", "real default 0"),
                ("relevance_score", "real default 0"),
                ("impact_score", "real default 0"),
                ("novelty_score", "real default 0"),
                ("recency_score", "real default 0"),
                ("priority_score", "real default 0"),
                ("event_id", "text"),
                ("event_title", "text"),
                ("related_article_ids", "text default '[]'"),
                ("is_official", "integer default 0"),
                ("is_reference", "integer default 0"),
                ("is_primary_source", "integer default 0"),
                ("collected_at", "text"),
                ("content", "text default ''"),
                ("key_points", "text default '[]'"),
                ("summary_model", "text"),
                ("summary_version", "text"),
                ("summary_created_at", "text"),
            ]
            for col_name, col_def in new_columns:
                if col_name not in existing_columns:
                    conn.execute(f"alter table articles add column {col_name} {col_def}")

            conn.execute(
                """
                create table if not exists events (
                    event_id text primary key,
                    issue_id integer not null references issues(id) on delete cascade,
                    title text not null,
                    category text not null default 'big',
                    importance real not null default 0.0,
                    primary_article_id text,
                    created_at text not null,
                    source_count integer not null default 1,
                    independent_source_count integer not null default 1,
                    has_official_source integer not null default 0,
                    has_regulatory_source integer not null default 0,
                    has_major_media_source integer not null default 0,
                    official_source_url text,
                    official_source_name text,
                    reference_source_name text,
                    related_sources text not null default '[]'
                )
                """
            )

            # Migration for events table
            existing_event_columns = {
                row["name"]
                for row in conn.execute("pragma table_info(events)").fetchall()
            }
            new_event_columns = [
                ("source_count", "integer not null default 1"),
                ("independent_source_count", "integer not null default 1"),
                ("has_official_source", "integer not null default 0"),
                ("has_regulatory_source", "integer not null default 0"),
                ("has_major_media_source", "integer not null default 0"),
                ("official_source_url", "text"),
                ("official_source_name", "text"),
                ("reference_source_name", "text"),
                ("related_sources", "text not null default '[]'"),
            ]
            for col_name, col_def in new_event_columns:
                if col_name not in existing_event_columns:
                    conn.execute(f"alter table events add column {col_name} {col_def}")

            conn.execute(
                """
                create table if not exists event_articles (
                    event_id text not null references events(event_id) on delete cascade,
                    article_id text not null,
                    relationship text not null default 'coverage',
                    similarity real not null default 1.0,
                    primary key (event_id, article_id)
                )
                """
            )

            conn.execute(
                """
                create table if not exists app_settings (
                    key text primary key,
                    value text not null,
                    updated_at text not null
                )
                """
            )

    @staticmethod
    def _row_to_article(row: sqlite3.Row) -> Article:
        keys = set(row.keys())

        def get_val(key: str, default: object = None) -> object:
            if key in keys:
                v = row[key]
                return v if v is not None else default
            return default

        def get_json_list(key: str) -> list[str]:
            val = get_val(key, "[]")
            if not val:
                return []
            try:
                parsed = json.loads(str(val))
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []

        title = str(get_val("title", ""))
        url = str(get_val("url", ""))
        source = str(get_val("source", ""))
        category = str(get_val("category", "big"))
        published_at = _parse_datetime(get_val("published_at"))
        summary_ko = str(get_val("summary_ko", ""))
        excerpt = str(get_val("excerpt", ""))
        tags = get_json_list("tags")
        score = float(get_val("score", 0.0))

        discovered_via = get_val("discovered_via")
        source_id = get_val("source_id")
        source_type = str(get_val("source_type", "media"))
        source_authority = int(get_val("source_authority", 70))
        publisher = get_val("publisher")

        article_id = get_val("article_id")
        canonical_url = get_val("canonical_url")
        original_url = get_val("original_url")

        summary_en = str(get_val("summary_en", ""))
        why_it_matters_ko = str(get_val("why_it_matters_ko", ""))

        primary_category = get_val("primary_category") or category
        secondary_categories = get_json_list("secondary_categories")
        topics = get_json_list("topics")
        entities = get_json_list("entities")

        source_score = float(get_val("source_score", source_authority))
        relevance_score = float(get_val("relevance_score", 0.0))
        impact_score = float(get_val("impact_score", 0.0))
        novelty_score = float(get_val("novelty_score", 0.0))
        recency_score = float(get_val("recency_score", 0.0))
        priority_score = float(get_val("priority_score", score))

        event_id = get_val("event_id")
        event_title = get_val("event_title")
        related_article_ids = get_json_list("related_article_ids")

        is_official = bool(get_val("is_official", 0))
        is_reference = bool(get_val("is_reference", 0))
        is_primary_source = bool(get_val("is_primary_source", 0))

        collected_at = _parse_datetime(get_val("collected_at"))
        content = str(get_val("content", ""))
        key_points = get_json_list("key_points")
        summary_model = get_val("summary_model")
        summary_version = get_val("summary_version")
        summary_created_at = _parse_datetime(get_val("summary_created_at"))

        return Article(
            title=title,
            url=url,
            source=source,
            category=category,
            published_at=published_at,
            summary_ko=summary_ko,
            excerpt=excerpt,
            tags=tags,
            score=score,
            discovered_via=discovered_via,
            source_id=source_id,
            authority_score=source_authority,
            source_type=source_type,
            source_authority=source_authority,
            publisher=publisher,
            article_id=article_id,
            canonical_url=canonical_url,
            original_url=original_url,
            summary_en=summary_en,
            why_it_matters_ko=why_it_matters_ko,
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            topics=topics,
            entities=entities,
            source_score=source_score,
            relevance_score=relevance_score,
            impact_score=impact_score,
            novelty_score=novelty_score,
            recency_score=recency_score,
            priority_score=priority_score,
            event_id=event_id,
            event_title=str(event_title) if event_title is not None else None,
            related_article_ids=related_article_ids,
            is_official=is_official,
            is_reference=is_reference,
            is_primary_source=is_primary_source,
            collected_at=collected_at,
            content=content,
            key_points=key_points,
            summary_model=str(summary_model) if summary_model is not None else None,
            summary_version=str(summary_version) if summary_version is not None else None,
            summary_created_at=summary_created_at,
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
