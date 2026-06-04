import asyncio
import base64

import httpx
from google import genai
from google.genai import types

from slate.config import Settings

MOCK_MODE = False

SLIDE_STYLE = """
Clean minimal Instagram carousel slide.
Dark navy background (#1B2B4B).
Bold white sans-serif headline text, large, centered.
Smaller white subtitle text below.
No borders, no clutter, professional and modern.
Square format 1:1.
"""


async def generate_slide_image(
    headline: str,
    body_copy: str,
    slide_number: int,
    total_slides: int,
    brand_tone: str = "bold and direct",
) -> str:  # returns base64 encoded PNG
    settings = Settings()
    client = genai.Client(api_key=settings.google_api_key)

    prompt = (
        f"{SLIDE_STYLE}\n"
        f"Slide {slide_number} of {total_slides}.\n"
        f'Headline: "{headline}"\n'
        f'Body text: "{body_copy}"\n'
        f"Tone: {brand_tone}\n"
        "Make it visually striking and ready to post on Instagram."
    )

    try:
        response = client.models.generate_images(
            model="imagen-4.0-flash-preview-05-20",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            ),
        )
        image_data = response.generated_images[0].image.image_bytes
        return base64.b64encode(image_data).decode()
    except Exception as exc:
        print(f"image_generator: slide {slide_number} failed — {exc}", flush=True)
        raise


async def generate_carousel(
    brief: dict,
    brand_tone: str = "bold and direct",
) -> list[str]:  # returns list of base64 PNG strings
    if MOCK_MODE:
        print("image_generator: MOCK_MODE — returning mock images", flush=True)
        return ["mock_base64_image"] * (len(brief["slides"]) + 2)  # hook + slides + CTA

    slides_to_generate = []

    # Hook slide
    slides_to_generate.append({"headline": brief["hook"], "body_copy": ""})

    # Body slides
    for slide in brief["slides"]:
        slides_to_generate.append(
            {
                "headline": slide.get("title", ""),
                "body_copy": slide.get("body_copy", ""),
            }
        )

    # CTA slide
    slides_to_generate.append(
        {
            "headline": brief["cta_slide"]["headline"],
            "body_copy": brief["cta_slide"]["sub_copy"],
        }
    )

    total = len(slides_to_generate)
    print(f"image_generator: generating {total} slides...", flush=True)
    images = []

    for i, slide in enumerate(slides_to_generate):
        print(f"image_generator: generating slide {i + 1}/{total}", flush=True)
        img = await generate_slide_image(
            headline=slide["headline"],
            body_copy=slide["body_copy"],
            slide_number=i + 1,
            total_slides=total,
            brand_tone=brand_tone,
        )
        images.append(img)
        await asyncio.sleep(1)

    print(f"image_generator: all {total} slides generated", flush=True)
    return images


async def upload_images_to_slack(
    images: list[str],  # base64 encoded PNGs
    channel_id: str,
    slack_bot_token: str,
    topic: str,
) -> list[str]:  # returns list of Slack file permalink URLs
    uploaded_urls = []

    async with httpx.AsyncClient() as client:
        for i, img_b64 in enumerate(images):
            img_bytes = base64.b64decode(img_b64)
            response = await client.post(
                "https://slack.com/api/files.uploadV2",
                headers={"Authorization": f"Bearer {slack_bot_token}"},
                files={"file": (f"slide_{i + 1}.png", img_bytes, "image/png")},
                data={
                    "channel": channel_id,
                    "filename": f"slide_{i + 1}.png",
                    "title": f"{topic} — Slide {i + 1}",
                },
            )
            result = response.json()
            if result.get("ok"):
                url = result.get("file", {}).get("permalink", "")
                uploaded_urls.append(url)
                print(f"image_generator: slide {i + 1} uploaded", flush=True)
            else:
                print(f"image_generator: upload failed slide {i + 1} — {result}", flush=True)

    return uploaded_urls
