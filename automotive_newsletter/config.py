from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    db_path: Path = Path("data/newsletter.db")
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    newsletter_to: str | None = None
    smtp_tls: bool = True
    daily_collection_time: str = "06:00"
    enable_daily_scheduler: bool = False
    request_timeout_seconds: float = 12.0
    max_entries_per_feed: int = 12
    resolve_news_links: bool = True
    fetch_article_excerpts: bool = False
    verify_tls: bool = True
    admin_key: str | None = None

    @property
    def recipients(self) -> list[str]:
        if not self.newsletter_to:
            return []
        return [item.strip() for item in self.newsletter_to.split(",") if item.strip()]

    def missing_smtp_fields(self) -> list[str]:
        fields = {
            "SMTP_HOST": self.smtp_host,
            "SMTP_FROM": self.smtp_from,
            "NEWSLETTER_TO": self.newsletter_to,
        }
        return [name for name, value in fields.items() if not value]


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        db_path=Path(os.getenv("NEWSLETTER_DB_PATH", "data/newsletter.db")),
        smtp_host=os.getenv("SMTP_HOST"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER"),
        smtp_password=os.getenv("SMTP_PASSWORD"),
        smtp_from=os.getenv("SMTP_FROM"),
        newsletter_to=os.getenv("NEWSLETTER_TO"),
        smtp_tls=_bool_env("SMTP_TLS", True),
        daily_collection_time=os.getenv("DAILY_COLLECTION_TIME", "06:00"),
        enable_daily_scheduler=_bool_env("ENABLE_DAILY_SCHEDULER", False),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "8")),
        max_entries_per_feed=int(os.getenv("MAX_ENTRIES_PER_FEED", "12")),
        resolve_news_links=_bool_env("RESOLVE_NEWS_LINKS", True),
        fetch_article_excerpts=_bool_env("FETCH_ARTICLE_EXCERPTS", False),
        verify_tls=_bool_env("VERIFY_TLS", True),
        admin_key=os.getenv("ADMIN_KEY") or os.getenv("ADMIN_PASSWORD"),
    )


def settings_with_mail_overrides(settings: Settings, values: dict[str, object]) -> Settings:
    def text(name: str, current: str | None) -> str | None:
        value = values.get(name)
        if value is None:
            return current
        cleaned = str(value).strip()
        return cleaned or None

    def port() -> int:
        value = values.get("smtp_port")
        if value is None or value == "":
            return settings.smtp_port
        return int(value)

    def flag() -> bool:
        value = values.get("smtp_tls")
        if value is None:
            return settings.smtp_tls
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    return replace(
        settings,
        smtp_host=text("smtp_host", settings.smtp_host),
        smtp_port=port(),
        smtp_user=text("smtp_user", settings.smtp_user),
        smtp_password=text("smtp_password", settings.smtp_password),
        smtp_from=text("smtp_from", settings.smtp_from),
        newsletter_to=text("newsletter_to", settings.newsletter_to),
        smtp_tls=flag(),
    )
