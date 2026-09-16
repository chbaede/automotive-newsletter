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


def test_store_persists_and_reads_summary_metadata(tmp_path):
    store = NewsletterStore(tmp_path / "newsletter.db")
    created_ts = datetime(2026, 6, 8, 12, 34, 56, tzinfo=timezone.utc)
    article = Article(
        title="NVIDIA and MediaTek partner on automotive cockpit SoC",
        url="https://example.com/nvidia-mediatek",
        source="Tech Automotive",
        category="sdv",
        summary_ko="엔비디아와 미디어텍이 차량용 콕핏 SoC 개발에 협력합니다.",
        summary_en="NVIDIA and MediaTek announced a partnership on automotive cockpit SoCs.",
        why_it_matters_ko="차세대 스마트 콕핏 시장에서의 칩셋 경쟁 구도 변화를 예고합니다.",
        key_points=["NVIDIA-MediaTek 협력 체결", "차세대 콕핏 SoC 개발 목표"],
        summary_model="ollama:llama3.2",
        summary_version="v1",
        summary_created_at=created_ts,
        content="Full article content text goes here.",
    )

    store.save_issue("2026-06-08", [article])
    retrieved = store.get_issue("2026-06-08")

    assert retrieved is not None
    assert len(retrieved.articles) == 1
    art = retrieved.articles[0]
    assert art.summary_ko == "엔비디아와 미디어텍이 차량용 콕핏 SoC 개발에 협력합니다."
    assert art.summary_en == "NVIDIA and MediaTek announced a partnership on automotive cockpit SoCs."
    assert art.why_it_matters_ko == "차세대 스마트 콕핏 시장에서의 칩셋 경쟁 구도 변화를 예고합니다."
    assert art.key_points == ["NVIDIA-MediaTek 협력 체결", "차세대 콕핏 SoC 개발 목표"]
    assert art.summary_model == "ollama:llama3.2"
    assert art.summary_version == "v1"
    assert art.summary_created_at == created_ts
    assert art.content == "Full article content text goes here."


