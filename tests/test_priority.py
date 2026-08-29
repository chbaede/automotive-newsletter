from automotive_newsletter.models import Article, NewsletterIssue
from automotive_newsletter.priority import assess_priority, priority_summary


def test_assess_priority_marks_high_issue_sdv_news_as_critical():
    article = Article(
        title="Toyota and Nvidia announce software-defined vehicle partnership",
        url="https://example.com/sdv-partnership",
        source="Reuters",
        category="sdv",
        excerpt="The partnership expands OTA and zonal architecture programs.",
        tags=["Toyota", "Nvidia", "SDV", "OTA"],
        score=78,
    )

    priority = assess_priority(article)

    assert priority.level == "critical"
    assert priority.label_ko == "최우선"
    assert "이슈화" in priority.reason_ko


def test_assess_priority_marks_low_score_fallback_as_watch():
    article = Article(
        title="Supplier official newsroom",
        url="https://example.com/newsroom",
        source="공식 뉴스룸",
        category="tier1",
        summary_ko="공식 뉴스룸 확인 링크입니다.",
        score=34,
    )

    priority = assess_priority(article)

    assert priority.level == "watch"
    assert priority.label_ko == "관찰"


def test_priority_summary_counts_levels_and_keeps_top_items_first():
    issue = NewsletterIssue(
        issue_date="2026-06-08",
        articles=[
            Article(
                title="Fallback",
                url="https://example.com/fallback",
                source="공식 뉴스룸",
                category="tier1",
                score=34,
            ),
            Article(
                title="OEM recall investigation expands",
                url="https://example.com/recall",
                source="Automotive News",
                category="big",
                tags=["OEM"],
                score=72,
            ),
        ],
    )

    summary = priority_summary(issue)

    assert summary.counts["critical"] == 1
    assert summary.counts["watch"] == 1
    assert summary.top_items[0].article.title == "OEM recall investigation expands"
