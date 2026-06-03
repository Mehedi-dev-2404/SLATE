from typing import Any

MOCK_MODE = True


async def build_canva_design(brief: dict[str, Any], slack_user_id: str) -> str:
    print(f"[canva_builder] Building Canva design for user={slack_user_id} (MOCK_MODE={MOCK_MODE})", flush=True)
    return "https://www.canva.com/design/mock-design-id/view"
