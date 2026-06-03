import httpx
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from slate.config import settings
from slate.database import get_client
from slate.pipeline import orchestrator

MOCK_MODE = True

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _post_to_slack(payload: dict) -> None:
    """POST payload to SLACK_WEBHOOK_URL, or print in MOCK_MODE."""
    if MOCK_MODE:
        print(f"[webhooks] MOCK_MODE — would POST to Slack: {payload}", flush=True)
        return
    async with httpx.AsyncClient() as client:
        await client.post(settings.SLACK_WEBHOOK_URL, json=payload)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def _run_start_job(
    user_id: str,
    channel_id: str,
    topic: str,
    trigger_id: str,
) -> None:
    result = await orchestrator.start_job(
        slack_user_id=user_id,
        slack_channel_id=channel_id,
        slack_thread_ts=trigger_id,
        topic=topic,
        brand_image_urls=[],
        style_image_url=None,
        slack_bot_token=settings.SLACK_BOT_TOKEN,
    )
    job_id = result["job_id"]
    questions = result["questions"]

    questions_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    payload = {
        "text": f"🔍 Got it. A few quick questions before I build:\n\n{questions_text}",
        "thread_ts": trigger_id,
    }
    await _post_to_slack(payload)


async def _run_complete_job(job_id: str, user_text: str, thread_ts: str) -> None:
    result = await orchestrator.complete_job(job_id, user_text)
    brief = result["brief"]
    canva_url = result["canva_url"]

    payload = {
        "text": (
            f"✅ Carousel brief built!\n\n"
            f"*Hook:* {brief['hook']}\n\n"
            f"🎨 Canva: {canva_url}"
        ),
        "thread_ts": thread_ts,
    }
    await _post_to_slack(payload)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/webhooks/slack")
async def slack_slash_command(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    # Slack url_verification (JSON body)
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        if "challenge" in body:
            return JSONResponse({"challenge": body["challenge"]})

    form = await request.form()

    # Slack url_verification via form (edge case)
    if "challenge" in form:
        return JSONResponse({"challenge": form["challenge"]})

    user_id = form.get("user_id", "")
    channel_id = form.get("channel_id", "")
    topic = (form.get("text") or "").strip()
    trigger_id = form.get("trigger_id", "")

    background_tasks.add_task(
        _run_start_job, user_id, channel_id, topic, trigger_id
    )

    return JSONResponse(
        {"text": "⚡ Analysing your brand... I'll post questions in a moment."}
    )


@router.post("/webhooks/slack/reply")
async def slack_reply(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    body = await request.json()

    # Slack url_verification
    if "challenge" in body:
        return JSONResponse({"challenge": body["challenge"]})

    event = body.get("event", {})

    # Only handle threaded user messages
    if event.get("type") != "message" or not event.get("thread_ts"):
        return JSONResponse({"ok": True})

    # Ignore bot messages
    if event.get("bot_id"):
        return JSONResponse({"ok": True})

    thread_ts = event["thread_ts"]
    user_text = event.get("text", "")

    if MOCK_MODE:
        job_id = "mock-job-001"
    else:
        db = get_client()
        rows = (
            db.table("carousel_jobs")
            .select("id")
            .eq("slack_thread_ts", thread_ts)
            .eq("status", "pending_answers")
            .limit(1)
            .execute()
        )
        if not rows.data:
            return JSONResponse({"ok": True})
        job_id = rows.data[0]["id"]

    background_tasks.add_task(_run_complete_job, job_id, user_text, thread_ts)

    return JSONResponse({"ok": True})
