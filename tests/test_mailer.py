import pytest

from automotive_newsletter.config import Settings
from automotive_newsletter.mailer import MailConfigError, build_email_html, build_email_text, send_issue
from automotive_newsletter.models import Article, NewsletterIssue


def test_send_issue_requires_smtp_settings(tmp_path):
    settings = Settings(db_path=tmp_path / "newsletter.db")
    issue = NewsletterIssue(issue_date="2026-06-08", articles=[])

    with pytest.raises(MailConfigError, match="SMTP_HOST"):
        send_issue(issue, settings=settings)


def test_build_email_html_contains_original_links():
    issue = NewsletterIssue(
        issue_date="2026-06-08",
        articles=[
            Article(
                title="Volkswagen updates EV platform",
                url="https://example.com/vw",
                source="Auto Wire",
                category="oem",
                summary_ko="Volkswagen의 EV 플랫폼 업데이트입니다. 원문 제목: Volkswagen updates EV platform",
                tags=["Volkswagen", "EV"],
                score=64,
            )
        ],
    )

    html = build_email_html(issue)
    text = build_email_text(issue)

    assert "Automotive Intelligence Brief" in html
    assert "brief-card" in html
    assert "priority-badge" in html
    assert "원문 보기" in html
    assert "Volkswagen의 EV 플랫폼 업데이트" in html
    assert "원문 제목" not in html
    assert "updates EV platform" not in html
    assert "전동화" in html or "EV" in html
    assert 'href="https://example.com/vw"' in html
    assert "유럽" in html
    assert "event_start:" not in html
    assert "[높음]" in text
    assert "원문 제목" not in text
    assert "지역: 유럽" in text


def test_build_email_html_uses_executive_briefing_layout():
    issue = NewsletterIssue(
        issue_date="2026-06-08",
        articles=[
            Article(
                title="OEM recall investigation expands after regulator probe",
                url="https://example.com/recall",
                source="Reuters",
                category="oem",
                summary_ko="GM 관련 품질·규제 리스크 확대 소식입니다.",
                tags=["GM", "event_start:2026-06-10"],
                score=82,
            ),
            Article(
                title="SDV USA 2026 | 2026년 6월 29-30일 · San Francisco",
                url="https://example.com/sdv-usa",
                source="공식 사이트",
                category="conference",
                tags=["event_start:2026-06-29", "event_end:2026-06-30"],
                score=40,
            ),
        ],
    )

    html = build_email_html(issue)

    assert "display:none" in html
    assert "Executive Snapshot" in html
    assert "최우선 뉴스" in html
    assert "예정 컨퍼런스" in html
    assert "brief-card--critical" in html
    assert "원문 보기" in html
    assert "event_start:" not in html
    assert "GM 관련 품질·규제" in html
