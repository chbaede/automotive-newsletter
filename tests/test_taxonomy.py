from automotive_newsletter.models import Article
from automotive_newsletter.summarizer import classify_article
from automotive_newsletter.taxonomy import (
    ALL_TOPICS,
    PRIMARY_CATEGORIES,
    TOPICS_OTHER,
    TOPICS_SOFTWARE,
    classify_taxonomy,
    extract_entities,
    extract_topics,
)


def test_taxonomy_categories_and_topics_definitions():
    # 15 Primary Categories
    expected_categories = {
        "big", "oem", "tier1", "sdv", "ev_battery", "adas_autonomous",
        "regulation", "market", "manufacturing", "supply_chain",
        "cybersecurity", "software", "conference", "institution", "reference",
    }
    assert set(PRIMARY_CATEGORIES) == expected_categories

    # Automotive Software Topics
    expected_sw_topics = {
        "SDV", "E/E Architecture", "Zonal Architecture", "HPC", "Vehicle Computer",
        "AUTOSAR", "Adaptive AUTOSAR", "Classic AUTOSAR", "SOA", "Middleware",
        "OTA", "Vehicle OS", "Android Automotive", "QNX", "Embedded Linux",
        "Yocto", "Automotive Cybersecurity", "Functional Safety", "DevOps",
        "Cloud", "CI/CD", "AI", "ADAS", "Autonomous Driving",
    }
    assert expected_sw_topics.issubset(set(TOPICS_SOFTWARE))

    # Other Topics
    expected_other_topics = {
        "EV", "Battery", "Charging", "Semiconductor", "Supply Chain",
        "Manufacturing", "Regulation", "CO2", "Euro 7", "Trade", "Tariff",
    }
    assert expected_other_topics.issubset(set(TOPICS_OTHER))
    assert len(ALL_TOPICS) == len(TOPICS_SOFTWARE) + len(TOPICS_OTHER)


def test_canonical_mercedes_zonal_architecture_bosch_example():
    title = "Mercedes + Zonal Architecture + Bosch"
    res = classify_taxonomy(title)

    assert res.primary_category == "sdv"
    assert res.secondary_categories == ["oem", "tier1"]
    assert res.topics == ["Zonal Architecture", "E/E Architecture", "SDV"]
    assert res.entities == ["Mercedes-Benz", "Bosch"]

    # Also verify via classify_article on an Article instance
    article = Article(
        title="Mercedes + Zonal Architecture + Bosch",
        url="https://example.com/mercedes-zonal",
        source="Tech Wire",
    )
    classified = classify_article(article)
    assert classified.primary_category == "sdv"
    assert classified.category == "sdv"
    assert classified.secondary_categories == ["oem", "tier1"]
    assert classified.topics == ["Zonal Architecture", "E/E Architecture", "SDV"]
    assert classified.entities == ["Mercedes-Benz", "Bosch"]


def test_software_topics_and_implications():
    # 1. AUTOSAR Adaptive & Classic
    t1 = extract_topics("Vehicle adopting Adaptive AUTOSAR and Classic AUTOSAR stacks")
    assert "Adaptive AUTOSAR" in t1
    assert "Classic AUTOSAR" in t1
    assert "AUTOSAR" in t1
    assert "Middleware" in t1
    assert "SDV" in t1

    # 2. Vehicle OS, Android Automotive, QNX, Yocto
    t2 = extract_topics("Cockpit running Android Automotive with QNX hypervisor and Yocto Linux")
    assert "Android Automotive" in t2
    assert "QNX" in t2
    assert "Yocto" in t2
    assert "Embedded Linux" in t2
    assert "Vehicle OS" in t2
    assert "SDV" in t2

    # 3. HPC and Vehicle Computer
    t3 = extract_topics("Central vehicle computer with HPC cluster for zonal control")
    assert "HPC" in t3
    assert "Vehicle Computer" in t3
    assert "Zonal Architecture" in t3
    assert "E/E Architecture" in t3
    assert "SDV" in t3

    # 4. SOA, Middleware, OTA, DevOps, CI/CD
    t4 = extract_topics("Automotive DevOps pipeline deploying OTA updates via SOA middleware with CI/CD")
    assert "SOA" in t4
    assert "Middleware" in t4
    assert "OTA" in t4
    assert "DevOps" in t4
    assert "CI/CD" in t4
    assert "SDV" in t4


