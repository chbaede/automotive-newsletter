from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage

from .config import Settings, load_settings
from .models import NewsletterIssue
from .presentation import (
    display_summary_ko,
    display_title_ko,
    display_url,
    regions_for_article,
    sort_articles_for_section,
    visible_tags,
)
from .priority import assess_priority
from .sources import SECTION_LABELS, SECTION_ORDER


class MailConfigError(RuntimeError):
    pass


PRIORITY_COLORS = {
    "critical": {"solid": "#b42318", "soft": "#fff1f2", "text": "#7f1d1d"},
    "high": {"solid": "#b45309", "soft": "#fff7ed", "text": "#7c2d12"},
    "medium": {"solid": "#2563eb", "soft": "#eff6ff", "text": "#1e3a8a"},
    "watch": {"solid": "#64748b", "soft": "#f1f5f9", "text": "#334155"},
}


def build_email_html(issue: NewsletterIssue) -> str:
    sections = _email_sections(issue)
    metrics = _email_metrics(sections)
    preheader = (
        f"{issue.issue_date} 자동차 산업 핵심 브리핑 "
        f"{metrics['total']}건, 최우선 {metrics['critical']}건, "
        f"예정 컨퍼런스 {metrics['conference']}건"
    )
    parts = [
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Automotive Intelligence Brief</title></head>",
        '<body style="margin:0;padding:0;background-color:#f3f6f8;color:#18202a;">',
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{html.escape(preheader)}</div>',
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f3f6f8;padding:28px 0;">',
        '<tr><td align="center" style="padding:0 14px;">',
        '<table role="presentation" width="720" cellspacing="0" cellpadding="0" style="width:100%;max-width:720px;border-collapse:separate;border-spacing:0;font-family:Arial,Helvetica,sans-serif;">',
        '<tr><td style="background-color:#12343b;color:#ffffff;padding:30px 30px 24px;border-radius:8px 8px 0 0;">',
        '<div style="font-size:12px;font-weight:700;line-height:1.4;color:#b9d8d4;">Automotive Intelligence Brief</div>',
        f'<h1 style="margin:8px 0 8px;font-size:28px;line-height:1.22;font-weight:800;color:#ffffff;">{html.escape(issue.issue_date)} 자동차 산업 브리핑</h1>',
        '<p style="margin:0;font-size:14px;line-height:1.6;color:#d7e8e5;">OEM, Tier 1, SDV, 기관 리포트와 예정 컨퍼런스를 우선순위 중심으로 정리했습니다.</p>',
        "</td></tr>",
        '<tr><td style="background-color:#ffffff;padding:24px 30px 30px;border-radius:0 0 8px 8px;border:1px solid #dde4ec;border-top:0;">',
        '<h2 style="margin:0 0 12px;font-size:18px;line-height:1.3;color:#18202a;">Executive Snapshot</h2>',
        _metric_table(metrics),
    ]
    for category, label, articles in sections:
        if not articles:
            continue
        parts.append(
            f'<h2 style="margin:28px 0 12px;font-size:20px;line-height:1.3;color:#18202a;">{html.escape(label)}</h2>'
        )
        for article in articles:
            parts.append(_article_card_html(article))
    if issue.warnings:
        parts.append(
            '<h2 style="margin:28px 0 12px;font-size:20px;line-height:1.3;color:#18202a;">수집 참고</h2>'
        )
        for warning in issue.warnings:
            parts.append(
                '<p style="margin:0 0 8px;padding:12px 14px;border:1px solid #f0d29a;border-radius:8px;background-color:#fff7e8;color:#5b3b04;font-size:13px;line-height:1.55;">'
                f"{html.escape(warning)}</p>"
            )
    parts.extend(
        [
            '<div style="margin-top:30px;padding-top:18px;border-top:1px solid #dde4ec;color:#657285;font-size:12px;line-height:1.55;">',
            "이 메일은 로컬 Automotive Newsletter 앱에서 생성했습니다. 원문 버튼은 확인 가능한 실제 기사 또는 공식 페이지로 연결됩니다.",
            "</div>",
            "</td></tr></table></td></tr></table></body></html>",
        ]
    )
    return "".join(parts)


def build_email_text(issue: NewsletterIssue) -> str:
    sections = _email_sections(issue)
    metrics = _email_metrics(sections)
    lines = [
        f"Automotive Intelligence Brief - {issue.issue_date}",
        f"총 브리핑: {metrics['total']}건 / 최우선 뉴스: {metrics['critical']}건 / 높음: {metrics['high']}건 / 예정 컨퍼런스: {metrics['conference']}건",
        "",
    ]
    for _, label, articles in sections:
        if not articles:
            continue
        lines.append(label)
        for article in articles:
            priority = assess_priority(article)
            lines.append(f"- [{priority.label_ko}] {display_title_ko(article)}")
            lines.append(f"  중요도: {priority.score} / {priority.reason_ko}")
            lines.append(f"  {display_summary_ko(article)}")
            region_label = ", ".join(region.label_ko for region in regions_for_article(article))
            lines.append(f"  지역: {region_label}")
            lines.append(f"  출처: {article.source}")
            source_url = display_url(article)
            if source_url:
                lines.append(f"  원문: {source_url}")
        lines.append("")
    return "\n".join(lines)


