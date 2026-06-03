from typing import Any

from slate.models.carousel import BrandAnalysis, StyleAnalysis

MOCK_MODE = True


async def build_brief(
    topic: str,
    brand_analysis: BrandAnalysis,
    style_analysis: StyleAnalysis,
    user_answers: str,
) -> dict[str, Any]:
    print(f"[brief_builder] Building brief for topic='{topic}' (MOCK_MODE={MOCK_MODE})", flush=True)
    return {
        "topic": topic,
        "slide_count": 7,
        "hook": f"Why {topic} is changing everything in 2024",
        "slides": [
            {"index": 1, "type": "cover", "headline": f"The Truth About {topic}", "body": None},
            {"index": 2, "type": "problem", "headline": "Here's what most people get wrong", "body": "..."},
            {"index": 3, "type": "insight", "headline": "The data doesn't lie", "body": "..."},
            {"index": 4, "type": "insight", "headline": "What the experts say", "body": "..."},
            {"index": 5, "type": "framework", "headline": "A simpler way to think about it", "body": "..."},
            {"index": 6, "type": "proof", "headline": "Real-world results", "body": "..."},
            {"index": 7, "type": "cta", "headline": "Your next step", "body": "Follow for more."},
        ],
        "palette": brand_analysis.palette,
        "tone": brand_analysis.tone,
        "layout_pattern": style_analysis.layout_pattern,
    }
