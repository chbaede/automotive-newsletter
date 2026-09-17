from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from automotive_newsletter.config import Settings, get_newsletter_timezone
from automotive_newsletter.scheduler import (
    DailyScheduler,
    parse_time_string,
    should_run_daily_collection,
)
from automotive_newsletter.store import NewsletterStore


def test_parse_time_string():
    assert parse_time_string("06:00") == (6, 0)
    assert parse_time_string("23:59") == (23, 59)
    assert parse_time_string("00:00") == (0, 0)


def test_should_run_daily_collection_timing(tmp_path):
    store = NewsletterStore(tmp_path / "test.db")
    tz = ZoneInfo("Europe/Berlin")

    # Before scheduled time (05:30 < 06:00)
    now_early = datetime(2026, 9, 17, 5, 30, tzinfo=tz)
    should_run, run_date, reason = should_run_daily_collection(
        now_dt=now_early, collection_time_str="06:00", store=store
    )
    assert should_run is False
    assert reason == "before_scheduled_time"
    assert run_date == "2026-09-17"

    # After scheduled time (06:05 > 06:00) - first run of the day
    now_ontime = datetime(2026, 9, 17, 6, 5, tzinfo=tz)
    should_run, run_date, reason = should_run_daily_collection(
        now_dt=now_ontime, collection_time_str="06:00", store=store
    )
    assert should_run is True
    assert run_date == "2026-09-17"

    # Missed execution catch-up (e.g. server down at 06:00, started at 10:30)
    now_late = datetime(2026, 9, 17, 10, 30, tzinfo=tz)
    should_run, run_date, reason = should_run_daily_collection(
        now_dt=now_late, collection_time_str="06:00", store=store
    )
    assert should_run is True
    assert reason == "scheduled_or_catchup"

    # Once run is recorded as completed, subsequent checks return False
    store.finish_daily_run("2026-09-17", metrics={"feeds_ok": 10})
    should_run, run_date, reason = should_run_daily_collection(
        now_dt=now_late, collection_time_str="06:00", store=store
    )
    assert should_run is False
    assert reason == "already_completed"

    # Force flag bypasses completion check
    should_run, run_date, reason = should_run_daily_collection(
        now_dt=now_late, collection_time_str="06:00", store=store, force=True
    )
    assert should_run is True
    assert reason == "forced"


def test_concurrency_locking_prevents_multiple_workers(tmp_path):
    store = NewsletterStore(tmp_path / "test.db")
    run_date = "2026-09-17"

    # Worker 1 acquires lock
    worker1_acquired = store.acquire_daily_run(run_date)
    assert worker1_acquired is True

    # Worker 2 attempts concurrent lock for same date -> rejected
    worker2_acquired = store.acquire_daily_run(run_date)
    assert worker2_acquired is False

    # Worker 1 finishes run
    store.finish_daily_run(run_date, metrics={"feeds_total": 40, "feeds_ok": 40})
    assert store.has_daily_run_completed(run_date) is True

    # Worker 3 tries to run completed job -> rejected
    worker3_acquired = store.acquire_daily_run(run_date)
    assert worker3_acquired is False


def test_scheduler_timezone_awareness(tmp_path):
    store = NewsletterStore(tmp_path / "test.db")
    settings = Settings(
        db_path=tmp_path / "test.db",
        newsletter_timezone="Europe/Berlin",
        daily_collection_time="06:00",
    )
    scheduler = DailyScheduler(store=store, settings=settings)
    assert scheduler.tz.key == "Europe/Berlin"
    assert scheduler.settings.newsletter_timezone == "Europe/Berlin"
