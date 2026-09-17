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


def test_priority_boundary_thresholds():
    # Boundary: 80.0 (critical) vs 79.9 (high)
    art_critical = Article(
        title="Critical boundary item",
        url="https://example.com/crit",
        source="Test Source",
        relevance_score=80.0,
        impact_score=80.0,
        priority_score=80.0,
    )
    signal_crit = assess_priority(art_critical)
    assert signal_crit.level == "critical"
    assert signal_crit.label_ko == "최우선"
    assert signal_crit.score == 80
    assert art_critical.priority_score == 80.0

    art_high = Article(
        title="High boundary item",
        url="https://example.com/high",
        source="Test Source",
        relevance_score=75.0,
        impact_score=60.0,
        priority_score=79.9,
    )
    signal_high = assess_priority(art_high)
    assert signal_high.level == "high"
    assert signal_high.label_ko == "높음"
    assert signal_high.score == 80  # rounded 79.9
    assert art_high.priority_score == 79.9

    # Boundary: 60.0 (high) vs 59.9 (medium)
    art_high_60 = Article(
        title="High boundary 60",
        url="https://example.com/high60",
        source="Test Source",
        relevance_score=60.0,
        impact_score=50.0,
        priority_score=60.0,
    )
    signal_high_60 = assess_priority(art_high_60)
    assert signal_high_60.level == "high"
    assert signal_high_60.label_ko == "높음"
    assert signal_high_60.score == 60

    art_med = Article(
        title="Medium boundary 59.9",
        url="https://example.com/med59",
        source="Test Source",
        relevance_score=50.0,
        impact_score=40.0,
        priority_score=59.9,
    )
    signal_med = assess_priority(art_med)
    assert signal_med.level == "medium"
    assert signal_med.label_ko == "보통"
    assert signal_med.score == 60

    # Boundary: 45.0 (medium) vs 44.9 (watch)
    art_med_45 = Article(
        title="Medium boundary 45",
        url="https://example.com/med45",
        source="Test Source",
        relevance_score=40.0,
        impact_score=35.0,
        priority_score=45.0,
    )
    signal_med_45 = assess_priority(art_med_45)
    assert signal_med_45.level == "medium"
    assert signal_med_45.label_ko == "보통"
    assert signal_med_45.score == 45

    art_watch = Article(
        title="Watch boundary 44.9",
        url="https://example.com/watch44",
        source="Test Source",
        relevance_score=30.0,
        impact_score=30.0,
        priority_score=44.9,
    )
    signal_watch = assess_priority(art_watch)
    assert signal_watch.level == "watch"
    assert signal_watch.label_ko == "관찰"
    assert signal_watch.score == 45

    # Min (10.0) and Max (100.0)
    art_min = Article(
        title="Min score item",
        url="https://example.com/min",
        source="Test Source",
        relevance_score=10.0,
        impact_score=10.0,
        priority_score=10.0,
    )
    assert assess_priority(art_min).level == "watch"

    art_max = Article(
        title="Max score item",
        url="https://example.com/max",
        source="Test Source",
        relevance_score=100.0,
        impact_score=100.0,
        priority_score=100.0,
    )
    assert assess_priority(art_max).level == "critical"


def test_priority_does_not_override_precomputed_priority_score():
    """Verify priority.py does not override or mutate scoring.py's priority_score."""
    article = Article(
        title="Pre-scored article with custom priority",
        url="https://example.com/prescored",
        source="Wire",
        relevance_score=72.0,
        impact_score=68.0,
        source_score=85.0,
        novelty_score=90.0,
        recency_score=70.0,
        priority_score=75.4,
    )

    signal = assess_priority(article)

    # Must preserve exact 75.4 without recalculating or hardcoded overriding
    assert article.priority_score == 75.4
    assert signal.score == 75
    assert signal.level == "high"

