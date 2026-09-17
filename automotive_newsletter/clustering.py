from __future__ import annotations

import hashlib
import re
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
    re.compile(r"\b(mach-e|f-150\s+lightning)\b", re.IGNORECASE),
]

# Generation & Standard patterns
GEN_PATTERNS = [
    re.compile(r"\b(?:gen|generation)\s*([0-9]+)\b", re.IGNORECASE),
    re.compile(r"\beuro\s*([0-9]+[a-z]?)\b", re.IGNORECASE),
    re.compile(r"\btier\s*([0-9]+)\b", re.IGNORECASE),
]

# Recall defect categories
RECALL_DEFECT_TERMS = {
    "airbag": ["airbag", "takata", "inflator"],
    "steering": ["steering", "power steering", "tie rod"],
    "brake": ["brake", "braking", "abs", "caliper"],
    "battery_fire": ["battery fire", "thermal runaway", "short circuit", "fire risk"],
    "software_glitch": ["software glitch", "display blank", "reboot", "infotainment crash"],
    "door_latch": ["door latch", "door open", "hood latch"],
    "seatbelt": ["seatbelt", "buckle", "seat belt"],
    "suspension": ["suspension", "ball joint", "control arm"],
}

# Automotive entity aliases (canonical mapping)
ENTITY_ALIASES = {
    "vw": "volkswagen",
    "volkswagen": "volkswagen",
    "audi": "volkswagen",
    "porsche": "volkswagen",
    "toyota": "toyota",
    "lexus": "toyota",
    "hyundai": "hyundai",
    "kia": "hyundai",
    "genesis": "hyundai",
    "ford": "ford",
    "gm": "gm",
    "general motors": "gm",
    "chevrolet": "gm",
    "cadillac": "gm",
    "tesla": "tesla",
    "stellantis": "stellantis",
    "jeep": "stellantis",
    "peugeot": "stellantis",
    "fiat": "stellantis",
    "byd": "byd",
    "bmw": "bmw",
    "mercedes": "mercedes",
    "mercedes-benz": "mercedes",
    "daimler": "mercedes",
    "renault": "renault",
    "nissan": "nissan",
    "honda": "honda",
    "volvo": "volvo",
    "geely": "geely",
    "rivian": "rivian",
    "lucid": "lucid",
    "bosch": "bosch",
    "continental": "continental",
    "zf": "zf",
    "denso": "denso",
    "magna": "magna",
    "valeo": "valeo",
    "forvia": "forvia",
    "aptiv": "aptiv",
    "catl": "catl",
    "lg energy solution": "lg energy",
    "lg energy": "lg energy",
    "samsung sdi": "samsung sdi",
    "sk on": "sk on",
    "panasonic": "panasonic",
    "nhtsa": "nhtsa",
    "kba": "kba",
    "epa": "epa",
}

# Event Action Themes
EVENT_ACTION_THEMES = {
    "restructuring": [
        "restructur", "cut", "layoff", "job cut", "closur", "plant clos",
        "reorganiz", "downsiz", "european oper"
    ],
    "recall": [
        "recall", "defect", "investig", "probe", "nhtsa", "inquiry"
    ],
    "partnership_jv": [
        "joint ventur", "partnership", "collaborat", "allianc", "team up", "partner"
    ],
    "investment_plant": [
        "invest", "gigafactory", "plant build", "expans", "spending"
    ],
    "platform_unveil": [
        "unveil", "reveal", "debut", "concept", "premier"
    ],
    "earnings_financial": [
        "earn", "profit", "revenu", "q1", "q2", "q3", "q4", "margin", "guidanc", "loss"
    ],
    "leadership_exec": [
        "ceo", "appoint", "step down", "resign", "execut", "chief"
    ],
    "cybersecurity_incident": [
        "hack", "cyber", "vulnerabilit", "ransomwar", "breach"
    ],
    "software_platform": [
        "sdv", "autosar", "ota", "operat system", "vehicle os", "middleware"
    ],
}

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
    """Extract canonical company/entity aliases from article entities, title, and tags."""
    found = set()
    sources_to_check = [
        *article.entities,
        article.title,
        *article.tags,
        article.source,
        article.publisher or "",
    ]
    combined = " ".join(sources_to_check).lower()
    for alias, canonical in ENTITY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", combined):
            found.add(canonical)
    return found


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


def extract_recall_defects(text: str) -> set[str]:
    """Extract specific recall defect keywords if text indicates a recall."""
    text_lower = text.lower()
    is_recall = any(w in text_lower for w in ["recall", "recalls", "safety defect", "nhtsa probe", "investigation"])
    if not is_recall:
        return set()
    defects = set()
    for defect_key, terms in RECALL_DEFECT_TERMS.items():
        if any(term in text_lower for term in terms):
            defects.add(defect_key)
    return defects


def extract_event_themes(text: str) -> set[str]:
    """Extract high-level automotive event action themes."""
    text_lower = text.lower()
    themes = set()
    for theme_name, terms in EVENT_ACTION_THEMES.items():
        if any(term in text_lower for term in terms):
            themes.add(theme_name)
    return themes


