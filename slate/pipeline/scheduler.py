import asyncio
from datetime import datetime, date

import httpx

from slate.config import settings
from slate.database import get_client
from slate.pipeline.content_strategist import generate_topic, get_next_content_slot
from slate.pipeline.orchestrator import complete_job, start_job

MOCK_MODE = False

_3X_DAYS = {0, 2, 4}  # Mon, Wed, Fri


async def run_autonomous_pipeline(
    workspace_id: str,
    brand_profile: dict,
) -> dict:
    if MOCK_MODE:
        print(f"scheduler: MOCK_MODE — run_autonomous_pipeline workspace={workspace_id}", flush=True)
        return {
            "carousel_job_id": "mock-auto-001",
            "canva_url": "https://www.canva.com/design/mock/edit",
            "topic": "3 signs your business is ready to automate",
        }

    # Step 1 — next content slot
    slot = await get_next_content_slot(workspace_id, brand_profile.get("cadence", "3x_week"))

    # Step 2 — generate topic
    topic = await generate_topic(workspace_id, slot["content_type"], brand_profile)

    # Step 3 — insert content_calendar row
    db = get_client()
    scheduled = slot["scheduled_date"]
    cal_row = (
        db.table("content_calendar")
        .insert(
            {
                "workspace_id": workspace_id,
                "scheduled_date": scheduled.isoformat(),
                "day_of_week": scheduled.strftime("%A"),
                "content_type": slot["content_type"],
                "topic": topic,
                "status": "running",
            }
        )
        .execute()
    )
    calendar_id = cal_row.data[0]["id"]

    # Step 4 — build user_answers from brand profile
    user_answers = (
        f"Business: {brand_profile.get('business_description', '')}\n"
        f"Audience: {brand_profile.get('target_audience', '')}\n"
        f"Goals: {brand_profile.get('content_goals', '')}\n"
        f"Tone: {brand_profile.get('brand_tone', '')}\n"
        f"Off limits: {brand_profile.get('off_limits', '')}\n"
        f"Content type: {slot['content_type']}"
    )

    r1 = await start_job(
        slack_user_id=workspace_id,
        slack_channel_id=brand_profile.get("slack_channel_id", ""),
        slack_thread_ts="",
        topic=topic,
        brand_image_urls=[],
        style_image_url=None,
        slack_bot_token="",
    )

    # Step 5 — skip questions, go straight to complete
    r2 = await complete_job(job_id=r1["job_id"], user_answers=user_answers)

    # Step 6 — update content_calendar
    db.table("content_calendar").update(
        {"status": "done", "carousel_job_id": r1["job_id"]}
    ).eq("id", calendar_id).execute()

    # Step 7 — post to Slack
    slack_payload = {
        "text": (
            f"📅 *New carousel ready*\n\n"
            f"*Topic:* {topic}\n"
            f"*Type:* {slot['content_type']}\n"
            f"*Hook:* {r2['brief']['hook']}\n\n"
            f"🎨 {r2['canva_url']}"
        )
    }
    try:
        async with httpx.AsyncClient() as http:
            await http.post(settings.SLACK_WEBHOOK_URL, json=slack_payload)
    except Exception as exc:
        print(f"scheduler: Slack post failed — {exc}", flush=True)

    print(f"scheduler: autonomous pipeline done workspace={workspace_id} job={r1['job_id']}", flush=True)
    return {
        "carousel_job_id": r1["job_id"],
        "canva_url": r2["canva_url"],
        "topic": topic,
    }


async def check_and_run_scheduled_jobs() -> None:
    if MOCK_MODE:
        print("scheduler: MOCK_MODE — check_and_run_scheduled_jobs simulating one workspace", flush=True)
        mock_profile = {
            "workspace_id": "W_MOCK_001",
            "cadence": "3x_week",
            "slack_channel_id": "C_MOCK_001",
            "business_description": "We help coaches automate their content.",
            "target_audience": "Coaches aged 30-50",
            "content_goals": "Build credibility",
            "brand_tone": "Direct and warm",
            "off_limits": "None",
        }
        result = await run_autonomous_pipeline("W_MOCK_001", mock_profile)
        print(f"scheduler: MOCK result — {result}", flush=True)
        return

    today = date.today()
    today_dow = today.weekday()

    db = get_client()
    profiles = (
        db.table("brand_profiles")
        .select("*")
        .eq("onboarding_complete", True)
        .execute()
    )

    for profile in profiles.data:
        workspace_id = profile["workspace_id"]
        cadence = profile.get("cadence", "3x_week")

        # Determine if due today
        due = False
        if cadence == "daily":
            due = True
        elif cadence == "3x_week":
            due = today_dow in _3X_DAYS
        elif cadence == "weekly":
            due = today_dow == 0  # Monday

        if not due:
            print(f"scheduler: workspace={workspace_id} not due today ({cadence})", flush=True)
            continue

        # Check if already run today
        existing = (
            db.table("content_calendar")
            .select("id")
            .eq("workspace_id", workspace_id)
            .eq("scheduled_date", today.isoformat())
            .limit(1)
            .execute()
        )
        if existing.data:
            print(f"scheduler: workspace={workspace_id} already ran today — skipping", flush=True)
            continue

        print(f"scheduler: running autonomous pipeline workspace={workspace_id}", flush=True)
        try:
            result = await run_autonomous_pipeline(workspace_id, profile)
            print(f"scheduler: done workspace={workspace_id} topic={result['topic']!r}", flush=True)
        except Exception as exc:
            print(f"scheduler: pipeline failed workspace={workspace_id} — {exc}", flush=True)


async def start_scheduler() -> None:
    if MOCK_MODE:
        print("scheduler: MOCK_MODE — running one check then stopping", flush=True)
        await check_and_run_scheduled_jobs()
        return

    while True:
        try:
            now = datetime.utcnow()
            if 7 <= now.hour <= 9:
                print(f"scheduler: checking jobs at {now}", flush=True)
                await check_and_run_scheduled_jobs()
            else:
                print(f"scheduler: outside window, sleeping — {now.hour}:00 UTC", flush=True)
        except Exception as exc:
            print(f"scheduler: error — {exc}", flush=True)
        await asyncio.sleep(3600)
