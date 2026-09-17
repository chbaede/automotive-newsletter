from __future__ import annotations

import base64
import re
import time
from dataclasses import replace
from datetime import date, datetime, time as datetime_time, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import httpx
from bs4 import BeautifulSoup

from .clustering import STOP_WORDS, cluster_articles, select_primary_article
from .config import Settings, load_settings
from .content_extractor import extract_usable_article_text
from .logging import logger
from .models import Article, CollectionMetrics, FeedEntry, NewsletterIssue
from .sources import (
    DEFAULT_FEEDS,
    SECTION_ORDER,
    SourceFeed,
    classify_source_type,
    get_enabled_sources,
    get_source,
    source_authority,
    source_metadata,
)
from .store import NewsletterStore
from .summarizer import BaseSummarizer, classify_article, get_summarizer

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid", "mc_cid", "mc_eid",
    "igshid", "yclid", "_hsenc", "_hsmi", "ref", "ref_src", "ref_url",
    "spjobid", "spmailingid", "spreportid",
}
REQUEST_HEADERS = {"User-Agent": "AutomotiveNewsletter/0.1 (+local research app)"}

TITLE_STOP_WORDS = STOP_WORDS | {"속보", "단독", "종합", "포토", "영상"}



def clean_title_for_comparison(title: str) -> str:
    title = re.sub(r"^\[.*?\]|\【.*?\】|\(.*?\)", " ", title)
    title = re.sub(r"\s*[-|–—]\s*[^-|–—]+$", "", title)
    title = re.sub(r"[^a-z0-9가-힣\s]", " ", title.lower())
    return " ".join(title.split())


def extract_title_tokens(title: str) -> set[str]:
    cleaned = clean_title_for_comparison(title)
    words = cleaned.split()
    return {w for w in words if w not in TITLE_STOP_WORDS}


def _title_numbers(title: str) -> set[str]:
    return set(re.findall(r"\b\d+[a-z]?\b", title.lower()))


def are_titles_similar(t1: str, t2: str) -> bool:
    norm1 = normalize_title(t1)
    norm2 = normalize_title(t2)
    if norm1 == norm2 and norm1:
        return True

    # If numeric identifiers differ (e.g. Model 3 vs Model Y, part 0 vs 1), do not treat as similar
    if _title_numbers(t1) != _title_numbers(t2):
        return False

    tokens1 = extract_title_tokens(t1)
    tokens2 = extract_title_tokens(t2)
    if not tokens1 or not tokens2:
        return False

    common = tokens1 & tokens2
    max_len = max(len(tokens1), len(tokens2))
    min_len = min(len(tokens1), len(tokens2))

    if len(common) >= 4 and (len(common) / max_len >= 0.8 or len(common) / min_len >= 0.85):
        return True

    if len(common) >= 3 and min_len >= 4:
        jaccard = len(common) / len(tokens1 | tokens2)
        if jaccard >= 0.75:
            return True

    return False


