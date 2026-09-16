from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

import httpx

from .models import Article
from .prompts import SUMMARIZATION_SYSTEM_PROMPT, build_user_prompt
from .scoring import compute_multi_dimensional_scores
from .taxonomy import CATEGORY_LABELS_EN, classify_taxonomy

logger = logging.getLogger(__name__)


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


@dataclass(slots=True)
class SummaryResult:
    summary_ko: str
    summary_en: str
    why_it_matters_ko: str
    key_points: list[str] = field(default_factory=list)
    summary_model: str = "template"
    summary_version: str = "v1"
    summary_created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseSummarizer(ABC):
    @abstractmethod
    def summarize(
        self, article: Article, content: str = "", is_short_excerpt: bool = False
    ) -> SummaryResult:
        """Produce factual summary result for article."""
        pass


class TemplateSummarizer(BaseSummarizer):
    def summarize(
        self, article: Article, content: str = "", is_short_excerpt: bool = False
    ) -> SummaryResult:
        summary_ko = summarize_article(article)
        en_label = CATEGORY_LABELS_EN.get(article.category, "Automotive Industry")
        en_signal = _business_signal_en(article)
        if article.excerpt:
            summary_en = article.excerpt.strip()
        else:
            summary_en = f"{article.title}. Key signal highlights {en_signal} in the {en_label} domain."

        why_it_matters_ko = _impact_sentence(article.category)

        entities = article.entities or [
            tag for tag in article.tags if tag not in {"SDV", "ADAS", "OTA", "EV"}
        ]
        topics = article.topics or [
            tag for tag in article.tags if tag in {"SDV", "ADAS", "OTA", "EV"}
        ]

        key_points: list[str] = []
        if entities:
            key_points.append(f"주요 기업 및 기관: {', '.join(entities[:4])}")
        elif article.source:
            key_points.append(f"출처: {article.source}")
        if topics:
            key_points.append(f"핵심 기술·주제: {', '.join(topics[:4])}")
        sig = _business_signal(article)
        key_points.append(f"산업 신호: {sig}")

        return SummaryResult(
            summary_ko=summary_ko,
            summary_en=summary_en,
            why_it_matters_ko=why_it_matters_ko,
            key_points=key_points,
            summary_model="template",
            summary_version="v1",
        )


class OllamaSummarizer(BaseSummarizer):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def summarize(
        self, article: Article, content: str = "", is_short_excerpt: bool = False
    ) -> SummaryResult:
        text_body = content or article.content or article.excerpt
        user_prompt = build_user_prompt(
            title=article.title,
            source=article.publisher or article.source,
            content=text_body,
            excerpt=article.excerpt,
            is_short_excerpt=is_short_excerpt,
        )

        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": SUMMARIZATION_SYSTEM_PROMPT,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
            },
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw_response = data.get("response", "")
        parsed = json.loads(raw_response)

        summary_ko = str(parsed.get("summary_ko", "")).strip()
        summary_en = str(parsed.get("summary_en", "")).strip()
        why_it_matters_ko = str(parsed.get("why_it_matters_ko", "")).strip()
        raw_points = parsed.get("key_points", [])
        key_points = [str(pt).strip() for pt in raw_points if str(pt).strip()]

        if not summary_ko or not summary_en:
            raise ValueError("Ollama response missing required summary fields")

        return SummaryResult(
            summary_ko=summary_ko,
            summary_en=summary_en,
            why_it_matters_ko=why_it_matters_ko,
            key_points=key_points,
            summary_model=f"ollama:{self.model}",
            summary_version="v1",
        )


class FallbackSummarizer(BaseSummarizer):
    def __init__(self, primary: BaseSummarizer, fallback: BaseSummarizer):
        self.primary = primary
        self.fallback = fallback

    def summarize(
        self, article: Article, content: str = "", is_short_excerpt: bool = False
    ) -> SummaryResult:
        try:
            return self.primary.summarize(
                article, content=content, is_short_excerpt=is_short_excerpt
            )
        except Exception as exc:
            logger.warning("Primary summarizer failed, falling back: %s", exc)
            return self.fallback.summarize(
                article, content=content, is_short_excerpt=is_short_excerpt
            )


def get_summarizer(settings: object = None) -> BaseSummarizer:
    if settings is None:
        from .config import load_settings
        settings = load_settings()

    template = TemplateSummarizer()
    if getattr(settings, "enable_ai_summary", False):
        ollama = OllamaSummarizer(
            base_url=getattr(settings, "ollama_base_url", "http://localhost:11434"),
            model=getattr(settings, "ollama_model", "llama3.2"),
            timeout=getattr(settings, "ollama_timeout", 30.0),
        )
        return FallbackSummarizer(primary=ollama, fallback=template)

    return template


def classify_article(
    article: Article,
    summarizer: BaseSummarizer | None = None,
    content: str = "",
    is_short_excerpt: bool = False,
) -> Article:
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

    tax_article = replace(
        article,
        category=category,
        primary_category=primary_category,
        secondary_categories=secondary_categories,
        tags=tags,
        topics=topics,
        entities=entities,
        content=content or article.content,
    )
    multi_scores = compute_multi_dimensional_scores(tax_article)
    score = multi_scores.priority_score

    classified_article = replace(
        tax_article,
        score=score,
        priority_score=score,
        source_score=multi_scores.source_score,
        relevance_score=multi_scores.relevance_score,
        impact_score=multi_scores.impact_score,
        novelty_score=multi_scores.novelty_score,
        recency_score=multi_scores.recency_score,
    )

    summarizer_inst = summarizer or TemplateSummarizer()
    summary_res = summarizer_inst.summarize(
        classified_article,
        content=content or article.content,
        is_short_excerpt=is_short_excerpt,
    )

    summary_ko = article.summary_ko or summary_res.summary_ko
    summary_en = article.summary_en or summary_res.summary_en
    why_it_matters_ko = article.why_it_matters_ko or summary_res.why_it_matters_ko
    key_points = article.key_points if article.key_points else summary_res.key_points
    summary_model = article.summary_model or summary_res.summary_model
    summary_version = article.summary_version or summary_res.summary_version
    summary_created_at = article.summary_created_at or summary_res.summary_created_at

    return replace(
        classified_article,
        summary_ko=summary_ko,
        summary_en=summary_en,
        why_it_matters_ko=why_it_matters_ko,
        key_points=key_points,
        summary_model=summary_model,
        summary_version=summary_version,
        summary_created_at=summary_created_at,
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


def _score_article(
    article: Article,
    category: str = "",
    tags: list[str] | None = None,
    lowered: str = "",
) -> float:
    candidate = replace(
        article,
        category=category or article.category,
        tags=tags if tags is not None else article.tags,
    )
    return compute_multi_dimensional_scores(candidate).priority_score


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


def _business_signal_en(article: Article) -> str:
    text = f"{article.title} {article.excerpt}".lower()
    if any(word in text for word in ["investment", "invest", "funding", "billion"]):
        return "investment and capital expansion"
    if any(word in text for word in ["partnership", "collaboration", "joint", "alliance"]):
        return "strategic partnership and ecosystem realignment"
    if any(word in text for word in ["recall", "probe", "investigation", "regulator"]):
        return "quality and regulatory risk"
    if any(word in text for word in ["software", "sdv", "ota", "zonal"]):
        return "software-defined vehicle competitiveness"
    if any(word in text for word in ["battery", "ev", "electric"]):
        return "electrification supply chain shift"
    return "product and strategy evolution"
