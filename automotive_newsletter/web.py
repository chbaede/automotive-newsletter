from __future__ import annotations

import threading
import time
from datetime import date, datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .collector import check_feed_health, collect_and_store
from .config import Settings, load_settings, settings_with_mail_overrides
from .mailer import MailConfigError, send_issue
from .models import NewsletterIssue
from .presentation import (
    REGION_FILTERS,
    display_summary_ko,
    display_summary_en,
    display_title_ko,
    display_title_en,
    display_url,
    region_counts,
    regions_for_article,
    sort_articles_for_section,
    visible_tags,
)
from .priority import assess_priority, priority_summary
from .sources import SECTION_LABELS, SECTION_LABELS_EN, SECTION_ORDER
from .store import NewsletterStore

PACKAGE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


def create_app(store: NewsletterStore | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    store = store or NewsletterStore(settings.db_path)
    app = FastAPI(title="Automotive Newsletter")
    app.state.store = store
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        issue = store.latest_issue()
        return _render_index(request, store, settings, issue)

    @app.get("/issues/{issue_date}", response_class=HTMLResponse)
    def issue_page(issue_date: str, request: Request) -> HTMLResponse:
        issue = store.get_issue(issue_date)
        if issue is None:
            raise HTTPException(status_code=404, detail="Issue not found")
        return _render_index(request, store, settings, issue)

    @app.post("/api/collect")
    def collect_today() -> JSONResponse:
        issue = collect_and_store(store=store, settings=settings, issue_date=date.today().isoformat())
        return JSONResponse({"ok": True, "issue_date": issue.issue_date, "articles": len(issue.articles)})

    @app.post("/api/issues/{issue_date}/send")
    def send_issue_api(issue_date: str, lang: str = "ko") -> JSONResponse:
        issue = store.get_issue(issue_date)
        if issue is None:
            raise HTTPException(status_code=404, detail="Issue not found")
        try:
            send_issue(issue, settings=_effective_mail_settings(settings, store), lang=lang)
        except MailConfigError as exc:
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
        store.mark_sent(issue.issue_date)
        return JSONResponse({"ok": True, "message": "메일을 발송했습니다."})

    @app.get("/api/settings/mail")
    def get_mail_settings_api() -> JSONResponse:
        return JSONResponse(
            {"ok": True, "settings": _public_mail_settings(settings, store.mail_settings())}
        )

    @app.post("/api/settings/mail")
    def save_mail_settings_api(payload: dict[str, object] = Body(...)) -> JSONResponse:
        try:
            normalized = _normalize_mail_settings_payload(payload, store.mail_settings())
        except ValueError as exc:
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
        store.save_mail_settings(normalized)
        return JSONResponse(
            {"ok": True, "settings": _public_mail_settings(settings, normalized)}
        )

    @app.get("/api/issues")
    def list_issues() -> JSONResponse:
        return JSONResponse({"issues": store.list_issues()})

    @app.get("/api/sources/health")
    def source_health() -> JSONResponse:
        return JSONResponse({"ok": True, "sources": check_feed_health(settings=settings)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.enable_daily_scheduler:
        start_daily_scheduler(app, collection_time=settings.daily_collection_time)

    return app


def _render_index(
    request: Request,
    store: NewsletterStore,
    settings: Settings,
    issue: NewsletterIssue | None,
) -> HTMLResponse:
    sections = []
    displayed_articles = []
    if issue:
        for category in SECTION_ORDER:
            articles = [article for article in issue.articles if article.category == category]
            articles = sort_articles_for_section(category, articles, issue.issue_date)
            displayed_articles.extend(articles)
            sections.append(
                {
                    "key": category,
                    "label_ko": SECTION_LABELS[category],
                    "label_en": SECTION_LABELS_EN[category],
                    "articles": articles,
                }
            )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "issue": issue,
            "sections": sections,
            "history": store.list_issues(),
            "today": date.today().isoformat(),
            "assess_priority": assess_priority,
            "display_summary_ko": display_summary_ko,
            "display_summary_en": display_summary_en,
            "display_title_ko": display_title_ko,
            "display_title_en": display_title_en,
            "display_url": display_url,
            "region_counts": region_counts(displayed_articles) if issue else {},
            "region_filter_options": REGION_FILTERS,
            "regions_for_article": regions_for_article,
            "visible_tags": visible_tags,
            "mail_settings": _public_mail_settings(settings, store.mail_settings()),
            "issue_metrics": _issue_metrics(displayed_articles) if issue else {},
            "warning_items": _warning_items(issue.warnings) if issue else [],
            "priority_summary": priority_summary(
                NewsletterIssue(
                    issue_date=issue.issue_date,
                    articles=[
                        article for article in displayed_articles if article.category != "conference"
                    ],
                )
            )
            if issue
            else None,
        },
    )


def _warning_items(warnings: list[str]) -> list[dict[str, str]]:
    items = []
    for warning in warnings:
        source, separator, detail = warning.partition(":")
        if not separator:
            source = "수집기"
            detail = warning
        detail = detail.strip()
        items.append(
            {
                "source": source.strip() or "수집기",
                "summary": _warning_summary(detail),
                "detail": warning,
            }
        )
    return items


def _warning_summary(detail: str) -> str:
    text = detail.lower()
    if "errno 8" in text or "nodename nor servname" in text or "name or service not known" in text:
        return "네트워크/DNS 오류"
    if "timeout" in text or "timed out" in text:
        return "응답 시간 초과"
    if "certificate_verify_failed" in text or "tls" in text:
        return "TLS 인증서 오류"
    if "피드 파싱 실패" in detail:
        return "피드 파싱 실패"
    return "수집 오류"


def _issue_metrics(articles: list) -> dict[str, int]:
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


def _effective_mail_settings(settings: Settings, store: NewsletterStore) -> Settings:
    return settings_with_mail_overrides(settings, store.mail_settings())


def _public_mail_settings(settings: Settings, saved_values: dict[str, object]) -> dict[str, object]:
    effective = settings_with_mail_overrides(settings, saved_values)
    return {
        "smtp_host": effective.smtp_host or "",
        "smtp_port": effective.smtp_port,
        "smtp_user": effective.smtp_user or "",
        "smtp_from": effective.smtp_from or "",
        "newsletter_to": effective.newsletter_to or "",
        "smtp_tls": effective.smtp_tls,
        "smtp_password_saved": bool(effective.smtp_password),
    }


def _normalize_mail_settings_payload(
    payload: dict[str, object], existing: dict[str, object]
) -> dict[str, object]:
    def text(name: str) -> str:
        value = payload.get(name)
        return str(value).strip() if value is not None else ""

    try:
        smtp_port = int(payload.get("smtp_port") or 587)
    except (TypeError, ValueError) as exc:
        raise ValueError("SMTP_PORT는 숫자로 입력해야 합니다.") from exc
    if smtp_port < 1 or smtp_port > 65535:
        raise ValueError("SMTP_PORT는 1-65535 사이여야 합니다.")

    password = text("smtp_password") or str(existing.get("smtp_password") or "")
    smtp_tls = payload.get("smtp_tls")
    if isinstance(smtp_tls, bool):
        use_tls = smtp_tls
    else:
        use_tls = str(smtp_tls or "").strip().lower() in {"1", "true", "yes", "on"}

    return {
        "smtp_host": text("smtp_host"),
        "smtp_port": smtp_port,
        "smtp_user": text("smtp_user"),
        "smtp_password": password,
        "smtp_from": text("smtp_from"),
        "newsletter_to": text("newsletter_to"),
        "smtp_tls": use_tls,
    }


def start_daily_scheduler(app: FastAPI, collection_time: str) -> None:
    state = {"last_run": None}

    def loop() -> None:
        while True:
            now = datetime.now()
            today = date.today().isoformat()
            if now.strftime("%H:%M") == collection_time and state["last_run"] != today:
                collect_and_store(
                    store=app.state.store,
                    settings=app.state.settings,
                    issue_date=today,
                )
                state["last_run"] = today
            time.sleep(30)

    @app.on_event("startup")
    def _start_scheduler() -> None:
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
