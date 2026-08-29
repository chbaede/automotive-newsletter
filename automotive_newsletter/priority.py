from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Article, NewsletterIssue


@dataclass(frozen=True, slots=True)
class PrioritySignal:
    level: str
    label_ko: str
    score: int
    reason_ko: str


@dataclass(frozen=True, slots=True)
class PrioritizedArticle:
    article: Article
    priority: PrioritySignal


@dataclass(frozen=True, slots=True)
class PrioritySummary:
    counts: dict[str, int]
    top_items: list[PrioritizedArticle]


LEVELS = {
    "critical": ("최우선", 4),
    "high": ("높음", 3),
    "medium": ("보통", 2),
    "watch": ("관찰", 1),
}

ISSUE_KEYWORDS = {
    "recall": "품질/리콜",
    "investigation": "조사/규제",
    "probe": "조사/규제",
    "regulator": "규제",
    "tariff": "정책/관세",
    "strike": "생산차질",
    "halt": "생산차질",
    "bankruptcy": "재무 리스크",
    "investment": "투자",
    "billion": "대규모 자금",
    "partnership": "전략 제휴",
    "joint venture": "전략 제휴",
    "software-defined": "SDV",
    "software defined": "SDV",
    "zonal": "SDV",
    "ota": "OTA",
    "robotaxi": "자율주행",
    "autonomous": "자율주행",
}

AUTHORITY_SOURCES = [
    "reuters",
    "bloomberg",
    "automotive news",
    "wardsauto",
    "mckinsey",
    "s&p global",
    "sae",
    "j.d. power",
    "cox automotive",
]


def assess_priority(article: Article) -> PrioritySignal:
    raw_score = int(round(article.score))
    issue_reasons = _issue_reasons(article)
    authority = any(source in article.source.lower() for source in AUTHORITY_SOURCES)
    category_weight = 8 if article.category in {"big", "oem", "tier1", "sdv"} else 0
    tag_weight = min(len(article.tags), 4) * 2
    issue_weight = min(len(issue_reasons), 3) * 7
    authority_weight = 6 if authority else 0
    priority_score = min(100, raw_score + category_weight + tag_weight + issue_weight + authority_weight)

    if priority_score >= 86:
        level = "critical"
    elif priority_score >= 70:
        level = "high"
    elif priority_score >= 52:
        level = "medium"
    else:
        level = "watch"

    label = LEVELS[level][0]
    reason_parts = []
    if issue_reasons:
        reason_parts.append("이슈화 신호: " + ", ".join(issue_reasons[:3]))
    if authority:
        reason_parts.append("권위 출처")
    if article.category in {"big", "oem", "tier1", "sdv"}:
        reason_parts.append("산업 영향 섹션")
    if not reason_parts:
        reason_parts.append("낮은 점수 또는 참고성 항목")
    return PrioritySignal(
        level=level,
        label_ko=label,
        score=priority_score,
        reason_ko=" · ".join(reason_parts),
    )


def priority_summary(issue: NewsletterIssue) -> PrioritySummary:
    prioritized = [
        PrioritizedArticle(article=article, priority=assess_priority(article))
        for article in issue.articles
    ]
    counts = {level: 0 for level in LEVELS}
    for item in prioritized:
        counts[item.priority.level] += 1
    prioritized.sort(
        key=lambda item: (
            LEVELS[item.priority.level][1],
            item.priority.score,
            item.article.score,
        ),
        reverse=True,
    )
    return PrioritySummary(counts=counts, top_items=prioritized[:5])


def _issue_reasons(article: Article) -> list[str]:
    text = f"{article.title} {article.excerpt} {' '.join(article.tags)}".lower()
    reasons: list[str] = []
    for keyword, reason in ISSUE_KEYWORDS.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text):
            if reason not in reasons:
                reasons.append(reason)
    return reasons
