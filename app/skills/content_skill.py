import json
import re
from typing import Any

from langchain_core.messages import HumanMessage

from .base_skill import BaseSkill


class ContentSkill(BaseSkill):
    name = "Content Quality"
    description = "Assesses readability, content depth, heading hierarchy, and page purpose clarity"

    async def analyze(self, url: str, page_data: dict, llm: Any, requirements: str = "") -> dict:
        text_sample = page_data.get("text_sample", "")[:2000]
        req_section = f"\n\nInferred product requirements (check whether content fulfils these):\n{requirements}\n" if requirements else ""
        prompt = f"""You are a content quality specialist. Analyze the content quality of this webpage and return ONLY valid JSON.

URL: {url}

Page Data:
- Title: "{page_data.get('title', '')}"
- Meta description: "{page_data.get('meta_description', '')}"
- Word count: {page_data.get('word_count', 0)}
- H1 tags: {page_data.get('h1_tags', [])}
- H2 tags (first 5): {page_data.get('h2_tags', [])}
- H3 tags (first 5): {page_data.get('h3_tags', [])}
- Text sample (first 2000 chars):
{text_sample}{req_section}

Evaluate: clarity of purpose, content depth, heading hierarchy, readability, and overall quality. Return ONLY this JSON (no markdown, no extra text):
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
