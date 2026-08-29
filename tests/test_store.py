from datetime import datetime, timezone

from automotive_newsletter.models import Article
from automotive_newsletter.store import NewsletterStore


def test_store_upserts_issue_and_returns_latest_with_history(tmp_path):
    db_path = tmp_path / "newsletter.db"
    store = NewsletterStore(db_path)
    article = Article(
        title="Toyota expands software-defined vehicle platform",
        url="https://example.com/toyota-sdv",
        source="Example Mobility",
        category="sdv",
        published_at=datetime(2026, 6, 8, 6, 0, tzinfo=timezone.utc),
        summary_ko="Toyota의 SDV 플랫폼 확대 동향입니다.",
        excerpt="Toyota announced a software platform update.",
        tags=["Toyota", "SDV"],
        score=88,
    )

    issue = store.save_issue("2026-06-08", [article], warnings=["one feed failed"])
    latest = store.latest_issue()
    history = store.list_issues()

    assert issue.issue_date == "2026-06-08"
    assert latest is not None
    assert latest.issue_date == "2026-06-08"
    assert latest.articles[0].title == article.title
    assert latest.articles[0].tags == ["Toyota", "SDV"]
    assert latest.warnings == ["one feed failed"]
    assert history == [("2026-06-08", 1)]


def test_store_replaces_same_day_articles(tmp_path):
    store = NewsletterStore(tmp_path / "newsletter.db")
    first = Article(title="Old", url="https://example.com/old", source="A", category="oem")
    second = Article(title="New", url="https://example.com/new", source="B", category="tier1")

    store.save_issue("2026-06-08", [first])
    store.save_issue("2026-06-08", [second])

    latest = store.latest_issue()
    assert latest is not None
    assert [article.title for article in latest.articles] == ["New"]

