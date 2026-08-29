from __future__ import annotations

import re
from dataclasses import replace

from .models import Article


OEM_NAMES = [
    "Toyota",
    "Volkswagen",
    "Hyundai",
    "Kia",
    "GM",
    "General Motors",
    "Ford",
    "Stellantis",
    "BMW",
    "Mercedes",
    "Mercedes-Benz",
    "Tesla",
    "BYD",
    "Honda",
    "Nissan",
    "Renault",
    "Rivian",
    "Lucid",
    "Mazda",
    "Subaru",
]

TIER1_NAMES = [
    "Bosch",
    "Continental",
    "Denso",
    "Magna",
    "ZF",
    "Aptiv",
    "Valeo",
    "Forvia",
    "Hyundai Mobis",
    "CATL",
    "LG Energy Solution",
    "Panasonic",
    "Mobileye",
    "Nvidia",
    "Qualcomm",
    "NXP",
    "Renesas",
    "Infineon",
]

INSTITUTION_NAMES = [
    "SAE",
    "S&P Global Mobility",
    "McKinsey",
    "Gartner",
    "WardsAuto",
    "Automotive News",
    "J.D. Power",
    "Cox Automotive",
    "Reuters",
    "Bloomberg",
]

CONFERENCE_NAMES = [
    "IAA Mobility",
    "CES",
    "SAE WCX",
    "Auto Shanghai",
    "Japan Mobility Show",
    "Automotive World Tokyo",
    "Automotive World Nagoya",
    "TU-Automotive",
    "AutoTech",
]

SDV_TERMS = [
    "software-defined",
    "software defined",
    "sdv",
    "zonal",
    "ota",
    "over-the-air",
    "autosar",
    "vehicle software",
    "adas",
    "autonomous",
    "cockpit",
    "digital chassis",
]

CATEGORY_LABELS = {
    "big": "대형 산업 이슈",
    "oem": "OEM",
    "tier1": "Tier 1",
    "sdv": "SDV",
    "institution": "기관/매거진",
    "conference": "컨퍼런스",
}


def classify_article(article: Article) -> Article:
    text = f"{article.title} {article.excerpt} {article.source}"
    lowered = text.lower()
    tags = _extract_tags(text)
    fallback_category = article.category or "big"
    category = "big"

    if any(_contains_name(text, name) for name in CONFERENCE_NAMES) or re.search(
        r"\b(conference|expo|summit|symposium|show|congress|event)\b", lowered
    ):
        category = "conference"
    elif any(term in lowered for term in SDV_TERMS):
        category = "sdv"
    elif any(_contains_name(text, name) for name in TIER1_NAMES):
        category = "tier1"
    elif any(_contains_name(text, name) for name in OEM_NAMES):
        category = "oem"
    elif any(_contains_name(text, name) for name in INSTITUTION_NAMES):
        category = "institution"
    elif fallback_category != "conference":
        category = fallback_category

    score = _score_article(article, category, tags, lowered)
    summary = article.summary_ko or summarize_article(
        replace(article, category=category, tags=tags, score=score)
    )
    return replace(article, category=category, tags=tags, score=score, summary_ko=summary)


def summarize_article(article: Article) -> str:
    label = CATEGORY_LABELS.get(article.category, "자동차 산업")
    names = [tag for tag in article.tags if tag not in {"SDV", "ADAS", "OTA", "EV"}]
    subject = ", ".join(names[:3]) if names else article.source
    signal = _business_signal(article)
    impact = _impact_sentence(article.category)
    return f"{subject} 관련 {label} 뉴스입니다. 핵심 신호는 {signal}이며, {impact}."


def _extract_tags(text: str) -> list[str]:
    found: list[str] = []
    for name in [*OEM_NAMES, *TIER1_NAMES, *INSTITUTION_NAMES, *CONFERENCE_NAMES]:
        if _contains_name(text, name) and name not in found:
            found.append(name)
    lowered = text.lower()
    if any(term in lowered for term in ["software-defined", "software defined", "sdv", "zonal"]):
        found.append("SDV")
    if "adas" in lowered:
        found.append("ADAS")
    if "ota" in lowered or "over-the-air" in lowered:
        found.append("OTA")
    if re.search(r"\bev\b|electric vehicle|battery", lowered):
        found.append("EV")
    return found[:8]


def _score_article(article: Article, category: str, tags: list[str], lowered: str) -> float:
    score = 35.0
    score += {
        "big": 10,
        "oem": 15,
        "tier1": 15,
        "sdv": 25,
        "institution": 12,
        "conference": 8,
    }.get(category, 0)
    score += min(len(tags), 5) * 4
    if any(word in lowered for word in ["billion", "investment", "partnership", "launch", "recall"]):
        score += 8
    if any(word in lowered for word in ["reuters", "automotive news", "bloomberg", "wardsauto"]):
        score += 6
    if article.published_at is not None:
        score += 5
    return round(score, 2)


def _business_signal(article: Article) -> str:
    text = f"{article.title} {article.excerpt}".lower()
    if any(word in text for word in ["investment", "invest", "funding", "billion"]):
        return "투자와 CAPEX 확대"
    if any(word in text for word in ["partnership", "collaboration", "joint", "alliance"]):
        return "전략적 제휴와 생태계 재편"
    if any(word in text for word in ["recall", "probe", "investigation", "regulator"]):
        return "품질·규제 리스크"
    if any(word in text for word in ["software", "sdv", "ota", "zonal"]):
        return "차량 소프트웨어 경쟁력 강화"
    if any(word in text for word in ["battery", "ev", "electric"]):
        return "전동화 공급망 변화"
    return "제품·전략 변화"


def _impact_sentence(category: str) -> str:
    if category == "sdv":
        return "SDV 전환 속도와 OEM-부품사 역할 분담을 볼 필요가 있습니다"
    if category == "tier1":
        return "부품사 수주·기술 포지션과 공급망 영향을 추적할 만합니다"
    if category == "oem":
        return "완성차 업체의 플랫폼, 지역, 투자 우선순위 변화를 보여줍니다"
    if category == "conference":
        return "행사 아젠다와 발표 기업을 통해 다음 기술 화두를 읽을 수 있습니다"
    if category == "institution":
        return "시장 전망과 업계 담론을 확인하는 참고 자료로 쓸 수 있습니다"
    return "산업 전반에 파급될 수 있는 흐름인지 확인할 만합니다"


def _clean_text(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _contains_name(text: str, name: str) -> bool:
    if len(name) <= 3 or name.isupper():
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None
    return name.lower() in text.lower()
