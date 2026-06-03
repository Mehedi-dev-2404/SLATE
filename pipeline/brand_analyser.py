import base64
import json

import httpx
from anthropic import Anthropic

from slate.config import settings
from slate.models.carousel import BrandAnalysis

MOCK_MODE = True

_SYSTEM_PROMPT = (
    "You are a brand analyst. Analyse the provided brand materials and extract: "
    "color palette (as hex values if visible, otherwise describe), tone of voice, "
    "visual style, and typography feel. Return ONLY a JSON object with keys: "
    "palette (array of strings), tone (string), visual_style (string), "
    "typography_feel (string). No markdown, no preamble."
)


async def analyse_brand(
    image_urls: list[str],
    slack_bot_token: str,
) -> BrandAnalysis:
    if MOCK_MODE:
        print("brand_analyser: MOCK_MODE — returning mock BrandAnalysis", flush=True)
        return BrandAnalysis(
            palette=["#1B2B4B", "#F5F0E8", "#E8604C"],
            tone="Direct and confident, slightly informal",
            visual_style="Clean with bold typography, minimal imagery",
            typography_feel="Strong sans-serif, high contrast",
        )

    # Download images from Slack and convert to base64
    image_contents = []
    async with httpx.AsyncClient() as http:
        for url in image_urls:
            response = await http.get(
                url,
                headers={"Authorization": f"Bearer {slack_bot_token}"},
                follow_redirects=True,
            )
            response.raise_for_status()
            media_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
            encoded = base64.standard_b64encode(response.content).decode("utf-8")
            image_contents.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": encoded,
                    },
                }
            )

    image_contents.append(
        {"type": "text", "text": "Analyse these brand materials and return the JSON object as instructed."}
    )

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": image_contents}],
        )
    except Exception as exc:
        print(f"brand_analyser: Anthropic API error — {exc}", flush=True)
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
        print(f"brand_analyser: JSON parse error — raw response: {raw!r}", flush=True)
        raise ValueError(f"Failed to parse BrandAnalysis JSON: {exc}") from exc

    return BrandAnalysis(
        palette=data["palette"],
        tone=data["tone"],
        visual_style=data["visual_style"],
        typography_feel=data["typography_feel"],
    )
