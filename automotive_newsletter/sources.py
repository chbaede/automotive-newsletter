from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus


SECTION_LABELS = {
    "big": "오늘의 큰 뉴스",
    "oem": "OEM 주요 동향",
    "tier1": "Tier 1 / 공급망",
    "sdv": "SDV / 소프트웨어",
    "institution": "기관 / 인물 / 매거진",
    "conference": "컨퍼런스 / 이벤트",
}

SECTION_ORDER = ["big", "oem", "tier1", "sdv", "institution", "conference"]


@dataclass(frozen=True, slots=True)
class SourceFeed:
    name: str
    bucket: str
    url: str


def google_news_rss(query: str) -> str:
    encoded = quote_plus(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"


def google_news_kr_rss(query: str) -> str:
    encoded = quote_plus(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"


DEFAULT_FEEDS = [
    SourceFeed(
        "Automotive News",
        "big",
        "https://www.autonews.com/arc/outboundfeeds/rss/?outputType=xml",
    ),
    SourceFeed(
        "Automotive News Europe",
        "oem",
        "https://europe.autonews.com/arc/outboundfeeds/rss/?outputType=xml",
    ),
    SourceFeed(
        "Automotive World",
        "big",
        "https://www.automotiveworld.com/feed/",
    ),
    SourceFeed(
        "WardsAuto",
        "big",
        "https://www.wardsauto.com/feeds/news/",
    ),
    SourceFeed(
        "PR Newswire Automotive",
        "big",
        "https://www.prnewswire.com/rss/automotive-transportation/automotive-list.rss",
    ),
    SourceFeed(
        "Global automotive big news",
        "big",
        google_news_rss(
            'automotive industry OR automaker OR "electric vehicle" OR SDV Reuters OR Bloomberg'
        ),
    ),
    SourceFeed(
        "Korea Auto News",
        "big",
        google_news_kr_rss(
            "현대차 OR 기아 OR 한국GM OR 르노코리아 OR 자동차 배터리 OR 자율주행 OR SDV"
        ),
    ),
    SourceFeed(
        "InsideEVs",
        "oem",
        "https://insideevs.com/rss/news/all/",
    ),
    SourceFeed(
        "Car and Driver News",
        "oem",
        "https://www.caranddriver.com/rss/news.xml",
    ),
    SourceFeed(
        "Motor1 News",
        "oem",
        "https://www.motor1.com/rss/news/all/",
    ),
    SourceFeed(
        "The Drive",
        "oem",
        "https://www.thedrive.com/feed",
    ),
    SourceFeed(
        "OEM strategy",
        "oem",
        google_news_rss(
            "Toyota OR Volkswagen OR Hyundai OR Kia OR GM OR Ford OR Stellantis OR BMW OR Mercedes OR Tesla OR BYD strategy OR EV"
        ),
    ),
    SourceFeed(
        "JustAuto",
        "tier1",
        "https://www.just-auto.com/feed/",
    ),
    SourceFeed(
        "Automotive Dive",
        "tier1",
        "https://www.automotivedive.com/feeds/news/",
    ),
    SourceFeed(
        "Tier 1 suppliers",
        "tier1",
        google_news_rss(
            'Bosch OR Continental OR Denso OR Magna OR ZF OR "Hyundai Mobis" OR Aptiv automotive'
        ),
    ),
    SourceFeed(
        "Electrek",
        "sdv",
        "https://electrek.co/feed/",
    ),
    SourceFeed(
        "TechCrunch Transportation",
        "sdv",
        "https://techcrunch.com/category/transportation/feed/",
    ),
    SourceFeed(
        "The Verge Transportation",
        "sdv",
        "https://www.theverge.com/rss/transportation/index.xml",
    ),
    SourceFeed(
        "Automotive Testing Technology International",
        "sdv",
        "https://www.automotivetestingtechnologyinternational.com/feed",
    ),
    SourceFeed(
        "SDV software",
        "sdv",
        google_news_rss(
            '"software-defined vehicle" OR SDV OR "autonomous driving" OR "zonal architecture" OR AUTOSAR'
        ),
    ),
    SourceFeed(
        "Regulators and safety",
        "institution",
        google_news_rss(
            'NHTSA OR "Euro NCAP" OR "European Commission" OR ACEA vehicle OR automotive safety OR emissions OR tariff'
        ),
    ),
    SourceFeed(
        "Institutions and magazines",
        "institution",
        google_news_rss(
            '"S&P Global Mobility" OR McKinsey OR Gartner OR "SAE International" automotive'
        ),
    ),
    SourceFeed(
        "Automotive conferences",
        "conference",
        google_news_rss(
            '"IAA Mobility" OR "SAE WCX" OR "Auto Shanghai" OR "Japan Mobility Show" OR "Automotive World" OR "CES automotive" when:30d'
        ),
    ),
]

SECTION_LABELS_EN = {
    "big": "Top News",
    "oem": "OEM Trends",
    "tier1": "Tier 1 / Supply Chain",
    "sdv": "SDV / Software",
    "institution": "Institutions / Magazines",
    "conference": "Conferences / Events",
}
