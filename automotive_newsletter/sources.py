from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus


SECTION_LABELS = {
    "big": "오늘의 큰 뉴스",
    "oem": "OEM 주요 동향",
    "tier1": "Tier 1 / 공급망",
    "sdv": "SDV / 소프트웨어",
    "ev_battery": "전기차 / 배터리",
    "adas_autonomous": "ADAS / 자율주행",
    "regulation": "정책 / 규제 / 통상",
    "market": "시장 / 판매 / 금융",
    "manufacturing": "생산 / 제조",
    "supply_chain": "공급망 / 반도체",
    "cybersecurity": "차량 사이버보안",
    "software": "임베디드 / 차량 SW",
    "conference": "컨퍼런스 / 이벤트",
    "institution": "기관 / 인물 / 매거진",
    "reference": "참고자료 / 기타",
}

SECTION_ORDER = [
    "big",
    "oem",
    "tier1",
    "sdv",
    "ev_battery",
    "adas_autonomous",
    "regulation",
    "market",
    "manufacturing",
    "supply_chain",
    "cybersecurity",
    "software",
    "conference",
    "institution",
    "reference",
]


AUTHORITY_HIERARCHY: dict[str, int] = {
    "regulator": 100,
    "news_agency": 95,
    "industry_media": 90,
    "specialist_media": 85,
    "research": 80,
    "tech_media": 75,
    "official": 70,
    "event": 70,
    "open_source": 85,
    "institution": 80,
    "media": 85,
    "press_release": 60,
    "aggregator": 40,
}

KNOWN_PUBLISHER_AUTHORITY: dict[str, int] = {
    "reuters": 95,
    "bloomberg": 95,
    "associated press": 95,
    "ap": 95,
    "automotive news": 90,
    "automotive news europe": 90,
    "automotive world": 90,
    "wardsauto": 90,
    "just auto": 90,
    "justauto": 90,
    "automotive dive": 90,
    "the drive": 85,
    "electrek": 85,
    "insideevs": 85,
    "motor1": 85,
    "car and driver": 85,
    "automotive testing technology international": 85,
    "techcrunch": 75,
    "the verge": 75,
    "nhtsa": 100,
    "acea": 100,
    "unece": 100,
    "euro ncap": 100,
    "s&p global mobility": 80,
    "mckinsey": 80,
    "gartner": 80,
    "sae international": 80,
    "sae": 80,
    "pr newswire": 60,
    "business wire": 60,
    "globe newswire": 60,
}


@dataclass(frozen=True, slots=True)
class SourceFeed:
    name: str
    bucket: str
    url: str
    id: str = ""
    source_type: str = "media"
    authority_score: int = 70
    region: str = "global"
    language: str = "en"
    paywalled: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            slug = re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")
            object.__setattr__(self, "id", slug)


