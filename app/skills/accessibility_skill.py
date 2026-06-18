import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from .base_skill import BaseSkill


class AccessibilitySkill(BaseSkill):
    name = "Accessibility Analysis"
    description = "Checks ARIA attributes, form labels, semantic HTML, language declaration, and keyboard nav indicators"

    async def analyze(self, url: str, page_data: dict, llm: Any, requirements: str = "") -> dict:
        req_section = f"\n\nInferred product requirements (check accessibility against these):\n{requirements}\n" if requirements else ""
        prompt = f"""You are a web accessibility expert (WCAG 2.1). Analyze the accessibility of this webpage and return ONLY valid JSON.

URL: {url}

Page Data:
- HTML lang attribute: "{page_data.get('lang', '')}"
- Has viewport meta tag: {page_data.get('has_viewport', False)} — "{page_data.get('viewport_content', '')}"
- Elements with role attribute: {page_data.get('aria_role_count', 0)}
- Elements with aria-label: {page_data.get('aria_label_count', 0)}
- Elements with aria-labelledby: {page_data.get('aria_labelledby_count', 0)}
- Forms found: {page_data.get('forms_count', 0)}
- Form inputs missing labels: {page_data.get('inputs_without_labels', 0)}
- Images total: {page_data.get('total_images', 0)}, missing alt text: {page_data.get('images_without_alt', 0)}
- H1 tags: {page_data.get('h1_tags', [])}
- H2 tags (first 5): {page_data.get('h2_tags', [])}
- Page title: "{page_data.get('title', '')}"
- Word count: {page_data.get('word_count', 0)}{req_section}

Evaluate WCAG 2.1 Level AA compliance signals. Return ONLY this JSON (no markdown, no extra text):
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
