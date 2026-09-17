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

    diag_parser = subparsers.add_parser("diagnose-clustering", help="Diagnose event clustering quality and coherence")
    diag_parser.add_argument("--date", dest="issue_date", help="Issue date (YYYY-MM-DD), default to latest")
    diag_parser.add_argument("--db", dest="db_path", help="Path to SQLite database")
    diag_parser.add_argument("--strict", action="store_true", help="Exit with code 1 if suspicious clusters are detected")

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
    if command == "diagnose-clustering":
        from .clustering import (
            cluster_articles,
            compute_event_coherence_metrics,
            calculate_event_similarity,
        )
        from .models import Article

        settings = load_settings()
        db_path = args.db_path or settings.db_path
        store = NewsletterStore(db_path)
        issue = store.get_issue(args.issue_date) if args.issue_date else store.latest_issue()

        articles = issue.articles if issue else []
        if articles:
            mode_str = f"MODE: REAL DATA (Issue Date: {issue.issue_date})"
        else:
            mode_str = "MODE: SYNTHETIC BENCHMARK"
            from datetime import timezone
            dt = datetime.now(timezone.utc)
            articles = [
                # Event 1: Toyota x Nvidia SDV partnership (3 articles)
                Article(title="Toyota and Nvidia announce software-defined vehicle partnership", url="https://reuters.com/1", source="Reuters", publisher="Reuters", published_at=dt, entities=["Toyota", "Nvidia"], priority_score=88),
                Article(title="Toyota teams up with Nvidia on SDV computing platform", url="https://autonews.com/2", source="Automotive News", publisher="Automotive News", published_at=dt, entities=["Toyota", "Nvidia"], priority_score=80),
                Article(title="Toyota Motor Corporation and NVIDIA Expand Strategic SDV Collaboration", url="https://toyota.com/3", source="Toyota Newsroom", publisher="Toyota Newsroom", source_type="official", is_official=True, published_at=dt, entities=["Toyota", "Nvidia"], priority_score=85),
                # Event 2: Toyota autonomous road tests (singleton)
                Article(title="Toyota expands autonomous driving road tests in Tokyo", url="https://bloomberg.com/4", source="Bloomberg", publisher="Bloomberg", published_at=dt, entities=["Toyota"], priority_score=72),
                # Event 3: Volkswagen manufacturing restructuring (2 articles)
                Article(title="Volkswagen announces major European manufacturing restructuring", url="https://reuters.com/5", source="Reuters", publisher="Reuters", published_at=dt, entities=["Volkswagen"], priority_score=92),
                Article(title="VW restructuring plans accelerate across plants", url="https://autonews.com/6", source="Automotive News", publisher="Automotive News", published_at=dt, entities=["VW"], priority_score=82),
                # Event 4: Ford 500k truck recall (2 articles)
                Article(title="Ford recalls 500,000 trucks over brake defect", url="https://nhtsa.gov/7", source="NHTSA", publisher="NHTSA", source_type="regulator", published_at=dt, entities=["Ford"], priority_score=95),
                Article(title="Ford issues recall for 500,000 pickup trucks due to brake line issues", url="https://reuters.com/8", source="Reuters", publisher="Reuters", published_at=dt, entities=["Ford"], priority_score=86),
                # Event 5: Ford 100k SUV airbag recall (separate event)
                Article(title="Ford recalls 100,000 SUVs over airbag inflator risk", url="https://nhtsa.gov/9", source="NHTSA", publisher="NHTSA", source_type="regulator", published_at=dt, entities=["Ford"], priority_score=90),
                # Event 6: BMW x Qualcomm automated driving partnership (2 articles)
                Article(title="BMW and Qualcomm collaborate on automated driving compute platform", url="https://reuters.com/10", source="Reuters", publisher="Reuters", published_at=dt, entities=["BMW", "Qualcomm"], priority_score=86),
                Article(title="BMW selects Qualcomm Snapdragon Ride for automated driving", url="https://autonews.com/11", source="Automotive News", publisher="Automotive News", published_at=dt, entities=["BMW", "Qualcomm"], priority_score=82),
                # Event 7: BMW x Nvidia cockpit AI partnership (disjoint partner - must remain separate!)
                Article(title="BMW partners with Nvidia on next-generation cockpit AI assistant", url="https://reuters.com/12", source="Reuters", publisher="Reuters", published_at=dt, entities=["BMW", "Nvidia"], priority_score=85),
                Article(title="BMW taps Nvidia for in-vehicle generative AI cockpit", url="https://autonews.com/13", source="Automotive News", publisher="Automotive News", published_at=dt, entities=["BMW", "Nvidia"], priority_score=81),
                # Event 8 & 9: Hyundai SDV vs Kia Infotainment (sibling brands - must remain separate)
                Article(title="Hyundai Motor announces next-generation SDV architecture for 2026", url="https://reuters.com/14", source="Reuters", publisher="Reuters", published_at=dt, entities=["Hyundai"], priority_score=84),
                Article(title="Kia reveals new software-driven infotainment experience for EV3", url="https://autonews.com/15", source="Automotive News", publisher="Automotive News", published_at=dt, entities=["Kia"], priority_score=78),
            ]

        events, event_articles, all_articles = cluster_articles(articles)

        print("=" * 80)
        print(f"EVENT CLUSTERING DIAGNOSTIC REPORT")
        print(f"{mode_str}")
        print(f"Total Articles: {len(all_articles)} | Total Events: {len(events)} | Multi-article Events: {sum(1 for e in events if e.source_count > 1)} | Singletons: {sum(1 for e in events if e.source_count == 1)}")
        print("=" * 80)

        suspicious_count = 0
        multi_coherence_scores: list[float] = []

        for idx, event in enumerate(events, 1):
            cluster_arts = [a for a in all_articles if a.event_id == event.event_id]
            primary = next((a for a in cluster_arts if a.article_id == event.primary_article_id), cluster_arts[0])
            metrics = compute_event_coherence_metrics(cluster_arts, primary)

            if len(cluster_arts) > 1:
                multi_coherence_scores.append(metrics.avg_similarity)

            if metrics.is_suspicious:
                suspicious_count += 1
                status_str = f"SUSPICIOUS ({'; '.join(metrics.suspicious_reasons)})"
            else:
                status_str = "HEALTHY"

            print(f"\n[Event {idx}] {event.event_id} | Members: {metrics.member_count} | Indep Sources: {metrics.independent_source_count} | Coherence: {metrics.avg_similarity:.3f} (min: {metrics.min_similarity:.3f})")
            print(f"Status: {status_str}")
            print(f"Entities: {', '.join(metrics.entity_overlap) if metrics.entity_overlap else 'None'}")
            print(f"Themes: {', '.join(metrics.theme_overlap) if metrics.theme_overlap else 'None'}")
            print("Articles:")
            for art in cluster_arts:
                sim = 1.0 if art.article_id == primary.article_id else calculate_event_similarity(primary, art)
                tag = "(Primary)" if art.article_id == primary.article_id else ("(Official)" if art.is_official else "(Coverage)")
                print(f"  * [{sim:.3f}] {tag:<10} [{art.publisher or art.source}] {art.title}")

        avg_multi_coherence = sum(multi_coherence_scores) / max(1, len(multi_coherence_scores)) if multi_coherence_scores else 0.0

        print("\n" + "=" * 80)
        print(f"DIAGNOSTIC SUMMARY: {len(events) - suspicious_count} Healthy, {suspicious_count} Suspicious clusters.")
        print(f"Average Multi-Article Cluster Coherence: {avg_multi_coherence:.3f}")
        print(f"Strict Mode: {'ENABLED' if args.strict else 'DISABLED'}")
        print("=" * 80)

        if args.strict and suspicious_count > 0:
            return 1
        return 0
    parser.print_help()
    return 1
