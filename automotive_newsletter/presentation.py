from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from urllib.parse import urlsplit

from .models import Article
from .priority import LEVELS, assess_priority
from .summarizer import (
    CONFERENCE_NAMES,
    INSTITUTION_NAMES,
    OEM_NAMES,
    TIER1_NAMES,
    summarize_article,
)

LEGACY_ORIGINAL_TITLE_RE = re.compile(r"\s*원문 제목\s*:\s*.*$", re.DOTALL)
HANGUL_RE = re.compile(r"[가-힣]")
SOURCE_SUFFIX_RE = re.compile(r"\s[-|]\s[^-|]{2,80}$")

GENERIC_TAGS = {"SDV", "ADAS", "OTA", "EV", "AI", "2026", "예정", "종료"}
TECHNICAL_TAG_PREFIXES = ("event_start:", "event_end:")


@dataclass(frozen=True, slots=True)
class RegionSignal:
    key: str
    label_ko: str
    label_en: str


REGION_FILTERS = [
    RegionSignal("all", "전체", "All"),
    RegionSignal("us", "미국", "US"),
    RegionSignal("europe", "유럽", "Europe"),
    RegionSignal("asia", "아시아", "Asia"),
    RegionSignal("global", "글로벌", "Global"),
]

REGION_LABELS = {region.key: region.label_ko for region in REGION_FILTERS}

REGION_TERMS = {
    "us": [
        "united states",
        "usa",
        "u.s.",
        "america",
        "north america",
        "detroit",
        "dearborn",
        "novi",
        "michigan",
        "las vegas",
        "san francisco",
        "california",
        "gm",
        "general motors",
        "ford",
        "tesla",
        "rivian",
        "lucid",
        "j.d. power",
        "automotive usa",
    ],
    "europe": [
        "europe",
        "eu ",
        "germany",
        "france",
        "frankfurt",
        "hannover",
        "stuttgart",
        "berlin",
        "sinsheim",
        "paris",
        "munich",
        "volkswagen",
        "vw",
        "bmw",
        "mercedes",
        "stellantis",
        "renault",
        "seat",
        "cupra",
        "bosch",
        "continental",
        "zf",
        "valeo",
        "forvia",
        "schaeffler",
        "iaa",
        "automotive europe",
    ],
    "asia": [
        "asia",
        "china",
        "japan",
        "korea",
        "india",
        "tokyo",
        "nagoya",
        "beijing",
        "aichi",
        "makuhari",
        "philippines",
        "toyota",
        "hyundai",
        "kia",
        "honda",
        "nissan",
        "byd",
        "denso",
        "hyundai mobis",
        "automotive world tokyo",
        "automotive world nagoya",
        "japan mobility show",
        "auto china",
    ],
}


def display_title_ko(article: Article) -> str:
    title = _clean_title(article.title)
    if article.category == "conference" and HANGUL_RE.search(title):
        return title
    if HANGUL_RE.search(title) and len(title) <= 90:
        return title

    subject = _subject(article, title)
    signal = _headline_signal(article, title)
    return f"{subject}: {signal}"


def display_summary_ko(article: Article) -> str:
    summary = article.summary_ko or summarize_article(replace(article, tags=visible_tags(article)))
    summary = LEGACY_ORIGINAL_TITLE_RE.sub("", summary).strip()
    if article.why_it_matters_ko and article.why_it_matters_ko not in summary:
        summary = f"{summary} [의미: {article.why_it_matters_ko.strip()}]" if summary else article.why_it_matters_ko.strip()
    if summary:
        return summary
    return "핵심 동향을 확인할 수 있는 자동차 산업 참고 링크입니다."


def display_title_en(article: Article) -> str:
    return _clean_title(article.title)


def display_summary_en(article: Article) -> str:
    if article.summary_en:
        return article.summary_en.strip()
    if article.excerpt:
        return article.excerpt.strip()
    return "Reference link for key trends in the automotive industry."


def display_key_points(article: Article) -> list[str]:
    return [pt.strip() for pt in article.key_points if pt.strip()]


def display_url(article: Article) -> str | None:
    target = article.canonical_url or article.original_url or article.url
    if _is_intermediary_url(target):
        return None
    return target


def display_event_coverage(article: Article) -> dict[str, str | int] | None:
    count = 1 + len(article.related_article_ids)
    if count <= 1:
        return None
    return {
        "count": count,
        "label_ko": f"{count}개 매체 보도 중",
        "label_en": f"{count} sources covering this event",
    }


def regions_for_article(article: Article) -> list[RegionSignal]:
    text = _region_text(article)
    matched = [
        key
        for key in ["us", "europe", "asia"]
        if any(_contains_region_term(text, term) for term in REGION_TERMS[key])
    ]
    if not matched:
        matched = ["global"]
    return [next(r for r in REGION_FILTERS if r.key == key) for key in matched]


def region_counts(articles: list[Article]) -> dict[str, int]:
    counts = {region.key: 0 for region in REGION_FILTERS}
    counts["all"] = len(articles)
    for article in articles:
        for region in regions_for_article(article):
            counts[region.key] += 1
    return counts


def visible_tags(article: Article) -> list[str]:
    return [
        tag
        for tag in article.tags
        if not any(tag.startswith(prefix) for prefix in TECHNICAL_TAG_PREFIXES)
    ]


