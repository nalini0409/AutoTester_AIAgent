import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from .base_skill import BaseSkill


class SEOSkill(BaseSkill):
    name = "SEO Analysis"
    description = "Checks title tags, meta descriptions, heading structure, alt text, and structured data"

    async def analyze(self, url: str, page_data: dict, llm: Any, requirements: str = "") -> dict:
        req_section = f"\n\nInferred product requirements (use these to judge SEO alignment):\n{requirements}\n" if requirements else ""
        prompt = f"""You are an SEO expert. Analyze the SEO quality of this webpage and return ONLY valid JSON.

URL: {url}

Page Data:
- Title: "{page_data.get('title', '')}" ({len(page_data.get('title', ''))} chars)
- Meta Description: "{page_data.get('meta_description', '')}" ({len(page_data.get('meta_description', ''))} chars)
- H1 tags ({len(page_data.get('h1_tags', []))}): {page_data.get('h1_tags', [])}
- H2 tags (first 5): {page_data.get('h2_tags', [])}
- Images total: {page_data.get('total_images', 0)}, missing alt: {page_data.get('images_without_alt', 0)}
- Word count: {page_data.get('word_count', 0)}
- Internal links: {page_data.get('internal_links_count', 0)}, External: {page_data.get('external_links_count', 0)}
- Canonical URL: "{page_data.get('canonical', '')}"
- Robots meta: "{page_data.get('robots_meta', '')}"
- OG title: "{page_data.get('og_title', '')}"
- OG description: "{page_data.get('og_description', '')}"
- Has Schema.org markup: {page_data.get('has_schema', False)}
- Has favicon: {page_data.get('has_favicon', False)}
- Language attribute: "{page_data.get('lang', '')}"{req_section}

Return ONLY this JSON (no markdown, no extra text):
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
