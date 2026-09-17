from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from urllib.parse import urlsplit

from .clustering import select_primary_article
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


UI_REGION_FILTERS = [
    RegionSignal("all", "전체", "All"),
    RegionSignal("europe", "유럽", "Europe"),
    RegionSignal("germany", "독일", "Germany"),
    RegionSignal("korea", "한국", "Korea"),
    RegionSignal("us", "미국", "US"),
    RegionSignal("global", "글로벌", "Global"),
]

# Preserves asia for backward compatibility with existing tests while offering full UI filters
REGION_FILTERS = [
    *UI_REGION_FILTERS,
    RegionSignal("asia", "아시아", "Asia"),
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
        "acea",
    ],
    "germany": [
        "germany",
        "deutschland",
        "german",
        "berlin",
        "munich",
        "münchen",
        "stuttgart",
        "wolfsburg",
        "ingolstadt",
        "frankfurt",
        "hannover",
        "heise",
        "electrive.net",
        "bmw",
        "volkswagen",
        "mercedes",
        "bosch",
        "continental",
        "zf",
        "porsche",
        "audi",
        "kba",
    ],
    "korea": [
        "korea",
        "south korea",
        "korean",
        "seoul",
        "hyundai",
        "kia",
        "genesis",
        "mobis",
        "hyundai mobis",
        "현대",
        "기아",
        "한국",
        "서울",
        "남양",
        "울산",
        "화성",
        "kama",
        "samsung sdi",
        "lg energy solution",
        "sk on",
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


@dataclass(frozen=True, slots=True)
class TopicFilter:
    key: str
    label: str
    terms: tuple[str, ...]


TOPIC_FILTERS = [
    TopicFilter("all", "All Topics", ()),
    TopicFilter("sdv", "SDV", ("sdv", "software defined vehicle", "software-defined vehicle", "차량 소프트웨어", "차량 sw")),
    TopicFilter("autosar", "AUTOSAR", ("autosar", "classic autosar", "adaptive autosar", "오토사")),
    TopicFilter("ota", "OTA", ("ota", "over-the-air", "over the air", "무선 업데이트", "무선 펌웨어")),
    TopicFilter("cybersecurity", "Cybersecurity", ("cybersecurity", "cyber security", "사이버보안", "보안", "iso/sae 21434", "wp.29 r155", "r155", "csms", "vulnerability")),
    TopicFilter("adas", "ADAS", ("adas", "autonomous", "자율주행", "주행보조", "lidar", "radar", "camera", "라이다", "레이다", "level 3", "level 4", "fused sensor")),
    TopicFilter("ev", "EV", ("ev", "electric vehicle", "전기차", "bev", "phev", "fcev", "전동화", "electrification")),
    TopicFilter("battery", "Battery", ("battery", "배터리", "bms", "solid-state", "solid state", "전고체", "catl", "lfp", "ncm", "lithium")),
    TopicFilter("ee_architecture", "E/E Architecture", ("e/e architecture", "zonal architecture", "zone controller", "zonal", "hpc", "vehicle computer", "중앙 집중형", "전자 아키텍처", "도메인 컨트롤러")),
]


@dataclass(frozen=True, slots=True)
class SourceTypeFilter:
    key: str
    label_en: str
    label_ko: str


SOURCE_TYPE_FILTERS = [
    SourceTypeFilter("all", "All Sources", "전체"),
    SourceTypeFilter("media", "Media", "언론"),
    SourceTypeFilter("official", "Official", "공식"),
    SourceTypeFilter("institution", "Institution", "기관"),
    SourceTypeFilter("regulator", "Regulator", "규제 기구"),
    SourceTypeFilter("research", "Research", "연구/분석"),
]


INTELLIGENCE_SECTION_DEFINITIONS = [
    {
        "key": "top_stories",
        "label_en": "Top Stories",
        "label_ko": "주요 뉴스 (Top Stories)",
        "subtitle_en": "High impact automotive developments and strategic moves",
        "subtitle_ko": "핵심 전략 및 주요 업계 동향",
        "categories": {"big"},
    },
    {
        "key": "oem",
        "label_en": "OEM",
        "label_ko": "완성차 (OEM)",
        "subtitle_en": "Automaker strategy, vehicle programs and restructuring",
        "subtitle_ko": "완성차 제조사 전략 및 신차 프로그램",
        "categories": {"oem"},
    },
    {
        "key": "tier1_supply",
        "label_en": "Tier 1 / Supply Chain",
        "label_ko": "Tier 1 / 공급망",
        "subtitle_en": "Suppliers, components, manufacturing and logistics",
        "subtitle_ko": "주요 부품사 및 글로벌 부품 공급망",
        "categories": {"tier1", "supply_chain"},
    },
    {
        "key": "software_sdv",
        "label_en": "Software / SDV",
        "label_ko": "소프트웨어 / SDV",
        "subtitle_en": "E/E architecture, vehicle OS, middleware, OTA and cybersecurity",
        "subtitle_ko": "차량용 SW, 전장 아키텍처, OTA 및 사이버보안",
        "categories": {"sdv", "software", "cybersecurity"},
    },
    {
        "key": "adas_autonomous",
        "label_en": "ADAS / Autonomous",
        "label_ko": "자율주행 / ADAS",
        "subtitle_en": "Driver assistance, sensor fusion and autonomous driving systems",
        "subtitle_ko": "첨단 운전자 보조 시스템 및 자율주행 기술",
        "categories": {"adas_autonomous"},
    },
    {
        "key": "ev_battery",
        "label_en": "EV / Battery",
        "label_ko": "전기차 / 배터리",
        "subtitle_en": "Electrification, battery technology, chemistry and charging",
        "subtitle_ko": "전기차 플랫폼, 배터리 셀 기술 및 충전 인프라",
        "categories": {"ev_battery"},
    },
    {
        "key": "regulation",
        "label_en": "Regulation",
        "label_ko": "정책 / 규제",
        "subtitle_en": "Safety standards, emissions, tariffs and trade compliance",
        "subtitle_ko": "각국 안전 기준, 배출 규제 및 무역 통상 정책",
        "categories": {"regulation"},
    },
    {
        "key": "market",
        "label_en": "Market",
        "label_ko": "시장 / 금융",
        "subtitle_en": "Industry forecasts, sales figures, investments and earnings",
        "subtitle_ko": "시장 점유율, 판매 실적 및 산업 투자 분석",
        "categories": {"market", "manufacturing"},
    },
    {
        "key": "conferences",
        "label_en": "Conferences / Events",
        "label_ko": "컨퍼런스 / 이벤트",
        "subtitle_en": "Upcoming global automotive summits and technical events",
        "subtitle_ko": "글로벌 모빌리티 컨퍼런스 및 기술 행사 일정",
        "categories": {"conference"},
    },
]


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


def display_event_coverage(article: Article) -> dict[str, object] | None:
    source_count = max(article.event_source_count, 1 + len(article.related_article_ids))
    if source_count <= 1 and not (article.event_has_official_source or article.is_official):
        return None

    independent_count = (
        article.event_independent_source_count
        if article.event_independent_source_count > 0
        else source_count
    )
    has_official = article.event_has_official_source or article.is_official
    has_reg = article.event_has_regulatory_source or (article.source_type == "regulator")

    source_label_ko = f"{source_count}개 매체"
    source_label_en = f"{source_count} sources"

    independent_label_ko = f"{independent_count}개 독립 매체"
    independent_label_en = f"{independent_count} independent publishers"

    official_label_ko = "공식 출처 제공" if has_official else None
    official_label_en = "Official source available" if has_official else None

    regulatory_label_ko = "규제 기관 출처" if has_reg else None
    regulatory_label_en = "Regulatory source available" if has_reg else None

    return {
        "count": source_count,
        "source_count": source_count,
        "independent_source_count": independent_count,
        "has_official_source": has_official,
        "has_regulatory_source": has_reg,
        "has_major_media_source": article.event_has_major_media_source,
        "official_source_url": article.event_official_source_url,
        "official_source_name": article.event_official_source_name,
        "reference_source_name": article.event_reference_source_name or article.source,
        "related_sources": article.event_related_sources or [article.source],
        "source_label_ko": source_label_ko,
        "source_label_en": source_label_en,
        "independent_label_ko": independent_label_ko,
        "independent_label_en": independent_label_en,
        "official_label_ko": official_label_ko,
        "official_label_en": official_label_en,
        "regulatory_label_ko": regulatory_label_ko,
        "regulatory_label_en": regulatory_label_en,
        "label_ko": f"{source_count}개 매체 보도 중",
        "label_en": f"{source_count} sources covering this event",
        "event_title": getattr(article, "event_title", None) or article.title,
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


def all_region_keys_for_article(article: Article) -> list[str]:
    text = _region_text(article)
    keys = ["all"]
    matched = False

    if any(_contains_region_term(text, term) for term in REGION_TERMS["us"]):
        keys.append("us")
        matched = True
    if any(_contains_region_term(text, term) for term in REGION_TERMS["europe"]):
        keys.append("europe")
        matched = True
    if any(_contains_region_term(text, term) for term in REGION_TERMS["germany"]):
        if "europe" not in keys:
            keys.append("europe")
        keys.append("germany")
        matched = True
    if any(_contains_region_term(text, term) for term in REGION_TERMS["korea"]):
        keys.append("korea")
        if "asia" not in keys:
            keys.append("asia")
        matched = True
    if any(_contains_region_term(text, term) for term in REGION_TERMS["asia"]):
        if "asia" not in keys:
            keys.append("asia")
        matched = True

    if not matched:
        keys.append("global")

    return keys


def region_counts(articles: list[Article]) -> dict[str, int]:
    counts = {region.key: 0 for region in REGION_FILTERS}
    counts["all"] = len(articles)
    for article in articles:
        for r in regions_for_article(article):
            if r.key in counts:
                counts[r.key] += 1
        sub_keys = set(all_region_keys_for_article(article))
        if "germany" in sub_keys and "germany" in counts:
            counts["germany"] += 1
        if "korea" in sub_keys and "korea" in counts:
            counts["korea"] += 1
    return counts


def topics_for_article(article: Article) -> list[TopicFilter]:
    search_text = f"{article.title} {article.summary_ko} {article.summary_en} {article.excerpt} {' '.join(article.tags)} {' '.join(getattr(article, 'topics', []))}".lower()
    matched = []
    for tf in TOPIC_FILTERS:
        if tf.key == "all":
            continue
        if any(term in search_text for term in tf.terms):
            matched.append(tf)
    return matched


def topic_keys_for_article(article: Article) -> list[str]:
    keys = ["all"]
    keys.extend(tf.key for tf in topics_for_article(article))
    return keys


def topic_counts(articles: list[Article]) -> dict[str, int]:
    counts = {tf.key: 0 for tf in TOPIC_FILTERS}
    counts["all"] = len(articles)
    for article in articles:
        for tf in topics_for_article(article):
            counts[tf.key] += 1
    return counts


def canonical_source_type(article: Article) -> str:
    st = (article.source_type or "").lower()
    if article.is_official or st in {"official", "event"}:
        return "official"
    if st == "regulator":
        return "regulator"
    if st == "research":
        return "research"
    if st in {"institution", "open_source"}:
        return "institution"
    return "media"


def source_type_keys_for_article(article: Article) -> list[str]:
    return ["all", canonical_source_type(article)]


def source_type_counts(articles: list[Article]) -> dict[str, int]:
    counts = {stf.key: 0 for stf in SOURCE_TYPE_FILTERS}
    counts["all"] = len(articles)
    for article in articles:
        st = canonical_source_type(article)
        if st in counts:
            counts[st] += 1
    return counts


def display_published_time(article: Article, lang: str = "ko") -> str:
    val = article.published_at
    if not val:
        return ""
    text = str(val).strip()
    if "T" in text:
        parts = text.split("T")
        date_part = parts[0]
        time_part = parts[1][:5]
        return f"{date_part} {time_part}"
    if len(text) >= 10:
        return text[:16]
    return text


def display_factual_summary_ko(article: Article) -> str:
    summary = article.summary_ko or summarize_article(replace(article, tags=visible_tags(article)))
    summary = LEGACY_ORIGINAL_TITLE_RE.sub("", summary).strip()
    clean = re.sub(r"\s*\[의미:.*?\]", "", summary).strip()
    return clean or "핵심 동향을 확인할 수 있는 자동차 산업 기사입니다."


def display_factual_summary_en(article: Article) -> str:
    if article.summary_en:
        return re.sub(r"\s*\[Why it matters:.*?\]", "", article.summary_en).strip()
    if article.excerpt:
        return article.excerpt.strip()
    return "Reference briefing covering key automotive industry developments."


def display_why_it_matters_ko(article: Article) -> str:
    if article.why_it_matters_ko:
        return article.why_it_matters_ko.strip()
    priority = assess_priority(article)
    return priority.reason_ko or ""


def display_why_it_matters_en(article: Article) -> str:
    priority = assess_priority(article)
    return priority.reason_en or ""


def display_primary_category(article: Article, lang: str = "ko") -> str:
    cat = getattr(article, "primary_category", "") or article.category or "general"
    is_en = lang == "en"
    mapping = {
        "big": "Top Stories" if is_en else "주요 뉴스",
        "oem": "OEM",
        "tier1": "Tier 1" if is_en else "부품사",
        "supply_chain": "Supply Chain" if is_en else "공급망",
        "sdv": "SDV",
        "software": "Software" if is_en else "소프트웨어",
        "cybersecurity": "Cybersecurity" if is_en else "사이버보안",
        "adas_autonomous": "ADAS / Autonomous" if is_en else "자율주행",
        "ev_battery": "EV / Battery" if is_en else "전기차 / 배터리",
        "regulation": "Regulation" if is_en else "정책 / 규제",
        "market": "Market" if is_en else "시장",
        "manufacturing": "Manufacturing" if is_en else "제조",
        "conference": "Conference" if is_en else "컨퍼런스",
        "institution": "Institution" if is_en else "기관",
        "reference": "Reference" if is_en else "참고",
    }
    return mapping.get(cat, cat.upper())


def build_intelligence_sections(issue: NewsletterIssue, lang: str = "ko") -> list[dict[str, object]]:
    is_en = lang == "en"
    sections: list[dict[str, object]] = []
    assigned_urls = set()

    # Identify primary articles for presentation:
    # A cluster displays only one primary article card in the newsletter,
    # with related sources and multi-source coverage indicators.
    primary_article_ids = {
        e.primary_article_id for e in issue.events if e.primary_article_id
    }
    if not primary_article_ids and any(a.event_id for a in issue.articles):
        seen_events: set[str] = set()
        for a in issue.articles:
            if a.event_id and a.event_id not in seen_events:
                event_group = [x for x in issue.articles if x.event_id == a.event_id]
                primary = select_primary_article(event_group)
                if primary.article_id:
                    primary_article_ids.add(primary.article_id)
                seen_events.add(a.event_id)

    # Eligible articles for display in sections (primary or standalone)
    displayable_articles = [
        a for a in issue.articles
        if not a.event_id or not primary_article_ids or a.article_id in primary_article_ids
    ]

    for defn in INTELLIGENCE_SECTION_DEFINITIONS:
        cats = defn["categories"]
        articles = [
            a for a in displayable_articles
            if (a.category in cats or getattr(a, "primary_category", "") in cats)
            and a.url not in assigned_urls
        ]
        for a in articles:
            assigned_urls.add(a.url)

        sort_cat = "conference" if defn["key"] == "conferences" else "standard"
        sorted_articles = sort_articles_for_section(sort_cat, articles, issue.issue_date)
        sections.append({
            "key": defn["key"],
            "label_en": defn["label_en"],
            "label_ko": defn["label_ko"],
            "label": defn["label_en"] if is_en else defn["label_ko"],
            "subtitle_en": defn["subtitle_en"],
            "subtitle_ko": defn["subtitle_ko"],
            "subtitle": defn["subtitle_en"] if is_en else defn["subtitle_ko"],
            "articles": sorted_articles,
        })

    leftovers = [a for a in displayable_articles if a.url not in assigned_urls]
    if leftovers:
        for a in leftovers:
            target_key = "regulation" if a.source_type in {"regulator", "institution"} else "market"
            for sec in sections:
                if sec["key"] == target_key:
                    sec["articles"].append(a)
                    break
        for sec in sections:
            if sec["key"] in {"regulation", "market"}:
                sec["articles"] = sort_articles_for_section("standard", sec["articles"], issue.issue_date)

    return sections


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
    if re.search(r"\b(ai|a\.i\.|artificial intelligence|generative ai|machine learning|diagnostic|repair)\b", text, re.IGNORECASE):
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
