import httpx

from slate.config import settings

MOCK_MODE = True

_CANVA_API_BASE = "https://api.canva.com/rest/v1"


async def build_canva_carousel(
    brief: dict,
    brand_kit_id: str | None = None,
) -> str:
    if MOCK_MODE:
        print("canva_builder: MOCK_MODE — returning mock Canva URL", flush=True)
        return "https://www.canva.com/design/mock-slate-carousel/view"

    headers = {
        "Authorization": f"Bearer {settings.CANVA_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(base_url=_CANVA_API_BASE, headers=headers) as client:
        # Step 1: Create design
        try:
            create_payload: dict = {
                "design_type": {"type": "preset", "name": "InstagramPost"},
                "title": brief["topic"][:50],
            }
            if brand_kit_id:
                create_payload["brand_kit_id"] = brand_kit_id

            resp = await client.post("/designs", json=create_payload)
            if resp.status_code not in (200, 201):
                print(
                    f"canva_builder: create design failed — {resp.status_code} {resp.text}",
                    flush=True,
                )
                raise RuntimeError(f"Canva API error: {resp.status_code}")
            design_id = resp.json()["design"]["id"]
        except RuntimeError:
            raise
        except Exception as exc:
            print(f"canva_builder: error creating design — {exc}", flush=True)
            raise

        # Step 2: Build pages list
        pages = []

        # Hook page
        pages.append({"title": brief["hook"], "body": ""})

        # Body slides
        for slide in brief.get("slides", []):
            pages.append(
                {
                    "title": slide["title"],
                    "body": slide["body_copy"],
                    "notes": slide["visual_direction"],
                }
            )

        # CTA page
        cta = brief.get("cta_slide", {})
        pages.append(
            {
                "title": cta.get("headline", ""),
                "body": cta.get("sub_copy", ""),
            }
        )

        # Add pages to design
        try:
            for page in pages:
                resp = await client.post(f"/designs/{design_id}/pages", json=page)
                if resp.status_code not in (200, 201):
                    print(
                        f"canva_builder: add page failed — {resp.status_code} {resp.text}",
                        flush=True,
                    )
                    raise RuntimeError(f"Canva API error: {resp.status_code}")
        except RuntimeError:
            raise
        except Exception as exc:
            print(f"canva_builder: error adding pages — {exc}", flush=True)
            raise

    return f"https://www.canva.com/design/{design_id}/edit"
