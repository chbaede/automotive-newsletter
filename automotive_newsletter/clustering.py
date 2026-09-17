from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable

from .models import Article, Event, EventArticle

# Model patterns for negative guard disambiguation
MODEL_PATTERNS = [
    re.compile(r"\bmodel\s+([3ysx]|[\d]+)\b", re.IGNORECASE),
    re.compile(r"\b(cybertruck|cybercab|semi|roadster)\b", re.IGNORECASE),
    re.compile(r"\bid\.?\s*([1-9]|buzz)\b", re.IGNORECASE),
    re.compile(r"\bioniq\s+([56789])\b", re.IGNORECASE),
    re.compile(r"\bev\s*([1-9])\b", re.IGNORECASE),
    re.compile(r"\b(taycan|macan|panamera|cayenne)\b", re.IGNORECASE),
    re.compile(r"\b(mach-e|f[- ]?150(?:\s+lightning)?)\b", re.IGNORECASE),
    re.compile(r"\b(i[34578]|ix[13]?|ix)\b", re.IGNORECASE),
    re.compile(r"\b(eq[abces]|eqe|eqs)\b", re.IGNORECASE),
]

# Generation & Standard patterns
GEN_PATTERNS = [
    re.compile(r"\b(?:gen|generation)\s*([0-9]+)\b", re.IGNORECASE),
    re.compile(r"\beuro\s*([0-9]+[a-z]?)\b", re.IGNORECASE),
    re.compile(r"\btier\s*([0-9]+)\b", re.IGNORECASE),
]

# Recall defect categories
RECALL_DEFECT_TERMS = {
    "airbag": ["airbag", "air bag", "takata", "inflator"],
    "steering": ["steering", "power steering", "tie rod", "steering loss", "steering defect"],
    "brake": ["brake", "braking", "abs", "caliper", "brake line", "brake defect"],
    "battery_fire": ["battery fire", "thermal runaway", "short circuit", "fire risk", "battery defect"],
    "software_glitch": ["software glitch", "software defect", "software bug", "software recall", "software issue", "display blank", "reboot", "infotainment crash"],
    "door_latch": ["door latch", "door open", "hood latch"],
    "seatbelt": ["seatbelt", "buckle", "seat belt"],
    "suspension": ["suspension", "ball joint", "control arm"],
}

from .entity_registry import (
    CANONICAL_ENTITY_MAP,
    COMMON_WORD_DISAMBIGUATION,
    OEM_ENTITIES,
    PARENT_GROUPS,
    TECH_SUPPLIER_ENTITIES,
    canonical_entity,
    contains_alias as _contains_alias,
    extract_canonical_entities,
    extract_parent_groups,
    parent_group,
)

ENTITY_ALIASES = CANONICAL_ENTITY_MAP


# Multi-Tiered Event Action Themes (Strong / Medium / Weak)
THEME_TIERS: dict[str, dict[str, list[str]]] = {
    "strong": {
        "restructuring": [
            "mass layoff", "plant closure", "factory closure", "workforce reduction",
            "job cuts", "downsizing", "restructuring program", "closing plant", "cut jobs",
        ],
        "recall": [
            "safety recall", "recall campaign", "nhtsa recall", "kba recall",
            "recalls vehicles", "recalling vehicles", "recalled", "safety probe",
        ],
        "partnership_jv": [
            "joint venture", "strategic partnership", "mou", "consortium", "jointly develop",
            "strategic collaboration", "team up", "teams up",
        ],
        "investment_plant": [
            "gigafactory", "battery plant", "new factory", "plant expansion", "billion investment",
            "million investment", "groundbreaking", "build factory", "build plant", "battery facility",
        ],
        "platform_unveil": [
            "world premiere", "concept car", "debuts platform", "reveals next-gen", "unveils new",
            "global debut", "unveiled",
        ],
        "earnings_financial": [
            "operating profit", "fiscal year", "revenue beats", "revenue misses", "guidance cut",
            "quarterly profit", "quarterly earnings", "net profit", "q1 earnings", "q2 earnings",
            "q3 earnings", "q4 earnings", "operating margin",
        ],
        "leadership_exec": [
            "ceo resigns", "names new ceo", "appoints ceo", "steps down as ceo", "board chairman",
            "chief executive",
        ],
        "cybersecurity_incident": [
            "ransomware attack", "data breach", "security vulnerability", "cyber attack", "hackers breach",
        ],
        "software_platform": [
            "software-defined vehicle", "sdv architecture", "vehicle os", "zonal architecture",
            "ota update", "over-the-air update", "over the air update", "infotainment platform",
            "super cruise", "hands-free driving", "driver assistance", "software architecture",
            "vehicle software",
        ],
    },
    "medium": {
        "restructuring": ["restructur", "cut", "layoff", "job cut", "closur", "plant clos", "reorganiz", "downsiz", "european oper"],
        "recall": ["recall", "recalls", "defect", "investig", "probe", "nhtsa", "inquiry"],
        "partnership_jv": ["joint ventur", "partnership", "collaborat", "allianc", "team up", "partner", "joint"],
        "investment_plant": ["invest", "gigafactory", "plant build", "expans", "spending", "facility", "commit"],
        "platform_unveil": ["unveil", "reveal", "debut", "concept", "premier"],
        "earnings_financial": ["earn", "profit", "revenu", "q1", "q2", "q3", "q4", "margin", "guidanc", "loss"],
        "leadership_exec": ["ceo", "appoint", "step down", "resign", "execut", "chief"],
        "cybersecurity_incident": ["hack", "cyber", "vulnerabilit", "ransomwar", "breach"],
        "software_platform": ["sdv", "autosar", "ota", "over-the-air", "over the air", "operating system", "vehicle os", "middleware", "infotainment", "super cruise", "driver assistance"],
    },
    "weak": {
        "restructuring": ["loss"],
        "investment_plant": ["plant"],
        "leadership_exec": ["leader"],
        "software_platform": ["software"],
    },
}

# Preserve EVENT_ACTION_THEMES for backwards compatibility
EVENT_ACTION_THEMES: dict[str, list[str]] = {
    theme: sorted(list(set(THEME_TIERS["strong"].get(theme, []) + THEME_TIERS["medium"].get(theme, []))))
    for theme in set(list(THEME_TIERS["strong"].keys()) + list(THEME_TIERS["medium"].keys()))
}

ACRONYM_THEMES: set[str] = {"mou", "ota", "sdv", "q1", "q2", "q3", "q4", "ceo"}

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to", "for", "with",
    "by", "from", "of", "about", "as", "into", "through", "after", "over", "between",
    "out", "against", "during", "without", "before", "under", "around", "among",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "shall", "should", "may", "might", "must", "can",
    "could", "it", "its", "this", "that", "these", "those", "new", "says", "said",
    "amid", "report", "reports", "update", "updates"
}


def extract_companies(article: Article) -> set[str]:
    """Extract canonical brand/legal entity identifiers for an article."""
    return extract_canonical_entities(article)


