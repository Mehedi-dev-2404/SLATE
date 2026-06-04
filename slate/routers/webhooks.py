import httpx
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from slate.config import settings
from slate.database import get_client
from slate.pipeline import content_strategist, onboarding, orchestrator

MOCK_MODE = False

router = APIRouter()


# ---------------------------------------------------------------------------
# Slack Web API helper — DM replies via chat.postMessage
# ---------------------------------------------------------------------------

async def _dm(user_id: str, text: str) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
            json={"channel": user_id, "text": text},
        )
        data = resp.json()
        if not data.get("ok"):
            print(f"[webhooks] chat.postMessage error: {data.get('error')}", flush=True)


# ---------------------------------------------------------------------------
# Background task: handle all DM logic
# ---------------------------------------------------------------------------

async def _handle_dm(user_id: str, text: str) -> None:
    db = get_client()
    text_lower = text.lower().strip()

    # Fetch brand profile
    profile_rows = (
        db.table("brand_profiles")
        .select("*")
        .eq("workspace_id", user_id)
        .limit(1)
        .execute()
    )
    profile = profile_rows.data[0] if profile_rows.data else None

    # ── ONBOARDING PATH ──────────────────────────────────────────────────────
    if not profile or not profile.get("onboarding_complete"):
        step = profile.get("onboarding_step", 0) if profile else 0

        if step == 0:
            result = await onboarding.start_onboarding(user_id, user_id)
        else:
            result = await onboarding.process_onboarding_reply(user_id, step, text)

        await _dm(user_id, result["message"])

        if result.get("complete"):
            # Onboarding done — kick off first autonomous carousel
            await _dm(user_id, "⚡ Generating your first carousel now...")
            try:
                fresh = (
                    db.table("brand_profiles")
                    .select("*")
                    .eq("workspace_id", user_id)
                    .limit(1)
                    .execute()
                )
                brand_profile = fresh.data[0]
                from slate.pipeline.scheduler import run_autonomous_pipeline
                result2 = await run_autonomous_pipeline(user_id, brand_profile)
                n_slides = len(result2.get("images", []))
                await _dm(
                    user_id,
                    f"🎨 *Your first carousel is ready!*\n\n"
                    f"*Topic:* {result2['topic']}\n\n"
                    f"{n_slides} slides uploaded above ☝️"
                )
            except Exception as exc:
                print(f"[webhooks] first carousel error: {exc}", flush=True)
                await _dm(user_id, "⚠️ Couldn't generate first carousel — try 'make a carousel' when ready.")
        return

    # ── BRAND EXISTS + ONBOARDING COMPLETE ───────────────────────────────────

    # Intent: carousel creation
    if any(kw in text_lower for kw in ("carousel", "make", "create", "build")):
        await _dm(user_id, "⚡ On it! Generating your carousel now...")
        try:
            topic = await content_strategist.generate_topic(
                workspace_id=user_id,
                content_type="educational",
                brand_profile=profile,
            )
            user_answers = (
                f"Business: {profile.get('business_description', '')}\n"
                f"Audience: {profile.get('target_audience', '')}\n"
                f"Goals: {profile.get('content_goals', '')}\n"
                f"Tone: {profile.get('brand_tone', '')}\n"
                f"Off limits: {profile.get('off_limits', '')}"
            )
            r1 = await orchestrator.start_job(
                slack_user_id=user_id,
                slack_channel_id=user_id,
                slack_thread_ts="",
                topic=topic,
                brand_image_urls=[],
                style_image_url=None,
                slack_bot_token=settings.SLACK_BOT_TOKEN,
            )
            r2 = await orchestrator.complete_job(r1["job_id"], user_answers)
            images = r2.get("images", [])
            if images:
                from slate.pipeline.image_generator import upload_images_to_slack
                await upload_images_to_slack(
                    images=images,
                    channel_id=user_id,
                    slack_bot_token=settings.SLACK_BOT_TOKEN,
                    topic=r2["brief"]["topic"],
                )
                reply = (
                    f"✅ *Carousel ready!*\n\n"
                    f"Hook: _{r2['brief']['hook']}_\n\n"
                    f"{len(images)} slides uploaded above ☝️\n\n"
                    f"Caption: {r2['brief'].get('caption', '')}"
                )
            else:
                reply = f"✅ Brief ready but image generation failed. Hook: {r2['brief']['hook']}"
            await _dm(user_id, reply)
        except Exception as exc:
            print(f"[webhooks] carousel error: {exc}", flush=True)
            await _dm(user_id, f"⚠️ Something went wrong: {exc}")
        return

    # Intent: status / profile
    if any(kw in text_lower for kw in ("status", "profile", "brand")):
        p = profile
        summary = (
            f"✅ *Your SLATE Brand Profile*\n"
            f"*Business:* {p.get('business_description', '—')}\n"
            f"*Audience:* {p.get('target_audience', '—')}\n"
            f"*Goals:* {p.get('content_goals', '—')}\n"
            f"*Tone:* {p.get('brand_tone', '—')}\n"
            f"*Cadence:* {p.get('cadence', '—')}\n"
            f"*Off limits:* {p.get('off_limits', '—')}"
        )
        await _dm(user_id, summary)
        return

    # Intent: performance rating
    if any(kw in text_lower for kw in ("good", "average", "poor")):
        try:
            job_rows = (
                db.table("carousel_jobs")
                .select("id, topic, brief")
                .eq("slack_user_id", user_id)
                .eq("status", "done")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if job_rows.data:
                job = job_rows.data[0]
                hook = (job.get("brief") or {}).get("hook", "")
                rating = next(r for r in ("good", "average", "poor") if r in text_lower)
                await content_strategist.record_performance(
                    workspace_id=user_id,
                    carousel_job_id=job["id"],
                    hook=hook,
                    topic=job.get("topic", ""),
                    content_type="unknown",
                    performance_rating=rating,
                )
                await _dm(user_id, "Thanks! I'll use that to improve future carousels. 📊")
            else:
                await _dm(user_id, "No recent carousels to rate yet.")
        except Exception as exc:
            print(f"[webhooks] record_performance error: {exc}", flush=True)
        return

    # Default help message
    await _dm(
        user_id,
        "Here's what I can do:\n\n"
        "• *make a carousel* — generate a new carousel\n"
        "• *show my profile* — see your brand setup\n"
        "• *good / average / poor* — rate your last carousel\n\n"
        "Or just message me any topic and I'll build a carousel around it."
    )


# ---------------------------------------------------------------------------
# Primary endpoint — all Slack Events API traffic
# ---------------------------------------------------------------------------

@router.post("/webhooks/slack/reply")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    body = await request.json()

    # Slack url_verification handshake
    if "challenge" in body:
        return JSONResponse({"challenge": body["challenge"]})

    event = body.get("event", {})

    # Rule 1: only handle real user messages
    if event.get("type") != "message" or event.get("bot_id") or event.get("subtype"):
        return JSONResponse({"ok": True})

    # Rule 2: only DMs (channel_type == "im")
    if event.get("channel_type") != "im":
        return JSONResponse({"ok": True})

    user_id = event.get("user", "")
    text = event.get("text", "").strip()

    if not user_id or not text:
        return JSONResponse({"ok": True})

    background_tasks.add_task(_handle_dm, user_id, text)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Stubbed slash command routes — kept so Railway doesn't 404
# ---------------------------------------------------------------------------

@router.post("/webhooks/slack")
async def slack_slash_stub(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


@router.post("/webhooks/slate-setup")
async def slate_setup_stub(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


@router.post("/webhooks/slate-status")
async def slate_status_stub(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})
