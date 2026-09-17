from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import Article

# Core high-relevance software and modern architecture topics
CORE_SOFTWARE_TOPICS = {
    "sdv",
    "e/e architecture",
    "zonal architecture",
    "vehicle computer",
    "hpc",
    "autosar",
    "adaptive autosar",
    "classic autosar",
    "soa",
    "middleware",
    "ota",
    "vehicle os",
    "android automotive",
    "qnx",
    "embedded linux",
    "yocto",
    "automotive cybersecurity",
    "cybersecurity",
    "functional safety",
    "adas",
    "autonomous driving",
    "vehicle software",
    "software",
    "cloud",
    "ci/cd",
    "devops",
    "ev platform",
    "electric vehicle",
    "battery",
    "ev",
}

# Major impact signal regex patterns
IMPACT_SIGNALS = {
    "investment": re.compile(r"\b(billion|million|investment|invest|funding|capex|ipo)\b", re.I),
    "platform_launch": re.compile(
        r"\b(platform launch|new platform|architecture launch|production start|start of production|sop|ev platform|updates?\s+(\w+\s+)?platform)\b",
        re.I,
    ),
    "partnership": re.compile(
        r"\b(partnership|strategic alliance|joint venture|collaborat\w*|alliance|supply deal)\b",
        re.I,
    ),
    "contract": re.compile(
        r"\b(major contract|design win|awarded|billion-dollar deal|multi-year agreement|commercial agreement)\b",
        re.I,
    ),
    "production_change": re.compile(
        r"\b(gigafactory|plant expansion|team expansion|expand\w*|halt production|production cut|factory closure|retool\w*)\b",
        re.I,
    ),
    "regulation": re.compile(
        r"\b(regulation|regulator|tariff|tariffs|euro 7|mandate|compliance|co2 standard|emission standard)\b",
        re.I,
    ),
    "recall": re.compile(
        r"\b(recall|defects?|flaws?)\b",
        re.I,
    ),
    "investigation": re.compile(
        r"\b(safety probe|investigation|probe|inquiry|probes?)\b",
        re.I,
    ),
    "security_cve": re.compile(
        r"\b(vulnerability|cve|exploit|breach|cyber attack)\b",
        re.I,
    ),
    "acquisition": re.compile(
        r"\b(acquisition|acquire[sd]?|merger|buyout|takeover)\b",
        re.I,
    ),
    "restructuring": re.compile(
        r"\b(restructuring|layoff[s]?|job cuts|plant closure|downsizing)\b",
        re.I,
    ),
    "tech_deployment": re.compile(
        r"\b(commercial deployment|fleet rollout|robotaxi launch|level 3 deployment|mass production)\b",
        re.I,
    ),
}

# Evergreen and promotional penalty patterns
EVERGREEN_PATTERNS = re.compile(
    r"\b(what is|how to|top 10|buyers? guide|overview of|guide to|explained|history of)\b",
    re.I,
)
PROMO_PATTERNS = re.compile(
    r"\b(proud to announce|honored to receive|award-winning|pioneering the future|presents at)\b",
    re.I,
)


@dataclass(frozen=True, slots=True)
class ScoreExplanation:
    reasons_ko: list[str] = field(default_factory=list)
    reasons_en: list[str] = field(default_factory=list)
    summary_ko: str = ""
    summary_en: str = ""


@dataclass(slots=True)
class ScoringResult:
    source_score: float
    relevance_score: float
    impact_score: float
    novelty_score: float
    recency_score: float
    priority_score: float
    explanation: ScoreExplanation


def compute_source_score(article: Article) -> float:
    """Evaluate source credibility and characteristics without presenting as truth score."""
    source_type = (article.source_type or "media").lower()
    source_name = (article.publisher or article.source or "").lower()

    # Authority based on source type and publisher reputation
    if source_name in {"공식 뉴스룸", "unknown"}:
        base = 50.0
    elif source_type in {"regulator", "institution"} or any(
        s in source_name for s in ["nhtsa", "epa", "unece", "iso", "sae"]
    ):
        base = 95.0
    elif any(s in source_name for s in ["reuters", "bloomberg", "associated press", "ap news"]):
        base = 93.0
    elif any(
        s in source_name
        for s in ["automotive news", "wardsauto", "green car congress", "electrek", "heise autos", "insideevs"]
    ):
        base = 88.0
    elif source_type in {"official", "press_release"} or "newsroom" in source_name:
        base = 85.0
    elif source_type == "research":
        base = 88.0
    elif source_type == "open_source" or any(s in source_name for s in ["eclipse", "linux foundation", "soafee"]):
        base = 85.0
    elif source_type == "aggregator" or "google" in source_name:
        base = 55.0
    else:
        base = 75.0

    if article.source_authority is not None and article.source_authority != 70:
        score = 0.5 * base + 0.5 * float(article.source_authority)
    else:
        score = base

    return round(max(10.0, min(100.0, score)), 1)