def extract_model_identifiers(text: str) -> set[str]:
    """Extract specific vehicle model tokens."""
    text_lower = text.lower()
    models = set()
    for pattern in MODEL_PATTERNS:
        for match in pattern.findall(text_lower):
            if isinstance(match, tuple):
                models.update(m.strip() for m in match if m.strip())
            elif isinstance(match, str) and match.strip():
                models.add(match.strip())
    return models


def extract_generation_identifiers(text: str) -> set[str]:
    """Extract generation or regulatory standard tokens."""
    text_lower = text.lower()
    gens = set()
    for pattern in GEN_PATTERNS:
        for match in pattern.findall(text_lower):
            if isinstance(match, str) and match.strip():
                gens.add(match.strip())
    return gens


RECALL_CONTEXT_NO_RECALL = "NO_RECALL"
RECALL_CONTEXT_RECALL = "RECALL"
RECALL_CONTEXT_INVESTIGATION = "INVESTIGATION"
RECALL_CONTEXT_RECALL_AND_INVESTIGATION = "RECALL_AND_INVESTIGATION"

RECALL_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brecalls?\b", re.I),
    re.compile(r"\brecalling\b", re.I),
    re.compile(r"\brecalled\b", re.I),
    re.compile(r"\bsafety recall\b", re.I),
]

INVESTIGATION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\binvestigat(?:e|es|ed|ing|ion|ions)\b", re.I),
    re.compile(r"\bprobes?\b", re.I),
    re.compile(r"\bprobing\b", re.I),
    re.compile(r"\bprobed\b", re.I),
    re.compile(r"\binquir(?:y|ies)\b", re.I),
    re.compile(r"\bpreliminary evaluation\b", re.I),
    re.compile(r"\bengineering analysis\b", re.I),
]


def detect_recall_context(text: str) -> str:
    """Detect whether text describes a recall, an investigation, both, or neither."""
    has_recall = any(p.search(text) for p in RECALL_PATTERNS)
    has_investigation = any(p.search(text) for p in INVESTIGATION_PATTERNS)
    if has_recall and has_investigation:
        return RECALL_CONTEXT_RECALL_AND_INVESTIGATION
    if has_recall:
        return RECALL_CONTEXT_RECALL
    if has_investigation:
        return RECALL_CONTEXT_INVESTIGATION
    return RECALL_CONTEXT_NO_RECALL


def extract_recall_defects(text: str) -> set[str]:
    """Extract specific recall defect keywords only if text indicates an actual recall context."""
    ctx = detect_recall_context(text)
    if ctx not in (RECALL_CONTEXT_RECALL, RECALL_CONTEXT_RECALL_AND_INVESTIGATION):
        return set()
    text_lower = text.lower()
    defects = set()
    for defect_key, terms in RECALL_DEFECT_TERMS.items():
        if any(term in text_lower for term in terms):
            defects.add(defect_key)
    return defects


def _matches_theme_term(term: str, text: str) -> bool:
    """Match theme keyword with word boundary protection for acronyms."""
    if term in ACRONYM_THEMES:
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
    return re.search(rf"\b{re.escape(term)}", text) is not None


def extract_event_themes(text: str) -> set[str]:
    """Extract strong and medium automotive event action themes."""
    text_lower = text.lower()
    themes: set[str] = set()
    for tier in ("strong", "medium"):
        for theme_name, terms in THEME_TIERS[tier].items():
            if any(_matches_theme_term(term, text_lower) for term in terms):
                themes.add(theme_name)
    return themes


def extract_event_themes_detailed(text: str) -> dict[str, set[str]]:
    """Extract themes categorized by confidence tier (strong, medium, weak)."""
    text_lower = text.lower()
    res: dict[str, set[str]] = {"strong": set(), "medium": set(), "weak": set()}
    for tier in ("strong", "medium", "weak"):
        for theme_name, terms in THEME_TIERS[tier].items():
            if any(_matches_theme_term(term, text_lower) for term in terms):
                res[tier].add(theme_name)
    return res


EVENT_SIMILARITY_THRESHOLD: float = 0.60
EVENT_MEMBER_THRESHOLD: float = 0.65


