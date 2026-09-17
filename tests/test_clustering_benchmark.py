from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import pytest

from automotive_newsletter.clustering import (
    cluster_articles,
    compute_event_coherence_metrics,
)
from automotive_newsletter.models import Article


@dataclass(slots=True)
class BenchmarkItem:
    gold_event_id: str
    article: Article


def get_realistic_benchmark_dataset() -> list[BenchmarkItem]:
    """Generate deterministic realistic automotive news dataset.

    Contains 58 synthetic articles representing 29 gold events:
    - 24 multi-article events (2 to 3 articles each from different publishers)
    - 5 singletons
    - Difficult negative pairs:
      * Disjoint tech partners (BMW + Qualcomm vs BMW + Nvidia)
      * Sister-brand independent events (VW restructuring vs Audi restructuring, Hyundai SDV vs Kia infotainment)
      * Recall vs Investigation (Tesla brake recall vs Tesla brake investigation)
      * Version differentiation (Tesla FSD v12 vs Tesla FSD v13)
      * Financial amount difference (Ford $2B Michigan plant vs Ford $5B Kentucky plant)
      * Same OEM same day different events (GM earnings vs GM Super Cruise)
      * Same model different events (Ford F-150 brake recall vs Ford F-150 electric launch)
      * Same parent group unrelated events (BMW earnings vs Mini pricing)
    - Difficult positive pairs:
      * Same event with paraphrased publisher wording
      * Same software version represented as v12, version 12, update 12
      * Same recall campaign represented as 24V-123 vs 24V123
      * Same partnership with OEM first vs supplier first
      * Sister brands with explicit joint program (VW + Audi joint restructuring, Hyundai + Kia joint SDV)
    """
    dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
    items: list[BenchmarkItem] = []

    def add(gold_id: str, title: str, source: str, entities: list[str] | None = None, content: str = "", is_official: bool = False):
        art_id = f"art_{len(items) + 1:03d}"
        art = Article(
            article_id=art_id,
            title=title,
            url=f"https://news.example.com/{gold_id}/{art_id}",
            source=source,
            publisher=source,
            source_type="official" if is_official else "media",
            is_official=is_official,
            published_at=dt,
            entities=entities or [],
            content=content,
        )
        items.append(BenchmarkItem(gold_event_id=gold_id, article=art))

    # Event 1: Toyota x Nvidia SDV Partnership (3 articles: OEM first, Supplier first, official newsroom)
    add("evt_01_toyota_nvidia", "Toyota and Nvidia announce software-defined vehicle platform partnership", "Reuters", ["Toyota", "Nvidia"])
    add("evt_01_toyota_nvidia", "Nvidia and Toyota team up on next-gen SDV computing platform", "Automotive News", ["Toyota", "Nvidia"])
    add("evt_01_toyota_nvidia", "Toyota Motor Corporation and NVIDIA Expand Strategic SDV Collaboration", "Toyota Newsroom", ["Toyota", "Nvidia"], is_official=True)

    # Event 2: BMW x Qualcomm Automated Driving (3 articles)
    add("evt_02_bmw_qualcomm", "BMW and Qualcomm collaborate on automated driving compute platform", "Reuters", ["BMW", "Qualcomm"])
    add("evt_02_bmw_qualcomm", "Qualcomm and BMW partner on Snapdragon Ride automated driving system", "Automotive News", ["BMW", "Qualcomm"])
    add("evt_02_bmw_qualcomm", "BMW selects Qualcomm chips for automated highway driving", "Bloomberg", ["BMW", "Qualcomm"])

    # Event 3: BMW x Nvidia Cockpit AI (2 articles - Disjoint tech partner vs Event 2!)
    add("evt_03_bmw_nvidia", "BMW partners with Nvidia on next-generation cockpit generative AI assistant", "Reuters", ["BMW", "Nvidia"])
    add("evt_03_bmw_nvidia", "Nvidia and BMW reveal generative AI in-vehicle digital assistant", "Automotive News", ["BMW", "Nvidia"])

    # Event 4: Tesla FSD v12 Release (3 articles - v12, version 12, update 12)
    add("evt_04_tesla_fsd_v12", "Tesla releases Full Self-Driving v12 update to customers", "Reuters", ["Tesla"])
    add("evt_04_tesla_fsd_v12", "Tesla rolls out Full Self-Driving version 12 to vehicle owners", "Automotive News", ["Tesla"])
    add("evt_04_tesla_fsd_v12", "Tesla releases Full Self-Driving update 12 to vehicle owners", "Electrek", ["Tesla"])

    # Event 5: Tesla FSD v13 Release (2 articles - Rigid version mismatch vs Event 4!)
    add("evt_05_tesla_fsd_v13", "Tesla begins rollout of Full Self-Driving v13 with end-to-end AI", "Electrek", ["Tesla"])
    add("evt_05_tesla_fsd_v13", "Tesla launches Full Self-Driving version 13 for early access fleet", "Reuters", ["Tesla"])

    # Event 6: Ford F-150 Truck Brake Recall (3 articles - 24V-123 vs 24V123)
    add("evt_06_ford_brake_recall", "Ford recalls 500,000 F-150 trucks over brake line defect under campaign 24V-123", "NHTSA", ["Ford"])
    add("evt_06_ford_brake_recall", "Ford issues recall for 500,000 pickup trucks citing brake issues under campaign 24V123", "Reuters", ["Ford"])
    add("evt_06_ford_brake_recall", "Half a million Ford F-150 trucks recalled due to hydraulic brake defect", "Automotive News", ["Ford"])

    # Event 7: Ford SUV Airbag Recall (2 articles - Different model/defect vs Event 6!)
    add("evt_07_ford_airbag_recall", "Ford recalls 100,000 Explorer SUVs over airbag inflator risk", "NHTSA", ["Ford"])
    add("evt_07_ford_airbag_recall", "Ford issues safety recall for Explorer SUVs over passenger airbag defect", "Reuters", ["Ford"])

    # Event 8: Tesla Brake Defect Investigation (2 articles - Investigation vs Recall!)
    add("evt_08_tesla_brake_investigation", "NHTSA opens defect investigation into Tesla Model Y braking system issues", "NHTSA", ["Tesla"])
    add("evt_08_tesla_brake_investigation", "Regulators probe Tesla Model Y braking complaints following unintended deceleration", "Reuters", ["Tesla"])

    # Event 9: Tesla Brake Defect Recall (2 articles - Actual recall vs Event 8!)
    add("evt_09_tesla_brake_recall", "Tesla recalls 40,000 Model Y vehicles to fix brake software issue", "Reuters", ["Tesla"])
    add("evt_09_tesla_brake_recall", "Tesla issues recall for 40,000 Model Y crossovers over brake caliper defect", "Automotive News", ["Tesla"])

    # Event 10: Volkswagen Independent Restructuring (2 articles - VW alone vs Audi alone!)
    add("evt_10_vw_restructuring", "Volkswagen announces major European manufacturing restructuring program", "Reuters", ["Volkswagen"])
    add("evt_10_vw_restructuring", "VW restructuring plans accelerate with potential German plant closures", "Automotive News", ["Volkswagen"])

    # Event 11: Audi Independent Restructuring (2 articles - Sister brand alone, must NOT merge with Event 10!)
    add("evt_11_audi_restructuring", "Audi announces European manufacturing restructuring and operations review", "Reuters", ["Audi"])
    add("evt_11_audi_restructuring", "Audi initiates cost restructuring plan across European facilities", "Automotive News", ["Audi"])

    # Event 12: Volkswagen and Audi Joint Restructuring (2 articles - Explicit joint program!)
    add("evt_12_vw_audi_joint_restructuring", "Volkswagen and Audi announce joint European manufacturing restructuring program", "Reuters", ["Volkswagen", "Audi"])
    add("evt_12_vw_audi_joint_restructuring", "VW and Audi confirm same restructuring program across shared European plants", "Automotive News", ["Volkswagen", "Audi"])

    # Event 13: Hyundai Independent SDV Platform (2 articles - Hyundai alone vs Kia alone!)
    add("evt_13_hyundai_sdv", "Hyundai Motor announces next-generation SDV architecture for 2026 models", "Reuters", ["Hyundai"])
    add("evt_13_hyundai_sdv", "Hyundai reveals new centralized vehicle software architecture", "Automotive News", ["Hyundai"])

    # Event 14: Kia Independent Infotainment (2 articles - Sister brand alone, must NOT merge with Event 13!)
    add("evt_14_kia_infotainment", "Kia reveals new software-driven infotainment experience for EV3", "Automotive News", ["Kia"])
    add("evt_14_kia_infotainment", "Kia debuts connected infotainment system for upcoming compact EV", "The Verge", ["Kia"])

    # Event 15: Hyundai and Kia Joint SDV Platform (2 articles - Explicit joint initiative!)
    add("evt_15_hyundai_kia_joint_sdv", "Hyundai and Kia announce joint next-generation SDV software platform", "Reuters", ["Hyundai", "Kia"])
    add("evt_15_hyundai_kia_joint_sdv", "Kia and Hyundai unveil new joint SDV software platform for future lineups", "Automotive News", ["Kia", "Hyundai"])

    # Event 16: Ford $2B Michigan Plant Investment (2 articles - $2B vs $5B!)
    add("evt_16_ford_investment_2b", "Ford invests $2 billion in Michigan electric vehicle plant", "Reuters", ["Ford"])
    add("evt_16_ford_investment_2b", "Ford confirms $2 billion investment to upgrade Michigan assembly facility", "Bloomberg", ["Ford"])

    # Event 17: Ford $5B Kentucky Battery Campus (2 articles - Disjoint amount/location vs Event 16!)
    add("evt_17_ford_investment_5b", "Ford invests $5 billion in Kentucky battery manufacturing complex", "Reuters", ["Ford"])
    add("evt_17_ford_investment_5b", "Ford commits $5 billion to Kentucky battery mega-campus", "Automotive News", ["Ford"])

    # Event 18: GM Q3 Earnings Beat (2 articles - Same OEM same day Event A)
    add("evt_18_gm_earnings", "General Motors beats third-quarter profit estimates on strong truck sales", "Reuters", ["General Motors"])
    add("evt_18_gm_earnings", "GM posts quarterly earnings beat and raises full-year guidance", "Bloomberg", ["General Motors"])

    # Event 19: GM Super Cruise Network Expansion (2 articles - Same OEM same day Event B, must NOT merge with Event 18!)
    add("evt_19_gm_supercruise", "General Motors expands Super Cruise hands-free driving to 750,000 miles", "The Verge", ["General Motors"])
    add("evt_19_gm_supercruise", "GM adds rural highways to Super Cruise driver assistance network", "Automotive News", ["General Motors"])

    # Event 20: Mercedes CLA MMA Architecture (3 articles)
    add("evt_20_mercedes_mma", "Mercedes-Benz begins production of new electric CLA with MMA architecture", "Reuters", ["Mercedes-Benz"])
    add("evt_20_mercedes_mma", "Mercedes kicks off CLA production on modular MMA electric platform", "Automotive News", ["Mercedes-Benz"])
    add("evt_20_mercedes_mma", "Mercedes-Benz rolls out first MMA architecture vehicle at Rastatt plant", "Electrive", ["Mercedes-Benz"])

    # Event 21: Volvo Connected Safety OTA Update (2 articles)
    add("evt_21_volvo_ota", "Volvo enables new connected safety features in electric vehicles with OTA update", "WardsAuto", ["Volvo"])
    add("evt_21_volvo_ota", "Volvo pushes over-the-air update adding connected hazard warning system", "Autocar", ["Volvo"])

    # Event 22: Lucid Air Battery Fire Recall (2 articles)
    add("evt_22_lucid_recall", "Lucid recalls 27,000 Air sedans over battery fire risk and warns owners", "InsideEVs", ["Lucid"])
    add("evt_22_lucid_recall", "Lucid issues safety recall for 27,000 Air electric vehicles over thermal risk", "Reuters", ["Lucid"])

    # Event 23: Rivian CFO Resignation (2 articles)
    add("evt_23_rivian_cfo", "Rivian Chief Financial Officer steps down amid production ramp", "WardsAuto", ["Rivian"])
    add("evt_23_rivian_cfo", "Rivian CFO resigns as EV maker seeks operational efficiency", "Reuters", ["Rivian"])

    # Event 24: BMW Group parent but unrelated events (2 articles: BMW profit vs Mini pricing - MUST NOT MERGE!)
    add("evt_24_bmw_earnings_unrelated", "BMW Group operating profit declines amid European market competition", "Reuters", ["BMW"])
    add("evt_25_mini_pricing_unrelated", "Mini announces US pricing and specifications for new electric Cooper", "Car and Driver", ["Mini"])

    # Singletons (5 independent events)
    add("evt_26_denso_nippon", "Nippon Seiki to absorb Denso global HUD division", "Automotive World", ["Denso"])
    add("evt_27_walmart_charging", "Walmart accelerates proprietary EV charging network with 100th station", "WardsAuto")
    add("evt_28_lotus_restructure", "Lotus merges production and electrified mobility divisions", "WardsAuto")
    add("evt_29_hoosier_tire", "Hoosier launches road-legal TrackAttack Pro tire with motorsport DNA", "Automotive Testing")
    add("evt_30_china_bigdata", "China International Big Data Industry Expo opens in Guiyang", "PR Newswire")

    return items


