from __future__ import annotations

import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .collector import collect_and_store
from .config import Settings, get_newsletter_timezone, load_settings
from .logging import logger
from .store import NewsletterStore


def parse_time_string(time_str: str) -> tuple[int, int]:
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str}, expected HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time values: {time_str}")
    return hour, minute


def should_run_daily_collection(
    now_dt: datetime,
    collection_time_str: str,
    store: NewsletterStore,
    force: bool = False,
) -> tuple[bool, str, str]:
    """Determine if scheduled collection should run for today.

    Handles:
    - Normal schedule triggers
    - Missed execution catch-up (e.g. server down or restarted after collection time)
    - Duplicate execution prevention
    """
    today_str = now_dt.strftime("%Y-%m-%d")
    if force:
        return True, today_str, "forced"

    hour, minute = parse_time_string(collection_time_str)
    target_today = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if now_dt < target_today:
        return False, today_str, "before_scheduled_time"

    if store.has_daily_run_completed(today_str):
        return False, today_str, "already_completed"

    return True, today_str, "scheduled_or_catchup"


def run_collection_job(
    store: NewsletterStore,
    settings: Settings,
    issue_date: str,
    force: bool = False,
) -> bool:
    """Safely execute a daily collection with concurrency locking and deduplication."""
    if not force:
        acquired = store.acquire_daily_run(issue_date)
        if not acquired:
            logger.info(
                component="scheduler",
                event="run_skipped_lock_unavailable",
                source="scheduler",
            )
            return False

    start_time = time.perf_counter()
    logger.info(
        component="scheduler",
        event="collection_job_started",
        source="scheduler",
    )
    try:
        issue = collect_and_store(
            store=store,
            settings=settings,
            issue_date=issue_date,
        )
        duration = time.perf_counter() - start_time
        logger.info(
            component="scheduler",
            event="collection_job_finished",
            source="scheduler",
            duration=duration,
        )
        return True
    except Exception as exc:
        duration = time.perf_counter() - start_time
        logger.error(
            component="scheduler",
            event="collection_job_failed",
            source="scheduler",
            duration=duration,
            error=str(exc),
        )
        store.fail_daily_run(issue_date, error=str(exc))
        raise


class DailyScheduler:
    """Robust standalone scheduler respecting timezones, catching up missed runs, and preventing duplicate runs."""

    def __init__(
        self,
        store: NewsletterStore | None = None,
        settings: Settings | None = None,
        poll_interval: float = 30.0,
    ) -> None:
        self.settings = settings or load_settings()
        self.store = store or NewsletterStore(self.settings.db_path)
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self.tz = get_newsletter_timezone(self.settings.newsletter_timezone)

    def run_once(self, force: bool = False) -> bool:
        now_dt = datetime.now(self.tz)
        should_run, today_str, reason = should_run_daily_collection(
            now_dt=now_dt,
            collection_time_str=self.settings.daily_collection_time,
            store=self.store,
            force=force,
        )
        if not should_run:
            logger.debug(
                component="scheduler",
                event="scheduler_tick_skip",
                source="scheduler",
                error=reason,
            )
            return False

        return run_collection_job(
            store=self.store,
            settings=self.settings,
            issue_date=today_str,
            force=force,
        )

    def stop(self) -> None:
        self._stop_event.set()

    def run_loop(self) -> None:
        time_str = self.settings.daily_collection_time
        tz_name = self.settings.newsletter_timezone
        logger.info(
            component="scheduler",
            event="scheduler_started",
            source="scheduler",
            error=f"time={time_str}, tz={tz_name}",
        )
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                logger.error(
                    component="scheduler",
                    event="scheduler_loop_error",
                    source="scheduler",
                    error=str(exc),
                )
            self._stop_event.wait(self.poll_interval)

