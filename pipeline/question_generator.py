from slate.models.carousel import BrandAnalysis, StyleAnalysis

MOCK_MODE = True


async def generate_questions(
    topic: str,
    brand_analysis: BrandAnalysis,
    style_analysis: StyleAnalysis,
) -> list[str]:
    print(f"[question_generator] Generating questions for topic='{topic}' (MOCK_MODE={MOCK_MODE})", flush=True)
    return [
        "Who is the target audience for this carousel?",
        "What is the primary call-to-action you want readers to take?",
        "Are there any specific statistics or data points you want to highlight?",
    ]
