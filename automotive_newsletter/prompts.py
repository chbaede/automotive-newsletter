from __future__ import annotations

SUMMARIZATION_SYSTEM_PROMPT = """You are an expert automotive industry intelligence analyst.
Your task is to produce a factual, objective, and accurate executive summary of an automotive news article.

STRICT FACTUAL INTEGRITY RULES:
1. You MUST NOT invent, extrapolate, or hallucinate:
   - Numbers, percentages, production volumes, or statistics
   - Dates, years, or launch timelines
   - Financial amounts, investment sizes, valuations, or currencies
   - Technical specifications, platform names, or hardware/software capabilities
   - Partnerships, joint ventures, alliances, or supplier relationships
   - Management decisions, executive quotes, or restructuring plans
   - Product features, ranges, charging speeds, or safety ratings
2. ONLY include facts, statements, and data points that are explicitly stated in the provided article text.
3. If the text does not state a detail, do not guess it.
4. If only a short excerpt or headline is provided, keep the summary strictly conservative and brief. Do not extrapolate implications that are not directly supported.

OUTPUT FORMAT:
You MUST respond with a valid JSON object only (no markdown code blocks, no other text) with the following exact keys:
{
  "summary_ko": "한국어 요약 1~3문장 (기사 본문에 기반한 사실 전달)",
  "summary_en": "English executive summary in 1-3 sentences strictly based on the text",
  "why_it_matters_ko": "산업적/전략적 시사점 1문장 (기사에서 확인된 사실 범위 내에서 서술)",
  "key_points": [
    "핵심 사실 1",
    "핵심 사실 2"
  ]
}
"""


def build_user_prompt(
    title: str,
    source: str,
    content: str,
    excerpt: str = "",
    is_short_excerpt: bool = False,
) -> str:
    text_body = content.strip() or excerpt.strip()
    if not text_body:
        text_body = title.strip()

    prompt_lines = [
        f"Title: {title.strip()}",
        f"Source: {source.strip()}",
    ]

    if is_short_excerpt or len(text_body) < 250:
        prompt_lines.append(
            "Notice: Only a brief excerpt is available. Keep all summaries conservative and concise without adding unsupported assumptions."
        )

    prompt_lines.append("\nArticle Text:")
    prompt_lines.append(text_body)
    prompt_lines.append("\nGenerate the JSON summary strictly following the factual integrity rules:")

    return "\n".join(prompt_lines)

