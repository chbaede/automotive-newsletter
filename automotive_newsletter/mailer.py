from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage

from .config import Settings, load_settings
from .models import NewsletterIssue
from .presentation import (
    build_intelligence_sections,
    canonical_source_type,
    compute_issue_metrics,
    display_event_coverage,
    display_factual_summary_en,
    display_factual_summary_ko,
    display_primary_category,
    display_published_time,
    display_summary_en,
    display_summary_ko,
    display_title_en,
    display_title_ko,
    display_url,
    display_why_it_matters_en,
    display_why_it_matters_ko,
    regions_for_article,
    sort_articles_for_section,
    visible_tags,
)
from .priority import assess_priority
from .sources import SECTION_LABELS, SECTION_LABELS_EN, SECTION_ORDER


class MailConfigError(RuntimeError):
    pass


PRIORITY_COLORS = {
    "critical": {"solid": "#b42318", "soft": "#fff1f2", "text": "#7f1d1d"},
    "high": {"solid": "#b45309", "soft": "#fff7ed", "text": "#7c2d12"},
    "medium": {"solid": "#2563eb", "soft": "#eff6ff", "text": "#1e3a8a"},
    "watch": {"solid": "#64748b", "soft": "#f1f5f9", "text": "#334155"},
}


def build_email_html(issue: NewsletterIssue, lang: str = "ko") -> str:
    sections = _email_sections(issue, lang=lang)
    metrics = compute_issue_metrics(sections)
    is_en = lang == "en"
    
    preheader = (
        f"{issue.issue_date} Automotive Industry Briefing "
        f"Total {metrics['total']}, Critical {metrics['critical']}, "
        f"Conferences {metrics['conference']}"
    ) if is_en else (
        f"{issue.issue_date} 자동차 산업 핵심 브리핑 "
        f"{metrics['total']}건, 최우선 {metrics['critical']}건, "
        f"예정 컨퍼런스 {metrics['conference']}건"
    )
    
    title_text = "Automotive Industry Briefing" if is_en else "자동차 산업 브리핑"
    subtitle_text = "Prioritized briefing on OEM, Tier 1, SDV, institutional reports and upcoming conferences." if is_en else "OEM, Tier 1, SDV, 기관 리포트와 예정 컨퍼런스를 우선순위 중심으로 정리했습니다."
    warnings_title = "Collection Note" if is_en else "수집 참고"
    
    parts = [
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Automotive Intelligence Brief</title></head>",
        '<body style="margin:0;padding:0;background-color:#f3f6f8;color:#18202a;">',
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{html.escape(preheader)}</div>',
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f3f6f8;padding:28px 0;">',
        '<tr><td align="center" style="padding:0 14px;">',
        '<table role="presentation" width="720" cellspacing="0" cellpadding="0" style="width:100%;max-width:720px;border-collapse:separate;border-spacing:0;font-family:Arial,Helvetica,sans-serif;">',
        '<tr><td style="background-color:#12343b;color:#ffffff;padding:30px 30px 24px;border-radius:8px 8px 0 0;">',
        '<div style="font-size:12px;font-weight:700;line-height:1.4;color:#b9d8d4;">Automotive Intelligence Brief</div>',
        f'<h1 style="margin:8px 0 8px;font-size:28px;line-height:1.22;font-weight:800;color:#ffffff;">{html.escape(issue.issue_date)} {title_text}</h1>',
        f'<p style="margin:0;font-size:14px;line-height:1.6;color:#d7e8e5;">{subtitle_text}</p>',
        "</td></tr>",
        '<tr><td style="background-color:#ffffff;padding:24px 30px 30px;border-radius:0 0 8px 8px;border:1px solid #dde4ec;border-top:0;">',
        '<h2 style="margin:0 0 12px;font-size:18px;line-height:1.3;color:#18202a;">Executive Snapshot</h2>',
        _metric_table(metrics, lang=lang),
    ]
    for category, label, articles in sections:
        if not articles:
            continue
        parts.append(
            f'<h2 style="margin:28px 0 12px;font-size:20px;line-height:1.3;color:#18202a;">{html.escape(label)}</h2>'
        )
        for article in articles:
            parts.append(_article_card_html(article, lang=lang))
    if issue.warnings:
        parts.append(
            f'<h2 style="margin:28px 0 12px;font-size:20px;line-height:1.3;color:#18202a;">{warnings_title}</h2>'
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


def build_email_text(issue: NewsletterIssue, lang: str = "ko") -> str:
    sections = _email_sections(issue, lang=lang)
    metrics = compute_issue_metrics(sections)
    is_en = lang == "en"

    
    lines = [
        f"Automotive Intelligence Brief - {issue.issue_date}",
        (
            f"Total News: {metrics['total']} / Critical: {metrics['critical']} / High: {metrics['high']} / Conferences: {metrics['conference']}"
        ) if is_en else (
            f"총 브리핑: {metrics['total']}건 / 최우선 뉴스: {metrics['critical']}건 / 높음: {metrics['high']}건 / 예정 컨퍼런스: {metrics['conference']}건"
        ),
        "",
    ]
    for _, label, articles in sections:
        if not articles:
            continue
        lines.append(label)
        for article in articles:
            priority = assess_priority(article)
            
            p_label = priority.label_en if is_en else priority.label_ko
            title = display_title_en(article) if is_en else display_title_ko(article)
            reason = priority.reason_en if is_en else priority.reason_ko
            summary = display_summary_en(article) if is_en else display_summary_ko(article)
            cat_label = display_primary_category(article, lang=lang)
            publisher = article.publisher or article.source
            
            lines.append(f"- [{p_label}] [{cat_label}] {title}")
            lines.append(f"  Score: {priority.score} / {reason}" if is_en else f"  중요도: {priority.score} / {reason}")
            lines.append(f"  {summary}")
            
            why_text = display_why_it_matters_en(article) if is_en else display_why_it_matters_ko(article)
            if why_text and why_text != reason:
                lines.append(f"  Why it matters: {why_text}")
            
            region_label = ", ".join(region.label_en if is_en else region.label_ko for region in regions_for_article(article))
            lines.append(f"  Region: {region_label}" if is_en else f"  지역: {region_label}")
            lines.append(f"  Source: {publisher}" if is_en else f"  출처: {publisher}")

            coverage = display_event_coverage(article)
            if coverage:
                if coverage.get("source_count", 1) > 1 and coverage.get("event_title"):
                    lines.append(f"  Event: {coverage['event_title']}")
                cov_parts = [str(coverage["source_label_en"] if is_en else coverage["source_label_ko"])]
                if coverage["independent_source_count"] < coverage["source_count"]:
                    cov_parts.append(str(coverage["independent_label_en"] if is_en else coverage["independent_label_ko"]))
                if coverage["has_official_source"]:
                    cov_parts.append(str(coverage["official_label_en"] if is_en else coverage["official_label_ko"]))
                lines.append(f"  [{' · '.join(cov_parts)}]")
                related_srcs = coverage.get("related_sources", [])
                if len(related_srcs) > 1:
                    rel_title = "Related Sources: " if is_en else "관련 출처: "
                    lines.append(f"  {rel_title}{', '.join(related_srcs)}")
                if coverage.get("official_source_url"):
                    off_title = "Official Source: " if is_en else "공식 발표: "
                    lines.append(f"  {off_title}{coverage['official_source_url']}")

            source_url = display_url(article)
            if source_url:
                lines.append(f"  원문: {source_url}")
        lines.append("")
    return "\n".join(lines)


def send_issue(issue: NewsletterIssue, settings: Settings | None = None, lang: str = "ko") -> None:
    settings = settings or load_settings()
    missing = settings.missing_smtp_fields()
    if missing:
        raise MailConfigError(f"메일 발송 설정이 부족합니다: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = f"[Automotive Brief] {issue.issue_date} | OEM·Tier1·SDV"
    message["From"] = settings.smtp_from or ""
    message["To"] = ", ".join(settings.recipients)
    message.set_content(build_email_text(issue, lang=lang))
    message.add_alternative(build_email_html(issue, lang=lang), subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host or "", settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailConfigError(f"메일 발송에 실패했습니다: {exc}") from exc


def _email_sections(issue: NewsletterIssue, lang: str = "ko") -> list[tuple[str, str, list]]:
    intel_sections = build_intelligence_sections(issue, lang=lang)
    return [
        (str(sec["key"]), str(sec["label"]), list(sec["articles"]))
        for sec in intel_sections
        if sec["articles"]
    ]


def _metric_table(metrics: dict[str, int], lang: str = "ko") -> str:
    is_en = lang == "en"
    cells = [
        ("Total News" if is_en else "총 브리핑", metrics["total"], "#12343b"),
        ("Critical" if is_en else "최우선 뉴스", metrics["critical"], "#b42318"),
        ("High" if is_en else "높음", metrics["high"], "#b45309"),
        ("Conferences" if is_en else "예정 컨퍼런스", metrics["conference"], "#0f766e"),
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


def _article_card_html(article, lang: str = "ko") -> str:
    is_en = lang == "en"
    priority = assess_priority(article)
    colors = PRIORITY_COLORS[priority.level]
    source_url = display_url(article)
    region_label = ", ".join((region.label_en if is_en else region.label_ko) for region in regions_for_article(article))
    tags = visible_tags(article)
    topics = getattr(article, "topics", [])
    
    tag_pills = []
    for top in topics:
        tag_pills.append(f'<span style="display:inline-block;margin:0 5px 5px 0;padding:4px 8px;border-radius:999px;background-color:#e0f2fe;color:#0369a1;font-size:12px;font-weight:700;">{html.escape(top)}</span>')
    for tag in tags[:6]:
        tag_pills.append(f'<span style="display:inline-block;margin:0 5px 5px 0;padding:4px 8px;border-radius:999px;background-color:#e8f2ef;color:#14534d;font-size:12px;font-weight:700;">{html.escape(tag)}</span>')
    
    tag_html = f'<div style="margin-top:12px;">{"".join(tag_pills)}</div>' if tag_pills else ""
    
    link_text = "Read Original" if is_en else "원문 보기"
    no_link_text = "Link Pending" if is_en else "원문 확인 중"
    
    cta_html = (
        f'<a href="{html.escape(source_url)}" style="display:inline-block;margin-top:14px;padding:10px 14px;border-radius:8px;background-color:#174ea6;color:#ffffff;font-size:13px;font-weight:800;text-decoration:none;">{link_text}</a>'
        if source_url
        else f'<span style="display:inline-block;margin-top:14px;color:#657285;font-size:13px;font-weight:700;">{no_link_text}</span>'
    )

    coverage = display_event_coverage(article)
    cluster_box_html = ""
    coverage_badges_html = ""
    official_cta_html = ""
    if coverage:
        pills = [
            f'<span style="display:inline-block;margin:0 5px 5px 0;padding:2px 7px;border-radius:999px;background-color:#eff6ff;color:#1e40af;font-size:11px;font-weight:700;border:1px solid #bfdbfe;">'
            f'{html.escape(str(coverage["source_label_en"] if is_en else coverage["source_label_ko"]))}</span>'
        ]
        if coverage["independent_source_count"] < coverage["source_count"]:
            pills.append(
                f'<span style="display:inline-block;margin:0 5px 5px 0;padding:2px 7px;border-radius:999px;background-color:#eff6ff;color:#1e40af;font-size:11px;font-weight:700;border:1px solid #bfdbfe;">'
                f'{html.escape(str(coverage["independent_label_en"] if is_en else coverage["independent_label_ko"]))}</span>'
            )
        if coverage["has_official_source"]:
            pills.append(
                f'<span style="display:inline-block;margin:0 5px 5px 0;padding:2px 7px;border-radius:999px;background-color:#f0fdf4;color:#166534;font-size:11px;font-weight:700;border:1px solid #bbf7d0;">'
                f'{html.escape(str(coverage["official_label_en"] if is_en else coverage["official_label_ko"]))}</span>'
            )
        if coverage["has_regulatory_source"]:
            pills.append(
                f'<span style="display:inline-block;margin:0 5px 5px 0;padding:2px 7px;border-radius:999px;background-color:#faf5ff;color:#6b21a8;font-size:11px;font-weight:700;border:1px solid #e9d5ff;">'
                f'{html.escape(str(coverage["regulatory_label_en"] if is_en else coverage["regulatory_label_ko"]))}</span>'
            )
        coverage_badges_html = f'<div style="margin-top:4px;margin-bottom:6px;">{"".join(pills)}</div>'

        if coverage["source_count"] > 1:
            ev_title = coverage.get("event_title") or (display_title_en(article) if is_en else display_title_ko(article))
            related_srcs = coverage.get("related_sources", [])
            rel_html = ""
            if len(related_srcs) > 1:
                rel_label = "Related Sources: " if is_en else "관련 출처: "
                rel_html = (
                    f'<p style="margin:6px 0 0;color:#657285;font-size:12px;line-height:1.4;">'
                    f'<strong style="color:#475569;">{rel_label}</strong>{html.escape(", ".join(related_srcs))}</p>'
                )
            cluster_box_html = (
                f'<div style="margin-top:12px;padding:10px 12px;border-radius:6px;background-color:#f0f9ff;border:1px solid #bae6fd;">'
                f'<div style="font-weight:800;font-size:13px;color:#0c4a6e;margin-bottom:6px;">{html.escape(str(ev_title))}</div>'
                f'{coverage_badges_html}'
                f'{rel_html}'
                f'</div>'
            )

        if coverage.get("official_source_url") and coverage["official_source_url"] != source_url:
            off_text = "Official Source" if is_en else "공식 발표 보기"
            official_cta_html = (
                f'<a href="{html.escape(str(coverage["official_source_url"]))}" '
                f'style="display:inline-block;margin-top:14px;margin-left:8px;padding:10px 14px;border-radius:8px;background-color:#0f766e;color:#ffffff;font-size:13px;font-weight:800;text-decoration:none;">'
                f'{off_text}</a>'
            )
    
    p_label = priority.label_en if is_en else priority.label_ko
    title = display_title_en(article) if is_en else display_title_ko(article)
    reason = priority.reason_en if is_en else priority.reason_ko
    summary = display_summary_en(article) if is_en else display_summary_ko(article)
    
    cat_label = display_primary_category(article, lang=lang)
    publisher = article.publisher or article.source
    pub_time = display_published_time(article, lang=lang)
    pub_time_html = f' · <span style="color:#657285;font-size:11px;">{html.escape(pub_time)}</span>' if pub_time else ""
    
    why_text = display_why_it_matters_en(article) if is_en else display_why_it_matters_ko(article)
    why_html = ""
    if why_text and why_text != reason:
        why_label = "Why it matters:"
        why_html = (
            f'<div style="margin-top:9px;padding:8px 10px;border-radius:6px;background-color:#f8fafc;border-left:3px solid #0f766e;">'
            f'<strong style="color:#0f766e;font-size:11px;text-transform:uppercase;">{why_label}</strong>'
            f'<p style="margin:2px 0 0;color:#1e293b;font-size:13px;line-height:1.5;font-weight:600;">{html.escape(why_text)}</p>'
            f'</div>'
        )
    
    region_prefix = "Region: " if is_en else "지역: "
    source_prefix = "Source: " if is_en else "출처: "
    
    return (
        f'<table class="brief-card brief-card--{priority.level}" role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        f'style="border-collapse:separate;border-spacing:0;margin:0 0 12px;border:1px solid #dde4ec;border-left:5px solid {colors["solid"]};border-radius:8px;background-color:#ffffff;">'
        '<tr><td style="padding:16px 18px 17px;">'
        '<div style="margin-bottom:8px;">'
        f'<span class="priority-badge" style="display:inline-block;margin:0 8px 7px 0;padding:5px 9px;border-radius:999px;background-color:{colors["solid"]};color:#ffffff;font-size:12px;line-height:1.2;font-weight:800;">{html.escape(p_label)} · {priority.score}</span>'
        f'<span style="display:inline-block;margin:0 6px 7px 0;padding:4px 8px;border-radius:4px;background-color:#f1f5f9;color:#334155;font-size:11px;line-height:1.2;font-weight:700;">{html.escape(cat_label)}</span>'
        f'<span style="display:inline-block;margin-bottom:7px;color:#657285;font-size:12px;line-height:1.2;font-weight:700;">{html.escape(publisher)}{pub_time_html}</span>'
        f"{coverage_badges_html if not cluster_box_html else ''}"
        "</div>"
        f'<h3 style="margin:0 0 9px;font-size:18px;line-height:1.38;color:#18202a;">{html.escape(title)}</h3>'
        f'<p style="margin:0 0 10px;padding:9px 10px;border-radius:8px;background-color:{colors["soft"]};color:{colors["text"]};font-size:13px;line-height:1.55;font-weight:700;">{html.escape(reason)}</p>'
        f'<p style="margin:0;color:#334155;font-size:14px;line-height:1.62;">{html.escape(summary)}</p>'
        f"{why_html}"
        f"{cluster_box_html}"
        f'<p style="margin:12px 0 0;color:#657285;font-size:12px;line-height:1.55;">{region_prefix}{html.escape(region_label)} · {source_prefix}{html.escape(publisher)}</p>'
        f"{tag_html}{cta_html}{official_cta_html}"
        "</td></tr></table>"
    )