def test_adas_and_autonomous_driving():
    res = classify_taxonomy(
        title="Tesla unveils Cybercab autonomous driving robotaxi fleet",
        excerpt="The vehicle relies on vision-only ADAS and end-to-end AI neural networks.",
    )
    assert res.primary_category == "adas_autonomous"
    assert "oem" in res.secondary_categories
    assert "Autonomous Driving" in res.topics
    assert "ADAS" in res.topics
    assert "AI" in res.topics
    assert "Tesla" in res.entities


def test_cybersecurity_classification():
    res = classify_taxonomy(
        title="Automotive Cybersecurity vulnerability discovered in vehicle telematics",
        excerpt="Researchers demonstrated remote attack exploiting unpatched OTA gateway.",
    )
    assert res.primary_category == "cybersecurity"
    assert "Automotive Cybersecurity" in res.topics
    assert "OTA" in res.topics
    assert "SDV" in res.topics


def test_ev_battery_multi_domain_joint_venture():
    res = classify_taxonomy(
        title="GM and LG Energy Solution begin battery cell manufacturing at third Gigafactory",
        excerpt="The facility produces advanced EV cells with next-generation chemistry.",
    )
    assert res.primary_category == "ev_battery"
    assert "oem" in res.secondary_categories
    assert "tier1" in res.secondary_categories
    assert "manufacturing" in res.secondary_categories
    assert "GM" in res.entities
    assert "LG Energy Solution" in res.entities
    assert "Battery" in res.topics
    assert "Manufacturing" in res.topics
    assert "EV" in res.topics


def test_regulation_euro7_and_tariffs():
    res = classify_taxonomy(
        title="EU announces 38% tariff on imported EVs following trade investigation ahead of Euro 7",
        excerpt="Regulators set strict CO2 targets and trade penalties.",
    )
    assert res.primary_category == "regulation"
    assert "ev_battery" in res.secondary_categories
    assert "Tariff" in res.topics
    assert "Euro 7" in res.topics
    assert "CO2" in res.topics
    assert "Trade" in res.topics
    assert "Regulation" in res.topics
    assert "EV" in res.topics


def test_semiconductor_and_supply_chain():
    res = classify_taxonomy(
        title="Automotive chip shortage eases as NXP and Renesas ramp up microcontroller supply chain",
        excerpt="Tier 1 suppliers secure long-term semiconductor foundry contracts.",
    )
    assert res.primary_category == "supply_chain"
    assert "tier1" in res.secondary_categories
    assert "Semiconductor" in res.topics
    assert "Supply Chain" in res.topics
    assert "NXP" in res.entities
    assert "Renesas" in res.entities


def test_classification_does_not_rely_solely_on_source_name():
    # Even if source is Reuters or Automotive News (institution/media),
    # the article content determines the primary category
    res = classify_taxonomy(
        title="Mercedes adopts Zonal Architecture with Bosch centralized compute",
        excerpt="German automaker transitions to zonal E/E platform.",
        source="Reuters",
        source_type="media",
    )
    assert res.primary_category == "sdv"
    assert "oem" in res.secondary_categories
    assert "tier1" in res.secondary_categories
    assert "Mercedes-Benz" in res.entities
    assert "Bosch" in res.entities


def test_entity_normalization_across_aliases():
    text = "Daimler and General Motors partner with Mobis and Faurecia on CES display"
    entities = extract_entities(text)
    assert "Mercedes-Benz" in entities
    assert "GM" in entities
    assert "Hyundai Mobis" in entities
    assert "Forvia" in entities
    assert "CES" in entities


def test_ai_topic_detection_precision_and_false_positive_prevention():
    """Verify AI topic detection:

    Matches true AI terms (generative AI, machine learning, LLM, AI-powered).
    Does NOT match substring 'ai' inside words like said, Chairman, maintains, etc.
    """
    # True positives: MUST be classified with AI topic
    true_positives = [
        "New generative AI assistant for vehicles",
        "Automaker expands machine learning platform",
        "New automotive LLM announced",
        "AI-powered driver assistance system",
    ]
    for text in true_positives:
        topics = extract_topics(text)
        assert "AI" in topics, f"Expected 'AI' topic in: {text}, got: {topics}"

    # False positive traps: MUST NOT be classified with AI topic
    false_positives = [
        "The company said it will invest €2 billion",
        "Chairman visits Germany",
        "The automaker maintains production",
        "Certain suppliers gain market share against rivals",
    ]
    for text in false_positives:
        topics = extract_topics(text)
        assert "AI" not in topics, f"Did NOT expect 'AI' topic in: {text}, got: {topics}"


