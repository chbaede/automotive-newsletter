from __future__ import annotations

import re
from dataclasses import dataclass, field

PRIMARY_CATEGORIES = [
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

TOPICS_SOFTWARE = [
    "SDV",
    "E/E Architecture",
    "Zonal Architecture",
    "HPC",
    "Vehicle Computer",
    "AUTOSAR",
    "Adaptive AUTOSAR",
    "Classic AUTOSAR",
    "SOA",
    "Middleware",
    "OTA",
    "Vehicle OS",
    "Android Automotive",
    "QNX",
    "Embedded Linux",
    "Yocto",
    "Automotive Cybersecurity",
    "Functional Safety",
    "DevOps",
    "Cloud",
    "CI/CD",
    "AI",
    "ADAS",
    "Autonomous Driving",
]

TOPICS_OTHER = [
    "EV",
    "Battery",
    "Charging",
    "Semiconductor",
    "Supply Chain",
    "Manufacturing",
    "Regulation",
    "CO2",
    "Euro 7",
    "Trade",
    "Tariff",
]

ALL_TOPICS = TOPICS_SOFTWARE + TOPICS_OTHER

CATEGORY_LABELS = {
    "big": "대형 산업 이슈",
    "oem": "완성차 / OEM",
    "tier1": "부품사 / Tier 1",
    "sdv": "SDV / 전장 아키텍처",
    "ev_battery": "전기차 / 배터리",
    "adas_autonomous": "ADAS / 자율주행",
    "regulation": "정책 / 규제 / 통상",
    "market": "시장 / 판매 / 금융",
    "manufacturing": "생산 / 제조",
    "supply_chain": "공급망 / 반도체",
    "cybersecurity": "차량 사이버보안",
    "software": "임베디드 / 차량 SW",
    "conference": "컨퍼런스 / 이벤트",
    "institution": "기관 / 연구소",
    "reference": "참고자료 / 기타",
}

CATEGORY_LABELS_EN = {
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
    "institution": "Institutions & Research",
    "reference": "References",
}

# Canonical entity maps: canonical name -> list of aliases
OEM_ENTITIES: dict[str, list[str]] = {
    "Mercedes-Benz": ["mercedes-benz", "mercedes benz", "mercedes", "daimler", "메르세데스", "벤츠"],
    "Toyota": ["toyota", "lexus", "토요타", "도요타", "렉서스"],
    "Hyundai": ["hyundai", "genesis", "현대차", "현대자동차", "제네시스"],
    "Kia": ["kia", "기아"],
    "GM": ["general motors", "gm", "chevrolet", "cadillac", "제너럴 모터스", "쉐보레", "캐딜락"],
    "Ford": ["ford", "lincoln", "포드", "링컨"],
    "Stellantis": ["stellantis", "chrysler", "peugeot", "fiat", "jeep", "스텔란티스", "지프", "피아트"],
    "BMW": ["bmw", "mini"],
    "Volkswagen": ["volkswagen", "vw", "audi", "porsche", "폭스바겐", "아우디", "포르쉐"],
    "Tesla": ["tesla", "테슬라"],
    "BYD": ["byd", "비야디"],
    "Honda": ["honda", "acura", "혼다", "어큐라"],
    "Nissan": ["nissan", "infiniti", "닛산", "인피니티"],
    "Renault": ["renault", "르노"],
    "Rivian": ["rivian", "리비안"],
    "Lucid": ["lucid", "lucid motors", "루시드"],
    "Volvo": ["volvo", "polestar", "geely", "볼보", "폴스타", "지리"],
    "Mazda": ["mazda", "마쓰다"],
    "Subaru": ["subaru", "스바루"],
}

TIER1_ENTITIES: dict[str, list[str]] = {
    "Bosch": ["bosch", "보쉬"],
    "Continental": ["continental", "콘티넨탈"],
    "Denso": ["denso", "덴소"],
    "Magna": ["magna", "마그나"],
    "ZF": ["zf", "zf friedrichshafen"],
    "Aptiv": ["aptiv", "앱티브"],
    "Valeo": ["valeo", "발레오"],
    "Forvia": ["forvia", "faurecia", "포비아", "포레시아"],
    "Hyundai Mobis": ["hyundai mobis", "mobis", "현대모비스"],
    "CATL": ["catl"],
    "LG Energy Solution": ["lg energy solution", "lg energy", "lg엔솔", "lg에너지솔루션"],
    "Samsung SDI": ["samsung sdi", "삼성sdi"],
    "SK On": ["sk on", "sk온"],
    "Panasonic": ["panasonic", "파나소닉"],
    "Mobileye": ["mobileye", "모빌아이"],
    "Nvidia": ["nvidia", "엔비디아"],
    "Qualcomm": ["qualcomm", "스냅드래곤", "snapdragon", "퀄컴"],
    "NXP": ["nxp", "nxp semiconductors"],
    "Renesas": ["renesas", "르네사스"],
    "Infineon": ["infineon", "인피니언"],
    "Schaeffler": ["schaeffler", "셰플러"],
}

INSTITUTION_ENTITIES: dict[str, list[str]] = {
    "SAE": ["sae", "sae international", "sae wcx"],
    "NHTSA": ["nhtsa", "도로교통안전국"],
    "EPA": ["epa", "environmental protection agency", "미국 환경청"],
    "ACEA": ["acea", "유럽자동차제조협회"],
    "UNECE": ["unece"],
    "Euro NCAP": ["euro ncap"],
    "IIHS": ["iihs"],
    "S&P Global Mobility": ["s&p global", "s&p global mobility", "sp global"],
    "McKinsey": ["mckinsey", "mckinsey & company", "맥킨지"],
    "Gartner": ["gartner", "가트너"],
    "WardsAuto": ["wardsauto", "wards auto"],
    "Automotive News": ["automotive news"],
    "J.D. Power": ["j.d. power", "jd power"],
    "Cox Automotive": ["cox automotive"],
    "KAMA": ["한국자동차모빌리티산업협회", "kama", "자동차산업협회"],
}

CONFERENCE_ENTITIES: dict[str, list[str]] = {
    "CES": ["ces", "ces 2025", "ces 2026"],
    "IAA Mobility": ["iaa mobility", "iaa", "iaa 2025", "iaa 2026"],
    "SAE WCX": ["wcx", "sae congress"],
    "Japan Mobility Show": ["japan mobility show", "tokyo motor show"],
    "Auto Shanghai": ["auto shanghai", "shanghai auto show", "상하이 모터쇼"],
    "Auto China": ["auto china", "beijing auto show", "베이징 모터쇼"],
    "Automotive World": ["automotive world", "automotive world tokyo", "automotive world nagoya"],
}

# Canonical name lists for summarization and tagging
OEM_NAMES: list[str] = [
    *list(OEM_ENTITIES.keys()),
    "General Motors",
]

TIER1_NAMES: list[str] = [
    *list(TIER1_ENTITIES.keys()),
]

INSTITUTION_NAMES: list[str] = [
    *list(INSTITUTION_ENTITIES.keys()),
    "Reuters",
    "Bloomberg",
]

CONFERENCE_NAMES: list[str] = [
    *list(CONFERENCE_ENTITIES.keys()),
    "TU-Automotive",
    "Automotive World Tokyo",
    "Automotive World Nagoya",
]


# Topic detection regex patterns and implications
TOPIC_PATTERNS: list[tuple[str, list[str], list[str]]] = [
    # (Canonical Topic, Patterns, Implied Topics)
    ("Zonal Architecture", ["zonal architecture", "zonal e/e", "zonal controller", "zone controller", "zonal"], ["E/E Architecture", "SDV"]),
    ("E/E Architecture", ["e/e architecture", "ee architecture", "electrical/electronic architecture", "electrical architecture", "electronic architecture"], ["SDV"]),
    ("Adaptive AUTOSAR", ["adaptive autosar", "autosar adaptive"], ["AUTOSAR", "Middleware", "SDV"]),
    ("Classic AUTOSAR", ["classic autosar", "autosar classic"], ["AUTOSAR"]),
    ("AUTOSAR", ["autosar"], ["SDV"]),
    ("Vehicle Computer", ["vehicle computer", "central vehicle computer", "car computer"], ["SDV"]),
    ("HPC", ["high-performance compute", "high performance compute", "hpc", "central compute"], ["Vehicle Computer", "SDV"]),
    ("Android Automotive", ["android automotive", "aaos", "google built-in"], ["Vehicle OS", "SDV"]),
    ("QNX", ["qnx", "blackberry qnx"], ["Vehicle OS", "SDV"]),
    ("Yocto", ["yocto project", "yocto"], ["Embedded Linux", "Vehicle OS", "SDV"]),
    ("Embedded Linux", ["embedded linux", "automotive linux", "agl", "automotive grade linux"], ["Vehicle OS", "SDV"]),
    ("Vehicle OS", ["vehicle os", "automotive os", "car os", "vehicle operating system"], ["SDV"]),
    ("SOA", ["service-oriented architecture", "service oriented architecture", "soa", "some/ip", "someip", "dds", "doip", "automotive ethernet", "can fd"], ["Middleware", "SDV"]),
    ("Middleware", ["middleware", "someip", "some/ip", "dds", "doip"], ["SDV"]),
    ("OTA", ["over-the-air", "ota update", "ota", "무선 업데이트"], ["SDV"]),
    ("Automotive Cybersecurity", ["automotive cybersecurity", "vehicle cybersecurity", "iso 21434", "unece r155", "unece r156", "cybersecurity", "사이버보안"], ["SDV"]),
    ("Functional Safety", ["functional safety", "iso 26262", "asil", "기능안전"], []),
    ("CI/CD", ["ci/cd", "continuous integration", "continuous delivery", "sbom", "slsa"], ["DevOps"]),
    ("DevOps", ["devops", "automotive devops", "devsecops", "virtual ecu", "v-ecu", "digital twin", "sil", "hil", "vil", "software-in-the-loop", "hardware-in-the-loop", "virtual validation"], ["SDV"]),
    ("Cloud", ["cloud", "cloud-native", "container", "oci", "kubernetes", "aws automotive", "azure automotive", "google cloud automotive"], []),
    ("Autonomous Driving", ["autonomous driving", "self-driving cars", "self-driving", "robotaxis", "robotaxi", "autonomous vehicles", "autonomous vehicle", "자율주행", "로보택시", "fsd", "driverless"], ["ADAS"]),
    ("ADAS", ["adas", "advanced driver assistance", "운전자 보조", "lane keeping", "aeb"], []),
    ("AI", [
        "artificial intelligence", "generative ai", "genai", "large language model",
        "llm", "foundation model", "neural network", "neural networks",
        "computer vision", "machine learning", "deep learning",
        "ai assistant", "ai agent", "ai-powered", "ai-driven",
        "인공지능", "머신러닝", "딥러닝", "a.i.", "ai"
    ], []),
    ("SDV", [
        "software-defined vehicles", "software-defined vehicle", "software defined vehicles",
        "software defined vehicle", "sdv", "sdvs", "소프트웨어 중심 자동차", "automotive software",
        "vehicle software", "차량용 소프트웨어", "차량 소프트웨어",
        "soafee", "eclipse sdv", "eclipse s-core", "covesa"
    ], []),
    ("Euro 7", ["euro 7", "euro vii"], ["CO2", "Regulation"]),
    ("CO2", ["co2 emissions", "carbon emission", "co2", "배출가스"], ["Regulation"]),
    ("Tariff", ["tariffs", "tariff", "customs duty", "customs duties", "관세"], ["Trade", "Regulation"]),
    ("Trade", ["trade barrier", "trade barriers", "trade war", "export restriction", "통상", "무역"], ["Regulation"]),
    ("Regulation", ["regulations", "regulation", "regulators", "regulator", "safety standard", "mandate", "probe", "investigation", "recall", "규제", "리콜"], []),
    ("Battery", ["batteries", "battery", "solid-state battery", "lfp", "ncm", "battery cells", "battery cell", "gigafactory", "배터리", "이차전지"], ["EV"]),
    ("Charging", ["charging", "ev chargers", "ev charger", "fast charging", "superchargers", "supercharger", "충전기", "급속충전"], ["EV"]),
    ("EV", ["electric vehicles", "electric vehicle", "evs", "ev", "bevs", "bev", "phev", "phevs", "전기차", "전동화"], []),
    ("Semiconductor", ["semiconductors", "semiconductor", "automotive chips", "automotive chip", "chips", "chip", "microcontrollers", "microcontroller", "mcu", "mcus", "soc", "socs", "반도체"], []),
    ("Supply Chain", ["supply chain", "tier 2", "component suppliers", "component supplier", "procurement", "공급망", "부품 공급"], []),
    ("Manufacturing", ["manufacturing", "assembly plants", "assembly plant", "production lines", "production line", "gigafactory", "factory output", "생산 공장", "제조"], []),
]


@dataclass(slots=True)
class TaxonomyResult:
    primary_category: str
    secondary_categories: list[str]
    topics: list[str]
    entities: list[str]


def _contains_word(text: str, word: str) -> bool:
    if not word:
        return False
    # If the word contains non-ascii characters (e.g. Korean), direct search
    if re.search(r"[^a-zA-Z0-9\s\-._/]", word):
        return word.lower() in text.lower()
    pattern = rf"(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def extract_entities(text: str) -> list[str]:
    found: list[str] = []

    for name, aliases in OEM_ENTITIES.items():
        if any(_contains_word(text, alias) for alias in aliases):
            if name not in found:
                found.append(name)

    for name, aliases in TIER1_ENTITIES.items():
        if any(_contains_word(text, alias) for alias in aliases):
            if name not in found:
                found.append(name)

    for name, aliases in INSTITUTION_ENTITIES.items():
        if any(_contains_word(text, alias) for alias in aliases):
            if name not in found:
                found.append(name)

    for name, aliases in CONFERENCE_ENTITIES.items():
        if any(_contains_word(text, alias) for alias in aliases):
            if name not in found:
                found.append(name)

    return found


def extract_topics(text: str) -> list[str]:
    matched_topics: list[str] = []
    implied_topics: list[str] = []

    for topic_name, patterns, implications in TOPIC_PATTERNS:
        if any(_contains_word(text, pat) for pat in patterns):
            if topic_name not in matched_topics:
                matched_topics.append(topic_name)
            for imp in implications:
                if imp not in implied_topics and imp not in matched_topics:
                    implied_topics.append(imp)

    # Combine matched topics first, then implied topics
    final_topics: list[str] = []
    for t in matched_topics + implied_topics:
        if t not in final_topics:
            final_topics.append(t)
    return final_topics


def classify_taxonomy(
    title: str,
    excerpt: str = "",
    source: str = "",
    source_type: str = "",
    content: str = "",
    bucket: str = "",
) -> TaxonomyResult:
    # Build text representation with weighted emphasis
    combined_text = f"{title} {title} {title} {excerpt} {excerpt} {content} {source}".strip()
    lowered = combined_text.lower()

    entities = extract_entities(f"{title} {excerpt} {content}")
    topics = extract_topics(f"{title} {excerpt} {content}")

    # Identify company actors
    has_oem = any(e in OEM_ENTITIES for e in entities)
    has_tier1 = any(e in TIER1_ENTITIES for e in entities)
    has_institution_entity = any(e in INSTITUTION_ENTITIES for e in entities)
    has_conference_entity = any(e in CONFERENCE_ENTITIES for e in entities)

    # Domain affinity scores
    scores: dict[str, float] = {cat: 0.0 for cat in PRIMARY_CATEGORIES}

    # 1. Conference
    if has_conference_entity or bucket == "conference" or source_type == "event":
        scores["conference"] += 35.0
    if re.search(r"\b(conference|expo|summit|symposium|show|congress)\b", lowered):
        scores["conference"] += 20.0

    # 2. Cybersecurity
    if "Automotive Cybersecurity" in topics:
        scores["cybersecurity"] += 36.0
    if any(k in lowered for k in ["cybersecurity", "vulnerability", "hack", "iso 21434", "unece r155"]):
        scores["cybersecurity"] += 15.0

    # 3. SDV & E/E Architecture
    sdv_topics = {
        "Zonal Architecture", "E/E Architecture", "AUTOSAR", "Adaptive AUTOSAR",
        "Classic AUTOSAR", "HPC", "Vehicle Computer", "SOA", "Middleware",
        "OTA", "Vehicle OS", "Android Automotive", "QNX", "Embedded Linux",
        "Yocto", "SDV",
    }
    matching_sdv_topics = [t for t in topics if t in sdv_topics]
    if matching_sdv_topics:
        scores["sdv"] += 32.0 + len(matching_sdv_topics) * 4.0
    if any(k in lowered for k in ["zonal", "e/e architecture", "software-defined", "sdv", "autosar"]):
        scores["sdv"] += 10.0

    # 4. ADAS & Autonomous Driving
    if "Autonomous Driving" in topics or "ADAS" in topics:
        scores["adas_autonomous"] += 30.0
    if any(k in lowered for k in ["robotaxi", "self-driving", "autonomous vehicle", "adas", "fsd"]):
        scores["adas_autonomous"] += 12.0

    # 5. EV & Battery
    if "Battery" in topics or "EV" in topics or "Charging" in topics:
        scores["ev_battery"] += 28.0
    if any(k in lowered for k in ["battery", "solid-state", "lfp", "ncm", "charging", "gigafactory", "electric vehicle"]):
        scores["ev_battery"] += 10.0

    # 6. Regulation & Trade
    if any(t in topics for t in ["Tariff", "Euro 7", "CO2", "Trade", "Regulation"]):
        scores["regulation"] += 26.0
    if source_type == "regulator" or any(k in lowered for k in ["recall", "probe", "investigation", "tariff", "regulator", "safety standard"]):
        scores["regulation"] += 12.0

    # 7. Supply Chain & Semiconductor
    if "Semiconductor" in topics or "Supply Chain" in topics:
        scores["supply_chain"] += 25.0
    if any(k in lowered for k in ["semiconductor", "chip shortage", "chips", "wafer", "foundry", "supply chain"]):
        scores["supply_chain"] += 10.0

    # 8. Manufacturing
    if "Manufacturing" in topics or any(k in lowered for k in ["assembly plant", "production line", "factory output", "manufacturing"]):
        scores["manufacturing"] += 22.0

    # 9. Market
    if any(k in lowered for k in ["sales", "deliveries", "quarterly profit", "revenue", "market share", "earnings", "guidance"]):
        scores["market"] += 20.0

    # 10. Software
    if any(t in topics for t in ["DevOps", "Cloud", "CI/CD", "Functional Safety", "AI"]):
        scores["software"] += 20.0

    # 11. Company actors (OEM / Tier 1)
    if has_oem:
        scores["oem"] += 21.0
    if has_tier1:
        scores["tier1"] += 21.0

    # 12. Institution
    if has_institution_entity or source_type in {"research", "institution"}:
        scores["institution"] += 18.0

    # Context & source adjustments (never classify solely from source)
    if bucket and bucket in scores and bucket != "big":
        scores[bucket] += 4.0

    # Filter out categories with zero score
    ranked = [(cat, score) for cat, score in scores.items() if score > 0]
    ranked.sort(key=lambda item: item[1], reverse=True)

    if not ranked:
        primary = "big"
        secondaries: list[str] = []
    else:
        primary = ranked[0][0]
        # Collect secondary categories from remaining ranked domains
        secondaries = []
        for cat, sc in ranked[1:]:
            if sc >= 15.0 and cat != primary and cat not in secondaries:
                secondaries.append(cat)

    # Ensure participating company domains (oem, tier1) are included in secondary if tech primary won
    if has_oem and "oem" != primary and "oem" not in secondaries:
        secondaries.append("oem")
    if has_tier1 and "tier1" != primary and "tier1" not in secondaries:
        secondaries.append("tier1")

    return TaxonomyResult(
        primary_category=primary,
        secondary_categories=secondaries[:4],
        topics=topics,
        entities=entities,
    )