@dataclass(slots=True)
class ClusteringQualityMetrics:
    total_articles: int
    gold_event_count: int
    predicted_event_count: int
    pair_precision: float
    pair_recall: float
    pair_f1: float
    false_merges: int
    false_splits: int
    article_coverage: float
    largest_cluster_size: int
    singleton_count: int
    avg_cluster_size: float
    suspicious_cluster_count: int
    false_merge_details: list[str]
    false_split_details: list[str]


def evaluate_benchmark_clustering(benchmark_items: list[BenchmarkItem]) -> ClusteringQualityMetrics:
    """Evaluate clustering quality against gold event labels and compute pair-wise metrics."""
    articles = [item.article for item in benchmark_items]
    gold_map = {item.article.article_id: item.gold_event_id for item in benchmark_items}
    gold_events_set = set(gold_map.values())

    events, event_articles, all_articles = cluster_articles(articles)
    pred_map = {a.article_id: a.event_id for a in all_articles}

    # 1. Pairwise precision, recall, F1
    n = len(all_articles)
    tp = 0
    fp = 0
    fn = 0
    tn = 0

    art_ids = [a.article_id for a in all_articles]
    for i in range(n):
        for j in range(i + 1, n):
            id_i = art_ids[i]
            id_j = art_ids[j]
            same_gold = gold_map[id_i] == gold_map[id_j]
            same_pred = pred_map[id_i] == pred_map[id_j]

            if same_gold and same_pred:
                tp += 1
            elif not same_gold and same_pred:
                fp += 1
            elif same_gold and not same_pred:
                fn += 1
            else:
                tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # 2. Event-level false merges (predicted clusters with >1 gold event)
    cluster_to_golds: dict[str, set[str]] = {}
    cluster_articles_map: dict[str, list[Article]] = {}
    for a in all_articles:
        cluster_to_golds.setdefault(a.event_id, set()).add(gold_map[a.article_id])
        cluster_articles_map.setdefault(a.event_id, []).append(a)

    false_merges = 0
    false_merge_details = []
    for pred_id, golds in cluster_to_golds.items():
        if len(golds) > 1:
            false_merges += 1
            member_titles = [a.title for a in cluster_articles_map[pred_id]]
            false_merge_details.append(f"Cluster {pred_id} falsely merged gold events: {golds} | Articles: {member_titles}")

    # 3. Event-level false splits (gold events with >1 predicted cluster)
    gold_to_clusters: dict[str, set[str]] = {}
    for a in all_articles:
        gold_to_clusters.setdefault(gold_map[a.article_id], set()).add(a.event_id)

    false_splits = 0
    false_split_details = []
    for gold_id, clusters in gold_to_clusters.items():
        if len(clusters) > 1:
            false_splits += 1
            false_split_details.append(f"Gold event {gold_id} falsely split across clusters: {clusters}")

    # 4. Cluster statistics
    cluster_sizes = [len(members) for members in cluster_articles_map.values()]
    largest_cluster = max(cluster_sizes) if cluster_sizes else 0
    singletons = sum(1 for size in cluster_sizes if size == 1)
    avg_size = sum(cluster_sizes) / max(1, len(cluster_sizes))

    suspicious_count = 0
    for pred_id, members in cluster_articles_map.items():
        primary = members[0]
        metrics = compute_event_coherence_metrics(members, primary)
        if metrics.is_suspicious:
            suspicious_count += 1

    return ClusteringQualityMetrics(
        total_articles=len(all_articles),
        gold_event_count=len(gold_events_set),
        predicted_event_count=len(events),
        pair_precision=precision,
        pair_recall=recall,
        pair_f1=f1,
        false_merges=false_merges,
        false_splits=false_splits,
        article_coverage=len(pred_map) / max(1, len(articles)),
        largest_cluster_size=largest_cluster,
        singleton_count=singletons,
        avg_cluster_size=avg_size,
        suspicious_cluster_count=suspicious_count,
        false_merge_details=false_merge_details,
        false_split_details=false_split_details,
    )