def stem_token(word: str) -> str:
    """Lightweight deterministic stemmer for English automotive terms."""
    w = word.lower().strip()
    if len(w) <= 3:
        return w
    for suffix in ("tions", "tion", "ments", "ment", "ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: -len(suffix)]
    return w


def extract_stemmed_tokens(text: str) -> set[str]:
    """Tokenize and stem alphanumeric words, filtering stopwords."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {
        stem_token(w)
        for w in words
        if w not in STOP_WORDS and len(w) > 1 and not w.isdigit()
    }


def are_articles_same_event(
    a1: Article, a2: Article, window_hours: float = 72.0
) -> tuple[bool, float]:
    """Determine whether two articles describe the same real-world event.

    Returns (is_same_event: bool, similarity: float).
    """
    # 1. Temporal window check
    if a1.published_at and a2.published_at:
        diff_hours = abs((a1.published_at - a2.published_at).total_seconds()) / 3600.0
        if diff_hours > window_hours:
            return False, 0.0

    t1 = f"{a1.title} {a1.summary_ko} {' '.join(a1.tags)}"
    t2 = f"{a2.title} {a2.summary_ko} {' '.join(a2.tags)}"

    # 2. Hard Negative Guards
    # Guard A: Model identifiers collision (e.g. Model 3 vs Model Y)
    m1 = extract_model_identifiers(t1)
    m2 = extract_model_identifiers(t2)
    if m1 and m2 and m1.isdisjoint(m2):
        return False, 0.0

    # Guard B: Generation / standard collision (e.g. Euro 6 vs Euro 7, Gen 2 vs Gen 3)
    g1 = extract_generation_identifiers(t1)
    g2 = extract_generation_identifiers(t2)
    if g1 and g2 and g1.isdisjoint(g2):
        return False, 0.0

    # Guard C: Recall defect collision (e.g. Airbag vs Brake recall)
    d1 = extract_recall_defects(t1)
    d2 = extract_recall_defects(t2)
    if d1 and d2 and d1.isdisjoint(d2):
        return False, 0.0

    # Guard D: Company mismatch
    c1 = extract_companies(a1)
    c2 = extract_companies(a2)
    # If both have identified companies and share none, they cannot be the same event
    if c1 and c2 and c1.isdisjoint(c2):
        return False, 0.0

    # Guard E: Numeric identifiers discrepancy (e.g. update 0 vs update 1, 500,000 vs 100,000)
    nums1 = set(re.findall(r"\b\d+\b", a1.title))
    nums2 = set(re.findall(r"\b\d+\b", a2.title))
    if nums1 and nums2 and nums1.isdisjoint(nums2):
        return False, 0.0

    # 3. Action / Theme compatibility
    themes1 = extract_event_themes(t1)
    themes2 = extract_event_themes(t2)
    has_theme_overlap = bool(themes1 & themes2)

    # If both have strong, disjoint event action themes (e.g. restructuring vs partnership)
    if themes1 and themes2 and themes1.isdisjoint(themes2):
        return False, 0.0

    # 4. Token Overlap (Stemmed Title Tokens)
    tokens1 = extract_stemmed_tokens(a1.title)
    tokens2 = extract_stemmed_tokens(a2.title)

    inter = tokens1 & tokens2
    union = tokens1 | tokens2

    jaccard = len(inter) / max(1, len(union))
    containment = len(inter) / max(1, min(len(tokens1), len(tokens2)))

    has_company_overlap = bool(c1 & c2)

    # 5. Matching Decision Heuristic
    # Case 1: Same company + Same action theme (e.g. VW restructuring)
    if has_company_overlap and has_theme_overlap:
        # At least 1 common content token or decent containment
        if len(inter) >= 1 or containment >= 0.25:
            sim = 0.4 + 0.3 * containment + 0.3 * jaccard
            return True, round(min(sim, 1.0), 3)

    # Case 2: High token overlap (Jaccard >= 0.45 or Containment >= 0.65)
    if jaccard >= 0.45 or containment >= 0.65:
        sim = 0.5 * jaccard + 0.5 * containment
        return True, round(min(sim, 1.0), 3)

    # Case 3: Same company + moderate token overlap
    if has_company_overlap and (containment >= 0.40 or len(inter) >= 2):
        sim = 0.3 + 0.4 * containment + 0.3 * jaccard
        return True, round(min(sim, 1.0), 3)

    return False, 0.0


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


def cluster_articles(
    articles: list[Article],
    window_hours: float = 72.0,
    embedder: Callable[[list[str]], list[list[float]]] | None = None,
) -> tuple[list[Event], list[EventArticle], list[Article]]:
    """Group articles into Event clusters, calculate source agreement, and link related articles."""
    if not articles:
        return [], [], []

    # Disjoint set / union-find or adjacency-based clustering
    n = len(articles)
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    similarity_map: dict[tuple[int, int], float] = {}

    for i in range(n):
        for j in range(i + 1, n):
            is_same, sim = are_articles_same_event(
                articles[i], articles[j], window_hours=window_hours
            )
            if is_same:
                adj[i].add(j)
                adj[j].add(i)
                similarity_map[(i, j)] = sim
                similarity_map[(j, i)] = sim

    visited = set()
    clusters: list[list[Article]] = []

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
            clusters.append(component)

    events: list[Event] = []
    event_articles: list[EventArticle] = []
    primary_articles: list[Article] = []

    for cluster in clusters:
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
            sim = 1.0 if article.article_id == primary.article_id else 0.85
            event_articles.append(
                EventArticle(
                    event_id=event_id,
                    article_id=article.article_id or "",
                    relationship=rel,
                    similarity=sim,
                )
            )

        primary_articles.append(primary)

    return events, event_articles, primary_articles