def stem_token(word: str) -> str:
    """Lightweight deterministic stemmer for English automotive terms."""
    w = word.lower().strip()
    if len(w) <= 3:
        return CANONICAL_ENTITY_MAP.get(w, w)
    # Canonical automotive term equivalences
    if w in {"software", "sw", "sdv", "sdvs"}:
        return "sdv"
    if w in {"partner", "partners", "partnership", "partnerships", "partnering"}:
        return "partner"
    if w in {"collaborate", "collaborates", "collaboration", "collaborating"}:
        return "partner"
    if w in {"invest", "invests", "investing", "investment", "investments"}:
        return "invest"
    if w in {"restructure", "restructures", "restructuring", "restructurings"}:
        return "restructur"
    if w in {"recall", "recalls", "recalling"}:
        return "recall"
    if w in {"platform", "platforms"}:
        return "platform"
    if w in {"architecture", "architectures"}:
        return "architectur"
    if w in {"electric", "electrification", "ev", "evs", "bev", "bevs"}:
        return "electr"
    if w in {"autonomous", "autonomy", "self-driving"}:
        return "autonom"
    if w in {"supplier", "suppliers", "supply", "supplies"}:
        return "suppl"
    if w in {"halt", "halts", "halting", "stop", "stops", "stopping"}:
        return "halt"

    for suffix in ("tions", "tion", "ments", "ment", "erships", "ership", "ships", "ship", "ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[: -len(suffix)]
            break
    return CANONICAL_ENTITY_MAP.get(w, w)


def extract_stemmed_tokens(text: str) -> set[str]:
    """Tokenize and stem alphanumeric words, filtering stopwords."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {
        stem_token(w)
        for w in words
        if w not in STOP_WORDS and len(w) > 1 and not w.isdigit()
    }


EXPLICIT_JOINT_PHRASES: set[str] = {
    "joint",
    "jointly",
    "together",
    "joint venture",
    "co-development",
    "co-develop",
    "jointly develop",
    "jointly developed",
    "jointly announce",
    "jointly announced",
    "joint announcement",
    "shared platform",
    "common platform",
    "unified platform",
    "unified software platform",
    "shared software platform",
    "common software platform",
    "group-wide platform",
    "group-wide software platform",
    "group-wide unified platform",
    "collaborative development",
    "same program",
    "same restructuring program",
    "same recall campaign",
    "same group-wide program",
    "group-wide",
    "groupwide",
    "parent company initiative",
}

JOINT_EVENT_TERMS: set[str] = EXPLICIT_JOINT_PHRASES

# Explicit cross-brand subject construction patterns for sister brands under shared parent groups
SISTER_BRAND_SUBJECT_PATTERNS: list[re.Pattern] = [
    # Volkswagen Group
    re.compile(r"\b(?:volkswagen|vw|audi|porsche)\s+(?:and|&|\+|with|,)\s+(?:both\s+)?(?:volkswagen|vw|audi|porsche|seat|skoda)\b", re.I),
    re.compile(r"\b(?:audi|porsche|seat|skoda)\s+(?:and|&|\+|with|,)\s+(?:both\s+)?(?:volkswagen|vw|audi|porsche)\b", re.I),
    re.compile(r"\bboth\s+(?:volkswagen|vw|audi|porsche)\s+and\s+(?:audi|porsche|seat|skoda)\b", re.I),
    re.compile(r"\bboth\s+(?:audi|porsche|seat|skoda)\s+and\s+(?:volkswagen|vw|audi|porsche)\b", re.I),
    # Hyundai Motor Group
    re.compile(r"\bhyundai\s+(?:and|&|\+|with|,)\s+(?:both\s+)?(?:kia|genesis)\b", re.I),
    re.compile(r"\bkia\s+(?:and|&|\+|with|,)\s+(?:both\s+)?(?:hyundai|genesis)\b", re.I),
    re.compile(r"\bboth\s+hyundai\s+and\s+kia\b", re.I),
    re.compile(r"\bboth\s+kia\s+and\s+hyundai\b", re.I),
    # BMW Group
    re.compile(r"\bbmw\s+(?:and|&|\+|with|,)\s+(?:both\s+)?(?:mini|rolls[- ]royce)\b", re.I),
    re.compile(r"\bmini\s+(?:and|&|\+|with|,)\s+(?:both\s+)?(?:bmw|rolls[- ]royce)\b", re.I),
    re.compile(r"\bboth\s+bmw\s+and\s+mini\b", re.I),
    # Toyota Group
    re.compile(r"\btoyota\s+(?:and|&|\+|with|,)\s+(?:both\s+)?lexus\b", re.I),
    re.compile(r"\blexus\s+(?:and|&|\+|with|,)\s+(?:both\s+)?toyota\b", re.I),
    re.compile(r"\bboth\s+toyota\s+and\s+lexus\b", re.I),
    # Stellantis
    re.compile(r"\b(?:peugeot|citroen|fiat|jeep|chrysler|dodge|ram)\s+(?:and|&|\+|with|,)\s+(?:both\s+)?(?:peugeot|citroen|fiat|jeep|chrysler|dodge|ram)\b", re.I),
]

# Explicit parent-program construction patterns
PARENT_PROGRAM_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(?:volkswagen|vw)\s+group\b.*?\b(?:covers?|affect(?:s|ed|ing)?|appl(?:ies|y)|includes?)\b.*?\b(?:both\s+)?(?:volkswagen|vw|audi|porsche)\b", re.I),
    re.compile(r"\bhyundai(?:\s+motor)?\s+group\b.*?\b(?:covers?|affect(?:s|ed|ing)?|appl(?:ies|y)|includes?)\b.*?\b(?:both\s+)?(?:hyundai|kia)\b", re.I),
    re.compile(r"\b(?:the\s+)?same\s+group[- ]wide\s+(?:program|initiative|restructuring|recall)\b", re.I),
    re.compile(r"\bgroup[- ]wide\s+(?:unified\s+|shared\s+)?(?:program|initiative|restructuring|recall|platform|software|architecture)\b", re.I),
    re.compile(r"\bgroup[- ]wide\s+(?:program|initiative|restructuring|recall|platform)\s+(?:covers?|affect(?:s|ed|ing)?|appl(?:ies|y)|includes?|for)\b", re.I),
    re.compile(r"\b(?:the\s+)?same\s+recall\s+campaign\s+(?:covers?|affect(?:s|ed|ing)?|appl(?:ies|y)|for)\s+both\b", re.I),
    re.compile(r"\b(?:included\s+in|part\s+of)\s+the\s+same\s+group[- ]wide\s+(?:program|initiative|restructuring)\b", re.I),
    re.compile(r"\b(?:covers?|affect(?:s|ed|ing)?|appl(?:ies|y)|includes?)\s+both\s+(?:brands|automakers|carmakers)\b", re.I),
    re.compile(r"\b(?:covers?|affect(?:s|ed|ing)?|appl(?:ies|y)|includes?)\s+both\s+\w+\s+and\s+\w+\b", re.I),
]

SHARED_INITIATIVE_PHRASES: set[str] = {
    "same program",
    "same restructuring program",
    "same recall campaign",
    "parent company initiative",
    "group-wide initiative",
    "group-wide program",
    "group-wide restructuring",
    "group-wide platform",
    "group-wide software platform",
    "group-wide unified platform",
    "the same joint program",
}


def has_explicit_joint_event_signal(
    a1: Article | None = None,
    a2: Article | None = None,
    f1: ArticleClusteringFeatures | None = None,
    f2: ArticleClusteringFeatures | None = None,
    text1: str | None = None,
    text2: str | None = None,
) -> bool:
    """Determine whether two articles share explicit joint-event, cross-brand, or parent-program signals.

    SAME PARENT GROUP ALONE IS NEVER SUFFICIENT.
    Generic event themes (restructuring, platform, recall, software, SDV) without explicit
    joint evidence are strictly rejected.

    Requires explicit evidence that the brands participate in the same initiative:
    A. Explicit joint phrases (e.g. 'jointly announce', 'joint venture', 'shared platform')
    B. Explicit cross-brand subject construction WITH joint phrase (e.g. 'Volkswagen and Audi jointly...')
    C. Explicit parent-program construction (e.g. 'Volkswagen Group restructuring covers VW and Audi')
    """
    t1 = text1 if text1 is not None else ((f1.text if f1 else (extract_clustering_features(a1).text if a1 else "")).lower())
    t2 = text2 if text2 is not None else ((f2.text if f2 else (extract_clustering_features(a2).text if a2 else "")).lower())

    combined = f"{t1} {t2}"

    # Check C: Explicit parent-program construction
    if any(p.search(t1) or p.search(t2) for p in PARENT_PROGRAM_PATTERNS):
        return True

    # Check B: Explicit cross-brand subject construction WITH joint phrase
    has_cross_brand = any(p.search(t1) or p.search(t2) for p in SISTER_BRAND_SUBJECT_PATTERNS)
    has_joint_phrase = any(term in t1 or term in t2 for term in EXPLICIT_JOINT_PHRASES)

    if has_cross_brand and (has_joint_phrase or any(p.search(combined) for p in PARENT_PROGRAM_PATTERNS)):
        return True

    # Check A: Both articles explicitly describe the same joint initiative
    if any(phrase in t1 for phrase in SHARED_INITIATIVE_PHRASES) and any(phrase in t2 for phrase in SHARED_INITIATIVE_PHRASES):
        return True
    if any(phrase in t1 or phrase in t2 for phrase in SHARED_INITIATIVE_PHRASES) and has_joint_phrase:
        return True

    return False


# Rigid Hard Numeric Identifiers
VERSION_PATTERN = re.compile(
    r"\b(?:software\s+)?(?:version|ver\.?|update|release|v)\s*[-_]?\s*(\d+(?:\.\d+)*)\b",
    re.IGNORECASE,
)
ENGINE_CYLINDER_PATTERN = re.compile(
    r"\bv[-_]?(6|8|10|12|16)\s*(?:cylinder|engine|biturbo|twin[- ]turbo|motor|powertrain)\b",
    re.IGNORECASE,
)
GEN_HARD_PATTERN = re.compile(
    r"\b(?:gen|generation)\s*[-_]?\s*(\d+)\b",
    re.IGNORECASE,
)
EURO_HARD_PATTERN = re.compile(
    r"\beuro\s*[-_]?\s*(\d+[a-z]?)\b",
    re.IGNORECASE,
)
NHTSA_CAMPAIGN_PATTERN = re.compile(
    r"\b(\d{2}[vVecEtT])[-_]?(\d{3,4})\b",
    re.IGNORECASE,
)


def _normalize_version_num(num_str: str) -> str:
    """Normalize version numbers e.g. '12.0' -> '12', '12' -> '12', '12.3' -> '12.3'."""
    parts = num_str.split(".")
    if len(parts) == 2 and parts[1] == "0":
        return parts[0]
    return num_str


def extract_hard_numeric_identifiers(text: str) -> set[str]:
    """Extract normalized rigid identifiers like software versions, generations, or NHTSA campaign IDs.

    Sequential phrases (phase, stage, part, step, round) remain soft contextual numeric attributes.
    """
    results: set[str] = set()
    text_lower = text.lower()

    # 1. Engine cylinder configuration check (e.g. V8 engine vs V12 engine)
    engine_matches = set()
    for m in ENGINE_CYLINDER_PATTERN.finditer(text_lower):
        results.add(f"engine:v{m.group(1)}")
        engine_matches.add(m.start())

    # 2. Software versions & updates (v12, version 12, ver 12, update 12 -> version:12)
    for m in VERSION_PATTERN.finditer(text_lower):
        if m.start() in engine_matches:
            continue
        prefix_slice = text_lower[max(0, m.start() - 15) : m.start()]
        if "twin-turbo" in prefix_slice or "biturbo" in prefix_slice:
            continue
        norm_v = _normalize_version_num(m.group(1))
        results.add(f"version:{norm_v}")

    # 3. Generation numbers (generation 2, gen 2, gen2 -> generation:2)
    for m in GEN_HARD_PATTERN.finditer(text_lower):
        results.add(f"generation:{m.group(1)}")

    # 4. Euro emissions standards (Euro 6, Euro-6, Euro 7 -> euro:6, euro:7)
    for m in EURO_HARD_PATTERN.finditer(text_lower):
        results.add(f"euro:{m.group(1)}")

    # 5. NHTSA recall campaign IDs (24V-123, 24V123 -> campaign:24v123)
    for m in NHTSA_CAMPAIGN_PATTERN.finditer(text_lower):
        results.add(f"campaign:{m.group(1)}{m.group(2)}")

    return results


def extract_quantity_numbers(text: str) -> set[str]:
    """Extract normalized financial amounts and production/recall volumes.

    Ignores model codes (e.g. F-150), software versions, campaign IDs,
    Euro standards, and 4-digit calendar years.
    """
    text_clean = text.lower()
    text_clean = NHTSA_CAMPAIGN_PATTERN.sub(" ", text_clean)
    text_clean = EURO_HARD_PATTERN.sub(" ", text_clean)
    text_clean = VERSION_PATTERN.sub(" ", text_clean)
    text_clean = GEN_HARD_PATTERN.sub(" ", text_clean)
    text_clean = re.sub(r"\b[a-z]{1,4}[-.]?\d+[a-z]?\b", " ", text_clean)
    text_clean = re.sub(r"\b(?:19|20)\d{2}\b", " ", text_clean)

    quantities: set[str] = set()
    for m in re.finditer(r"\$\s*(\d+(?:\.\d+)?)\s*(b|billion|m|million)?\b", text_clean):
        val = m.group(1)
        unit = (m.group(2) or "").lower()
        if unit.startswith("b"):
            quantities.add(f"${val}b")
        elif unit.startswith("m"):
            quantities.add(f"${val}m")
        else:
            quantities.add(f"${val}")

    for m in re.finditer(r"\b(\d{1,3}(?:,\d{3})+)\b", text_clean):
        norm = m.group(1).replace(",", "")
        quantities.add(norm)

    for m in re.finditer(r"\b(\d+)\b", text_clean):
        num_str = m.group(1)
        if len(num_str) >= 4 and int(num_str) >= 1000:
            quantities.add(num_str)

    return quantities


@dataclass(slots=True)
class ArticleClusteringFeatures:
    """Precomputed article features for high-performance deterministic clustering."""
    text: str
    models: set[str]
    gens: set[str]
    defects: set[str]
    recall_context: str
    hard_nums: set[str]
    canonical_entities: set[str]
    parent_groups: set[str]
    oems: set[str]
    tech_suppliers: set[str]
    tokens: set[str]
    themes: set[str]
    nums: set[str]
    topics: set[str]


def extract_clustering_features(article: Article) -> ArticleClusteringFeatures:
    """Extract and precompute all article features required for clustering and similarity.

    Evidence Priority:
    1. Article title
    2. Original extracted article content (bounded to first 1500 chars)
    3. RSS original summary / excerpt
    4. Explicit deterministic tags / topics
    (AI-generated summary is strictly NEVER used as clustering evidence).
    """
    evidence_parts = [article.title]
    if article.excerpt:
        evidence_parts.append(article.excerpt)
    if article.content:
        evidence_parts.append(article.content[:1500])
    if article.tags:
        evidence_parts.append(" ".join(article.tags))
    text = " ".join(evidence_parts)

    canonical = extract_canonical_entities(article)
    parents = extract_parent_groups(article, entities=canonical)
    return ArticleClusteringFeatures(
        text=text,
        models=extract_model_identifiers(text),
        gens=extract_generation_identifiers(text),
        defects=extract_recall_defects(text),
        recall_context=detect_recall_context(text),
        hard_nums=extract_hard_numeric_identifiers(article.title),
        canonical_entities=canonical,
        parent_groups=parents,
        oems=canonical & OEM_ENTITIES,
        tech_suppliers=canonical & TECH_SUPPLIER_ENTITIES,
        tokens=extract_stemmed_tokens(article.title),
        themes=extract_event_themes(text),
        nums=extract_quantity_numbers(article.title),
        topics={t.lower() for t in article.topics},
    )


def calculate_event_similarity(
    a1: Article,
    a2: Article,
    window_hours: float = 72.0,
    f1: ArticleClusteringFeatures | None = None,
    f2: ArticleClusteringFeatures | None = None,
) -> float:
    """Calculate deterministic pairwise similarity between two articles (0.0 to 1.0).

    Similarity Ranges:
    * 0.90 ~ 1.00: Virtually identical event (same entity, same theme, high token overlap/syndication)
    * 0.75 ~ 0.89: Very strong candidate (same entity, common theme, high containment)
    * 0.60 ~ 0.74: Similar, needs caution (same entity, moderate overlap)
    * < 0.60: Generally separate event
    """
    if a1.article_id and a1.article_id == a2.article_id:
        return 1.0
    if a1.canonical_url and a1.canonical_url == a2.canonical_url:
        return 1.0
    if a1.url and a1.url == a2.url:
        return 1.0

    # 1. Temporal window check
    if a1.published_at and a2.published_at:
        diff_hours = abs((a1.published_at - a2.published_at).total_seconds()) / 3600.0
        if diff_hours > window_hours:
            return 0.0

    if f1 is None:
        f1 = extract_clustering_features(a1)
    if f2 is None:
        f2 = extract_clustering_features(a2)

    # 2. Hard Negative Guards
    # Guard A: Model identifiers collision (e.g. Model 3 vs Model Y)
    m1 = f1.models
    m2 = f2.models
    if m1 and m2 and m1.isdisjoint(m2):
        return 0.0

    # Guard B: Generation / standard collision (e.g. Euro 6 vs Euro 7, Gen 2 vs Gen 3)
    g1 = f1.gens
    g2 = f2.gens
    if g1 and g2 and g1.isdisjoint(g2):
        return 0.0

    # Guard C1: Recall vs Pure Investigation collision
    # (e.g. NHTSA investigates Tesla vs Tesla recalls vehicles)
    ctx1 = f1.recall_context
    ctx2 = f2.recall_context
    if (ctx1 == RECALL_CONTEXT_INVESTIGATION and ctx2 == RECALL_CONTEXT_RECALL) or \
       (ctx1 == RECALL_CONTEXT_RECALL and ctx2 == RECALL_CONTEXT_INVESTIGATION):
        return 0.0

    # Guard C2: Recall defect collision (e.g. Airbag vs Brake recall)
    d1 = f1.defects
    d2 = f2.defects
    if d1 and d2 and d1.isdisjoint(d2):
        return 0.0

    # Guard D: Brand / legal entity mismatch with parent group context and cross-OEM separation
    c1 = f1.canonical_entities
    c2 = f2.canonical_entities
    p1 = f1.parent_groups
    p2 = f2.parent_groups

    oem1 = f1.oems
    oem2 = f2.oems

    tokens1 = f1.tokens
    tokens2 = f2.tokens
    inter = tokens1 & tokens2
    union = tokens1 | tokens2
    jaccard = len(inter) / max(1, len(union))
    containment = len(inter) / max(1, min(len(tokens1), len(tokens2)))
    themes1 = f1.themes
    themes2 = f2.themes
    has_theme_overlap = bool(themes1 & themes2)

    # Cross-OEM Guard:
    # If both articles have known OEMs, but have NO common OEM (disjoint):
    # e.g. Toyota x Nvidia vs Mercedes x Nvidia, or Ford brake vs GM brake
    if oem1 and oem2 and oem1.isdisjoint(oem2):
        if not (p1 and p2 and (p1 & p2)):
            return 0.0

        # Distinct brands under the same parent group (e.g. Hyundai vs Kia, VW vs Audi):
        # MUST remain separate events unless there is explicit joint-event evidence
        # AND shared theme + substantial token overlap.
        if not has_explicit_joint_event_signal(a1, a2, f1, f2):
            return 0.0
        has_strong_joint_signal = (
            has_theme_overlap
            and len(inter) >= 3
            and (jaccard >= 0.40 or containment >= 0.60)
        )
        if not has_strong_joint_signal:
            return 0.0

    if c1 and c2 and c1.isdisjoint(c2):
        # If they don't share a parent group, hard reject
        if not (p1 and p2 and (p1 & p2)):
            return 0.0

        if not has_explicit_joint_event_signal(a1, a2, f1, f2):
            return 0.0
        has_strong_joint_signal = (
            has_theme_overlap
            and len(inter) >= 3
            and (jaccard >= 0.40 or containment >= 0.60)
        )
        if not has_strong_joint_signal:
            return 0.0

    # Sister-brand Joint vs Standalone Guard:
    # If one article reports a multi-brand joint initiative (>= 2 sister brands under parent group P)
    # and the other only reports a single brand under P without explicit joint signal,
    # they must remain separate events.
    if p1 and p2 and (p1 & p2):
        for pg in (p1 & p2):
            sisters1 = {o for o in oem1 if parent_group(o) == pg}
            sisters2 = {o for o in oem2 if parent_group(o) == pg}
            if len(sisters1) >= 2 and len(sisters2) == 1:
                if not has_explicit_joint_event_signal(a2, a2, f2, f2):
                    return 0.0
            elif len(sisters2) >= 2 and len(sisters1) == 1:
                if not has_explicit_joint_event_signal(a1, a1, f1, f1):
                    return 0.0

    # Guard D2: Disjoint Tech / Supplier Partner Guard
    # Same or different automakers partnering with distinct tech/supplier partners
    # (e.g. BMW x Qualcomm vs BMW x Nvidia) must NEVER merge.
    tech1 = f1.tech_suppliers
    tech2 = f2.tech_suppliers
    if tech1 and tech2 and tech1.isdisjoint(tech2):
        return 0.0

    # Guard E1: Hard numeric identifiers (software versions like v12 vs v13, campaign IDs)
    hn1 = f1.hard_nums
    hn2 = f2.hard_nums
    if hn1 and hn2 and hn1.isdisjoint(hn2):
        return 0.0

    # Soft numeric attributes mismatch (e.g. 500,000 vs 100,000, $2B vs $5B):
    # Treated as a similarity penalty, not a hard reject
    nums1 = f1.nums
    nums2 = f2.nums
    numeric_penalty = 0.35 if (nums1 and nums2 and nums1.isdisjoint(nums2)) else 0.0

    # Guard F: Action / Theme incompatibility
    # If both have strong/medium, disjoint event action themes (e.g. restructuring vs partnership)
    if themes1 and themes2 and themes1.isdisjoint(themes2):
        collab_themes = {"partnership_jv", "platform_unveil", "software_platform"}
        is_collab_pair = (
            len(c1 & c2) >= 2
            and themes1.issubset(collab_themes)
            and themes2.issubset(collab_themes)
            and (len(inter) >= 2 or containment >= 0.35)
        )
        if not is_collab_pair:
            return 0.0

    has_company_overlap = bool(c1 & c2)

    # 3. Positive Similarity Calculation
    lex = 0.55 * containment + 0.45 * jaccard

    # Match boosts
    num_bonus = 0.04 if (nums1 and nums2 and bool(nums1 & nums2)) else 0.0
    model_bonus = 0.05 if (m1 and m2 and bool(m1 & m2)) else 0.0
    multi_entity_bonus = 0.05 if len(c1 & c2) >= 2 else 0.0
    topics1 = f1.topics
    topics2 = f2.topics
    topic_jaccard = len(topics1 & topics2) / max(1, len(topics1 | topics2)) if (topics1 and topics2) else 0.0
    topic_bonus = 0.03 * topic_jaccard if topic_jaccard > 0 else 0.0

    if has_company_overlap and has_theme_overlap:
        if len(inter) >= 1 or containment >= 0.25:
            score = 0.68 + 0.24 * lex + num_bonus + model_bonus + multi_entity_bonus + topic_bonus - numeric_penalty
            return round(min(0.99, max(0.40, score)), 3)
    elif has_company_overlap:
        # Multi-entity articles (sharing >= 2 specific entities, e.g. OEM + Tech partner)
        # with strong lexical/token overlap:
        if len(c1 & c2) >= 2 and (containment >= 0.40 or len(inter) >= 3):
            score = 0.65 + 0.25 * lex + num_bonus + model_bonus + multi_entity_bonus + topic_bonus - numeric_penalty
            return round(min(0.99, max(0.40, score)), 3)
        # If one article has an explicit action theme and the other does not (single company):
        if bool(themes1 ^ themes2):
            score = 0.35 + 0.30 * lex + num_bonus + model_bonus + topic_bonus - numeric_penalty
            return round(min(0.55, max(0.20, score)), 3)
        elif containment >= 0.40 or len(inter) >= 2:
            score = 0.58 + 0.32 * lex + num_bonus + model_bonus + topic_bonus - numeric_penalty
            return round(min(0.95, max(0.35, score)), 3)
    elif p1 and p2 and (p1 & p2) and has_theme_overlap and (len(inter) >= 3 and (jaccard >= 0.40 or containment >= 0.60)):
        score = 0.65 + 0.30 * lex + num_bonus - numeric_penalty
        return round(min(0.98, max(0.40, score)), 3)
    elif jaccard >= 0.45 or containment >= 0.65:
        score = 0.60 + 0.38 * lex + num_bonus - numeric_penalty
        return round(min(0.98, max(0.40, score)), 3)

    return round(min(0.20, 0.40 * lex), 3)


def are_articles_same_event(
    a1: Article,
    a2: Article,
    window_hours: float = 72.0,
    f1: ArticleClusteringFeatures | None = None,
    f2: ArticleClusteringFeatures | None = None,
) -> tuple[bool, float]:
    """Determine whether two articles describe the same real-world event.

    Returns (is_same_event: bool, similarity: float).
    """
    sim = calculate_event_similarity(a1, a2, window_hours=window_hours, f1=f1, f2=f2)
    is_same = sim >= EVENT_SIMILARITY_THRESHOLD
    return is_same, sim


def check_cluster_coherence(
    cluster: list[Article],
    primary: Article,
    window_hours: float = 72.0,
    features_by_id: dict[int, ArticleClusteringFeatures] | None = None,
) -> tuple[float, list[Article], list[Article]]:
    """Validate cluster coherence against primary and pairwise compatibility.

    Rules:
    * Rule 1: Every member must have similarity >= EVENT_MEMBER_THRESHOLD to primary.
    * Rule 2: Incompatible articles are separated (no pairwise negative guard violations).
    * Rule 3: Calculate cluster coherence score (average similarity to primary).

    Returns:
        (coherence_score, retained_articles, outlier_articles)
    """
    if len(cluster) <= 1:
        return 1.0, list(cluster), []

    retained: list[Article] = [primary]
    outliers: list[Article] = []

    f_primary = features_by_id.get(id(primary)) if features_by_id else None

    # Rule 1: Validate each member against primary article
    candidates = [a for a in cluster if a.article_id != primary.article_id]
    scored_candidates: list[tuple[Article, float]] = []

    for member in candidates:
        f_member = features_by_id.get(id(member)) if features_by_id else None
        sim = calculate_event_similarity(primary, member, window_hours=window_hours, f1=f_primary, f2=f_member)
        is_same, _ = are_articles_same_event(primary, member, window_hours=window_hours, f1=f_primary, f2=f_member)
        if is_same and sim >= EVENT_MEMBER_THRESHOLD:
            scored_candidates.append((member, sim))
        else:
            outliers.append(member)

    # Sort candidates by similarity to primary descending
    scored_candidates.sort(key=lambda x: x[1], reverse=True)

    # Rule 2: Pairwise compatibility check on retained members
    for member, sim in scored_candidates:
        f_member = features_by_id.get(id(member)) if features_by_id else None
        incompatible = False
        for existing in retained:
            f_existing = features_by_id.get(id(existing)) if features_by_id else None
            is_compat, _ = are_articles_same_event(existing, member, window_hours=window_hours, f1=f_existing, f2=f_member)
            if not is_compat:
                incompatible = True
                break
        if not incompatible:
            retained.append(member)
        else:
            outliers.append(member)

    # Rule 3: Cluster coherence calculation
    if len(retained) <= 1:
        return 1.0, retained, outliers

    member_sims = [
        calculate_event_similarity(primary, m, window_hours=window_hours)
        for m in retained
        if m.article_id != primary.article_id
    ]
    avg_sim = sum(member_sims) / len(member_sims)
    coherence_score = round(avg_sim, 3)

    return coherence_score, retained, outliers


def primary_source_rank(article: Article) -> tuple[int, float, float]:
    """Calculate ranking tuple for preferred primary reference source.

    Hierarchy:
    Rank 4: Regulatory authority (NHTSA, KBA, EPA, etc.)
    Rank 3: Official newsroom / automaker press release
    Rank 2: Major financial wire (Reuters, Bloomberg, AP)
    Rank 1: Specialized automotive trade press (Automotive News, electrive, etc.)
    Rank 0: General media / aggregator

    Secondary: priority_score, recency
    """
    tier = 0
    src_type = (article.source_type or "").lower()
    pub = (article.publisher or article.source or "").lower()

    if src_type == "regulator" or article.is_reference and "regulat" in src_type:
        tier = 4
    elif src_type in {"official", "press_release"} or article.is_official or article.is_primary_source:
        tier = 3
    elif any(w in pub for w in ["reuters", "bloomberg", "associated press", "ap news", "dow jones"]):
        tier = 2
    elif (article.source_authority or 0) >= 75 or any(
        w in pub for w in ["automotive news", "electrive", "just auto", "green car congress"]
    ):
        tier = 1
    else:
        tier = 0

    ts = article.published_at.timestamp() if article.published_at else 0.0
    return (tier, article.priority_score, ts)


def select_primary_article(articles: list[Article]) -> Article:
    """Select the preferred primary reference source from a cluster of articles."""
    if not articles:
        raise ValueError("Cannot select primary article from empty list")
    return max(articles, key=primary_source_rank)


PUBLISHER_CANONICAL = {
    "reuters": "Reuters",
    "thomson reuters": "Reuters",
    "bloomberg": "Bloomberg",
    "bloomberg news": "Bloomberg",
    "associated press": "Associated Press",
    "ap news": "Associated Press",
    "ap": "Associated Press",
    "dow jones": "Dow Jones",
    "automotive news": "Automotive News",
    "autonews": "Automotive News",
    "automotive news europe": "Automotive News",
    "insideevs": "InsideEVs",
    "insideevs us": "InsideEVs",
    "electrive": "electrive",
    "electrive.com": "electrive",
    "the verge": "The Verge",
    "techcrunch": "TechCrunch",
    "just auto": "Just Auto",
    "green car congress": "Green Car Congress",
    "wardsauto": "WardsAuto",
    "motortrend": "MotorTrend",
    "car and driver": "Car and Driver",
    "autoblog": "Autoblog",
    "auto motor und sport": "auto motor und sport",
    "handelsblatt": "Handelsblatt",
    "yna": "연합뉴스",
    "yonhap": "연합뉴스",
    "yonhap news": "연합뉴스",
    "news1": "뉴스1",
    "newsis": "뉴시스",
    "korea economic daily": "한국경제",
    "hankyung": "한국경제",
    "maeil business": "매일경제",
    "mk": "매일경제",
    "nhtsa": "NHTSA",
    "kba": "KBA",
    "epa": "EPA",
}


def resolve_originating_publisher(article: Article) -> str:
    """Resolve originating independent publisher, detecting syndication or wire republication."""
    pub = (article.publisher or article.source or "Unknown").strip()
    norm_pub = PUBLISHER_CANONICAL.get(pub.lower(), pub)

    text_to_check = f"{article.title} {article.excerpt} {article.content[:500]}"

    # Check for explicit wire or syndication attribution in text
    wire_patterns = [
        re.compile(r"\bvia\s+(reuters|bloomberg|associated press|ap|automotive news|yonhap)\b", re.I),
        re.compile(r"\((reuters|bloomberg|associated press|ap|afp|yonhap)\)", re.I),
        re.compile(r"\b(?:reported by|according to|courtesy of)\s+(reuters|bloomberg|associated press|ap|automotive news)\b", re.I),
        re.compile(r"\b(?:from|by)\s+(reuters|bloomberg|associated press|ap)\b", re.I),
    ]
    for pat in wire_patterns:
        m = pat.search(text_to_check)
        if m:
            matched_wire = m.group(1).strip().lower()
            return PUBLISHER_CANONICAL.get(matched_wire, matched_wire.title())

    if article.discovered_via and any(w in article.discovered_via.lower() for w in ["reuters", "bloomberg", "ap"]):
        return PUBLISHER_CANONICAL.get(article.discovered_via.lower(), article.discovered_via)

    return norm_pub


def calculate_event_source_agreement(cluster: list[Article], primary: Article) -> dict[str, object]:
    """Calculate source agreement, independent source count, and official/regulatory availability.

    Important: Does not equate source count to truth. Detects syndicated / copied reports.
    """
    source_count = len(cluster)

    # 1. Distinguish independent reporting from syndicated/copied content
    independent_reporters = set()
    for article in cluster:
        orig = resolve_originating_publisher(article)
        independent_reporters.add(orig.lower())

    independent_source_count = max(1, len(independent_reporters))
    independent_source_count = min(independent_source_count, source_count)

    # 2. Check for official source
    official_art = next(
        (a for a in cluster if a.source_type in {"official", "press_release"} or a.is_official),
        None,
    )
    has_official_source = official_art is not None
    official_source_url = (official_art.canonical_url or official_art.url) if official_art else None
    official_source_name = (official_art.publisher or official_art.source) if official_art else None

    # 3. Check for regulatory source
    has_regulatory_source = any(
        a.source_type == "regulator"
        or any(
            reg in (a.publisher or a.source or "").lower()
            for reg in ["nhtsa", "kba", "epa", "unece", "european commission", "ftc", "sec"]
        )
        for a in cluster
    )

    # 4. Check for major media source
    has_major_media_source = any(
        any(
            wire in (a.publisher or a.source or "").lower()
            for wire in [
                "reuters",
                "bloomberg",
                "associated press",
                "ap news",
                "dow jones",
                "wall street journal",
                "wsj",
                "financial times",
            ]
        )
        for a in cluster
    )

    reference_source_name = primary.publisher or primary.source

    # 5. Related sources list (preserving primary, official, then others)
    related_sources: list[str] = []
    seen: set[str] = set()
    ordered_arts = [primary]
    if official_art and official_art != primary:
        ordered_arts.append(official_art)
    for a in cluster:
        if a not in ordered_arts:
            ordered_arts.append(a)

    for a in ordered_arts:
        name = (a.publisher or a.source or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            related_sources.append(name)

    return {
        "source_count": source_count,
        "independent_source_count": independent_source_count,
        "has_official_source": has_official_source,
        "has_regulatory_source": has_regulatory_source,
        "has_major_media_source": has_major_media_source,
        "official_source_url": official_source_url,
        "official_source_name": official_source_name,
        "reference_source_name": reference_source_name,
        "related_sources": related_sources,
    }


@dataclass
class EventCoherenceMetrics:
    """Internal diagnostic metrics for event cluster coherence and quality."""
    event_id: str
    primary_title: str
    member_count: int
    min_similarity: float
    avg_similarity: float
    entity_overlap: list[str]
    theme_overlap: list[str]
    source_count: int
    independent_source_count: int
    is_suspicious: bool = False
    suspicious_reasons: list[str] = field(default_factory=list)


def compute_event_coherence_metrics(
    cluster: list[Article],
    primary: Article,
    window_hours: float = 72.0,
    features_by_id: dict[int, ArticleClusteringFeatures] | None = None,
) -> EventCoherenceMetrics:
    """Compute diagnostic coherence metrics for an event cluster."""
    event_seed = f"{primary.article_id}_{primary.title}"
    event_id = f"evt_{hashlib.sha256(event_seed.encode()).hexdigest()[:16]}"
    member_count = len(cluster)

    if features_by_id is None:
        features_by_id = {id(a): extract_clustering_features(a) for a in cluster}

    f_primary = features_by_id.get(id(primary))

    if member_count <= 1:
        entities = sorted(list(f_primary.canonical_entities if f_primary else extract_canonical_entities(primary)))
        themes = sorted(list(f_primary.themes if f_primary else extract_clustering_features(primary).themes))
        return EventCoherenceMetrics(
            event_id=event_id,
            primary_title=primary.title,
            member_count=1,
            min_similarity=1.0,
            avg_similarity=1.0,
            entity_overlap=entities,
            theme_overlap=themes,
            source_count=1,
            independent_source_count=1,
            is_suspicious=False,
            suspicious_reasons=[],
        )

    # Calculate pairwise similarities to primary
    member_sims: list[float] = []
    suspicious_reasons: list[str] = []

    for m in cluster:
        if m.article_id == primary.article_id:
            continue
        f_m = features_by_id.get(id(m))
        sim = calculate_event_similarity(primary, m, window_hours=window_hours, f1=f_primary, f2=f_m)
        member_sims.append(sim)
        if sim < EVENT_MEMBER_THRESHOLD:
            suspicious_reasons.append(
                f"Member '{m.title[:40]}' similarity {sim:.3f} < threshold {EVENT_MEMBER_THRESHOLD}"
            )

    min_sim = round(min(member_sims), 3) if member_sims else 1.0
    avg_sim = round(sum(member_sims) / len(member_sims), 3) if member_sims else 1.0

    # Overlap of entities across all members
    member_entities = [features_by_id[id(m)].canonical_entities for m in cluster if id(m) in features_by_id]
    common_entities = set.intersection(*member_entities) if member_entities else set()

    # Overlap of themes across all members
    member_themes = [features_by_id[id(m)].themes for m in cluster if id(m) in features_by_id]
    common_themes = set.intersection(*member_themes) if member_themes else set()

    # Pairwise compatibility check across all members in the cluster
    for i in range(len(cluster)):
        f_i = features_by_id.get(id(cluster[i]))
        for j in range(i + 1, len(cluster)):
            f_j = features_by_id.get(id(cluster[j]))
            is_compat, sim_ij = are_articles_same_event(
                cluster[i], cluster[j], window_hours=window_hours, f1=f_i, f2=f_j
            )
            if not is_compat:
                suspicious_reasons.append(
                    f"Pairwise incompatibility: '{cluster[i].title[:30]}' vs '{cluster[j].title[:30]}' (sim={sim_ij:.3f})"
                )

    agreement = calculate_event_source_agreement(cluster, primary)
    source_count = int(agreement["source_count"])  # type: ignore[arg-type]
    independent_source_count = int(agreement["independent_source_count"])  # type: ignore[arg-type]

    is_suspicious = len(suspicious_reasons) > 0

    return EventCoherenceMetrics(
        event_id=event_id,
        primary_title=primary.title,
        member_count=member_count,
        min_similarity=min_sim,
        avg_similarity=avg_sim,
        entity_overlap=sorted(list(common_entities)),
        theme_overlap=sorted(list(common_themes)),
        source_count=source_count,
        independent_source_count=independent_source_count,
        is_suspicious=is_suspicious,
        suspicious_reasons=suspicious_reasons,
    )


def cluster_articles(
    articles: list[Article],
    window_hours: float = 72.0,
    embedder: Callable[[list[str]], list[list[float]]] | None = None,
) -> tuple[list[Event], list[EventArticle], list[Article]]:
    """Group articles into Event clusters, calculate source agreement, and link related articles.

    Note: The embedder parameter is reserved for future optional semantic embedding models;
    deterministic clustering is currently used.
    Clustering NEVER removes articles: returns (events, event_articles, all_articles).
    """
    if not articles:
        return [], [], []

    # 1. Precompute features for each article once (O(N) vs previous O(N^2) feature extraction)
    features_by_id = {id(a): extract_clustering_features(a) for a in articles}
    features_list = [features_by_id[id(a)] for a in articles]

    # 2. Build pairwise adjacency graph for candidates
    n = len(articles)
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for i in range(n):
        f_i = features_list[i]
        for j in range(i + 1, n):
            is_same, _ = are_articles_same_event(
                articles[i], articles[j], window_hours=window_hours, f1=f_i, f2=features_list[j]
            )
            if is_same:
                adj[i].add(j)
                adj[j].add(i)

    # 3. Extract connected components
    visited = set()
    candidates: list[list[Article]] = []
    for i in range(n):
        if i not in visited:
            component = []
            queue = [i]
            visited.add(i)
            while queue:
                curr = queue.pop(0)
                component.append(articles[curr])
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            candidates.append(component)

    # 4. Validate coherence of each component against primary and pairwise compatibility
    final_clusters: list[list[Article]] = []
    for comp in candidates:
        if len(comp) == 1:
            final_clusters.append(comp)
            continue

        remaining = list(comp)
        while remaining:
            if len(remaining) == 1:
                final_clusters.append(remaining)
                break
            primary = select_primary_article(remaining)
            _, retained, outliers = check_cluster_coherence(
                remaining, primary, window_hours=window_hours, features_by_id=features_by_id
            )
            final_clusters.append(retained)
            retained_ids = {a.article_id for a in retained}
            remaining = [a for a in remaining if a.article_id not in retained_ids]


    events: list[Event] = []
    event_articles: list[EventArticle] = []

    for cluster in final_clusters:
        primary = select_primary_article(cluster)
        now = datetime.now(timezone.utc)
        earliest_time = min(
            (a.published_at for a in cluster if a.published_at), default=now
        )
        # Deterministic event ID
        event_seed = f"{primary.article_id}_{primary.title}"
        event_id = f"evt_{hashlib.sha256(event_seed.encode()).hexdigest()[:16]}"

        agreement = calculate_event_source_agreement(cluster, primary)

        event = Event(
            event_id=event_id,
            title=primary.title,
            category=primary.category,
            created_at=earliest_time,
            importance=max(a.priority_score for a in cluster),
            primary_article_id=primary.article_id,
            source_count=int(agreement["source_count"]),  # type: ignore[arg-type]
            independent_source_count=int(agreement["independent_source_count"]),  # type: ignore[arg-type]
            has_official_source=bool(agreement["has_official_source"]),
            has_regulatory_source=bool(agreement["has_regulatory_source"]),
            has_major_media_source=bool(agreement["has_major_media_source"]),
            official_source_url=str(agreement["official_source_url"]) if agreement["official_source_url"] else None,
            official_source_name=str(agreement["official_source_name"]) if agreement["official_source_name"] else None,
            reference_source_name=str(agreement["reference_source_name"]) if agreement["reference_source_name"] else None,
            related_sources=list(agreement["related_sources"]),  # type: ignore[arg-type]
        )
        events.append(event)

        # Set related article IDs and event metadata on all articles in the cluster
        cluster_article_ids = [a.article_id for a in cluster if a.article_id]
        f_primary = features_by_id.get(id(primary))
        for article in cluster:
            article.event_id = event_id
            article.event_title = event.title
            article.related_article_ids = [
                aid for aid in cluster_article_ids if aid != article.article_id
            ]
            article.event_source_count = event.source_count
            article.event_independent_source_count = event.independent_source_count
            article.event_has_official_source = event.has_official_source
            article.event_has_regulatory_source = event.has_regulatory_source
            article.event_has_major_media_source = event.has_major_media_source
            article.event_official_source_url = event.official_source_url
            article.event_official_source_name = event.official_source_name
            article.event_reference_source_name = event.reference_source_name
            article.event_related_sources = event.related_sources

            rel = "primary" if article.article_id == primary.article_id else (
                "official" if article.is_official else "coverage"
            )
            sim = 1.0 if article.article_id == primary.article_id else calculate_event_similarity(
                primary, article, window_hours=window_hours, f1=f_primary, f2=features_by_id.get(id(article))
            )
            event_articles.append(
                EventArticle(
                    event_id=event_id,
                    article_id=article.article_id or "",
                    relationship=rel,
                    similarity=sim,
                )
            )

    return events, event_articles, articles
