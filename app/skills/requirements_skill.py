import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from .base_skill import BaseSkill


class RequirementsSkill(BaseSkill):
    name = "Requirements Analysis"
    description = "Infers functional and non-functional requirements from website content and structure"

    async def analyze(self, url: str, page_data: dict, llm: Any) -> dict:
        text_sample = page_data.get("text_sample", "")[:2500]
        prompt = f"""You are a business analyst. Based solely on this website's content and structure, infer what the product requirements likely are. Make your best informed guess — be specific and confident.

URL: {url}

Website Data:
- Title: "{page_data.get('title', '')}"
- Meta Description: "{page_data.get('meta_description', '')}"
- H1 tags: {page_data.get('h1_tags', [])}
- H2 tags: {page_data.get('h2_tags', [])}
- H3 tags: {page_data.get('h3_tags', [])}
- Has forms: {page_data.get('forms_count', 0) > 0} ({page_data.get('forms_count', 0)} forms)
- Total links: {page_data.get('internal_links_count', 0) + page_data.get('external_links_count', 0)}
- Word count: {page_data.get('word_count', 0)}
- OG description: "{page_data.get('og_description', '')}"
- Page text sample:
{text_sample}

Generate a requirements analysis. Return ONLY this JSON (no markdown, no extra text):
{{
  "score": <0-10, how clearly the site communicates its purpose>,
  "findings": [
    "Target audience: <who this is for>",
    "Core purpose: <what the product/service does>",
    "FR1: <functional requirement>",
    "FR2: <functional requirement>",
    "FR3: <functional requirement>",
    "FR4: <functional requirement>",
    "FR5: <functional requirement>",
    "NFR1: <non-functional requirement, e.g. performance/security/accessibility>",
    "NFR2: <non-functional requirement>",
    "NFR3: <non-functional requirement>"
  ],
  "details": "<2-3 sentence summary of the product and its inferred requirements>"
}}"""

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
        "findings": ["Requirements analysis completed — see details"],
        "details": text[:400] if text else "Analysis unavailable",
    }