def should_allow_page_fetch(
    feed: SourceFeed | None = None,
    entry_bucket: str | None = None,
    entry_source_type: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Determine whether page extraction is permissible for an entry.

    Respects settings and avoids fetching for conference reference entries or
    known static fallback/reference articles unless explicitly configured.
    """
    if settings is None:
        settings = load_settings()
    if not settings.fetch_article_excerpts:
        return False
    # Requirement 10: Do not fetch article pages unnecessarily for conference reference entries
    if entry_bucket == "conference" or (feed and feed.bucket == "conference"):
        return False
    # Requirement 10: Do not fetch for known static fallback/reference articles
    if entry_source_type in {"reference", "static"}:
        return False
    if feed and (feed.source_type in {"reference", "static"} or feed.bucket in {"reference", "conference"}):
        return False
    return True


def collect_from_entries(
    entries: Iterable[FeedEntry],
    recent_articles: Iterable[Article] | None = None,
    summarizer: BaseSummarizer | None = None,
    settings: Settings | None = None,
) -> tuple[list[Article], list[str]]:
    articles: list[Article] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    title_index: dict[str, list[str]] = {}

    if recent_articles:
        for past_article in recent_articles:
            if past_article.category == "conference":
                continue
            past_url = canonicalize_url(past_article.url)
            past_norm = normalize_title(past_article.title)
            if past_url:
                seen_urls.add(past_url)
            if past_norm:
                seen_titles.add(past_norm)
            past_tokens = extract_title_tokens(past_article.title)
            for tok in past_tokens:
                title_index.setdefault(tok, []).append(past_article.title)

    for entry in entries:
        canonical_url = canonicalize_url(entry.url)
        title_key = normalize_title(entry.title)
        if not canonical_url or not title_key:
            continue
        if canonical_url in seen_urls or title_key in seen_titles:
            continue

        tokens = extract_title_tokens(entry.title)
        if tokens and entry.bucket != "conference":
            candidate_titles = {
                cand for tok in tokens for cand in title_index.get(tok, [])
            }
            if any(are_titles_similar(cand, entry.title) for cand in candidate_titles):
                continue

        seen_urls.add(canonical_url)
        seen_titles.add(title_key)
        if tokens and entry.bucket != "conference":
            for tok in tokens:
                title_index.setdefault(tok, []).append(entry.title)

        publisher_name = clean_text(entry.publisher or entry.source, 80) or "Unknown"
        article_content = entry.content
        content_source = getattr(entry, "content_source_type", "fallback") or "fallback"

        # Requirement 1: Call extract_usable_article_text when content is missing
        if not article_content:
            active_settings = settings or load_settings()
            allow_fetch = should_allow_page_fetch(
                feed=None,
                entry_bucket=entry.bucket,
                entry_source_type=entry.source_type,
                settings=active_settings,
            )
            extracted = extract_usable_article_text(
                raw_entry=None,
                url=canonical_url,
                title=entry.title,
                excerpt=entry.excerpt,
                allow_page_fetch=allow_fetch,
                timeout=active_settings.content_fetch_timeout,
            )
            article_content = extracted.text
            content_source = extracted.source_type

        article = Article(
            title=clean_text(entry.title, 240),
            url=canonical_url,
            source=publisher_name,
            category=entry.bucket,
            published_at=entry.published_at,
            excerpt=clean_text(entry.excerpt or article_content, 420),
            discovered_via=entry.discovered_via,
            source_id=entry.source_id,
            authority_score=entry.authority_score,
            source_type=entry.source_type,
            source_authority=entry.source_authority,
            publisher=publisher_name,
            canonical_url=canonical_url,
            original_url=entry.url,
            primary_category=entry.bucket,
            is_official=(entry.source_type == "official"),
            is_reference=(entry.source_type in {"regulator", "institution", "research"}),
            is_primary_source=(
                entry.source_type in {"official", "regulator", "press_release"}
            ),
            collected_at=entry.collected_at or datetime.now(timezone.utc),
            content=article_content,
            content_source_type=content_source,
        )
        is_short = len((article_content or article.excerpt).strip()) < 250
        articles.append(
            classify_article(
                article,
                summarizer=summarizer,
                content=article_content,
                is_short_excerpt=is_short,
            )
        )

    articles.sort(
        key=lambda article: (
            article.score,
            article.published_at.timestamp() if article.published_at else 0,
        ),
        reverse=True,
    )
    return articles, []


def select_presentation_articles(
    articles: list[Article],
    events: list[Event] | None = None,
    per_section: int = 5,
) -> list[Article]:
    """Select primary article for each cluster and limit to per_section per category."""
    primary_ids = {e.primary_article_id for e in events or [] if e.primary_article_id}
    if not primary_ids and any(a.event_id for a in articles):
        seen_events: set[str] = set()
        for a in articles:
            if a.event_id and a.event_id not in seen_events:
                group = [x for x in articles if x.event_id == a.event_id]
                prim = select_primary_article(group)
                if prim.article_id:
                    primary_ids.add(prim.article_id)
                seen_events.add(a.event_id)

    candidate_articles = [
        a for a in articles
        if not a.event_id or not primary_ids or a.article_id in primary_ids
    ]

    selected: list[Article] = []
    for section in SECTION_ORDER:
        section_articles = [article for article in candidate_articles if article.category == section]
        direct_section_articles = [
            article for article in section_articles if not is_intermediary_url(article.url)
        ]
        if direct_section_articles:
            section_articles = direct_section_articles
        selected.extend(section_articles[:per_section])
    if not selected:
        selected = candidate_articles[: per_section * len(SECTION_ORDER)]
    return selected


def build_issue_articles(
    entries: Iterable[FeedEntry] | Iterable[Article],
    per_section: int = 5,
    recent_articles: Iterable[Article] | None = None,
    summarizer: BaseSummarizer | None = None,
) -> list[Article]:
    entry_list = list(entries)
    if not entry_list:
        return []
    if isinstance(entry_list[0], FeedEntry):
        articles, _warnings = collect_from_entries(
            entry_list,  # type: ignore[arg-type]
            recent_articles=recent_articles,
            summarizer=summarizer,
        )
    else:
        articles = [
            classify_article(article, summarizer=summarizer) for article in entry_list  # type: ignore[arg-type]
        ]

    events, _event_articles, all_articles = cluster_articles(articles)
    return select_presentation_articles(all_articles, events=events, per_section=per_section)


def collect_and_store(
    store: NewsletterStore | None = None,
    settings: Settings | None = None,
    issue_date: str | None = None,
    feeds: list[SourceFeed] | None = None,
    summarizer: BaseSummarizer | None = None,
) -> NewsletterIssue:
    t0 = time.perf_counter()
    settings = settings or load_settings()
    store = store or NewsletterStore(settings.db_path)
    summarizer = summarizer or get_summarizer(settings)
    issue_date = issue_date or date.today().isoformat()

    logger.info(component="collector", event="collection_started", source="collector")
    recent_articles = store.get_recent_articles(before_issue_date=issue_date, days=7)
    feeds_to_fetch = feeds if feeds is not None else get_enabled_sources()

    try:
        # 1. Fetch
        entries, warnings, stats = fetch_feed_entries(  # type: ignore[misc]
            feeds_to_fetch, settings=settings, return_stats=True
        )
        raw_count = len(entries)

        # 2. Canonicalize -> Deduplicate -> Classify -> Score
        deduped_articles, _ = collect_from_entries(
            entries, recent_articles=recent_articles, summarizer=summarizer
        )
        articles_after_dedupe = len(deduped_articles)

        # 3. Add fallback/reference content if necessary
        all_articles = ensure_required_fallbacks(deduped_articles, issue_date=issue_date)

        # 4. Cluster ONCE (clustering NEVER removes articles)
        events, event_articles, all_articles = cluster_articles(all_articles)

        # 5. Select articles for newsletter presentation (for metrics and priority ordering)
        presentation_articles = select_presentation_articles(
            all_articles, events=events, per_section=5
        )
        articles_selected = len(presentation_articles)

        # Order all articles so presentation articles appear first, followed by coverage articles
        presentation_ids = {a.article_id for a in presentation_articles}
        ordered_all_articles = [
            *presentation_articles,
            *[a for a in all_articles if a.article_id not in presentation_ids],
        ]

        if not all_articles and warnings:
            warnings = [*warnings, "수집된 기사가 없어 빈 이슈를 저장했습니다."]

        duration = time.perf_counter() - t0
        metrics = CollectionMetrics(
            feeds_total=stats.get("feeds_total", len(feeds_to_fetch)),
            feeds_ok=stats.get("feeds_ok", 0),
            feeds_failed=stats.get("feeds_failed", 0),
            articles_collected=raw_count,
            articles_after_dedupe=articles_after_dedupe,
            articles_selected=articles_selected,
            collection_duration=round(duration, 4),
        ).to_dict()

        # 6. Store ALL collected articles and events
        issue = store.save_issue(
            issue_date,
            ordered_all_articles,
            warnings=warnings,
            events=events,
            event_articles=event_articles,
            metrics=metrics,
        )
        store.finish_daily_run(issue_date, metrics=metrics)
        logger.info(
            component="collector",
            event="collection_completed",
            source="collector",
            duration=duration,
        )
        return issue
    except Exception as exc:
        duration = time.perf_counter() - t0
        logger.error(
            component="collector",
            event="collection_failed",
            source="collector",
            duration=duration,
            error=str(exc),
        )
        store.fail_daily_run(issue_date, error=str(exc))
        raise


def ensure_required_fallbacks(
    articles: list[Article], issue_date: str | date | None = None
) -> list[Article]:
    on_date = _coerce_date(issue_date)
    enriched = list(articles)
    if not any(
        article.category == "tier1" and not is_intermediary_url(article.url) for article in enriched
    ):
        enriched.extend(supplier_fallback_articles())
    if not any(
        article.category == "institution" and not is_intermediary_url(article.url)
        for article in enriched
    ):
        enriched.extend(institution_fallback_articles())
    if not any(
        article.category == "conference" and not is_intermediary_url(article.url)
        for article in enriched
    ):
        enriched.extend(conference_fallback_articles(on_date=on_date))
    else:
        enriched.extend(conference_fallback_articles(on_date=on_date))
    return remove_intermediary_articles(dedupe_articles(enriched))


def supplier_fallback_articles() -> list[Article]:
    suppliers = [
        (
            "Bosch: software-defined vehicle 심층 페이지",
            "https://www.bosch-mobility.com/en/mobility-topics/software-defined-vehicle",
            "Bosch Mobility의 SDV 정의, E/E 아키텍처 전환, OTA 기반 기능 확장 관점을 확인할 수 있습니다.",
            ["Bosch", "ADAS", "SDV"],
        ),
        (
            "Continental: 차량-클라우드 SDV 생태계 보도자료",
            "https://www.continental.com/en/press/press-releases/20230614-continental-techshow-topicfield/",
            "Continental의 Software-Defined Vehicle, 고성능 컴퓨터, 클라우드 개발 환경, 사이버보안 전략을 다룬 보도자료입니다.",
            ["Continental", "SDV"],
        ),
        (
            "Valeo SDV 공식 인사이트",
            "https://www.valeo.com/en/everything-you-need-to-know-about-the-software-defined-vehicle-sdv/",
            "Valeo의 Software Defined Vehicle 정의, 시장 과제, Tier 1 관점의 기술 포지션을 확인할 수 있습니다.",
            ["Valeo", "SDV"],
        ),
        (
            "Magna-NVIDIA: DRIVE Hyperion 통합 서비스 보도자료",
            "https://www.magna.com/stories/news-press-release/2026/magna-to-offer-drive-hyperion-compatible-ecus-and-tier-1-integration-services-for-nvidia-drive-av",
            "Magna와 NVIDIA의 DRIVE AV, Hyperion 호환 ECU, Tier 1 시스템 통합 서비스 발표를 확인할 수 있습니다.",
            ["Magna", "ADAS", "SDV"],
        ),
        (
            "ZF CES 2026 SDV 섀시 보도자료",
            "https://press.zf.com/press/en/releases/release_97988.html",
            "ZF의 AI Road Sense, 능동 소음 저감, 소프트웨어 기반 섀시 전략을 확인할 수 있습니다.",
            ["ZF", "SDV"],
        ),
    ]
    return [
        Article(
            title=title,
            url=url,
            source="공식 뉴스룸",
            category="tier1",
            summary_ko=summary,
            tags=tags,
            score=34 - index,
        )
        for index, (title, url, summary, tags) in enumerate(suppliers)
    ]


def institution_fallback_articles() -> list[Article]:
    institutions = [
        (
            "Cox Automotive: 2026 미국 신차 판매 전망",
            "https://www.coxautoinc.com/insights-hub/cox-automotive-2026-outlook/",
            "Cox Automotive의 2026년 미국 자동차 시장 전망, 수요 양극화, 금리·가격 영향을 다룬 인사이트입니다.",
            ["Cox Automotive"],
        ),
        (
            "J.D. Power: 2026 미국 차량 내구품질 조사",
            "https://www.jdpower.com/pr-id/2026133",
            "OTA와 인포테인먼트 문제가 장기 품질 인식에 미치는 영향을 다룬 J.D. Power 2026 VDS 보도자료입니다.",
            ["J.D. Power", "OTA"],
        ),
        (
            "S&P Global Mobility: 2025 자동차 충성도 어워즈",
            "https://press.spglobal.com/2026-01-14-S-P-Global-Mobility-2025-Loyalty-Awards-Reveal-Divergent-Paths-to-Customer-Retention-General-Motors-and-Tesla-Secure-Top-Honors",
            "S&P Global Mobility가 GM과 Tesla의 고객 유지 성과를 포함해 브랜드 충성도 흐름을 분석한 공식 보도자료입니다.",
            ["S&P Global Mobility", "GM", "Tesla"],
        ),
        (
            "SAE: SDV 아키텍처 기술 논문",
            "https://saemobilus.sae.org/papers/software-defined-vehicles-architecting-future-intelligent-connected-mobility-2026-26-0691",
            "SAE Mobilus의 Software-Defined Vehicle 아키텍처, SOA, AUTOSAR, OTA, AI 적용 기술 논문입니다.",
            ["SAE", "SDV"],
        ),
        (
            "WardsAuto: 데이터 준비형 차량과 SDV 분석",
            "https://www.wardsauto.com/spons/the-drive-for-data-ready-vehicles-is-accelerating-smarter-mobility/804696/",
            "WardsAuto의 SDV 데이터 오케스트레이션, 품질 데이터, 개발 피드백 루프 관련 분석 글입니다.",
            ["WardsAuto", "SDV"],
        ),
    ]
    return [
        Article(
            title=title,
            url=url,
            source="기관/매거진",
            category="institution",
            summary_ko=summary,
            tags=tags,
            score=32 - index,
        )
        for index, (title, url, summary, tags) in enumerate(institutions)
    ]


def conference_fallback_articles(on_date: str | date | None = None) -> list[Article]:
    on_date = _coerce_date(on_date)
    events = [
        (
            "2026 CES",
            "2026-01-06",
            "2026-01-09",
            "Las Vegas",
            "https://www.ces.tech/",
            "CES 2026의 차량 기술, AI, 모빌리티 발표를 확인할 수 있습니다.",
            ["CES", "2026", "종료"],
        ),
        (
            "2026 Detroit Auto Show",
            "2026-01-14",
            "2026-01-25",
            "Detroit",
            "https://detroitautoshow.com/",
            "Detroit Auto Show의 OEM 참가, 미디어 데이, 북미 시장 발표를 확인할 수 있습니다.",
            ["Detroit Auto Show", "OEM", "2026", "종료"],
        ),
        (
            "Automotive World Tokyo 2026",
            "2026-01-21",
            "2026-01-23",
            "Tokyo Big Sight",
            "https://www.automotiveworld.jp/tokyo/en-gb.html",
            "Automotive World Tokyo의 SDV, 전동화, 전장, 자율주행 전시 정보를 볼 수 있습니다.",
            ["Automotive World Tokyo", "SDV", "EV", "2026", "종료"],
        ),
        (
            "Automotive Computing Conference USA",
            "2026-03-24",
            "2026-03-25",
            "Dearborn/Detroit",
            "https://www.automotive-computing-usa.com/",
            "차량 컴퓨팅, 칩렛, 가상 ECU, SDV 아키텍처 중심의 전문 컨퍼런스입니다.",
            ["SDV", "AI", "2026", "종료"],
        ),
        (
            "SAE WCX 2026",
            "2026-04-14",
            "2026-04-16",
            "Detroit",
            "https://www.sae.org/attend/wcx",
            "SAE WCX의 기술 세션, 규제, 안전, 전동화, 차량 엔지니어링 아젠다를 확인할 수 있습니다.",
            ["SAE WCX", "SAE", "SDV", "2026", "종료"],
        ),
        (
            "Auto China 2026",
            "2026-04-24",
            "2026-05-03",
            "Beijing",
            "https://www.autobeijing.org.cn/en/index.html",
            "중국 OEM, EV, 배터리, SDV 신차 발표와 글로벌 경쟁 구도를 확인할 수 있습니다.",
            ["Auto China", "OEM", "EV", "2026", "종료"],
        ),
        (
            "AutoTech Detroit 2026",
            "2026-06-02",
            "2026-06-04",
            "Novi",
            "https://attend.techevents.informaconnect.com/event/autotech-2026",
            "커넥티드카 수익화, SDV, 사이버보안, UX, ADAS 세션을 다루는 북미 자동차 기술 행사입니다.",
            ["AutoTech", "SDV", "ADAS", "2026", "종료"],
        ),
        (
            "The Battery Show Europe 2026",
            "2026-06-09",
            "2026-06-11",
            "Stuttgart",
            "https://www.thebatteryshow.eu/",
            "배터리 제조, 셀·팩 기술, 전기·하이브리드차 공급망을 확인할 수 있는 유럽 주요 행사입니다.",
            ["Battery", "EV", "2026", "예정"],
        ),
        (
            "Autonomous Vehicle Technology Expo Europe",
            "2026-06-23",
            "2026-06-25",
            "Stuttgart",
            "https://www.autonomousvehicletechnologyexpo.com/",
            "ADAS, 자율주행, 테스트, 센서, 시뮬레이션 기술을 확인할 수 있는 Vehicle Tech Week 행사입니다.",
            ["ADAS", "Autonomous", "2026", "예정"],
        ),
        (
            "SDV USA 2026",
            "2026-06-29",
            "2026-06-30",
            "San Francisco",
            "https://www.software-defined-vehicles-conference.us/",
            "Software-Defined Vehicle 전략, AI, 안전, 소프트웨어 아키텍처를 다루는 SDV 전문 행사입니다.",
            ["SDV", "AI", "2026", "예정"],
        ),
        (
            "Reuters Automotive Europe 2026",
            "2026-06-29",
            "2026-06-30",
            "Frankfurt",
            "https://www.reutersprofessional.com/reuters-events?event=automotive-europe",
            "유럽 OEM 전략, 전동화, 공급망, 소프트웨어 전환을 다루는 Reuters 자동차 컨퍼런스입니다.",
            ["Reuters", "OEM", "EV", "SDV", "2026", "예정"],
        ),
        (
            "Automotive World Tokyo 2026 Autumn",
            "2026-09-09",
            "2026-09-11",
            "Makuhari Messe",
            "https://www.automotiveworld.jp/autumn/en-gb.html",
            "일본 9월 Automotive World의 SDV, EV, 자율주행, 제조 기술 전시 일정입니다.",
            ["Automotive World Tokyo", "SDV", "EV", "2026", "예정"],
        ),
        (
            "IAA Transportation 2026",
            "2026-09-15",
            "2026-09-20",
            "Hannover",
            "https://www.iaa-transportation.com/en",
            "상용차, 물류, 전동화, 버스, 운송 플랫폼 중심의 글로벌 전시입니다.",
            ["IAA Transportation", "EV", "2026", "예정"],
        ),
        (
            "Automotive Technology Show 2026",
            "2026-09-29",
            "2026-09-30",
            "Sinsheim",
            "https://www.automotivetechnology.org/",
            "ADAS, 자율주행, SDV, 커넥티비티, 사이버보안 개발자를 위한 기술 쇼입니다.",
            ["SDV", "ADAS", "2026", "예정"],
        ),
        (
            "AGL All Member Meeting",
            "2026-09-30",
            "2026-10-01",
            "Berlin",
            "https://www.automotivelinux.org/",
            "Automotive Grade Linux와 SoDeV 기반 오픈소스 SDV 플랫폼 논의를 추적할 수 있습니다.",
            ["AGL", "SDV", "2026", "예정"],
        ),
        (
            "Japan Mobility Show Bizweek 2026",
            "2026-10-13",
            "2026-10-16",
            "Makuhari Messe",
            "https://www.japan-mobility-show.com/en/",
            "JAMA가 주관하는 일본 모빌리티 비즈니스 전시로, 이종 산업 협업과 모빌리티 전략을 확인할 수 있습니다.",
            ["Japan Mobility Show", "OEM", "2026", "예정"],
        ),
        (
            "Paris Motor Show 2026",
            "2026-10-12",
            "2026-10-18",
            "Paris",
            "https://mondial.paris/en",
            "유럽 OEM, 전동화, 신차 발표 흐름을 볼 수 있는 주요 국제 모터쇼입니다.",
            ["Paris Motor Show", "OEM", "EV", "2026", "예정"],
        ),
        (
            "Reuters Automotive USA 2026",
            "2026-10-28",
            "2026-10-29",
            "Detroit",
            "https://www.reutersprofessional.com/reuters-events?event=automotive-usa",
            "북미 OEM 리더십, SDV, 전동화, 커넥티드카, 공급망 전략을 다루는 Reuters 행사입니다.",
            ["Reuters", "OEM", "SDV", "2026", "예정"],
        ),
        (
            "Automotive World Nagoya 2026",
            "2026-11-25",
            "2026-11-27",
            "Aichi Sky Expo",
            "https://www.automotiveworld.jp/nagoya/en-gb.html",
            "일본 중부 자동차 산업권의 SDV, 전장, EV/HV/FCV 기술 전시입니다.",
            ["Automotive World Nagoya", "SDV", "EV", "2026", "예정"],
        ),
    ]
    articles = []
    for index, (name, starts_on, ends_on, location, url, summary, tags) in enumerate(events):
        start_date = date.fromisoformat(starts_on)
        end_date = date.fromisoformat(ends_on)
        if end_date < on_date:
            continue
        status_tag = "예정" if start_date >= on_date else "진행중"
        display_tags = [tag for tag in tags if tag not in {"종료", "예정"}]
        articles.append(
            Article(
                title=f"{name} | {_format_event_date_range(start_date, end_date)} · {location}",
                url=url,
                source="공식 사이트",
                category="conference",
                published_at=datetime.combine(start_date, datetime_time.min, tzinfo=timezone.utc),
                summary_ko=summary,
                tags=[
                    *display_tags,
                    status_tag,
                    f"event_start:{starts_on}",
                    f"event_end:{ends_on}",
                ],
                score=_conference_score([*display_tags, status_tag], index),
            )
        )
    return sorted(articles, key=lambda article: article.published_at or datetime.max.replace(tzinfo=timezone.utc))


def remove_intermediary_articles(articles: list[Article]) -> list[Article]:
    direct_articles = [article for article in articles if not is_intermediary_url(article.url)]
    return direct_articles if direct_articles else articles


def dedupe_articles(articles: list[Article]) -> list[Article]:
    deduped: list[Article] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    title_index: dict[str, list[str]] = {}

    for article in articles:
        canon_url = canonicalize_url(article.url)
        norm_title = normalize_title(article.title)
        if canon_url and canon_url in seen_urls:
            continue
        if norm_title and norm_title in seen_titles:
            continue

        tokens = extract_title_tokens(article.title)
        if tokens and article.category != "conference":
            candidate_titles = {
                cand for tok in tokens for cand in title_index.get(tok, [])
            }
            if any(are_titles_similar(cand, article.title) for cand in candidate_titles):
                continue

        if canon_url:
            seen_urls.add(canon_url)
        if norm_title:
            seen_titles.add(norm_title)
        if tokens and article.category != "conference":
            for tok in tokens:
                title_index.setdefault(tok, []).append(article.title)
        deduped.append(article)
    return deduped


def _conference_score(tags: list[str], index: int) -> float:
    score = 48 - min(index, 12)
    if "예정" in tags:
        score += 10
    if "SDV" in tags:
        score += 6
    if "ADAS" in tags:
        score += 4
    if "EV" in tags:
        score += 3
    return float(score)


def _coerce_date(value: str | date | None) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return date.today()


def _format_event_date_range(start: date, end: date) -> str:
    if start == end:
        return f"{start.year}년 {start.month}월 {start.day}일"
    if start.year == end.year and start.month == end.month:
        return f"{start.year}년 {start.month}월 {start.day}-{end.day}일"
    if start.year == end.year:
        return f"{start.year}년 {start.month}월 {start.day}일-{end.month}월 {end.day}일"
    return f"{start.year}년 {start.month}월 {start.day}일-{end.year}년 {end.month}월 {end.day}일"


def fetch_feed_entries(
    feeds: Iterable[SourceFeed],
    settings: Settings | None = None,
    return_stats: bool = False,
) -> tuple[list[FeedEntry], list[str]] | tuple[list[FeedEntry], list[str], dict[str, int]]:
    settings = settings or load_settings()
    entries: list[FeedEntry] = []
    warnings: list[str] = []
    warned_tls_fallback = False
    feeds_total = 0
    feeds_ok = 0
    feeds_failed = 0
    with _feed_client(settings, verify=settings.verify_tls) as client, _feed_client(
        settings, verify=False
    ) as insecure_client:
        for feed in feeds:
            if not feed.enabled:
                continue
            feeds_total += 1
            feed_start = time.perf_counter()
            try:
                response, used_tls_fallback = _get_with_tls_fallback(
                    feed.url,
                    settings=settings,
                    client=client,
                    insecure_client=insecure_client,
                )
                if used_tls_fallback and not warned_tls_fallback:
                    warnings.append("TLS 인증서 검증 실패로 일부 피드는 검증 없이 재시도했습니다.")
                    warned_tls_fallback = True
                response.raise_for_status()
                parsed = feedparser.parse(response.content)
            except Exception as exc:
                warnings.append(f"{feed.name}: {exc}")
                feeds_failed += 1
                logger.warning(
                    component="collector",
                    event="feed_fetch_failed",
                    source=feed.id or feed.name,
                    duration=time.perf_counter() - feed_start,
                    error=str(exc),
                )
                continue
            if getattr(parsed, "bozo", False) and not parsed.entries:
                warnings.append(f"{feed.name}: 피드 파싱 실패")
                feeds_failed += 1
                logger.warning(
                    component="collector",
                    event="feed_fetch_failed",
                    source=feed.id or feed.name,
                    duration=time.perf_counter() - feed_start,
                    error="피드 파싱 실패",
                )
                continue

            feeds_ok += 1
            logger.info(
                component="collector",
                event="feed_fetch_ok",
                source=feed.id or feed.name,
                duration=time.perf_counter() - feed_start,
            )
            for raw in parsed.entries[: settings.max_entries_per_feed]:
                title = raw.get("title", "")
                url = raw.get("link", "")
                if not title or not url:
                    continue
                publisher, discovered_via, authority = extract_source_and_publisher(raw, feed)
                if publisher == "Unknown":
                    warnings.append(f"{feed.name}: 출처(publisher) 식별 실패 - {clean_text(title, 60)}")
                source_type = classify_source_type(publisher, feed)
                excerpt = strip_html(raw.get("summary", "") or raw.get("description", ""))
                published_at = _entry_date(raw)
                resolved_url = (
                    resolve_original_url(url, timeout=settings.request_timeout_seconds)
                    if settings.resolve_news_links
                    else url
                )

                allow_fetch = should_allow_page_fetch(
                    feed=feed,
                    entry_bucket=feed.bucket,
                    entry_source_type=source_type,
                    settings=settings,
                )
                extracted = extract_usable_article_text(
                    raw_entry=raw,
                    url=resolved_url,
                    title=title,
                    excerpt=excerpt,
                    allow_page_fetch=allow_fetch,
                    timeout=settings.content_fetch_timeout,
                )
                usable_content = extracted.text
                content_source = extracted.source_type
                if not excerpt and usable_content:
                    excerpt = clean_text(usable_content, 420)

                entries.append(
                    FeedEntry(
                        title=title,
                        url=resolved_url,
                        source=publisher,
                        bucket=feed.bucket,
                        published_at=published_at,
                        excerpt=excerpt,
                        discovered_via=discovered_via,
                        publisher=publisher,
                        source_id=feed.id,
                        authority_score=authority,
                        source_type=source_type,
                        source_authority=authority,
                        content=usable_content,
                        content_source_type=content_source,
                    )
                )
                time.sleep(0.02)
    stats = {
        "feeds_total": feeds_total,
        "feeds_ok": feeds_ok,
        "feeds_failed": feeds_failed,
    }
    if return_stats:
        return entries, warnings, stats
    return entries, warnings


def check_feed_health(
    feeds: Iterable[SourceFeed] | None = None, settings: Settings | None = None
) -> list[dict[str, object]]:
    settings = settings or load_settings()
    results: list[dict[str, object]] = []
    with _feed_client(settings, verify=settings.verify_tls) as client, _feed_client(
        settings, verify=False
    ) as insecure_client:
        for feed in feeds or DEFAULT_FEEDS:
            result: dict[str, object] = {
                "id": feed.id,
                "name": feed.name,
                "bucket": feed.bucket,
                "url": feed.url,
                "source_type": feed.source_type,
                "authority_score": feed.authority_score,
                "enabled": feed.enabled,
                "catalog_group": getattr(feed, "catalog_group", "media"),
                "discovery_method": getattr(feed, "discovery_method", "rss"),
                "ok": False,
                "status_code": None,
                "entries": 0,
                "tls_fallback": False,
                "error": "",
            }
            parsed = None
            try:
                response, used_tls_fallback = _get_with_tls_fallback(
                    feed.url,
                    settings=settings,
                    client=client,
                    insecure_client=insecure_client,
                )
                if getattr(feed, "discovery_method", "rss") == "manual_web":
                    result.update(
                        {
                            "ok": response.status_code < 400,
                            "status_code": response.status_code,
                            "entries": 0,
                            "tls_fallback": used_tls_fallback,
                        }
                    )
                else:
                    parsed = feedparser.parse(response.content)
                    entries = len(parsed.entries)
                    parse_failed = bool(getattr(parsed, "bozo", False) and not parsed.entries)
                    result.update(
                        {
                            "ok": response.status_code < 400 and not parse_failed,
                            "status_code": response.status_code,
                            "entries": entries,
                            "tls_fallback": used_tls_fallback,
                        }
                    )
                    if parse_failed:
                        result["error"] = "피드 파싱 실패"
            except Exception as exc:
                result["error"] = str(exc)

            diagnostic_label = feed.name
            if parsed and parsed.entries:
                first_entry = parsed.entries[0]
                pub, _, _ = extract_source_and_publisher(first_entry, feed)
                if pub and pub != feed.name and pub != "Unknown":
                    diagnostic_label = f"{feed.name} → {pub}"

            result["diagnostic_label"] = diagnostic_label
            state_str = "OK" if result["ok"] else "FAIL"
            if result["ok"]:
                result["diagnostic"] = f"{state_str}  {diagnostic_label}"
            else:
                result["diagnostic"] = f"{state_str} {diagnostic_label}"

            results.append(result)
    return results


def unwrap_google_redirect(url: str) -> str:
    if not url:
        return ""
    curr = unescape(url.strip())
    for _ in range(5):
        parts = urlsplit(curr)
        host = parts.netloc.lower()
        if not ("google." in host or host.endswith("google.com")):
            break

        # Check query parameters: continue, q, url
        params = dict(parse_qsl(parts.query, keep_blank_values=True))
        found = False
        for key in ("continue", "q", "url"):
            val = params.get(key, "")
            if val and val.startswith(("http://", "https://")):
                curr = val
                found = True
                break
        if found:
            continue

        # Check base64 encoded token in /articles/ path
        if "/articles/" in parts.path:
            token = parts.path.split("/articles/")[-1].split("?")[0].split("/")[0]
            if token.startswith("CBMi") or token.startswith("CBM"):
                try:
                    padded = token + "=" * (-len(token) % 4)
                    decoded = base64.urlsafe_b64decode(padded)
                    matches = re.findall(
                        rb"https?://[a-zA-Z0-9_\-.~:/?#[\]@!$&\'()*+,;=%]+", decoded
                    )
                    if matches:
                        curr = matches[0].decode("utf-8", errors="ignore")
                        found = True
                except Exception:
                    pass
        if not found:
            break

    return curr


def resolve_original_url(url: str, timeout: float = 8.0) -> str:
    unwrapped = unwrap_google_redirect(url)
    if (
        unwrapped != url
        and "news.google.com" not in unwrapped
        and not urlsplit(unwrapped).netloc.lower().endswith("google.com")
    ):
        return unwrapped
    consent_continue = _google_consent_continue(unwrapped)
    if consent_continue:
        if "news.google.com" in consent_continue:
            return resolve_original_url(consent_continue, timeout=timeout)
        return consent_continue
    if "news.google.com" not in unwrapped:
        return unwrapped
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, verify=True) as client:
            response = client.get(unwrapped, headers={"User-Agent": _user_agent()})
        if response.url and not is_intermediary_url(str(response.url)):
            return str(response.url)
    except httpx.ConnectError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            return unwrapped
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, verify=False) as client:
                response = client.get(unwrapped, headers={"User-Agent": _user_agent()})
            if response.url and not is_intermediary_url(str(response.url)):
                return str(response.url)
        except httpx.HTTPError:
            return unwrapped
    except httpx.HTTPError:
        return unwrapped
    return unwrapped


def _google_consent_continue(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if not host.endswith("google.com"):
        return ""
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    return params.get("continue", "")


def fetch_article_excerpt(url: str, timeout: float = 8.0) -> str:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": _user_agent()})
        if response.status_code >= 400:
            return ""
    except httpx.HTTPError:
        return ""
    soup = BeautifulSoup(response.text, "html.parser")
    for selector in [
        'meta[name="description"]',
        'meta[property="og:description"]',
        'meta[name="twitter:description"]',
    ]:
        meta = soup.select_one(selector)
        if meta and meta.get("content"):
            return clean_text(meta["content"], 420)
    paragraphs = [clean_text(p.get_text(" "), 240) for p in soup.find_all("p")]
    paragraphs = [paragraph for paragraph in paragraphs if len(paragraph) > 60]
    return clean_text(" ".join(paragraphs[:2]), 420)


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    unwrapped = unwrap_google_redirect(url)
    parts = urlsplit(unescape(unwrapped.strip()))
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower().rstrip(".")
    if ":" in netloc:
        host, port = netloc.split(":", 1)
        if (scheme == "https" and port == "443") or (scheme == "http" and port == "80"):
            netloc = host

    path = parts.path
    if path != "/":
        path = path.rstrip("/")
    if not path:
        path = "/"
    path = re.sub(r"/{2,}", "/", path)

    query_items = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    query_items.sort(key=lambda item: (item[0], item[1]))
    query_str = urlencode(query_items)
    return urlunsplit((scheme, netloc, path, query_str, ""))


def is_intermediary_url(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return host.endswith("google.com") or host.endswith("news.google.com")


def normalize_title(title: str) -> str:
    title = re.sub(r"^\[.*?\]|\【.*?\】|\(.*?\)", " ", title)
    title = re.sub(r"\s*[-|–—]\s*[^-|–—]+$", "", title)
    return re.sub(r"[^a-z0-9가-힣]+", "", title.lower())


def strip_html(value: str) -> str:
    if not value:
        return ""
    return clean_text(BeautifulSoup(value, "html.parser").get_text(" "), 420)


def clean_text(value: str, limit: int = 240) -> str:
    value = re.sub(r"\s+", " ", unescape(value or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def extract_source_and_publisher(raw: object, feed: SourceFeed) -> tuple[str, str, int]:
    is_aggregator = (
        feed.source_type == "aggregator"
        or "google.com" in feed.url
        or "Google News" in feed.name
    )
    discovered_via = "Google News" if is_aggregator else feed.name
    publisher = ""

    source_attr = getattr(raw, "source", None)
    if isinstance(source_attr, dict) and source_attr.get("title"):
        cand = str(source_attr["title"]).strip()
        if cand and cand.lower() not in {"google news", "google"}:
            publisher = cand
    elif isinstance(source_attr, str) and source_attr.strip():
        cand = source_attr.strip()
        if cand.lower() not in {"google news", "google"}:
            publisher = cand
    elif hasattr(raw, "get"):
        raw_src = raw.get("source", {})  # type: ignore[attr-defined]
        if isinstance(raw_src, dict) and raw_src.get("title"):
            cand = str(raw_src["title"]).strip()
            if cand and cand.lower() not in {"google news", "google"}:
                publisher = cand
        elif isinstance(raw_src, str) and raw_src.strip():
            cand = raw_src.strip()
            if cand.lower() not in {"google news", "google"}:
                publisher = cand

    if not publisher and is_aggregator:
        raw_title = getattr(raw, "title", "") or (
            raw.get("title", "") if hasattr(raw, "get") else ""
        )
        m = re.search(r"\s+[-|–—]\s+([^-|–—]+)$", str(raw_title))
        if m:
            cand = m.group(1).strip()
            if cand and cand.lower() not in {"google news", "google"}:
                publisher = cand

    if not publisher and is_aggregator:
        link = getattr(raw, "link", None) or (
            raw.get("link", "") if hasattr(raw, "get") else ""
        )
        if link:
            unwrapped = unwrap_google_redirect(str(link))
            domain = urlsplit(unwrapped).netloc.lower()
            if domain and not ("google." in domain or domain.endswith("google.com")):
                if domain.endswith("reuters.com"):
                    publisher = "Reuters"
                elif domain.endswith("bloomberg.com"):
                    publisher = "Bloomberg"
                elif domain.endswith("autonews.com"):
                    publisher = "Automotive News"
                elif domain.endswith("electrek.co"):
                    publisher = "Electrek"
                elif domain.endswith("insideevs.com"):
                    publisher = "InsideEVs"
                elif domain.endswith("theverge.com"):
                    publisher = "The Verge"
                elif domain.endswith("techcrunch.com"):
                    publisher = "TechCrunch"
                elif domain.endswith("motorgraph.com"):
                    publisher = "모터그래프"
                elif domain.endswith("autodaily.co.kr"):
                    publisher = "오토데일리"
                elif domain.endswith("autoherald.co.kr"):
                    publisher = "오토헤럴드"
                elif domain.endswith("etnews.com"):
                    publisher = "전자신문"
                elif domain.endswith("yna.co.kr"):
                    publisher = "연합뉴스"

    if not publisher:
        if is_aggregator:
            publisher = "Unknown"
        else:
            publisher = feed.name

    if publisher and publisher != feed.name and publisher != "Unknown":
        authority = source_authority(publisher)
    elif feed.authority_score is not None:
        authority = feed.authority_score
    else:
        authority = source_authority(publisher or feed.name)

    return publisher, discovered_via, authority


def _entry_source(raw: object, feed: SourceFeed) -> str:
    publisher, _, _ = extract_source_and_publisher(raw, feed)
    return publisher


def _entry_date(raw: object) -> datetime | None:
    if hasattr(raw, "get"):
        published = raw.get("published") or raw.get("updated")  # type: ignore[attr-defined]
        if published:
            try:
                parsed = parsedate_to_datetime(published)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed
            except (TypeError, ValueError):
                return None
    return None


def _user_agent() -> str:
    return REQUEST_HEADERS["User-Agent"]


def _feed_client(settings: Settings, verify: bool) -> httpx.Client:
    return httpx.Client(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
        headers=REQUEST_HEADERS,
        verify=verify,
    )


def _get_with_tls_fallback(
    url: str,
    settings: Settings,
    client: httpx.Client | None = None,
    insecure_client: httpx.Client | None = None,
) -> tuple[httpx.Response, bool]:
    active_client = client
    close_active_client = False
    if active_client is None:
        active_client = _feed_client(settings, verify=settings.verify_tls)
        close_active_client = True
    try:
        response = active_client.get(url)
        return response, False
    except httpx.ConnectError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        fallback_client = insecure_client
        close_fallback_client = False
        if fallback_client is None:
            fallback_client = _feed_client(settings, verify=False)
            close_fallback_client = True
        try:
            response = fallback_client.get(url)
        finally:
            if close_fallback_client:
                fallback_client.close()
        return response, True
    finally:
        if close_active_client:
            active_client.close()
