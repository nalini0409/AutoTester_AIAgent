import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from .base_skill import BaseSkill


class PerformanceSkill(BaseSkill):
    name = "Performance Analysis"
    description = "Evaluates page weight, script count, inline code, render-blocking resources, and mobile readiness"

    async def analyze(self, url: str, page_data: dict, llm: Any) -> dict:
        prompt = f"""You are a web performance engineer. Analyze the performance indicators of this webpage and return ONLY valid JSON.

URL: {url}

Page Data:
- HTML size: {page_data.get('html_size_kb', 0)} KB
- Total script tags: {page_data.get('scripts_total', 0)} ({page_data.get('external_scripts', 0)} external, {page_data.get('inline_scripts', 0)} inline)
- Stylesheet links: {page_data.get('stylesheets_count', 0)}
- Total images: {page_data.get('total_images', 0)}
- Has viewport meta (mobile-ready): {page_data.get('has_viewport', False)}
- Viewport content: "{page_data.get('viewport_content', '')}"
- Word count: {page_data.get('word_count', 0)}
- Internal links: {page_data.get('internal_links_count', 0)}

Evaluate load performance signals: script bloat, render-blocking resources, mobile readiness, and HTML weight. Return ONLY this JSON (no markdown, no extra text):
{{"score": <0-10>, "findings": ["finding1", "finding2", "finding3", "finding4"], "details": "<2-3 sentence assessment>"}}"""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return _parse_json(response.content)


def _parse_json(text: str, default_score: float = 5.0) -> dict:
    for pattern in [
        r"```json\s*(\{.*?\})\s*```",
        r"```\s*(\{.*?\})\s*```",
        r"(\{[^{}]*\"score\"[^{}]*\})",
    ]:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    return {
        "score": default_score,
        "findings": ["Analysis completed — see details"],
        "details": text[:400] if text else "Analysis unavailable",
    }
