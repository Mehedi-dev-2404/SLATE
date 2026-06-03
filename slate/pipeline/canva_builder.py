import httpx

from slate.config import Settings

MOCK_MODE = False

CANVA_API_BASE = "https://api.canva.com/rest/v1"


async def get_canva_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {settings.canva_access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def build_canva_carousel(
    brief: dict,
    brand_kit_id: str | None = None,
) -> str:
    if MOCK_MODE:
        print("canva_builder: MOCK_MODE — returning mock Canva URL", flush=True)
        return "https://www.canva.com/design/mock-slate-carousel/view"

    settings = Settings()
    print("canva_builder: creating Canva design...", flush=True)

    async with await get_canva_client(settings) as client:
        # Step 1: Create design
        create_payload: dict = {
            "design_type": {
                "type": "preset",
                "name": "presentation",
            },
            "title": brief["topic"][:50],
        }
        if brand_kit_id:
            create_payload["brand_template_id"] = brand_kit_id

        try:
            resp = await client.post(f"{CANVA_API_BASE}/designs", json=create_payload)
        except Exception as exc:
            print(f"canva_builder: request error — {exc}", flush=True)
            raise

        if resp.status_code not in (200, 201):
            print(f"canva_builder: create design failed {resp.status_code} — {resp.text}", flush=True)
            raise RuntimeError(f"Canva create design failed: {resp.status_code}")

        design_data = resp.json()
        design_id = design_data.get("design", {}).get("id")
        if not design_id:
            print(f"canva_builder: no design_id in response — {resp.text}", flush=True)
            raise RuntimeError("Canva: no design_id returned")

        print(f"canva_builder: design created — {design_id}", flush=True)

        # Step 2: Return edit URL
        url = f"https://www.canva.com/design/{design_id}/edit"
        print(f"canva_builder: done — {url}", flush=True)
        return url
