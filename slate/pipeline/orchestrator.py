from slate.models.carousel import CarouselJob, CarouselStatus
from slate.pipeline import (
    brand_analyser,
    style_analyser,
    question_generator,
    brief_builder,
    canva_builder,
)

MOCK_MODE = True


async def run_pipeline(job: CarouselJob) -> CarouselJob:
    print(f"[orchestrator] Starting pipeline for job={job.id} topic='{job.topic}' (MOCK_MODE={MOCK_MODE})", flush=True)

    job.status = CarouselStatus.ANALYSING
    job.brand_analysis = await brand_analyser.analyse_brand(job.slack_user_id)
    job.style_analysis = await style_analyser.analyse_style(job.slack_user_id)

    job.status = CarouselStatus.QUESTIONING
    job.questions_asked = await question_generator.generate_questions(
        job.topic, job.brand_analysis, job.style_analysis
    )

    job.status = CarouselStatus.BRIEFING
    job.brief = await brief_builder.build_brief(
        job.topic,
        job.brand_analysis,
        job.style_analysis,
        job.user_answers or "",
    )

    job.status = CarouselStatus.BUILDING
    job.canva_url = await canva_builder.build_canva_design(job.brief, job.slack_user_id)

    job.status = CarouselStatus.DONE
    print(f"[orchestrator] Pipeline complete for job={job.id} canva_url={job.canva_url}", flush=True)
    return job
