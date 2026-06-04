from slate.database import get_client

MOCK_MODE = False

_STEP_QUESTIONS = {
    1: "*Question 1 of 6:* What's your business name and what do you do in one sentence?",
    2: "*Question 2 of 6:* Who is your target audience? Be specific — age, role, pain points.",
    3: "*Question 3 of 6:* What are your content goals? (e.g. build credibility, generate leads, educate your audience)",
    4: "*Question 4 of 6:* How would you describe your brand tone? (e.g. bold and direct, friendly and casual, professional and authoritative)",
    5: "*Question 5 of 6:* Are there any topics, words, or angles that are off-limits for your content?",
    6: (
        "*Question 6 of 6:* How often do you want SLATE to create carousels?\n\n"
        "Reply with:\n"
        "• *daily* — 7 carousels per week\n"
        "• *3x* — Mon, Wed, Fri\n"
        "• *weekly* — once per week"
    ),
}

_WELCOME = (
    "👋 Welcome to SLATE! I'll ask you 6 quick questions to set up your content engine. "
    "You only need to do this once.\n\n"
)

_STEP_FIELDS = {
    1: "business_description",
    2: "target_audience",
    3: "content_goals",
    4: "brand_tone",
    5: "off_limits",
}


def _parse_cadence(answer: str) -> str:
    a = answer.strip().lower()
    if "daily" in a or a == "7":
        return "daily"
    if "weekly" in a or a == "1":
        return "weekly"
    return "3x_week"


async def start_onboarding(
    workspace_id: str,
    slack_channel_id: str,
) -> dict:
    print(f"onboarding: start_onboarding workspace={workspace_id} MOCK_MODE={MOCK_MODE}", flush=True)

    if not MOCK_MODE:
        db = get_client()
        rows = (
            db.table("brand_profiles")
            .select("onboarding_complete, onboarding_step")
            .eq("workspace_id", workspace_id)
            .limit(1)
            .execute()
        )
        if rows.data:
            profile = rows.data[0]
            if profile["onboarding_complete"]:
                return {
                    "message": "✅ Your brand is already set up. Type /slate-status to see your profile.",
                    "step": -1,
                }
            # Resume from current step
            step = profile["onboarding_step"] or 1
            question = _STEP_QUESTIONS.get(step, _STEP_QUESTIONS[1])
            return {"message": f"Resuming setup ✍️\n\n{question}", "step": step}
        else:
            db.table("brand_profiles").insert(
                {
                    "workspace_id": workspace_id,
                    "slack_user_id": workspace_id,
                    "slack_channel_id": slack_channel_id,
                    "onboarding_step": 1,
                    "onboarding_complete": False,
                }
            ).execute()

    return {
        "message": _WELCOME + _STEP_QUESTIONS[1],
        "step": 1,
    }


async def process_onboarding_reply(
    workspace_id: str,
    step: int,
    answer: str,
) -> dict:
    print(
        f"onboarding: process_onboarding_reply workspace={workspace_id} step={step} MOCK_MODE={MOCK_MODE}",
        flush=True,
    )

    if step in _STEP_FIELDS:
        field = _STEP_FIELDS[step]
        next_step = step + 1

        if not MOCK_MODE:
            get_client().table("brand_profiles").update(
                {field: answer, "onboarding_step": next_step, "updated_at": "now()"}
            ).eq("workspace_id", workspace_id).execute()

        return {"message": _STEP_QUESTIONS[next_step], "step": next_step, "complete": False}

    if step == 6:
        cadence = _parse_cadence(answer)

        if not MOCK_MODE:
            get_client().table("brand_profiles").update(
                {
                    "cadence": cadence,
                    "onboarding_complete": True,
                    "onboarding_step": 7,
                    "updated_at": "now()",
                }
            ).eq("workspace_id", workspace_id).execute()

        return {
            "message": (
                "✅ *SLATE is set up!*\n\n"
                "I'll start generating carousels on your chosen schedule. "
                "Your first carousel will be ready shortly.\n\n"
                "You can always update your brand profile with /slate-setup."
            ),
            "step": 7,
            "complete": True,
        }

    # Unexpected step
    print(f"onboarding: unexpected step={step} — ignoring", flush=True)
    return {"message": "Something went wrong. Type /slate-setup to restart onboarding.", "step": step, "complete": False}