def compute_relevance_score(article: Article) -> float:
    """Evaluate automotive software, SDV, and modern architecture relevance."""
    category = (article.primary_category or article.category or "").lower()
    text = f"{article.title} {article.excerpt} {' '.join(article.topics)} {' '.join(article.tags)}".lower()

    if category in {"sdv", "software", "cybersecurity"}:
        base = 65.0
    elif category in {"adas_autonomous"}:
        base = 60.0
    elif category in {"oem", "tier1", "supply_chain", "ev_battery", "regulation"}:
        base = 35.0
    else:
        base = 25.0

    matched_software_topics = set()
    for topic in [*article.topics, *article.tags]:
        t_low = topic.lower()
        if t_low in CORE_SOFTWARE_TOPICS:
            matched_software_topics.add(t_low)

    for term in CORE_SOFTWARE_TOPICS:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text):
            matched_software_topics.add(term)

    topic_bonus = min(len(matched_software_topics) * 12.0, 45.0)
    score = base + topic_bonus

    return round(max(10.0, min(100.0, score)), 1)


def compute_impact_score(article: Article) -> float:
    """Evaluate signals of market, financial, technical, or regulatory disruption."""
    category = (article.primary_category or article.category or "").lower()
    text = f"{article.title} {article.excerpt}".lower()

    if category in {"big", "sdv"}:
        base = 42.0
    elif category in {"oem", "tier1", "regulation"}:
        base = 35.0
    else:
        base = 25.0

    signals_found = 0
    for pattern in IMPACT_SIGNALS.values():
        if pattern.search(text):
            signals_found += 1

    signal_bonus = min(signals_found * 18.0, 55.0)
    score = base + signal_bonus

    return round(max(10.0, min(100.0, score)), 1)


def compute_novelty_score(
    article: Article,
    past_articles: list[Article] | None = None,
) -> float:
    """Evaluate novelty, penalizing duplication, repeated PR, and evergreen content."""
    score = 90.0
    text = f"{article.title} {article.excerpt}".lower()

    # Penalize evergreen / guide articles
    if EVERGREEN_PATTERNS.search(article.title.lower()):
        score -= 35.0
    elif EVERGREEN_PATTERNS.search(text):
        score -= 20.0

    # Penalize corporate promotional puffery without concrete news
    if PROMO_PATTERNS.search(text) and not any(p.search(text) for p in IMPACT_SIGNALS.values()):
        score -= 20.0

    # Check for duplicate reporting among past articles
    if past_articles:
        title_tokens = _simple_tokens(article.title)
        if title_tokens:
            for past in past_articles:
                if past.url == article.url or past.canonical_url == article.canonical_url:
                    continue
                past_tokens = _simple_tokens(past.title)
                if not past_tokens:
                    continue
                common = title_tokens & past_tokens
                if len(common) >= 4 and len(common) / max(len(title_tokens), len(past_tokens)) >= 0.75:
                    score -= 30.0
                    break

    return round(max(10.0, min(100.0, score)), 1)


def compute_recency_score(
    article: Article,
    ref_time: datetime | None = None,
    half_life_hours: float = 36.0,
) -> float:
    """Evaluate freshness with exponential decay based on published_at."""
    if not article.published_at:
        return 50.0

    ref = ref_time or datetime.now(timezone.utc)
    if article.published_at.tzinfo is None:
        pub = article.published_at.replace(tzinfo=timezone.utc)
    else:
        pub = article.published_at

    diff_seconds = max(0.0, (ref - pub).total_seconds())
    diff_hours = diff_seconds / 3600.0

    # Half-life exponential decay: recency = 100 * (0.5 ** (diff_hours / half_life))
    decay = math.pow(0.5, diff_hours / max(1.0, half_life_hours))
    score = 100.0 * decay

    return round(max(5.0, min(100.0, score)), 1)


