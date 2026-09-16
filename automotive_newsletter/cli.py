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

    send_parser = subparsers.add_parser("send", help="Send an issue by email")
    send_parser.add_argument("--date", dest="issue_date")

    subparsers.add_parser("sources", help="Check external feed health")

    schedule_parser = subparsers.add_parser("schedule", help="Collect once per day")
    schedule_parser.add_argument("--time", dest="collection_time")

    args = parser.parse_args(argv)
    command = args.command or "serve"

    if command == "serve":
        uvicorn.run(
            "automotive_newsletter.web:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=args.reload,
            proxy_headers=True,
            forwarded_allow_ips="*",
        )
        return 0
    if command == "collect":
        settings = load_settings()
        issue = collect_and_store(
            store=NewsletterStore(settings.db_path),
            settings=settings,
            issue_date=args.issue_date,
        )
        print(f"saved {issue.issue_date}: {len(issue.articles)} articles")
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
        settings = load_settings()
        collection_time = args.collection_time or settings.daily_collection_time
        return run_schedule(collection_time)
    parser.print_help()
    return 1


def run_schedule(collection_time: str) -> int:
    print(f"daily collection scheduled for {collection_time}")
    last_run: str | None = None
    while True:
        try:
            now = datetime.now()
            today = date.today().isoformat()
            if now.strftime("%H:%M") == collection_time and last_run != today:
                settings = load_settings()
                issue = collect_and_store(
                    store=NewsletterStore(settings.db_path),
                    settings=settings,
                    issue_date=today,
                )
                print(f"saved {issue.issue_date}: {len(issue.articles)} articles")
                last_run = today
        except Exception as exc:
            print(f"error during scheduled collection: {exc}")
        time.sleep(30)
