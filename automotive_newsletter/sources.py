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


DEFAULT_FEEDS = [
    SourceFeed(
        "Automotive World",
        "big",
        "https://www.automotiveworld.com/feed/",
    ),
    SourceFeed(
        "Electrek",
        "sdv",
        "https://electrek.co/feed/",
    ),
    SourceFeed(
        "InsideEVs",
        "oem",
        "https://insideevs.com/rss/news/all/",
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
        "Global automotive big news",
        "big",
        google_news_rss(
            "automotive industry OEM supplier Reuters Automotive News WardsAuto when:7d"
        ),
    ),
    SourceFeed(
        "OEM strategy",
        "oem",
        google_news_rss(
            "Toyota Volkswagen Hyundai GM Ford Stellantis BMW Mercedes Tesla BYD vehicle strategy when:7d"
        ),
    ),
    SourceFeed(
        "Tier 1 suppliers",
        "tier1",
        google_news_rss(
            "Bosch Continental Denso Magna ZF Aptiv Valeo Forvia Hyundai Mobis CATL automotive supplier when:14d"
        ),
    ),
    SourceFeed(
        "Regulators and safety",
        "institution",
        google_news_rss(
            "site:nhtsa.gov OR site:transport.ec.europa.eu OR site:acea.auto automotive vehicle safety regulation when:14d"
        ),
    ),
    SourceFeed(
        "SDV software",
        "sdv",
        google_news_rss(
            '"software-defined vehicle" OR SDV OR "zonal architecture" OR automotive OTA OR AUTOSAR when:7d'
        ),
    ),
    SourceFeed(
        "Institutions and magazines",
        "institution",
        google_news_rss(
            '"S&P Global Mobility" OR McKinsey automotive OR Gartner automotive OR SAE automotive OR WardsAuto when:7d'
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