def google_news_rss(query: str) -> str:
    encoded = quote_plus(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"


def google_news_kr_rss(query: str) -> str:
    encoded = quote_plus(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"


DEFAULT_FEEDS = [
    SourceFeed(
        name="Automotive News",
        bucket="big",
        url="https://www.autonews.com/arc/outboundfeeds/rss/?outputType=xml",
        id="automotive_news",
        source_type="media",
        authority_score=90,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Automotive News Europe",
        bucket="oem",
        url="https://europe.autonews.com/arc/outboundfeeds/rss/?outputType=xml",
        id="automotive_news_europe",
        source_type="media",
        authority_score=90,
        region="europe",
        language="en",
    ),
    SourceFeed(
        name="Automotive World",
        bucket="big",
        url="https://www.automotiveworld.com/feed/",
        id="automotive_world",
        source_type="media",
        authority_score=90,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="WardsAuto",
        bucket="big",
        url="https://www.wardsauto.com/feeds/news/",
        id="wardsauto",
        source_type="media",
        authority_score=90,
        region="us",
        language="en",
    ),
    SourceFeed(
        name="PR Newswire Automotive",
        bucket="big",
        url="https://www.prnewswire.com/rss/automotive-transportation/automotive-list.rss",
        id="pr_newswire_automotive",
        source_type="press_release",
        authority_score=60,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Global automotive big news",
        bucket="big",
        url=google_news_rss(
            'automotive industry OR automaker OR "electric vehicle" OR SDV Reuters OR Bloomberg'
        ),
        id="global_automotive_big_news",
        source_type="aggregator",
        authority_score=40,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Korea Auto News",
        bucket="big",
        url=google_news_kr_rss(
            "현대차 OR 기아 OR 한국GM OR 르노코리아 OR 자동차 배터리 OR 자율주행 OR SDV"
        ),
        id="korea_auto_news",
        source_type="aggregator",
        authority_score=40,
        region="kr",
        language="ko",
    ),
    SourceFeed(
        name="InsideEVs",
        bucket="oem",
        url="https://insideevs.com/rss/news/all/",
        id="insideevs",
        source_type="media",
        authority_score=85,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Car and Driver News",
        bucket="oem",
        url="https://www.caranddriver.com/rss/news.xml",
        id="car_and_driver",
        source_type="media",
        authority_score=85,
        region="us",
        language="en",
    ),
    SourceFeed(
        name="Motor1 News",
        bucket="oem",
        url="https://www.motor1.com/rss/news/all/",
        id="motor1",
        source_type="media",
        authority_score=85,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="The Drive",
        bucket="oem",
        url="https://www.thedrive.com/feed",
        id="the_drive",
        source_type="media",
        authority_score=85,
        region="us",
        language="en",
    ),
    SourceFeed(
        name="OEM strategy",
        bucket="oem",
        url=google_news_rss(
            "Toyota OR Volkswagen OR Hyundai OR Kia OR GM OR Ford OR Stellantis OR BMW OR Mercedes OR Tesla OR BYD strategy OR EV"
        ),
        id="oem_strategy",
        source_type="aggregator",
        authority_score=40,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="JustAuto",
        bucket="tier1",
        url="https://www.just-auto.com/feed/",
        id="just_auto",
        source_type="media",
        authority_score=90,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Automotive Dive",
        bucket="tier1",
        url="https://www.automotivedive.com/feeds/news/",
        id="automotive_dive",
        source_type="media",
        authority_score=90,
        region="us",
        language="en",
    ),
    SourceFeed(
        name="Tier 1 suppliers",
        bucket="tier1",
        url=google_news_rss(
            'Bosch OR Continental OR Denso OR Magna OR ZF OR "Hyundai Mobis" OR Aptiv automotive'
        ),
        id="tier1_suppliers",
        source_type="aggregator",
        authority_score=40,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Electrek",
        bucket="sdv",
        url="https://electrek.co/feed/",
        id="electrek",
        source_type="media",
        authority_score=85,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="TechCrunch Transportation",
        bucket="sdv",
        url="https://techcrunch.com/category/transportation/feed/",
        id="techcrunch_transportation",
        source_type="media",
        authority_score=75,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="The Verge Transportation",
        bucket="sdv",
        url="https://www.theverge.com/rss/transportation/index.xml",
        id="the_verge_transportation",
        source_type="media",
        authority_score=75,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Automotive Testing Technology International",
        bucket="sdv",
        url="https://www.automotivetestingtechnologyinternational.com/feed",
        id="atti",
        source_type="media",
        authority_score=85,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="SDV software",
        bucket="sdv",
        url=google_news_rss(
            '"software-defined vehicle" OR SDV OR "autonomous driving" OR "zonal architecture" OR AUTOSAR'
        ),
        id="sdv_software",
        source_type="aggregator",
        authority_score=40,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Regulators and safety",
        bucket="institution",
        url=google_news_rss(
            'NHTSA OR "Euro NCAP" OR "European Commission" OR ACEA vehicle OR automotive safety OR emissions OR tariff'
        ),
        id="regulators_and_safety",
        source_type="aggregator",
        authority_score=40,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Institutions and magazines",
        bucket="institution",
        url=google_news_rss(
            '"S&P Global Mobility" OR McKinsey OR Gartner OR "SAE International" automotive'
        ),
        id="institutions_and_magazines",
        source_type="aggregator",
        authority_score=40,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Automotive conferences",
        bucket="conference",
        url=google_news_rss(
            '"IAA Mobility" OR "SAE WCX" OR "Auto Shanghai" OR "Japan Mobility Show" OR "Automotive World" OR "CES automotive" when:30d'
        ),
        id="automotive_conferences",
        source_type="event",
        authority_score=70,
        region="global",
        language="en",
    ),
]

EXTRA_SOURCES: list[SourceFeed] = [
    SourceFeed(
        name="Reuters Automotive",
        bucket="big",
        url=google_news_rss("Reuters automotive OR vehicle"),
        id="reuters",
        source_type="media",
        authority_score=95,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="ACEA (European Automobile Manufacturers’ Association)",
        bucket="institution",
        url=google_news_rss("site:acea.auto automotive"),
        id="acea",
        source_type="regulator",
        authority_score=100,
        region="europe",
        language="en",
    ),
    SourceFeed(
        name="UNECE WP.29 Vehicle Regulations",
        bucket="institution",
        url=google_news_rss("UNECE vehicle regulations OR WP.29"),
        id="unece",
        source_type="regulator",
        authority_score=100,
        region="global",
        language="en",
    ),
    SourceFeed(
        name="Eclipse SDV",
        bucket="sdv",
        url=google_news_rss('"Eclipse SDV" OR "Eclipse Foundation" automotive'),
        id="eclipse_sdv",
        source_type="open_source",
        authority_score=85,
        region="global",
        language="en",
    ),
]

ALL_SOURCES: list[SourceFeed] = [*DEFAULT_FEEDS, *EXTRA_SOURCES]


def _normalize_source_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def get_source(source_id: str) -> SourceFeed | None:
    target = _normalize_source_key(source_id)
    for feed in ALL_SOURCES:
        if (
            feed.id == source_id
            or _normalize_source_key(feed.id) == target
            or _normalize_source_key(feed.name) == target
        ):
            return feed
    return None


def get_enabled_sources() -> list[SourceFeed]:
    return [feed for feed in DEFAULT_FEEDS if feed.enabled]


def source_metadata(source_id: str) -> dict[str, object] | None:
    source = get_source(source_id)
    if source is None:
        return None
    return {
        "id": source.id,
        "name": source.name,
        "bucket": source.bucket,
        "url": source.url,
        "source_type": source.source_type,
        "authority_score": source.authority_score,
        "region": source.region,
        "language": source.language,
        "paywalled": source.paywalled,
        "enabled": source.enabled,
    }


def source_authority(source_id: str) -> int:
    source = get_source(source_id)
    if source is not None:
        return source.authority_score

    cleaned = re.sub(r"[^a-z0-9]+", " ", source_id.lower()).strip()
    if cleaned in KNOWN_PUBLISHER_AUTHORITY:
        return KNOWN_PUBLISHER_AUTHORITY[cleaned]

    for key, val in KNOWN_PUBLISHER_AUTHORITY.items():
        if key in cleaned or cleaned in key:
            return val

    slug = re.sub(r"[^a-z0-9]+", "_", source_id.lower()).strip("_")
    if slug in AUTHORITY_HIERARCHY:
        return AUTHORITY_HIERARCHY[slug]

    return 70


def classify_source_type(name: str, feed: SourceFeed | None = None) -> str:
    cleaned = re.sub(r"[^a-z0-9가-힣]+", " ", name.lower()).strip()

    if any(
        term in cleaned
        for term in [
            "nhtsa",
            "dot gov",
            "epa gov",
            "acea",
            "unece",
            "euro ncap",
            "iihs",
            "regulator",
            "safety commission",
        ]
    ):
        return "regulator"
    if any(
        term in cleaned
        for term in [
            "institution",
            "association",
            "federation",
            "institute",
            "ieee",
            "iso",
            "kama",
            "oecd",
            "협회",
            "학회",
            "연구원",
        ]
    ):
        return "institution"
    if any(
        term in cleaned
        for term in [
            "mckinsey",
            "s p global",
            "gartner",
            "cox automotive",
            "j d power",
            "jd power",
            "sae",
            "research",
            "analyst",
        ]
    ):
        return "research"
    if any(
        term in cleaned
        for term in [
            "pr newswire",
            "business wire",
            "globe newswire",
            "newsfile",
            "press release",
        ]
    ):
        return "press_release"
    if any(
        term in cleaned
        for term in ["eclipse", "autoware", "linux foundation", "agl", "autosar", "open source"]
    ):
        return "open_source"
    if any(
        term in cleaned
        for term in [
            "toyota",
            "hyundai",
            "kia",
            "gm",
            "general motors",
            "ford",
            "stellantis",
            "bmw",
            "mercedes",
            "tesla",
            "volkswagen",
            "byd",
            "bosch",
            "continental",
            "denso",
            "magna",
            "zf",
            "valeo",
            "aptiv",
            "mobis",
            "catl",
            "공식 뉴스룸",
            "official newsroom",
        ]
    ):
        return "official"
    if any(term in cleaned for term in ["google news", "aggregator", "news aggregator"]):
        return "aggregator"

    if feed is not None and feed.source_type != "aggregator":
        return feed.source_type

    return "media"


SECTION_LABELS_EN = {
    "big": "Top News",
    "oem": "OEM Trends",
    "tier1": "Tier 1 & Suppliers",
    "sdv": "SDV & E/E Architecture",
    "ev_battery": "EV & Battery",
    "adas_autonomous": "ADAS & Autonomous",
    "regulation": "Regulation & Policy",
    "market": "Market & Sales",
    "manufacturing": "Manufacturing & Production",
    "supply_chain": "Supply Chain & Chips",
    "cybersecurity": "Cybersecurity",
    "software": "Vehicle Software",
    "conference": "Conferences & Events",
    "institution": "Institutions & Magazines",
    "reference": "References",
}
