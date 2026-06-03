import json

from anthropic import AsyncAnthropic

from slate.config import settings
from slate.models.carousel import BrandAnalysis, StyleAnalysis

MOCK_MODE = True

_FALLBACK_QUESTIONS = [
    "Who is this carousel for — your own brand or a client?",
    "What's the goal — educate, sell, or build credibility?",
    "Any words or phrases that are off-brand and should be avoided?",
]


async def generate_questions(
    topic: str,
    brand_analysis: BrandAnalysis,
    style_analysis: StyleAnalysis | None,
) -> list[str]:
    if MOCK_MODE:
        print("question_generator: MOCK_MODE — returning mock questions", flush=True)
        return _FALLBACK_QUESTIONS

    prompt_parts = [
        f"Carousel topic: {topic}",
        f"Brand tone: {brand_analysis.tone}",
        f"Visual style: {brand_analysis.visual_style}",
        f"Colour palette: {', '.join(brand_analysis.palette)}",
    ]
    if style_analysis:
        prompt_parts += [
            f"Layout pattern: {style_analysis.layout_pattern}",
            f"Slide structure: {style_analysis.slide_structure}",
            f"Design density: {style_analysis.design_density}",
        ]

    prompt = "\n".join(prompt_parts) + (
        "\n\nBased on this brand analysis and carousel topic, generate 3-5 targeted "
        "clarifying questions to ask the user before building their carousel. "
        "Focus ONLY on what is genuinely unclear. If tone is already obvious, do not "
        "ask about tone. Questions should be short and conversational. "
        "Return ONLY a JSON array of strings. No markdown, no preamble."
    )

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip optional ```json fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        questions = json.loads(raw)
        if not isinstance(questions, list) or not (2 <= len(questions) <= 6):
            raise ValueError("invalid question count")
        return [str(q) for q in questions]
    except Exception:
        return _FALLBACK_QUESTIONS
