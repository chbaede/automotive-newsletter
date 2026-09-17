"""Centralized Automotive Entity Registry and Disambiguation.

This module is the single source of truth for canonical entities, brand/parent group
hierarchies, and entity disambiguation across taxonomy classification and event clustering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Article


@dataclass(frozen=True, slots=True)
class EntityDefinition:
    """Definition of a canonical automotive industry entity."""

    canonical_name: str  # Human-readable display name, e.g. "Audi", "Mercedes-Benz"
    canonical_id: str  # Normalized identifier, e.g. "audi", "mercedes"
    entity_type: str  # "oem", "tier1", "tech", "battery", "institution", "regulator", "conference"
    parent_group: str | None = None  # e.g. "Volkswagen Group", "Hyundai Motor Group"
    aliases: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Canonical Entity Definitions
# ---------------------------------------------------------------------------

ENTITY_DEFINITIONS: list[EntityDefinition] = [
    # --- OEMs: Volkswagen Group ---
    EntityDefinition("Volkswagen", "volkswagen", "oem", "Volkswagen Group", ["volkswagen", "vw", "폭스바겐"]),
    EntityDefinition("Audi", "audi", "oem", "Volkswagen Group", ["audi", "아우디"]),
    EntityDefinition("Porsche", "porsche", "oem", "Volkswagen Group", ["porsche", "포르쉐"]),
    EntityDefinition("Skoda", "skoda", "oem", "Volkswagen Group", ["skoda", "스코다"]),
    EntityDefinition("SEAT", "seat", "oem", "Volkswagen Group", ["seat", "세아트"]),
    EntityDefinition("Cupra", "cupra", "oem", "Volkswagen Group", ["cupra", "쿠프라"]),
    EntityDefinition("Bentley", "bentley", "oem", "Volkswagen Group", ["bentley", "벤틀리"]),
    EntityDefinition("Lamborghini", "lamborghini", "oem", "Volkswagen Group", ["lamborghini", "람보르기니"]),

    # --- OEMs: Toyota Group ---
    EntityDefinition("Toyota", "toyota", "oem", "Toyota Group", ["toyota", "토요타", "도요타"]),
    EntityDefinition("Lexus", "lexus", "oem", "Toyota Group", ["lexus", "렉서스"]),
    EntityDefinition("Daihatsu", "daihatsu", "oem", "Toyota Group", ["daihatsu", "다이하츠"]),

    # --- OEMs: Hyundai Motor Group ---
    EntityDefinition("Hyundai", "hyundai", "oem", "Hyundai Motor Group", ["hyundai", "hyundai motor", "현대", "현대차", "현대자동차"]),
    EntityDefinition("Kia", "kia", "oem", "Hyundai Motor Group", ["kia", "기아", "기아차"]),
    EntityDefinition("Genesis", "genesis", "oem", "Hyundai Motor Group", ["genesis", "제네시스"]),

    # --- OEMs: General Motors ---
    EntityDefinition("GM", "gm", "oem", "General Motors", ["general motors", "gm", "제너럴 모터스"]),
    EntityDefinition("Chevrolet", "chevrolet", "oem", "General Motors", ["chevrolet", "chevy", "쉐보레"]),
    EntityDefinition("Cadillac", "cadillac", "oem", "General Motors", ["cadillac", "캐딜락"]),
    EntityDefinition("Buick", "buick", "oem", "General Motors", ["buick", "뷰익"]),
    EntityDefinition("GMC", "gmc", "oem", "General Motors", ["gmc"]),

    # --- OEMs: Stellantis ---
    EntityDefinition("Stellantis", "stellantis", "oem", "Stellantis", ["stellantis", "스텔란티스"]),
    EntityDefinition("Jeep", "jeep", "oem", "Stellantis", ["jeep", "지프"]),
    EntityDefinition("Peugeot", "peugeot", "oem", "Stellantis", ["peugeot", "푸조"]),
    EntityDefinition("Fiat", "fiat", "oem", "Stellantis", ["fiat", "피아트"]),
    EntityDefinition("Chrysler", "chrysler", "oem", "Stellantis", ["chrysler", "크라이슬러"]),
    EntityDefinition("Ram", "ram", "oem", "Stellantis", ["ram", "램"]),
    EntityDefinition("Dodge", "dodge", "oem", "Stellantis", ["dodge", "닷지"]),
    EntityDefinition("Alfa Romeo", "alfa_romeo", "oem", "Stellantis", ["alfa romeo", "알파로메오"]),
    EntityDefinition("Maserati", "maserati", "oem", "Stellantis", ["maserati", "마세라티"]),
    EntityDefinition("Citroën", "citroen", "oem", "Stellantis", ["citroen", "citroën", "시트로엥"]),
    EntityDefinition("Opel", "opel", "oem", "Stellantis", ["opel", "오펠"]),

    # --- OEMs: Geely Holding Group ---
    EntityDefinition("Volvo", "volvo", "oem", "Geely Holding Group", ["volvo", "volvo cars", "볼보"]),
    EntityDefinition("Polestar", "polestar", "oem", "Geely Holding Group", ["polestar", "폴스타"]),
    EntityDefinition("Geely", "geely", "oem", "Geely Holding Group", ["geely", "지리", "지리자동차"]),
    EntityDefinition("Zeekr", "zeekr", "oem", "Geely Holding Group", ["zeekr", "지커"]),
    EntityDefinition("Lotus", "lotus", "oem", "Geely Holding Group", ["lotus", "로터스"]),

    # --- OEMs: BMW Group ---
    EntityDefinition("BMW", "bmw", "oem", "BMW Group", ["bmw"]),
    EntityDefinition("Mini", "mini", "oem", "BMW Group", ["mini", "미니"]),
    EntityDefinition("Rolls-Royce", "rolls_royce", "oem", "BMW Group", ["rolls-royce", "rolls royce", "롤스로이스"]),

    # --- OEMs: Mercedes-Benz Group ---
    EntityDefinition("Mercedes-Benz", "mercedes", "oem", "Mercedes-Benz Group", ["mercedes-benz", "mercedes benz", "mercedes", "daimler", "메르세데스", "벤츠"]),

    # --- OEMs: Ford Motor Company ---
    EntityDefinition("Ford", "ford", "oem", "Ford Motor Company", ["ford", "포드"]),
    EntityDefinition("Lincoln", "lincoln", "oem", "Ford Motor Company", ["lincoln", "링컨"]),

    # --- OEMs: Honda Motor Company ---
    EntityDefinition("Honda", "honda", "oem", "Honda Motor Company", ["honda", "혼다"]),
    EntityDefinition("Acura", "acura", "oem", "Honda Motor Company", ["acura", "어큐라"]),

    # --- OEMs: Renault-Nissan-Mitsubishi Alliance ---
    EntityDefinition("Renault", "renault", "oem", "Renault-Nissan-Mitsubishi Alliance", ["renault", "르노"]),
    EntityDefinition("Nissan", "nissan", "oem", "Renault-Nissan-Mitsubishi Alliance", ["nissan", "닛산"]),
    EntityDefinition("Infiniti", "infiniti", "oem", "Renault-Nissan-Mitsubishi Alliance", ["infiniti", "인피니티"]),
    EntityDefinition("Mitsubishi", "mitsubishi", "oem", "Renault-Nissan-Mitsubishi Alliance", ["mitsubishi", "미쓰비시"]),
    EntityDefinition("Dacia", "dacia", "oem", "Renault-Nissan-Mitsubishi Alliance", ["dacia", "다치아"]),

    # --- OEMs: Independent / EV Specialists ---
    EntityDefinition("Tesla", "tesla", "oem", None, ["tesla", "테슬라"]),
    EntityDefinition("BYD", "byd", "oem", None, ["byd", "비야디"]),
    EntityDefinition("Rivian", "rivian", "oem", None, ["rivian", "리비안"]),
    EntityDefinition("Lucid", "lucid", "oem", None, ["lucid", "lucid motors", "루시드"]),
    EntityDefinition("NIO", "nio", "oem", None, ["nio", "니오"]),
    EntityDefinition("XPeng", "xpeng", "oem", None, ["xpeng", "샤오펑"]),
    EntityDefinition("Mazda", "mazda", "oem", None, ["mazda", "마쓰다"]),
    EntityDefinition("Subaru", "subaru", "oem", None, ["subaru", "스바루"]),

    # --- Tier 1 Suppliers ---
    EntityDefinition("Bosch", "bosch", "tier1", None, ["bosch", "보쉬"]),
    EntityDefinition("Continental", "continental", "tier1", None, ["continental", "콘티넨탈"]),
    EntityDefinition("ZF", "zf", "tier1", None, ["zf", "zf friedrichshafen"]),
    EntityDefinition("Denso", "denso", "tier1", "Toyota Group", ["denso", "덴소"]),
    EntityDefinition("Magna", "magna", "tier1", None, ["magna", "마그나"]),
    EntityDefinition("Valeo", "valeo", "tier1", None, ["valeo", "발레오"]),
    EntityDefinition("Forvia", "forvia", "tier1", None, ["forvia", "faurecia", "포비아", "포레시아"]),
    EntityDefinition("Aptiv", "aptiv", "tier1", None, ["aptiv", "앱티브"]),
    EntityDefinition("Hyundai Mobis", "hyundai_mobis", "tier1", "Hyundai Motor Group", ["hyundai mobis", "mobis", "현대모비스", "모비스"]),
    EntityDefinition("Schaeffler", "schaeffler", "tier1", None, ["schaeffler", "셰플러"]),

    # --- Battery Manufacturers ---
    EntityDefinition("CATL", "catl", "battery", None, ["catl"]),
    EntityDefinition("LG Energy Solution", "lg_energy", "battery", None, ["lg energy solution", "lg energy", "lg엔솔", "lg에너지솔루션"]),
    EntityDefinition("Samsung SDI", "samsung_sdi", "battery", None, ["samsung sdi", "삼성sdi"]),
    EntityDefinition("SK On", "sk_on", "battery", None, ["sk on", "sk온"]),
    EntityDefinition("Panasonic", "panasonic", "battery", None, ["panasonic", "파나소닉"]),

    # --- Autonomous & Tech Partners ---
    EntityDefinition("Nvidia", "nvidia", "tech", None, ["nvidia", "엔비디아"]),
    EntityDefinition("Qualcomm", "qualcomm", "tech", None, ["qualcomm", "스냅드래곤", "snapdragon", "퀄컴"]),
    EntityDefinition("Mobileye", "mobileye", "tech", None, ["mobileye", "모빌아이"]),
    EntityDefinition("NXP", "nxp", "tech", None, ["nxp", "nxp semiconductors"]),
    EntityDefinition("Renesas", "renesas", "tech", None, ["renesas", "르네사스"]),
    EntityDefinition("Infineon", "infineon", "tech", None, ["infineon", "인피니언"]),
    EntityDefinition("Waymo", "waymo", "tech", None, ["waymo", "웨이모"]),
    EntityDefinition("Sony", "sony", "tech", None, ["sony", "소니"]),
    EntityDefinition("Foxconn", "foxconn", "tech", None, ["foxconn", "폭스콘"]),
    EntityDefinition("Baidu", "baidu", "tech", None, ["baidu", "바이두"]),

    # --- Regulators ---
    EntityDefinition("NHTSA", "nhtsa", "regulator", None, ["nhtsa", "도로교통안전국"]),
    EntityDefinition("EPA", "epa", "regulator", None, ["epa", "environmental protection agency", "미국 환경청"]),
    EntityDefinition("KBA", "kba", "regulator", None, ["kba"]),
    EntityDefinition("UNECE", "unece", "regulator", None, ["unece"]),

    # --- Institutions & Research ---
    EntityDefinition("SAE", "sae", "institution", None, ["sae", "sae international", "sae wcx"]),
    EntityDefinition("ACEA", "acea", "institution", None, ["acea", "유럽자동차제조협회"]),
    EntityDefinition("Euro NCAP", "euro_ncap", "institution", None, ["euro ncap"]),
    EntityDefinition("IIHS", "iihs", "institution", None, ["iihs"]),
    EntityDefinition("S&P Global Mobility", "sp_global", "institution", None, ["s&p global", "s&p global mobility", "sp global"]),
    EntityDefinition("McKinsey", "mckinsey", "institution", None, ["mckinsey", "mckinsey & company", "맥킨지"]),
    EntityDefinition("Gartner", "gartner", "institution", None, ["gartner", "가트너"]),
    EntityDefinition("WardsAuto", "wardsauto", "institution", None, ["wardsauto", "wards auto"]),
    EntityDefinition("Automotive News", "automotive_news", "institution", None, ["automotive news"]),
    EntityDefinition("J.D. Power", "jd_power", "institution", None, ["j.d. power", "jd power"]),
    EntityDefinition("Cox Automotive", "cox_automotive", "institution", None, ["cox automotive"]),
    EntityDefinition("KAMA", "kama", "institution", None, ["한국자동차모빌리티산업협회", "kama", "자동차산업협회"]),

    # --- Conferences & Events ---
    EntityDefinition("CES", "ces", "conference", None, ["ces", "ces 2025", "ces 2026"]),
    EntityDefinition("IAA Mobility", "iaa", "conference", None, ["iaa mobility", "iaa", "iaa 2025", "iaa 2026"]),
    EntityDefinition("SAE WCX", "sae_wcx", "conference", None, ["wcx", "sae congress"]),
    EntityDefinition("Japan Mobility Show", "japan_mobility_show", "conference", None, ["japan mobility show", "tokyo motor show"]),
    EntityDefinition("Auto Shanghai", "auto_shanghai", "conference", None, ["auto shanghai", "shanghai auto show", "상하이 모터쇼"]),
    EntityDefinition("Auto China", "auto_china", "conference", None, ["auto china", "beijing auto show", "베이징 모터쇼"]),
    EntityDefinition("Automotive World", "automotive_world", "conference", None, ["automotive world", "automotive world tokyo", "automotive world nagoya"]),
]


# ---------------------------------------------------------------------------
# Fast Lookup Dictionaries & Sets
# ---------------------------------------------------------------------------

ENTITY_BY_ID: dict[str, EntityDefinition] = {e.canonical_id: e for e in ENTITY_DEFINITIONS}
ENTITY_BY_NAME: dict[str, EntityDefinition] = {e.canonical_name: e for e in ENTITY_DEFINITIONS}

# alias -> canonical_id
CANONICAL_ENTITY_MAP: dict[str, str] = {}
for e in ENTITY_DEFINITIONS:
    CANONICAL_ENTITY_MAP[e.canonical_id] = e.canonical_id
    CANONICAL_ENTITY_MAP[e.canonical_name.lower()] = e.canonical_id
    for alias in e.aliases:
        CANONICAL_ENTITY_MAP[alias.lower()] = e.canonical_id

# canonical_id -> parent corporate group name
PARENT_GROUPS: dict[str, str] = {
    e.canonical_id: e.parent_group for e in ENTITY_DEFINITIONS if e.parent_group
}

# Categorized sets of canonical IDs
OEM_ENTITIES: set[str] = {e.canonical_id for e in ENTITY_DEFINITIONS if e.entity_type == "oem"}
TIER1_ENTITIES: set[str] = {e.canonical_id for e in ENTITY_DEFINITIONS if e.entity_type == "tier1"}
BATTERY_ENTITIES: set[str] = {e.canonical_id for e in ENTITY_DEFINITIONS if e.entity_type == "battery"}
TECH_ENTITIES: set[str] = {e.canonical_id for e in ENTITY_DEFINITIONS if e.entity_type == "tech"}
REGULATOR_ENTITIES: set[str] = {e.canonical_id for e in ENTITY_DEFINITIONS if e.entity_type == "regulator"}
INSTITUTION_ENTITIES: set[str] = {e.canonical_id for e in ENTITY_DEFINITIONS if e.entity_type in {"institution", "regulator"}}
CONFERENCE_ENTITIES: set[str] = {e.canonical_id for e in ENTITY_DEFINITIONS if e.entity_type == "conference"}

# Tech / Supplier entities relevant for partnership guards
TECH_SUPPLIER_ENTITIES: set[str] = TIER1_ENTITIES | BATTERY_ENTITIES | TECH_ENTITIES

# Canonical display name mappings for Taxonomy
TAXONOMY_OEM_MAP: dict[str, list[str]] = {
    e.canonical_name: [e.canonical_name.lower(), *[a.lower() for a in e.aliases]]
    for e in ENTITY_DEFINITIONS if e.entity_type == "oem"
}
TAXONOMY_TIER1_MAP: dict[str, list[str]] = {
    e.canonical_name: [e.canonical_name.lower(), *[a.lower() for a in e.aliases]]
    for e in ENTITY_DEFINITIONS if e.entity_type in {"tier1", "battery", "tech"}
}
TAXONOMY_INSTITUTION_MAP: dict[str, list[str]] = {
    e.canonical_name: [e.canonical_name.lower(), *[a.lower() for a in e.aliases]]
    for e in ENTITY_DEFINITIONS if e.entity_type in {"institution", "regulator"}
}
TAXONOMY_CONFERENCE_MAP: dict[str, list[str]] = {
    e.canonical_name: [e.canonical_name.lower(), *[a.lower() for a in e.aliases]]
    for e in ENTITY_DEFINITIONS if e.entity_type == "conference"
}


# ---------------------------------------------------------------------------
# Common Short/Ambiguous Word Disambiguation
# ---------------------------------------------------------------------------

COMMON_WORD_DISAMBIGUATION: dict[str, dict[str, list[re.Pattern]]] = {
    "seat": {
        "negative": [
            re.compile(r"\bseats?\s+(?:belt|belts|cushion|cushions|heater|heaters|heating|warmer|warmers|track|tracks|frame|frames|module|modules|adjustment|sensor|sensors|position|occupancy|cover|covers|massage|ventilation|failure|problem|issue|before|after|during)\b", re.I),
            re.compile(r"\b(?:heated|heating|ventilated|massage|leather|power|folding|safety|child|baby|infant|bucket|front|rear|back|driver|passenger|third-row|second-row|row)\s+seats?\b", re.I),
            re.compile(r"\b(?:driver|passenger|front|rear)\s+(?:side\s+)?seat\b", re.I),
            re.compile(r"\b(?:driver'?s?|passenger'?s?)\s+seat\b", re.I),
            re.compile(r"\b(?:adjust|adjusts|adjusted|adjusting|take|takes|taking|sit|sits|sitting|sat|in|into|on|onto|recline|reclines|reclined)\s+(?:the\s+|a\s+|their\s+|his\s+|her\s+)?seats?\b", re.I),
            re.compile(r"\bseating\b", re.I),
        ],
        "positive": [
            re.compile(r"\bseat\s*(?:s\.?a\.?|cupra|martorell|ibiza|leon|ateca|arona|tarraco)\b", re.I),
            re.compile(r"\b(?:carmaker|automaker|oem|brand)\s+seat\b", re.I),
            re.compile(r"\bseat\s+(?:brand|carmaker|automaker|unveils|reveals|debuts|recalls|reports|launches|delivers|sales|announces|plans|targets|invests|develops)\b", re.I),
        ],
    },
    "mini": {
        "negative": [
            re.compile(r"\bmini(?:-|\s+)(?:excavator|van|bus|split|series|led|lidar|truck|factory|suv|size|car|market)\b", re.I),
            re.compile(r"\bin\s+mini\b", re.I),
        ],
        "positive": [
            re.compile(r"\bmini\s*(?:cooper|countryman|aceman|clubman|john cooper|electric|ev|brand|carmaker|automaker)\b", re.I),
            re.compile(r"\b(?:bmw|carmaker|automaker|brand)\s+mini\b", re.I),
            re.compile(r"\bmini\s+(?:unveils|reveals|debuts|launches|reports|recalls|sales|announces|plans)\b", re.I),
        ],
    },
    "ram": {
        "negative": [
            re.compile(r"\b(?:\d+\s*)?(?:gb|mb|tb|ddr|ddr4|ddr5)\s+ram\b", re.I),
            re.compile(r"\bram\s+(?:into|med|ming|s\s+into)\b", re.I),
            re.compile(r"\b(?:hydraulic|battering)\s+ram\b", re.I),
        ],
        "positive": [
            re.compile(r"\bram\s*(?:1500|2500|3500|trx|promaster|rev|pickup|truck|trucks|brand|carmaker|automaker)\b", re.I),
            re.compile(r"\b(?:dodge|stellantis|carmaker|automaker|brand)\s+ram\b", re.I),
            re.compile(r"\bram\s+(?:unveils|reveals|debuts|launches|recalls|sales|announces|plans)\b", re.I),
        ],
    },
    "ford": {
        "negative": [
            re.compile(r"\b(?:harrison|gerald|doug|tom|betty|henry)\s+ford\b", re.I),
            re.compile(r"\bford\s+(?:foundation|theater|theatre|museum|river|crossing)\b", re.I),
            re.compile(r"\briver\s+ford\b", re.I),
        ],
        "positive": [
            re.compile(r"\bford\s*(?:motor|motor\s+co|f-150|mustang|bronco|explorer|ranger|ev|evs|ceo|shares|recalls|unveils|reveals|sales|said|announced|announces|investment|trucks?)\b", re.I),
            re.compile(r"\b(?:carmaker|automaker|brand)\s+ford\b", re.I),
        ],
    },
    "lotus": {
        "negative": [
            re.compile(r"\b(?:white|blue|water|sacred)\s+lotus\b", re.I),
            re.compile(r"\blotus\s+(?:flower|leaf|position|temple|blooms?|blooming)\b", re.I),
        ],
        "positive": [
            re.compile(r"\blotus\s*(?:cars|emira|eletre|evija|emeya|brand|carmaker|automaker|group)\b", re.I),
            re.compile(r"\b(?:geely|carmaker|automaker|brand)\s+lotus\b", re.I),
            re.compile(r"\blotus\s+(?:unveils|reveals|debuts|launches|sales|announces)\b", re.I),
        ],
    },
    "gm": {
        "negative": [
            re.compile(r"\b\d+\s*gm\b", re.I),
            re.compile(r"\bgm\s+(?:of\s+material|foods|crops)\b", re.I),
            re.compile(r"\b(?:plant|general)\s+gm\b", re.I),
        ],
        "positive": [
            re.compile(r"\bgeneral\s+motors\b", re.I),
            re.compile(r"\bgm\s+(?:cruise|korea|defense|motors|ev|evs|ceo|shares|stock|invests|investment|plant|plants|workers|uaw|recalls|unveils|reveals|sales|profit|earnings|said|announced|announces|reported)\b", re.I),
            re.compile(r"\b(?:carmaker|automaker|oem)\s+gm\b", re.I),
        ],
    },
    "zf": {
        "negative": [
            re.compile(r"\b(?:nikon|camera|lens|sensor)\s+zf\b", re.I),
            re.compile(r"\bzf\s+(?:camera|lens|mount)\b", re.I),
            re.compile(r"\bzero[- ]frequency\b", re.I),
        ],
        "positive": [
            re.compile(r"\bzf\s*(?:friedrichshafen|group|chassis|gearbox|transmission|supplier|lifeguard|procurement|mobility)\b", re.I),
            re.compile(r"\b(?:supplier|tier\s*1)\s+zf\b", re.I),
            re.compile(r"\bzf\s+(?:said|announced|announces|reported|unveiled|revealed|unveils|develops|develop|presents)\b", re.I),
        ],
    },
}


# ---------------------------------------------------------------------------
# Disambiguation & Entity Resolution Helpers
# ---------------------------------------------------------------------------

def contains_alias(text: str, alias: str, raw_text: str = "") -> bool:
    """Detect alias presence with proper word boundaries and disambiguation."""
    if not alias:
        return False
    alias_lower = alias.lower()
    if re.search(r"[^a-zA-Z0-9\s\-._/]", alias):
        has_match = alias_lower in text.lower()
    else:
        pattern = rf"(?<![A-Za-z0-9]){re.escape(alias_lower)}(?![A-Za-z0-9])"
        has_match = re.search(pattern, text.lower()) is not None

    if not has_match:
        return False

    # Disambiguate common/short words
    if alias_lower in COMMON_WORD_DISAMBIGUATION:
        rules = COMMON_WORD_DISAMBIGUATION[alias_lower]
        combined = f"{text} {raw_text}"

        # 1. If positive pattern matches, it's definitely the brand
        if any(pat.search(combined) for pat in rules["positive"]):
            return True

        # 2. If negative pattern matches, it's NOT the brand
        if any(pat.search(combined) for pat in rules["negative"]):
            return False

        # 3. For short 2-letter words (gm, zf) or ambiguous words, check uppercase boundary
        if alias_lower in {"gm", "zf", "seat", "mini", "ram", "lotus"}:
            if raw_text and re.search(rf"\b{re.escape(alias.upper())}\b", raw_text):
                return True
            return False

    return True


def canonical_entity(name_or_alias: str | None) -> str | None:
    """Return canonical entity identifier (lowercase id) for a name or alias."""
    if not name_or_alias:
        return None
    cleaned = name_or_alias.strip().lower()
    return CANONICAL_ENTITY_MAP.get(cleaned)


def canonical_entity_name(name_or_alias: str | None) -> str | None:
    """Return canonical display name (e.g. 'Audi', 'Mercedes-Benz') for a name or alias."""
    cid = canonical_entity(name_or_alias)
    if not cid:
        return None
    defn = ENTITY_BY_ID.get(cid)
    return defn.canonical_name if defn else cid.title()


def parent_group(entity_or_name: str | None) -> str | None:
    """Return parent corporate group for a canonical entity or alias."""
    if not entity_or_name:
        return None
    cleaned = entity_or_name.strip().lower()
    if cleaned in PARENT_GROUPS:
        return PARENT_GROUPS[cleaned]
    can = CANONICAL_ENTITY_MAP.get(cleaned)
    if can and can in PARENT_GROUPS:
        return PARENT_GROUPS[can]
    return None


def extract_canonical_entities(article: Article) -> set[str]:
    """Extract canonical brand/legal entities (IDs) for event clustering and guards.

    Inspects title, tags, and excerpt as primary evidence.
    Falls back to bounded content (first 1500 chars) only if no entities found.
    Excludes media/institution publishers (e.g. WardsAuto, Reuters) from contaminating article entities.
    """
    found: set[str] = set()
    # Primary text: title, tags, excerpt (explicit subject of the article)
    primary_text = f"{article.title} {' '.join(article.tags)} {article.excerpt or ''}"

    # If it is an official OEM newsroom/press release, we can also check the official publisher/source
    if article.is_official or article.source_type == "official":
        primary_text = f"{primary_text} {article.source} {article.publisher or ''}"

    sorted_aliases = sorted(CANONICAL_ENTITY_MAP.keys(), key=lambda k: len(k), reverse=True)
    for alias in sorted_aliases:
        if contains_alias(primary_text, alias, raw_text=primary_text):
            found.add(CANONICAL_ENTITY_MAP[alias])

    # Fallback: if no entities found in title/tags/excerpt, check bounded content[:1500]
    if not found and article.content:
        bounded_content = article.content[:1500]
        for alias in sorted_aliases:
            if contains_alias(bounded_content, alias, raw_text=bounded_content):
                found.add(CANONICAL_ENTITY_MAP[alias])

    # Fallback: if still not found, check pre-extracted article.entities
    if not found and article.entities:
        for ent in article.entities:
            can = canonical_entity(ent)
            if can:
                found.add(can)

    # Filter out pure media/publishing institution entities (e.g. WardsAuto, Automotive News)
    # from being considered as event participants/subjects, unless title explicitly discusses them.
    title_lower = article.title.lower()
    filtered: set[str] = set()
    for ent_id in found:
        if ent_id in {"wardsauto", "automotive_news"}:
            if ent_id in title_lower or CANONICAL_ENTITY_MAP.get(ent_id) in title_lower:
                filtered.add(ent_id)
        else:
            filtered.add(ent_id)

    return filtered


def extract_parent_groups(article: Article, entities: set[str] | None = None) -> set[str]:
    """Extract parent corporate groups as weak contextual signals."""
    groups: set[str] = set()
    if entities is None:
        entities = extract_canonical_entities(article)
    for ent in entities:
        grp = parent_group(ent)
        if grp:
            groups.add(grp)

    # Check title, excerpt and official sources for explicit group mentions
    source_text = f" {article.source}" if (article.is_official or article.source_type == "official") else ""
    combined = f"{article.title}{source_text} {article.excerpt or ''} {' '.join(article.entities)}".lower()
    for grp_name in set(PARENT_GROUPS.values()):
        if grp_name.lower() in combined:
            groups.add(grp_name)
    return groups


# ---------------------------------------------------------------------------
# High-Precision AI Topic Detection
# ---------------------------------------------------------------------------

AI_MULTI_WORD_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bartificial\s+intelligence\b", re.I),
    re.compile(r"\bgenerative\s+ai\b", re.I),
    re.compile(r"\bgenai\b", re.I),
    re.compile(r"\blarge\s+language\s+models?\b", re.I),
    re.compile(r"\bllms?\b", re.I),
    re.compile(r"\bfoundation\s+models?\b", re.I),
    re.compile(r"\bneural\s+networks?\b", re.I),
    re.compile(r"\bcomputer\s+vision\b", re.I),
    re.compile(r"\bmachine\s+learning\b", re.I),
    re.compile(r"\bdeep\s+learning\b", re.I),
    re.compile(r"\bai[- ](?:powered|driven|assistant|agent|platform|chip|chips|model|models|cockpit|system|systems)\b", re.I),
    re.compile(r"(?<![A-Za-z0-9])a\.i\.(?![A-Za-z0-9])", re.I),
    # Korean AI terms
    re.compile(r"(?:인공지능|머신러닝|딥러닝)"),
]

# Strict uppercase AI with alphanumeric boundary protection
AI_UPPERCASE_PATTERN = re.compile(r"(?<![A-Za-z0-9])AI(?![A-Za-z0-9])")



def matches_ai_topic(text: str) -> bool:
    """Determine whether text discusses Artificial Intelligence.

    Guarantees that bare substring 'ai' inside common words like:
    said, again, daily, available, maintenance, failure, train, Daimler, Asia, etc.
    will strictly NEVER trigger a match.
    """
    if not text:
        return False

    # Check uppercase \bAI\b (case-sensitive)
    if AI_UPPERCASE_PATTERN.search(text):
        return True

    # Check multi-word and compound patterns
    for pat in AI_MULTI_WORD_PATTERNS:
        if pat.search(text):
            return True

    return False