def test_automotive_software_ecosystem_and_virtualization_taxonomy():
    """Verify expanded automotive software, virtualization, and ecosystem topics."""
    # Virtualization & DevOps
    t_virt = extract_topics("Tier 1 deploys virtual ECU simulation with hardware-in-the-loop validation")
    assert "DevOps" in t_virt
    assert "SDV" in t_virt

    # Automotive Ecosystems (SOAFEE, Eclipse SDV)
    t_eco = extract_topics("Automaker adopts SOAFEE and Eclipse SDV open source framework")
    assert "SDV" in t_eco

    # SOA, SOME/IP, Automotive Ethernet
    t_soa = extract_topics("Zonal gateway with SOME/IP and Automotive Ethernet communication")
    assert "SOA" in t_soa
    assert "Middleware" in t_soa
    assert "SDV" in t_soa

    # Cybersecurity standards (ISO 21434, UNECE R155, UNECE R156)
    t_sec = extract_topics("Compliance with UNECE R156 software update and ISO 21434 cybersecurity")
    assert "Automotive Cybersecurity" in t_sec
    assert "SDV" in t_sec


def test_bare_ai_regression_and_compound_phrases():
    """Verify bare 'ai' inside common words is never classified as AI topic."""
    # Words with 'ai' substring that MUST NOT trigger AI topic
    false_positives = [
        "The spokesperson said the plant will resume operations",
        "Deliveries will resume again next month",
        "Daily maintenance inspection on assembly line",
        "The model is available in Europe and North America",
        "Brake failure caused emergency stop",
        "Engineers train workers on the new production line",
        "Daimler Truck reports quarterly commercial vehicle sales",
        "Automaker expands distribution network across Asia",
    ]
    for text in false_positives:
        topics = extract_topics(text)
        assert "AI" not in topics, f"False positive 'AI' detected in: '{text}' (topics: {topics})"

    # Legitimate AI expressions that MUST trigger AI topic
    true_positives = [
        "The vehicle uses AI for path planning and perception",
        "Next-generation A.I. platform deployed in vehicle",
        "AI-powered infotainment system with voice assistant",
        "AI-driven automated driving system",
        "Automotive AI chip announced for central compute",
        "In-vehicle AI agent assists driver with navigation",
        "Hyundai develops generative AI cockpit assistant",
        "자율주행을 위한 인공지능 기반 딥러닝 비전 솔루션",
    ]
    for text in true_positives:
        topics = extract_topics(text)
        assert "AI" in topics, f"Expected 'AI' topic in: '{text}' (topics: {topics})"


def test_canonical_brand_extraction_not_parent_groups():
    """Verify taxonomy entity extraction returns canonical brand/entity, not parent corporate groups."""
    e_audi = extract_entities("Audi unveils new electric luxury sedan in Ingolstadt")
    assert "Audi" in e_audi
    assert "Volkswagen" not in e_audi

    e_genesis = extract_entities("Genesis introduces flagship GV90 luxury electric SUV")
    assert "Genesis" in e_genesis
    assert "Hyundai" not in e_genesis

    e_mini = extract_entities("Mini Cooper EV debuts with circular OLED display")
    assert "Mini" in e_mini
    assert "BMW" not in e_mini

    e_jeep = extract_entities("Jeep expands plug-in hybrid 4xe lineup across North America")
    assert "Jeep" in e_jeep
    assert "Stellantis" not in e_jeep

    e_kia = extract_entities("Kia launches high-performance EV6 GT with 576 horsepower")
    assert "Kia" in e_kia
    assert "Hyundai" not in e_kia


def test_taxonomy_common_word_disambiguation():
    """Verify common ambiguous words (seat, mini, ram) are properly disambiguated in taxonomy."""
    # "seat"
    e_seat_neg = extract_entities("The driver adjusted the heated seat and seatbelt before driving")
    assert "SEAT" not in e_seat_neg

    e_seat_pos = extract_entities("Automaker SEAT announces future electrification strategy in Martorell")
    assert "SEAT" in e_seat_pos

    # "mini"
    e_mini_neg = extract_entities("A mini excavator was used during factory maintenance")
    assert "Mini" not in e_mini_neg

    e_mini_pos = extract_entities("BMW Mini Cooper begins production at Oxford plant")
    assert "Mini" in e_mini_pos
    assert "BMW" in e_mini_pos


