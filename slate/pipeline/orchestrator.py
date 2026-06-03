from slate.config import settings
from slate.database import get_client
from slate.models.carousel import BrandAnalysis, StyleAnalysis
from slate.pipeline import (
    brand_analyser,
    style_analyser,
    question_generator,
    brief_builder,
    canva_builder,
)

MOCK_MODE = False

_MOCK_JOB_ID = "mock-job-001"


def _db_update(job_id: str, fields: dict) -> None:
    get_client().table("carousel_jobs").update(fields).eq("id", job_id).execute()


async def start_job(
    slack_user_id: str,
    slack_channel_id: str,
    slack_thread_ts: str,
    topic: str,
    brand_image_urls: list[str],
    style_image_url: str | None,
    slack_bot_token: str,
) -> dict:
    print(f"orchestrator: start_job topic='{topic}' MOCK_MODE={MOCK_MODE}", flush=True)

    if MOCK_MODE:
        job_id = _MOCK_JOB_ID
    else:
        result = (
            get_client()
            .table("carousel_jobs")
            .insert(
                {
                    "slack_user_id": slack_user_id,
                    "slack_channel_id": slack_channel_id,
                    "slack_thread_ts": slack_thread_ts,
                    "topic": topic,
                    "status": "analysing",
                }
            )
            .execute()
        )
        job_id = result.data[0]["id"]

    # Phase 1a — brand analysis
    try:
        brand_analysis = await brand_analyser.analyse_brand(brand_image_urls, slack_bot_token)
        if not MOCK_MODE:
            _db_update(job_id, {"brand_analysis": brand_analysis.dict()})
    except Exception as exc:
        print(f"orchestrator: brand_analyser failed — {exc}", flush=True)
        if not MOCK_MODE:
            _db_update(job_id, {"status": "failed"})
        raise

    # Phase 1b — style analysis
    try:
        style_analysis = await style_analyser.analyse_style(
            style_image_url or "", slack_bot_token
        )
        if not MOCK_MODE:
            _db_update(
                job_id,
                {"style_analysis": style_analysis.dict() if style_analysis else None},
            )
    except Exception as exc:
        print(f"orchestrator: style_analyser failed — {exc}", flush=True)
        if not MOCK_MODE:
            _db_update(job_id, {"status": "failed"})
        raise

    # Phase 1c — question generation
    try:
        if not MOCK_MODE:
            _db_update(job_id, {"status": "questioning"})
        questions = await question_generator.generate_questions(
            topic, brand_analysis, style_analysis
        )
        if not MOCK_MODE:
            _db_update(job_id, {"questions_asked": questions, "status": "pending_answers"})
    except Exception as exc:
        print(f"orchestrator: question_generator failed — {exc}", flush=True)
        if not MOCK_MODE:
            _db_update(job_id, {"status": "failed"})
        raise

    print(f"orchestrator: start_job complete job_id={job_id} questions={len(questions)}", flush=True)
    return {"job_id": job_id, "questions": questions}


async def complete_job(job_id: str, user_answers: str) -> dict:
    print(f"orchestrator: complete_job job_id={job_id} MOCK_MODE={MOCK_MODE}", flush=True)

    if MOCK_MODE:
        # Use mock brand/style data so downstream modules run normally
        brand_analysis = BrandAnalysis(
            palette=["#1B2B4B", "#F5F0E8", "#E8604C"],
            tone="Direct and confident, slightly informal",
            visual_style="Clean with bold typography, minimal imagery",
            typography_feel="Strong sans-serif, high contrast",
        )
        style_analysis = StyleAnalysis(
            layout_pattern="Text-led with bold hook, image secondary",
            slide_structure="Hook → 3-4 value slides → CTA",
            design_density="Minimal — lots of whitespace, one idea per slide",
        )
        topic = "Mock carousel topic"
    else:
        result = (
            get_client()
            .table("carousel_jobs")
            .select("*")
            .eq("id", job_id)
            .execute()
        )
        row = result.data[0]
        topic = row["topic"]

        brand_analysis = BrandAnalysis(**row["brand_analysis"])
        style_analysis = (
            StyleAnalysis(**row["style_analysis"]) if row.get("style_analysis") else None
        )
        _db_update(job_id, {"status": "briefing", "user_answers": user_answers})

    # Phase 2a — brief
    try:
        brief = await brief_builder.build_brief(
            topic, brand_analysis, style_analysis, user_answers, slide_count=7
        )
        if not MOCK_MODE:
            _db_update(job_id, {"brief": brief, "status": "building"})
    except Exception as exc:
        print(f"orchestrator: brief_builder failed — {exc}", flush=True)
        if not MOCK_MODE:
            _db_update(job_id, {"status": "failed"})
        raise

    # Phase 2b — Canva design
    try:
        canva_url = await canva_builder.build_canva_carousel(brief)
        if not MOCK_MODE:
            _db_update(job_id, {"canva_url": canva_url, "status": "done"})
    except Exception as exc:
        print(f"orchestrator: canva_builder failed — {exc}", flush=True)
        if not MOCK_MODE:
            _db_update(job_id, {"status": "failed"})
        raise

    print(f"orchestrator: complete_job done job_id={job_id} canva_url={canva_url}", flush=True)
    return {"canva_url": canva_url, "brief": brief}
