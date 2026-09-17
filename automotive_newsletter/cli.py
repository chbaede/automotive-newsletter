from __future__ import annotations

import argparse
import time
from datetime import date, datetime

import uvicorn

from .collector import check_feed_health, collect_and_store
from .config import load_settings
from .mailer import MailConfigError, send_issue
from .store import NewsletterStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="automotive-newsletter")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Run the web app")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8000, type=int)
    serve_parser.add_argument("--reload", action="store_true")

    collect_parser = subparsers.add_parser("collect", help="Collect and store today's issue")
    collect_parser.add_argument("--date", dest="issue_date")
    collect_parser.add_argument("--force", action="store_true", help="Force collection even if already completed")

    send_parser = subparsers.add_parser("send", help="Send an issue by email")
    send_parser.add_argument("--date", dest="issue_date")

    subparsers.add_parser("sources", help="Check external feed health")

    schedule_parser = subparsers.add_parser("schedule", help="Collect once per day with robust scheduler")
    schedule_parser.add_argument("--time", dest="collection_time")

    args = parser.parse_args(argv)
    command = args.command or "serve"

    if command == "serve":
        settings = load_settings()
        uvicorn.run(
            "automotive_newsletter.web:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=args.reload,
            proxy_headers=True,
            forwarded_allow_ips=settings.forwarded_allow_ips,
        )
        return 0
    if command == "collect":
        from .config import get_newsletter_timezone
        from .scheduler import run_collection_job

        settings = load_settings()
        tz = get_newsletter_timezone(settings.newsletter_timezone)
        issue_date = args.issue_date or datetime.now(tz).strftime("%Y-%m-%d")
        store = NewsletterStore(settings.db_path)
        if not args.force and store.has_daily_run_completed(issue_date):
            print(f"collection for {issue_date} has already completed (use --force to re-collect)")
            return 0
        success = run_collection_job(
            store=store,
            settings=settings,
            issue_date=issue_date,
            force=args.force,
        )
        if success:
            issue = store.get_issue(issue_date)
            count = len(issue.articles) if issue else 0
            print(f"saved {issue_date}: {count} articles")
            return 0
        else:
            print(f"collection for {issue_date} skipped (another worker is currently collecting)")
            return 0
    if command == "send":
        settings = load_settings()
        store = NewsletterStore(settings.db_path)
        issue = store.get_issue(args.issue_date) if args.issue_date else store.latest_issue()
        if issue is None:
            print("no issue found")
            return 1
        try:
            send_issue(issue, settings=settings)
        except MailConfigError as exc:
            print(str(exc))
            return 2
        store.mark_sent(issue.issue_date)
        print(f"sent {issue.issue_date}")
        return 0
    if command == "sources":
        settings = load_settings()
        rows = check_feed_health(settings=settings)
        for row in rows:
            diag = row.get("diagnostic") or (f"OK  {row['name']}" if row["ok"] else f"FAIL {row['name']}")
            tls = " tls-fallback" if row["tls_fallback"] else ""
            error = f" {row['error']}" if row["error"] else ""
            print(f"{diag}{tls}{error}")
        return 1 if any(not row["ok"] for row in rows) else 0
    if command == "schedule":
        from .scheduler import DailyScheduler

        settings = load_settings()
        if args.collection_time:
            settings.daily_collection_time = args.collection_time
        scheduler = DailyScheduler(settings=settings)
        print(
            f"daily collection scheduled for {settings.daily_collection_time} ({settings.newsletter_timezone})"
        )
        try:
            scheduler.run_loop()
        except (KeyboardInterrupt, SystemExit):
            print("\nscheduler stopped")
        return 0
    parser.print_help()
    return 1