def conference_event_dates(article: Article) -> tuple[date, date] | None:
    start = _tag_date(article, "event_start:")
    end = _tag_date(article, "event_end:")
    if start and end:
        return start, end
    return None


def filter_upcoming_conferences(
    articles: list[Article], on_date: str | date | None
) -> list[Article]:
    reference_date = _coerce_date(on_date)
    upcoming = []
    for article in articles:
        dates = conference_event_dates(article)
        if dates is None or dates[1] >= reference_date:
            upcoming.append(article)
    return upcoming


def sort_articles_for_section(
    category: str, articles: list[Article], issue_date: str | date | None = None
) -> list[Article]:
    if category == "conference":
        return sorted(
            filter_upcoming_conferences(articles, issue_date),
            key=lambda article: (
                conference_event_dates(article)[0]
                if conference_event_dates(article)
                else date.max,
                display_title_ko(article),
            ),
        )
    return sort_articles_by_priority(articles)


def sort_articles_by_priority(articles: list[Article]) -> list[Article]:
    return sorted(
        articles,
        key=lambda article: (
            LEVELS[assess_priority(article).level][2],
            assess_priority(article).score,
            article.score,
            _timestamp(article.published_at),
        ),
        reverse=True,
    )


def _subject(article: Article, title: str) -> str:
    preferred_tags = [
        tag
        for tag in visible_tags(article)
        if tag not in GENERIC_TAGS
    ]
    if preferred_tags:
        return ", ".join(preferred_tags[:2])

    for name in [*OEM_NAMES, *TIER1_NAMES, *INSTITUTION_NAMES, *CONFERENCE_NAMES]:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", title, re.IGNORECASE):
            return name

    if article.category == "conference":
        return "자동차 컨퍼런스"
    if article.category == "tier1":
        return "Tier 1"
    if article.category == "oem":
        return "OEM"
    if article.category == "sdv":
        return "SDV"
    if article.category == "institution":
        return "기관/매거진"
    return article.source or "자동차 업계"


def _headline_signal(article: Article, title: str) -> str:
    text = f"{title} {article.excerpt} {article.summary_ko} {' '.join(article.tags)}".lower()

    if article.category == "conference":
        if any(word in text for word in ["sdv", "software", "computing", "autotech", "aglg", "linux"]):
            return "SDV·차량 소프트웨어 아젠다"
        if any(word in text for word in ["battery", "electric", "ev"]):
            return "전동화·배터리 기술 행사"
        if any(word in text for word in ["autonomous", "adas", "vehicle tech"]):
            return "ADAS·자율주행 기술 행사"
        return "2026 주요 행사 일정"
    if any(word in text for word in ["recall", "probe", "investigation", "regulator", "warranty"]):
        return "품질·규제 리스크 확대"
    if any(
        word in text
        for word in [
            "software-defined",
            "software defined",
            "sdv",
            "zonal",
            "ota",
            "vehicle software",
            "carplay",
            "cockpit",
            "buttons",
        ]
    ):
        return "SDV·차량 소프트웨어 전략 변화"
    if any(word in text for word in ["battery", "4680", "electric", "ev", "charging"]):
        return "전동화·배터리 공급망 변화"
    if any(word in text for word in ["investment", "invest", "funding", "billion", "plant"]):
        return "투자·CAPEX 확대"
    if any(word in text for word in ["partnership", "collaboration", "joint", "alliance"]):
        return "전략 제휴와 생태계 확대"
    if any(word in text for word in ["production", "manufacturing", "supply", "forecast", "output"]):
        return "생산·공급망 계획 조정"
    if any(word in text for word in ["launch", "unveil", "debut", "model", "flex-fuel"]):
        return "신차·제품 전략 업데이트"
    if any(word in text for word in ["sales", "market", "outlook", "inflation", "gas prices", "consumer"]):
        return "수요·시장 전망 이슈"
    if any(word in text for word in ["ai", "diagnostic", "repair"]):
        return "AI·품질 데이터 활용 확대"
    if article.category == "institution":
        return "시장 전망과 업계 담론 업데이트"
    if article.category == "tier1":
        return "부품사 기술·수주 포지션 변화"
    if article.category == "oem":
        return "플랫폼·시장 전략 업데이트"
    return "산업 영향 이슈"


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    return SOURCE_SUFFIX_RE.sub("", title)


def _tag_date(article: Article, prefix: str) -> date | None:
    for tag in article.tags:
        if tag.startswith(prefix):
            try:
                return date.fromisoformat(tag.removeprefix(prefix))
            except ValueError:
                return None
    return None


def _coerce_date(value: str | date | None) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return date.today()


def _region_text(article: Article) -> str:
    return " ".join(
        [
            article.title,
            article.url,
            article.excerpt,
            article.summary_ko,
            " ".join(article.tags),
        ]
    ).lower()


def _contains_region_term(text: str, term: str) -> bool:
    term = term.lower()
    if term.endswith(" "):
        return term in f"{text} "
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def _is_intermediary_url(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return host.endswith("google.com") or host.endswith("news.google.com")


def _timestamp(value: datetime | None) -> float:
    return value.timestamp() if value else 0.0
