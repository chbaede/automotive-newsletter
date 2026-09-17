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


def test_email_renders_intelligence_sections_why_it_matters_and_cluster():
    from datetime import datetime, timezone

    dt = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
    issue = NewsletterIssue(
        issue_date="2026-09-17",
        articles=[
            Article(
                title="Continental unveils zonal HPC architecture for next-gen vehicles",
                url="https://continental.com/zonal-hpc",
                source="Continental",
                category="tier1",
                primary_category="tier1",
                source_type="official",
                published_at=dt,
                summary_ko="콘티넨탈이 차세대 E/E 아키텍처를 위한 조널 고성능 컴퓨터를 공개했습니다.",
                why_it_matters_ko="소프트웨어 정의 차량 아키텍처 구축 핵심 부품 선점",
                topics=["SDV", "E/E Architecture"],
                event_title="Continental Zonal HPC Launch",
                event_source_count=3,
                event_independent_source_count=2,
                event_has_official_source=True,
                event_official_source_url="https://continental.com/press/zonal-hpc",
                event_related_sources=["Continental", "Automotive News Europe", "Reuters"],
                score=85,
            )
        ],
    )

    html = build_email_html(issue, lang="ko")
    text = build_email_text(issue, lang="ko")

    # Section header
    assert "Tier 1 / 공급망" in html
    assert "Tier 1 / 공급망" in text

    # Category badge and Why it matters
    assert "부품사" in html or "Tier 1" in html
    assert "Why it matters:" in html
    assert "소프트웨어 정의 차량 아키텍처 구축 핵심 부품 선점" in html
    assert "Why it matters: 소프트웨어 정의 차량 아키텍처 구축 핵심 부품 선점" in text

    # Clustered event box
    assert "Continental Zonal HPC Launch" in html
    assert "3개 매체" in html
    assert "2개 독립 매체" in html
    assert "공식 출처 제공" in html
    assert "Continental, Automotive News Europe, Reuters" in html
    assert "https://continental.com/press/zonal-hpc" in html

    # Plain text event details
    assert "Event: Continental Zonal HPC Launch" in text
    assert "관련 출처: Continental, Automotive News Europe, Reuters" in text
    assert "공식 발표: https://continental.com/press/zonal-hpc" in text

    text_en = build_email_text(issue, lang="en")
    assert "Related Sources: Continental, Automotive News Europe, Reuters" in text_en
    assert "Official Source: https://continental.com/press/zonal-hpc" in text_en

