import json
from typing import Any

from anthropic import AsyncAnthropic

from slate.config import settings
from slate.models.carousel import BrandAnalysis, StyleAnalysis

MOCK_MODE = False

_REQUIRED_KEYS = {"topic", "slide_count", "tone", "hook", "slides", "cta_slide", "caption", "hashtags"}

_SYSTEM_PROMPT = (
    "You are an expert Instagram content strategist. Build a complete carousel brief based on the inputs provided. "
    "Return ONLY a valid JSON object. No markdown, no preamble. "
    "The JSON must have exactly these keys: topic, slide_count, tone, hook, slides (array), "
    "cta_slide (object with headline and sub_copy), caption, hashtags (array of strings without # symbol). "
    "Each object in the slides array must use the key 'title' (not 'headline') for the slide heading."
)

_MOCK_BRIEF: dict[str, Any] = {
    "topic": "5 reasons UGC outperforms studio content",
    "slide_count": 7,
    "tone": "Warm, confident, evidence-led",
    "hook": "Your customers trust strangers more than you.",
    "slides": [
        {
            "slide_number": 1,
            "title": "The Trust Gap",
            "body_copy": "82% of consumers trust peer reviews over brand content.",
            "visual_direction": "Bold stat on clean background, brand navy",
        },
        {
            "slide_number": 2,
            "title": "It Feels Real",
            "body_copy": "UGC looks unpolished. That's the point.",
            "visual_direction": "Split: glossy studio shot vs phone video",
        },
        {
            "slide_number": 3,
            "title": "The Algorithm Loves It",
            "body_copy": "Native-looking content gets 3x more reach.",
            "visual_direction": "Phone screen mockup showing engagement",
        },
        {
            "slide_number": 4,
            "title": "It Scales",
            "body_copy": "One campaign brief can generate 50 unique assets.",
            "visual_direction": "Grid of varied UGC thumbnails",
        },
        {
            "slide_number": 5,
            "title": "Your Customers Do the Selling",
            "body_copy": "Word of mouth, automated.",
            "visual_direction": "Customer holding product, candid feel",
        },
    ],
    "cta_slide": {
        "headline": "Ready to test UGC for your brand?",
        "sub_copy": "Link in bio — free strategy call this week.",
    },
    "caption": (
        "Studio content is beautiful. But it doesn't convert like this. "
        "Here's why UGC is winning in 2025 — and how to use it without a big budget."
    ),
    "hashtags": [
        "ugccontent",
        "contentmarketing",
        "instagramgrowth",
        "socialmediastrategy",
        "ugcmarketing",
        "brandcontent",
        "creatoreconomy",
        "contentcreator",
    ],
}


async def build_brief(
    topic: str,
    brand_analysis: BrandAnalysis,
    style_analysis: StyleAnalysis | None,
    user_answers: str,
    slide_count: int = 7,
) -> dict[str, Any]:
    if MOCK_MODE:
        print("brief_builder: MOCK_MODE — returning mock brief", flush=True)
        return _MOCK_BRIEF

    style_notes = (
        f"Layout pattern: {style_analysis.layout_pattern}\n"
        f"Slide structure: {style_analysis.slide_structure}\n"
        f"Design density: {style_analysis.design_density}"
        if style_analysis
        else "No style reference provided."
    )

    user_prompt = (
        f"Topic: {topic}\n"
        f"Brand tone: {brand_analysis.tone}\n"
        f"Visual style: {brand_analysis.visual_style}\n"
        f"Color palette: {', '.join(brand_analysis.palette)}\n"
        f"Style reference notes: {style_notes}\n"
        f"User answers: {user_answers}\n"
        f"Slide count: {slide_count}\n\n"
        "Make the hook provocative and specific. "
        "Each slide should have one clear idea. Body copy maximum 2 sentences. "
        "Visual direction should be actionable for a designer. "
        "IMPORTANT: In the slides array, use 'title' as the key for each slide heading. Do not use 'headline'."
    )

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        print(f"brief_builder: Anthropic API error — {exc}", flush=True)
        raise

    raw = message.content[0].text.strip()
    # Strip ```json fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"brief_builder: JSON parse error — raw response: {raw!r}", flush=True)
        raise ValueError(f"Failed to parse brief JSON: {exc}") from exc

    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        print(f"brief_builder: missing keys in response — {missing}", flush=True)
        raise ValueError(f"Brief response missing required keys: {missing}")

    return data
