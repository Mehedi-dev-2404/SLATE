from slate.models.carousel import StyleAnalysis

MOCK_MODE = True


async def analyse_style(slack_user_id: str) -> StyleAnalysis:
    print(f"[style_analyser] Running for user={slack_user_id} (MOCK_MODE={MOCK_MODE})", flush=True)
    return StyleAnalysis(
        layout_pattern="full-bleed hero + text overlay",
        slide_structure="title / insight / supporting detail / CTA",
        design_density="low density — lots of whitespace",
    )