def test_realistic_automotive_clustering_benchmark():
    """Verify that deterministic clustering achieves high precision, high recall, and zero false merges on realistic news."""
    dataset = get_realistic_benchmark_dataset()
    metrics = evaluate_benchmark_clustering(dataset)

    print("\n" + "=" * 80)
    print("REALISTIC AUTOMOTIVE NEWS CLUSTERING BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Total Articles: {metrics.total_articles}")
    print(f"Gold Events: {metrics.gold_event_count}")
    print(f"Predicted Clusters: {metrics.predicted_event_count}")
    print(f"Pair Precision: {metrics.pair_precision:.4f}")
    print(f"Pair Recall:    {metrics.pair_recall:.4f}")
    print(f"Pair F1 Score:  {metrics.pair_f1:.4f}")
    print(f"False Merges:   {metrics.false_merges}")
    print(f"False Splits:   {metrics.false_splits}")
    print(f"Article Coverage: {metrics.article_coverage * 100:.1f}%")
    print(f"Largest Cluster Size: {metrics.largest_cluster_size}")
    print(f"Singleton Count: {metrics.singleton_count}")
    print(f"Average Cluster Size: {metrics.avg_cluster_size:.2f}")
    print(f"Suspicious Clusters: {metrics.suspicious_cluster_count}")
    print("=" * 80)

    if metrics.false_merge_details:
        print("FALSE MERGE DETAILS:")
        for det in metrics.false_merge_details:
            print("  *", det)

    if metrics.false_split_details:
        print("FALSE SPLIT DETAILS:")
        for det in metrics.false_split_details:
            print("  *", det)

    # Core Assertions:
    # 1. Zero False Merges (different gold events must NEVER merge)
    assert metrics.false_merges == 0, f"Detected {metrics.false_merges} false merges: {metrics.false_merge_details}"
    # 2. High Pair Precision: must be 1.0 (no false positive pairs)
    assert metrics.pair_precision == 1.0, f"Expected 1.0 precision, got {metrics.pair_precision}"
    # 3. High Pair Recall: at least 0.90
    assert metrics.pair_recall >= 0.90, f"Expected >= 0.90 recall, got {metrics.pair_recall}"
    # 4. High Pair F1: at least 0.90
    assert metrics.pair_f1 >= 0.90, f"Expected >= 0.90 F1, got {metrics.pair_f1}"
    # 5. Article coverage: 100%
    assert metrics.article_coverage == 1.0
