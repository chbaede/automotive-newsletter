from automotive_newsletter.models import Article
from automotive_newsletter.summarizer import classify_article, summarize_article


def test_classify_article_prefers_sdv_keywords():
    article = Article(
        title="BMW and Qualcomm expand software-defined vehicle architecture",
        url="https://example.com/bmw-qualcomm-sdv",
        source="Auto Tech",
        excerpt="The companies are working on zonal architecture and OTA updates.",
    )

    classified = classify_article(article)

    assert classified.category == "sdv"
    assert "BMW" in classified.tags
    assert "Qualcomm" in classified.tags
    assert "SDV" in classified.tags
    assert classified.score > 50


def test_summarize_article_writes_korean_business_context():
    article = Article(
        title="Bosch invests in new ADAS components for automakers",
        url="https://example.com/bosch-adas",
        source="Supplier Daily",
        category="tier1",
        excerpt="Bosch said the investment supports automaker demand for driver assistance systems.",
        tags=["Bosch", "ADAS"],
        score=75,
    )

    summary = summarize_article(article)

    assert "Bosch" in summary
    assert "Tier 1" in summary
    assert "원문 제목" not in summary
    assert "ADAS" not in summary or "핵심 신호" in summary
