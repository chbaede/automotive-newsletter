from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

STANDARD_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


@dataclass(slots=True)
class StructuredLogRecord:
    timestamp: str
    level: str
    component: str
    source: str | None
    event: str
    duration: float | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "component": self.component,
            "source": self.source,
            "event": self.event,
            "duration": self.duration,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class StructuredLogger:
    """Production structured logger emitting JSON events."""

    def __init__(self, name: str = "automotive_newsletter", output=None) -> None:
        self.name = name
        self.output = output or sys.stdout
        self._underlying = logging.getLogger(name)

    def log(
        self,
        level: str,
        component: str,
        event: str,
        source: str | None = None,
        duration: float | None = None,
        error: str | None = None,
    ) -> StructuredLogRecord:
        level_upper = level.upper()
        now = datetime.now(timezone.utc).isoformat()
        record = StructuredLogRecord(
            timestamp=now,
            level=level_upper,
            component=component,
            source=source,
            event=event,
            duration=round(duration, 4) if duration is not None else None,
            error=str(error) if error is not None else None,
        )

        try:
            line = record.to_json()
            print(line, file=self.output, flush=True)
        except Exception:
            pass

        return record

    def info(
        self,
        component: str,
        event: str,
        source: str | None = None,
        duration: float | None = None,
        error: str | None = None,
    ) -> StructuredLogRecord:
        return self.log("INFO", component, event, source=source, duration=duration, error=error)

    def warning(
        self,
        component: str,
        event: str,
        source: str | None = None,
        duration: float | None = None,
        error: str | None = None,
    ) -> StructuredLogRecord:
        return self.log("WARNING", component, event, source=source, duration=duration, error=error)

    def error(
        self,
        component: str,
        event: str,
        source: str | None = None,
        duration: float | None = None,
        error: str | None = None,
    ) -> StructuredLogRecord:
        return self.log("ERROR", component, event, source=source, duration=duration, error=error)

    def debug(
        self,
        component: str,
        event: str,
        source: str | None = None,
        duration: float | None = None,
        error: str | None = None,
    ) -> StructuredLogRecord:
        return self.log("DEBUG", component, event, source=source, duration=duration, error=error)


# Default global logger instance
logger = StructuredLogger()

