from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/webhooks/slack")
async def slack_webhook(request: Request) -> dict:
    return {"ok": True}