def compute_multi_dimensional_scores(
    article: Article,
    past_articles: list[Article] | None = None,
    ref_time: datetime | None = None,
    half_life_hours: float = 36.0,
) -> ScoringResult:
    """Compute independent multi-dimensional scores and explainable priority."""
    src = compute_source_score(article)
    rel = compute_relevance_score(article)
    imp = compute_impact_score(article)
    nov = compute_novelty_score(article, past_articles=past_articles)
    rec = compute_recency_score(article, ref_time=ref_time, half_life_hours=half_life_hours)

    # Base weighted combination for priority score
    base_priority = (
        0.30 * rel
        + 0.25 * imp
        + 0.20 * src
        + 0.15 * rec
        + 0.10 * nov
    )

    # Named synergy signals and penalties for automotive intelligence
    impact_authority_boost = 0.0
    software_impact_boost = 0.0
    low_signal_penalty = 0.0

    # 1. Authoritative Major Impact Signal (major recall, regulatory probe, restructuring by wire/official)
    if imp >= 65.0 and src >= 85.0:
        impact_authority_boost = 20.0

    # 2. Strategic Vehicle Software & SDV Deployment Signal
    if rel >= 80.0 and imp >= 45.0:
        software_impact_boost = 15.0

    # 3. Low Signal Reference / Generic Fallback Penalty
    if rel < 40.0 and imp < 40.0:
        low_signal_penalty = 10.0

    synergy_boost = max(impact_authority_boost, software_impact_boost)
    priority = base_priority + synergy_boost - low_signal_penalty
    priority = round(max(10.0, min(100.0, priority)), 1)

    explanation = build_score_explanation(
        source_score=src,
        relevance_score=rel,
        impact_score=imp,
        novelty_score=nov,
        recency_score=rec,
        priority_score=priority,
        impact_authority_boost=impact_authority_boost > 0,
        software_impact_boost=software_impact_boost > 0,
        low_signal_penalty=low_signal_penalty > 0,
    )

    return ScoringResult(
        source_score=src,
        relevance_score=rel,
        impact_score=imp,
        novelty_score=nov,
        recency_score=rec,
        priority_score=priority,
        explanation=explanation,
    )


def build_score_explanation(
    source_score: float,
    relevance_score: float,
    impact_score: float,
    novelty_score: float,
    recency_score: float,
    priority_score: float,
    impact_authority_boost: bool = False,
    software_impact_boost: bool = False,
    low_signal_penalty: bool = False,
) -> ScoreExplanation:
    """Produce human-readable explainability rationale without exposing numerical precision."""
    reasons_ko: list[str] = []
    reasons_en: list[str] = []

    has_impact_authority = impact_authority_boost or (impact_score >= 65.0 and source_score >= 85.0)
    has_software_impact = software_impact_boost or (relevance_score >= 80.0 and impact_score >= 45.0)
    has_low_signal = low_signal_penalty or (relevance_score < 40.0 and impact_score < 40.0)

    if has_impact_authority:
        reasons_ko.append("주요 출처의 대형 산업 이슈화 신호")
        reasons_en.append("High-impact development from authoritative source")

    if has_software_impact:
        reasons_ko.append("SDV·SW 분야 핵심 협력·배치 이슈")
        reasons_en.append("Strategic SDV & software initiative")

    if relevance_score >= 70.0:
        reasons_ko.append("차량 소프트웨어·SDV 관련성 높음")
        reasons_en.append("High software & SDV relevance")
    elif relevance_score >= 50.0:
        reasons_ko.append("전동화·차량 전장 관련 이슈")
        reasons_en.append("Automotive systems relevance")

    if impact_score >= 65.0:
        reasons_ko.append("투자·제휴·규제 등 대형 이슈화 신호")
        reasons_en.append("High industry impact (investment/partnership/regulation)")
    elif impact_score >= 45.0:
        reasons_ko.append("사업·제휴 등 주요 이슈화 신호")
        reasons_en.append("Moderate business signal (partnership/product)")

    if source_score >= 88.0:
        reasons_ko.append("주요 통신사·공신력 출처")
        reasons_en.append("High authority publication")
    elif source_score >= 80.0:
        reasons_ko.append("공식 발표·전문 매체")
        reasons_en.append("Official/specialized source")

    if recency_score >= 70.0:
        reasons_ko.append("최근 24시간 이내 보도")
        reasons_en.append("Recent publication")

    if novelty_score >= 85.0:
        reasons_ko.append("독창적 신규 보도")
        reasons_en.append("Fresh reporting")
    elif novelty_score <= 50.0:
        reasons_ko.append("중복 또는 일반 해설 항목")
        reasons_en.append("Previously covered / evergreen content")

    if has_low_signal:
        reasons_ko.append("관찰 항목 (낮은 관련도·영향도)")
        reasons_en.append("Watch item (low relevance & impact)")

    if not reasons_ko:
        reasons_ko.append("일반 산업 참고 항목")
        reasons_en.append("General industry reference")

    summary_ko = " · ".join(reasons_ko[:3])
    summary_en = " · ".join(reasons_en[:3])

    return ScoreExplanation(
        reasons_ko=reasons_ko,
        reasons_en=reasons_en,
        summary_ko=summary_ko,
        summary_en=summary_en,
    )


def _simple_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9가-힣\s]", " ", text.lower())
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "about",
        "will", "are", "were", "was", "has", "have", "its", "new",
        "in", "on", "at", "by", "an", "a", "to", "of", "is", "it",
    }
    return {w for w in cleaned.split() if len(w) > 2 and w not in stop_words}
