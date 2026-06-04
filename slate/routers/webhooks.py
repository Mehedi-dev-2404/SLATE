import httpx
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from slate.config import settings
from slate.database import get_client
from slate.pipeline import onboarding, orchestrator
from slate.pipeline import content_strategist

MOCK_MODE = False

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


async def _run_setup(workspace_id: str, channel_id: str) -> None:
    result = await onboarding.start_onboarding(workspace_id, channel_id)
    await _post_to_slack({"text": result["message"]})


async def _run_onboarding_reply(workspace_id: str, step: int, text: str) -> None:
    result = await onboarding.process_onboarding_reply(workspace_id, step, text)
    await _post_to_slack({"text": result["message"]})


async def _run_record_performance(
    workspace_id: str, carousel_job_id: str, hook: str,
    topic: str, content_type: str, rating: str,
) -> None:
    await content_strategist.record_performance(
        workspace_id, carousel_job_id, hook, topic, content_type, rating
    )
    await _post_to_slack({"text": "Thanks! I'll use that to improve future carousels."})


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


@router.post("/webhooks/slate-setup")
async def slate_setup(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    form = await request.form()
    channel_id = form.get("channel_id", "")
    workspace_id = channel_id

    background_tasks.add_task(_run_setup, workspace_id, channel_id)

    return JSONResponse({"text": "Starting setup..."})


@router.post("/webhooks/slate-status")
async def slate_status(request: Request) -> JSONResponse:
    form = await request.form()
    workspace_id = form.get("channel_id", "")

    if MOCK_MODE:
        db_rows = []
    else:
        db = get_client()
        result = (
            db.table("brand_profiles")
            .select("*")
            .eq("workspace_id", workspace_id)
            .limit(1)
            .execute()
        )
        db_rows = result.data

    if not db_rows or not db_rows[0].get("onboarding_complete"):
        return JSONResponse(
            {"text": "⚠️ Brand not set up yet. Run /slate-setup to get started."}
        )

    p = db_rows[0]
    summary = (
        f"✅ *SLATE Status*\n"
        f"*Business:* {p.get('business_description', '')}\n"
        f"*Audience:* {p.get('target_audience', '')}\n"
        f"*Goals:* {p.get('content_goals', '')}\n"
        f"*Tone:* {p.get('brand_tone', '')}\n"
        f"*Cadence:* {p.get('cadence', '')}\n"
        f"*Off limits:* {p.get('off_limits', '')}"
    )
    return JSONResponse({"text": summary})


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

    if event.get("type") != "message":
        return JSONResponse({"ok": True})

    # Ignore bot messages
    if event.get("bot_id"):
        return JSONResponse({"ok": True})

    user_text = event.get("text", "").strip()

    # --- DM: onboarding or performance rating ---
    if event.get("channel_type") == "im":
        workspace_id = event.get("channel", "")

        if MOCK_MODE:
            print(
                f"[webhooks] MOCK_MODE — DM from workspace={workspace_id} text={user_text!r}",
                flush=True,
            )
            return JSONResponse({"ok": True})

        db = get_client()
        profile_rows = (
            db.table("brand_profiles")
            .select("onboarding_complete, onboarding_step, id, topic, brand_tone")
            .eq("workspace_id", workspace_id)
            .limit(1)
            .execute()
        )

        if profile_rows.data:
            profile = profile_rows.data[0]

            if not profile.get("onboarding_complete"):
                step = profile.get("onboarding_step", 1)
                background_tasks.add_task(
                    _run_onboarding_reply, workspace_id, step, user_text
                )
                return JSONResponse({"ok": True})

            # Performance rating reply
            if user_text.lower() in ("good", "average", "poor"):
                job_rows = (
                    db.table("carousel_jobs")
                    .select("id, topic, brief")
                    .eq("slack_channel_id", workspace_id)
                    .eq("status", "done")
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if job_rows.data:
                    job = job_rows.data[0]
                    hook = (job.get("brief") or {}).get("hook", "")
                    background_tasks.add_task(
                        _run_record_performance,
                        workspace_id,
                        job["id"],
                        hook,
                        job.get("topic", ""),
                        "unknown",
                        user_text.lower(),
                    )
                return JSONResponse({"ok": True})

        return JSONResponse({"ok": True})

    # --- Thread reply: carousel completion ---
    thread_ts = event.get("thread_ts")
    if not thread_ts:
        return JSONResponse({"ok": True})

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
