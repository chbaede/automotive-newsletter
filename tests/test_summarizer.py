from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx

from automotive_newsletter.models import Article
from automotive_newsletter.prompts import build_user_prompt
from automotive_newsletter.summarizer import (
    FallbackSummarizer,
    OllamaSummarizer,
    TemplateSummarizer,
    classify_article,
    summarize_article,
)


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


def test_template_summarizer_outputs_all_required_fields():
    article = Article(
        title="Mercedes-Benz introduces new MB.OS software architecture",
        url="https://example.com/mb-os",
        source="Tech Auto",
        category="sdv",
        excerpt="Mercedes-Benz announced details of its proprietary MB.OS operating system for future luxury vehicles.",
        tags=["Mercedes-Benz", "SDV"],
        score=80,
    )

    summarizer = TemplateSummarizer()
    res = summarizer.summarize(article)

    assert res.summary_ko
    assert res.summary_en
    assert res.why_it_matters_ko
    assert isinstance(res.key_points, list)
    assert len(res.key_points) >= 2
    assert res.summary_model == "template"
    assert res.summary_version == "v1"
    assert "Mercedes-Benz" in res.summary_ko


def test_ollama_summarizer_mocked_success():
    article = Article(
        title="Continental develops new zonal control unit for next-gen vehicles",
        url="https://example.com/continental-zcu",
        source="Automotive News",
        category="sdv",
        excerpt="Continental revealed a new zonal controller with high computing power.",
    )

    fake_payload = {
        "response": json.dumps(
            {
                "summary_ko": "콘티넨탈이 차세대 차량용 존 컨트롤러를 공개했습니다. 높은 연산 성능을 제공합니다.",
                "summary_en": "Continental announced a new zonal control unit for next-generation vehicles with high compute capabilities.",
                "why_it_matters_ko": "E/E 아키텍처 중앙 집중화 트렌드에 대응하는 핵심 부품 기술입니다.",
                "key_points": [
                    "콘티넨탈, 차세대 존 컨트롤러 공개",
                    "고성능 연산 기능 탑재",
                ],
            }
        )
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_payload

    with patch("httpx.Client.post", return_value=mock_resp):
        summarizer = OllamaSummarizer(base_url="http://localhost:11434", model="llama3.2")
        res = summarizer.summarize(article, content="Continental unveiled a new zonal controller...")

        assert "콘티넨탈" in res.summary_ko
        assert "Continental announced" in res.summary_en
        assert "E/E 아키텍처" in res.why_it_matters_ko
        assert len(res.key_points) == 2
        assert res.summary_model == "ollama:llama3.2"
        assert res.summary_version == "v1"


def test_fallback_summarizer_on_network_failure():
    article = Article(
        title="Toyota announces new battery technology roadmap",
        url="https://example.com/toyota-battery",
        source="Reuters",
        category="ev_battery",
        excerpt="Toyota plans to introduce solid-state batteries in the coming years.",
        tags=["Toyota", "Battery"],
    )

    primary = OllamaSummarizer()
    fallback = TemplateSummarizer()
    composite = FallbackSummarizer(primary=primary, fallback=fallback)

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        res = composite.summarize(article)

        # Successfully falls back to template summarizer without raising exception
        assert res.summary_model == "template"
        assert "Toyota" in res.summary_ko
        assert res.why_it_matters_ko
        assert len(res.key_points) > 0


def test_fallback_summarizer_on_malformed_json():
    article = Article(
        title="Volvo expands EV software development center",
        url="https://example.com/volvo-software",
        source="Auto Express",
        category="software",
        excerpt="Volvo is hiring engineers to accelerate vehicle software development.",
    )

    primary = OllamaSummarizer()
    fallback = TemplateSummarizer()
    composite = FallbackSummarizer(primary=primary, fallback=fallback)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "This is plain text, not JSON"}

    with patch("httpx.Client.post", return_value=mock_resp):
        res = composite.summarize(article)

        assert res.summary_model == "template"
        assert res.summary_ko
        assert res.summary_en


def test_classify_article_attaches_summary_metadata():
    article = Article(
        title="Qualcomm Snapdragon Digital Chassis adopted by multiple OEMs",
        url="https://example.com/qualcomm-chassis",
        source="Tech Crunch",
        category="sdv",
        excerpt="Qualcomm announced increasing adoption of Snapdragon Digital Chassis.",
    )

    classified = classify_article(article)

    assert classified.summary_ko
    assert classified.summary_en
    assert classified.why_it_matters_ko
    assert isinstance(classified.key_points, list)
    assert classified.summary_model == "template"
    assert classified.summary_version == "v1"
    assert classified.summary_created_at is not None


def test_prompt_builder_conservative_on_short_excerpt():
    prompt = build_user_prompt(
        title="Quick Headline",
        source="Media",
        content="Short text",
        is_short_excerpt=True,
    )
    assert "Notice: Only a brief excerpt is available" in prompt
    assert "conservative" in prompt
