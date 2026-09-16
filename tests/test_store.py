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


def test_store_get_recent_articles(tmp_path):
    store = NewsletterStore(tmp_path / "newsletter.db")
    past_article = Article(title="Past OEM News", url="https://example.com/past", source="A", category="oem")
    conf_article = Article(title="CES 2026", url="https://example.com/ces", source="B", category="conference")
    old_article = Article(title="Very Old News", url="https://example.com/old", source="C", category="sdv")
    today_article = Article(title="Today News", url="https://example.com/today", source="D", category="big")

    store.save_issue("2026-06-01", [old_article])
    store.save_issue("2026-06-07", [past_article, conf_article])
    store.save_issue("2026-06-08", [today_article])

    # 7 days before 2026-06-08: includes 2026-06-07 and 2026-06-01
    recent = store.get_recent_articles(before_issue_date="2026-06-08", days=7)
    recent_titles = [a.title for a in recent]

    assert "Past OEM News" in recent_titles
    assert "Very Old News" in recent_titles
    assert "CES 2026" not in recent_titles  # conferences excluded
    assert "Today News" not in recent_titles  # before_issue_date excluded


