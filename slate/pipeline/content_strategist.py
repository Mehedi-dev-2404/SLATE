from datetime import date, timedelta

from anthropic import AsyncAnthropic

from slate.config import settings
from slate.database import get_client

MOCK_MODE = False

_MOCK_TOPICS = {
    "educational": "3 signs your business is ready to automate",
    "social_proof": "What happened when we automated our client's inbox",
    "promotional": "How SLATE builds 3 carousels a week without any input",
}

# day-of-week → content_type (Mon=0 … Sun=6)
_DOW_TYPE = {
    0: "educational",   # Mon
    1: "social_proof",  # Tue
    2: "promotional",   # Wed
    3: "educational",   # Thu
    4: "social_proof",  # Fri
    5: "promotional",   # Sat
    6: "educational",   # Sun
}

_3X_SLOTS = {0: "educational", 2: "social_proof", 4: "promotional"}  # Mon/Wed/Fri


async def generate_topic(
    workspace_id: str,
    content_type: str,
    brand_profile: dict,
) -> str:
    if MOCK_MODE:
        print("content_strategist: MOCK_MODE — returning mock topic", flush=True)
        return _MOCK_TOPICS.get(content_type, _MOCK_TOPICS["educational"])

    # Fetch last 10 topics for this workspace to avoid repetition
    db = get_client()
    rows = (
        db.table("content_calendar")
        .select("topic")
        .eq("workspace_id", workspace_id)
        .order("scheduled_date", desc=True)
        .limit(10)
        .execute()
    )
    recent_topics = "\n".join(f"- {r['topic']}" for r in rows.data) or "None yet"

    system_prompt = (
        "You are a content strategist for Instagram carousels. "
        "Generate one specific, compelling carousel topic. Return ONLY "
        "the topic as a plain string. No explanation, no preamble."
    )

    user_prompt = (
        f"Business: {brand_profile.get('business_description', '')}\n"
        f"Audience: {brand_profile.get('target_audience', '')}\n"
        f"Goals: {brand_profile.get('content_goals', '')}\n"
        f"Tone: {brand_profile.get('brand_tone', '')}\n"
        f"Off limits: {brand_profile.get('off_limits', '')}\n"
        f"Content type: {content_type}\n\n"
        "Content type guidance:\n"
        "- educational: teach something specific and actionable\n"
        "- social_proof: credibility, results, transformation story\n"
        "- promotional: soft sell, outcome-focused, not pushy\n\n"
        f"Recent topics already used (DO NOT repeat these angles):\n{recent_topics}\n\n"
        "Generate one carousel topic that fits the content type, "
        "suits this brand, and hasn't been covered recently. "
        "Be specific — not 'tips for X' but '3 specific ways X does Y'."
    )

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()


async def get_next_content_slot(
    workspace_id: str,
    cadence: str,
) -> dict:
    if MOCK_MODE:
        return {
            "content_type": "educational",
            "scheduled_date": date.today() + timedelta(days=1),
        }

    today = date.today()

    if cadence == "daily":
        scheduled = today + timedelta(days=1)
        content_type = _DOW_TYPE[scheduled.weekday()]

    elif cadence == "3x_week":
        # Find next Mon, Wed, or Fri from today (not including today)
        scheduled = today + timedelta(days=1)
        while scheduled.weekday() not in _3X_SLOTS:
            scheduled += timedelta(days=1)
        content_type = _3X_SLOTS[scheduled.weekday()]

    else:  # weekly
        # Next Monday
        days_until_monday = (7 - today.weekday()) % 7 or 7
        scheduled = today + timedelta(days=days_until_monday)
        week_num = scheduled.isocalendar()[1]
        rotation = ["educational", "social_proof", "promotional"]
        content_type = rotation[(week_num - 1) % 3]

    return {"content_type": content_type, "scheduled_date": scheduled}


async def record_performance(
    workspace_id: str,
    carousel_job_id: str,
    hook: str,
    topic: str,
    content_type: str,
    performance_rating: str,
) -> bool:
    if MOCK_MODE:
        print(
            f"content_strategist: MOCK_MODE — record_performance "
            f"workspace={workspace_id} job={carousel_job_id} "
            f"rating={performance_rating} topic={topic!r}",
            flush=True,
        )
        return True

    try:
        db = get_client()
        db.table("content_performance").insert({
            "workspace_id": workspace_id,
            "carousel_job_id": carousel_job_id,
            "hook": hook,
            "topic": topic,
            "content_type": content_type,
            "performance_rating": performance_rating,
        }).execute()
        return True
    except Exception as exc:
        print(f"content_strategist: record_performance error — {exc}", flush=True)
        return False
