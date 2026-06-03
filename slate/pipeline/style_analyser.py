import base64
import json

import httpx
from anthropic import Anthropic

from slate.config import settings
from slate.models.carousel import StyleAnalysis

MOCK_MODE = True

_SYSTEM_PROMPT = (
    "You are a design analyst. Analyse this Instagram carousel slide or style reference. Extract: "
    "layout_pattern (how text and images are arranged), "
    "slide_structure (the narrative flow pattern you can infer), "
    "design_density (minimal/balanced/busy with explanation). "
    "Return ONLY a JSON object with keys: layout_pattern, slide_structure, design_density. "
    "No markdown, no preamble."
)


async def analyse_style(
    image_url: str,
    slack_bot_token: str,
) -> StyleAnalysis | None:
    if not image_url:
        return None

    if MOCK_MODE:
        print("style_analyser: MOCK_MODE — returning mock StyleAnalysis", flush=True)
        return StyleAnalysis(
            layout_pattern="Text-led with bold hook, image secondary",
            slide_structure="Hook → 3-4 value slides → CTA",
            design_density="Minimal — lots of whitespace, one idea per slide",
        )

    # Download image from Slack
    async with httpx.AsyncClient() as http:
        response = await http.get(
            image_url,
            headers={"Authorization": f"Bearer {slack_bot_token}"},
            follow_redirects=True,
        )
        response.raise_for_status()
        media_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
        encoded = base64.standard_b64encode(response.content).decode("utf-8")

    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        },
        {"type": "text", "text": "Analyse this style reference and return the JSON object as instructed."},
    ]

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        print(f"style_analyser: Anthropic API error — {exc}", flush=True)
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
    except json.JSONDecodeError:
        print(f"style_analyser: JSON parse error — raw response: {raw!r}", flush=True)
        return None

    return StyleAnalysis(
        layout_pattern=data["layout_pattern"],
        slide_structure=data["slide_structure"],
        design_density=data["design_density"],
    )
