from __future__ import annotations

import re
from dataclasses import replace

from .models import Article
from .taxonomy import classify_taxonomy


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
    "ev_battery": "전기차/배터리",
    "adas_autonomous": "ADAS/자율주행",
    "regulation": "규제/정책",
    "market": "시장/판매",
    "manufacturing": "생산/제조",
    "supply_chain": "공급망/반도체",
    "cybersecurity": "차량 사이버보안",
    "software": "차량 소프트웨어",
    "institution": "기관/매거진",
    "conference": "컨퍼런스",
    "reference": "참고자료",
}


def classify_article(article: Article) -> Article:
    tax = classify_taxonomy(
        title=article.title,
        excerpt=article.excerpt,
        source=article.source,
        source_type=article.source_type,
        bucket=article.category,
    )
    category = tax.primary_category
    primary_category = tax.primary_category
    secondary_categories = tax.secondary_categories
    topics = tax.topics
    entities = tax.entities

    # Unified tags preserving entities and topics
    tags = entities + [t for t in topics if t not in entities]

    text = f"{article.title} {article.excerpt} {article.source}".lower()
    score = _score_article(article, category, tags, text)
    summary = article.summary_ko or summarize_article(
        replace(article, category=category, primary_category=primary_category, tags=tags, score=score)
    )

    return replace(
        article,
        category=category,
        primary_category=primary_category,
        secondary_categories=secondary_categories,
        tags=tags,
        topics=topics,
        entities=entities,
        score=score,
        priority_score=score,
        source_score=float(article.source_authority),
        summary_ko=summary,
    )


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
    if category == "ev_battery":
        return "전동화 전환 속도와 배터리 공급망 협력 구도를 점검할 필요가 있습니다"
    if category == "adas_autonomous":
        return "자율주행 상용화 일정과 규제 대응 현황을 주목해야 합니다"
    if category == "regulation":
        return "글로벌 규제 및 관세 장벽이 공급망과 수출 전략에 미칠 파장을 주시해야 합니다"
    if category == "cybersecurity":
        return "차량 보안 규정 준수와 침해 대응 역량 확보가 핵심 과제입니다"
    if category == "supply_chain":
        return "반도체 및 핵심 부품 수급 안정성과 리스크 관리가 요구됩니다"
    if category == "manufacturing":
        return "생산 효율화와 공장 가동률 변화를 살펴볼 만합니다"
    if category == "market":
        return "지역별 판매 추이와 수익성 변화를 파악할 필요가 있습니다"
    if category == "software":
        return "소프트웨어 개발 스택과 오픈소스 생태계 흐름을 파악할 만합니다"
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