def send_issue(issue: NewsletterIssue, settings: Settings | None = None) -> None:
    settings = settings or load_settings()
    missing = settings.missing_smtp_fields()
    if missing:
        raise MailConfigError(f"메일 발송 설정이 부족합니다: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = f"[Automotive Brief] {issue.issue_date} | OEM·Tier1·SDV"
    message["From"] = settings.smtp_from or ""
    message["To"] = ", ".join(settings.recipients)
    message.set_content(build_email_text(issue))
    message.add_alternative(build_email_html(issue), subtype="html")

    with smtplib.SMTP(settings.smtp_host or "", settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def _email_sections(issue: NewsletterIssue) -> list[tuple[str, str, list]]:
    sections = []
    for category in SECTION_ORDER:
        articles = sort_articles_for_section(
            category,
            [article for article in issue.articles if article.category == category],
            issue.issue_date,
        )
        sections.append((category, SECTION_LABELS[category], articles))
    return sections


def _email_metrics(sections: list[tuple[str, str, list]]) -> dict[str, int]:
    articles = [article for category, _, items in sections for article in items]
    news_articles = [article for article in articles if article.category != "conference"]
    critical = 0
    high = 0
    for article in news_articles:
        priority = assess_priority(article)
        if priority.level == "critical":
            critical += 1
        elif priority.level == "high":
            high += 1
    return {
        "total": len(articles),
        "critical": critical,
        "high": high,
        "conference": len([article for article in articles if article.category == "conference"]),
    }


def _metric_table(metrics: dict[str, int]) -> str:
    cells = [
        ("총 브리핑", metrics["total"], "#12343b"),
        ("최우선 뉴스", metrics["critical"], "#b42318"),
        ("높음", metrics["high"], "#b45309"),
        ("예정 컨퍼런스", metrics["conference"], "#0f766e"),
    ]
    rendered = []
    for label, value, color in cells:
        rendered.append(
            '<td width="25%" style="padding:0 6px 8px 0;">'
            f'<div style="border:1px solid #dde4ec;border-radius:8px;background-color:#f8fafc;padding:14px 12px;">'
            f'<div style="font-size:24px;line-height:1;font-weight:800;color:{color};">{value}</div>'
            f'<div style="margin-top:7px;font-size:12px;line-height:1.4;font-weight:700;color:#657285;">{html.escape(label)}</div>'
            "</div></td>"
        )
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:0;margin-bottom:8px;"><tr>'
        + "".join(rendered)
        + "</tr></table>"
    )


def _article_card_html(article) -> str:
    priority = assess_priority(article)
    colors = PRIORITY_COLORS[priority.level]
    source_url = display_url(article)
    region_label = ", ".join(region.label_ko for region in regions_for_article(article))
    tags = visible_tags(article)
    tag_html = ""
    if tags:
        tag_html = (
            '<div style="margin-top:12px;">'
            + "".join(
                f'<span style="display:inline-block;margin:0 5px 5px 0;padding:4px 8px;border-radius:999px;background-color:#e8f2ef;color:#14534d;font-size:12px;font-weight:700;">{html.escape(tag)}</span>'
                for tag in tags[:6]
            )
            + "</div>"
        )
    cta_html = (
        f'<a href="{html.escape(source_url)}" style="display:inline-block;margin-top:14px;padding:10px 14px;border-radius:8px;background-color:#174ea6;color:#ffffff;font-size:13px;font-weight:800;text-decoration:none;">원문 보기</a>'
        if source_url
        else '<span style="display:inline-block;margin-top:14px;color:#657285;font-size:13px;font-weight:700;">원문 확인 중</span>'
    )
    return (
        f'<table class="brief-card brief-card--{priority.level}" role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        f'style="border-collapse:separate;border-spacing:0;margin:0 0 12px;border:1px solid #dde4ec;border-left:5px solid {colors["solid"]};border-radius:8px;background-color:#ffffff;">'
        '<tr><td style="padding:16px 18px 17px;">'
        '<div style="margin-bottom:10px;">'
        f'<span class="priority-badge" style="display:inline-block;margin:0 8px 7px 0;padding:5px 9px;border-radius:999px;background-color:{colors["solid"]};color:#ffffff;font-size:12px;line-height:1.2;font-weight:800;">{html.escape(priority.label_ko)} · {priority.score}</span>'
        f'<span style="display:inline-block;margin-bottom:7px;color:#657285;font-size:12px;line-height:1.2;font-weight:700;">{html.escape(article.source)}</span>'
        "</div>"
        f'<h3 style="margin:0 0 9px;font-size:18px;line-height:1.38;color:#18202a;">{html.escape(display_title_ko(article))}</h3>'
        f'<p style="margin:0 0 10px;padding:9px 10px;border-radius:8px;background-color:{colors["soft"]};color:{colors["text"]};font-size:13px;line-height:1.55;font-weight:700;">{html.escape(priority.reason_ko)}</p>'
        f'<p style="margin:0;color:#334155;font-size:14px;line-height:1.62;">{html.escape(display_summary_ko(article))}</p>'
        f'<p style="margin:12px 0 0;color:#657285;font-size:12px;line-height:1.55;">지역: {html.escape(region_label)} · 출처: {html.escape(article.source)}</p>'
        f"{tag_html}{cta_html}"
        "</td></tr></table>"
    )
