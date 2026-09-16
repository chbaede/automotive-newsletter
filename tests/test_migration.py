import json
import sqlite3
from datetime import datetime, timezone

from automotive_newsletter.models import Article
from automotive_newsletter.store import NewsletterStore


def test_legacy_database_migration_and_data_preservation(tmp_path):
    db_path = tmp_path / "legacy_newsletter.db"

    # 1. Create a database strictly simulating the legacy 11-column schema
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            create table issues (
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
            create table articles (
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
        # Insert legacy issue and legacy article
        conn.execute(
            """
            insert into issues (id, issue_date, title, warnings, created_at, updated_at)
            values (1, '2026-05-01', '2026-05-01 Automotive Newsletter', '[]', '2026-05-01T06:00:00+00:00', '2026-05-01T06:00:00+00:00')
            """
        )
        conn.execute(
            """
            insert into articles (
                issue_id, position, title, url, source, category, published_at,
                summary_ko, excerpt, tags, score
            )
            values (
                1, 0, 'Legacy Tesla Battery Factory Update', 'https://example.com/legacy-tesla',
                'Reuters', 'big', '2026-05-01T05:30:00+00:00',
                '레거시 요약본입니다.', 'Legacy excerpt content', '["Tesla", "Battery"]', 85.5
            )
            """
        )

    # 2. Open this legacy database using the new NewsletterStore
    store = NewsletterStore(db_path)

    # 3. Verify existing legacy data is read properly without data loss
    issue = store.get_issue("2026-05-01")
    assert issue is not None
    assert issue.issue_date == "2026-05-01"
    assert len(issue.articles) == 1

    art = issue.articles[0]
    # Check original fields preserved
    assert art.title == "Legacy Tesla Battery Factory Update"
    assert art.url == "https://example.com/legacy-tesla"
    assert art.source == "Reuters"
    assert art.category == "big"
    assert art.published_at == datetime(2026, 5, 1, 5, 30, tzinfo=timezone.utc)
    assert art.summary_ko == "레거시 요약본입니다."
    assert art.excerpt == "Legacy excerpt content"
    assert art.tags == ["Tesla", "Battery"]
    assert art.score == 85.5

    # Check migrated fields populated with safe defaults
    assert art.canonical_url == "https://example.com/legacy-tesla"
    assert art.original_url == "https://example.com/legacy-tesla"
    assert art.article_id.startswith("art_")
    assert art.publisher == "Reuters"
    assert art.source_type == "media"
    assert art.source_authority == 70
    assert art.primary_category == "big"
    assert art.is_official is False

    # 4. Verify SQLite schema was safely upgraded with new columns
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cols = {row["name"] for row in conn.execute("pragma table_info(articles)").fetchall()}
        required_cols = {
            "article_id",
            "canonical_url",
            "original_url",
            "source_id",
            "publisher",
            "discovered_via",
            "source_type",
            "source_authority",
            "summary_en",
            "why_it_matters_ko",
            "primary_category",
            "secondary_categories",
            "topics",
            "entities",
            "source_score",
            "relevance_score",
            "impact_score",
            "novelty_score",
            "recency_score",
            "priority_score",
            "event_id",
            "related_article_ids",
            "is_official",
            "is_reference",
            "is_primary_source",
            "collected_at",
        }
        for col in required_cols:
            assert col in cols, f"Column {col} missing from migrated table"

    # 5. Save a new issue with complete intelligence metadata and verify retrieval
    rich_article = Article(
        title="Hyundai Mobis debuts new Steer-by-Wire system",
        url="https://example.com/mobis-sbw",
        source="Hyundai Mobis Newsroom",
        category="tier1",
        published_at=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
        summary_ko="현대모비스가 차세대 SbW 시스템을 공개했습니다.",
        summary_en="Hyundai Mobis unveiled its next-generation Steer-by-Wire system.",
        why_it_matters_ko="SDV 아키텍처 핵심 부품의 국산화 및 공급망 다변화 가속화.",
        excerpt="The new SbW system enhances safety and cabin space.",
        tags=["Hyundai Mobis", "SbW", "SDV"],
        score=92.0,
        discovered_via="Official Press",
        source_id="mobis_official",
        publisher="Hyundai Mobis",
        source_type="official",
        source_authority=95,
        canonical_url="https://example.com/mobis-sbw",
        original_url="https://example.com/mobis-sbw?ref=rss",
        primary_category="tier1",
        secondary_categories=["sdv"],
        topics=["Steer-by-Wire", "Chassis"],
        entities=["Hyundai Mobis"],
        source_score=95.0,
        relevance_score=88.0,
        impact_score=90.0,
        novelty_score=85.0,
        recency_score=95.0,
        priority_score=92.0,
        event_id="EVT_2026_SBW",
        related_article_ids=["art_12345"],
        is_official=True,
        is_reference=False,
        is_primary_source=True,
        collected_at=datetime(2026, 9, 16, 8, 30, tzinfo=timezone.utc),
    )

    store.save_issue("2026-09-16", [rich_article])
    saved_issue = store.get_issue("2026-09-16")
    assert saved_issue is not None
    assert len(saved_issue.articles) == 1
    retrieved = saved_issue.articles[0]

    assert retrieved.title == rich_article.title
    assert retrieved.summary_en == "Hyundai Mobis unveiled its next-generation Steer-by-Wire system."
    assert retrieved.why_it_matters_ko == "SDV 아키텍처 핵심 부품의 국산화 및 공급망 다변화 가속화."
    assert retrieved.source_type == "official"
    assert retrieved.source_authority == 95
    assert retrieved.is_official is True
    assert retrieved.is_primary_source is True
    assert retrieved.secondary_categories == ["sdv"]
    assert retrieved.topics == ["Steer-by-Wire", "Chassis"]
    assert retrieved.entities == ["Hyundai Mobis"]
    assert retrieved.event_id == "EVT_2026_SBW"
    assert retrieved.related_article_ids == ["art_12345"]
    assert retrieved.priority_score == 92.0

