from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import Article, NewsletterIssue


class NewsletterStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save_issue(
        self, issue_date: str, articles: Iterable[Article], warnings: list[str] | None = None
    ) -> NewsletterIssue:
        now = datetime.now(timezone.utc).isoformat()
        article_list = list(articles)
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
                        summary_ko, excerpt, tags, score
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
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

        articles = [self._row_to_article(row) for row in article_rows]
        created_at = _parse_datetime(issue_row["created_at"])
        sent_at = _parse_datetime(issue_row["sent_at"])
        return NewsletterIssue(
            issue_date=issue_row["issue_date"],
            title=issue_row["title"],
            articles=articles,
            warnings=json.loads(issue_row["warnings"] or "[]"),
            created_at=created_at,
            sent_at=sent_at,
        )

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
                    score real not null
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
        return Article(
            title=row["title"],
            url=row["url"],
            source=row["source"],
            category=row["category"],
            published_at=_parse_datetime(row["published_at"]),
            summary_ko=row["summary_ko"],
            excerpt=row["excerpt"],
            tags=json.loads(row["tags"] or "[]"),
            score=row["score"],
        )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
