"""LangGraph testing workflow — builds the graph dynamically from discovered skills."""
import json
import operator
from typing import Annotated, Any, TypedDict
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph

from app.config import GEMINI_MODEL, GOOGLE_API_KEY, MAX_CONTENT_LENGTH, REQUEST_TIMEOUT
from app.skills import discover_skills


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class TestState(TypedDict):
    url: str
    html_content: str
    page_data: dict
    requirements: str                            # populated by runs_first skills
    skill_results: Annotated[list, operator.add]
    progress_updates: Annotated[list, operator.add]
    report: dict
    overall_score: float
    status: str
    error: str


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def get_llm() -> Any:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.1,
        max_output_tokens=2048,
    )


# ---------------------------------------------------------------------------
# HTML parsing helper
# ---------------------------------------------------------------------------

def _extract_page_data(soup: BeautifulSoup, url: str, html: str) -> dict:
    parsed_base = urlparse(url)

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag.get("content", "") if meta_desc_tag else ""

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")][:6]
    h3_tags = [h.get_text(strip=True) for h in soup.find_all("h3")][:6]

    images = soup.find_all("img")
    total_images = len(images)
    images_without_alt = sum(1 for img in images if not img.get("alt"))

    all_links = soup.find_all("a", href=True)
    internal, external = [], []
    for link in all_links:
        href = link.get("href", "")
        if href.startswith("http"):
            netloc = urlparse(href).netloc
            (internal if netloc == parsed_base.netloc else external).append(href)
        elif href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
            internal.append(urljoin(url, href))

    # Text content (strip scripts/styles first)
    soup_copy = BeautifulSoup(str(soup), "html.parser")
    for tag in soup_copy(["script", "style", "noscript"]):
        tag.extract()
    text_content = " ".join(soup_copy.get_text(separator=" ").split())
    word_count = len(text_content.split())

    def _meta(name=None, prop=None):
        if name:
            tag = soup.find("meta", attrs={"name": name})
        else:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"property": prop})
        return tag.get("content", "") if tag else ""

    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href", "") if canonical_tag else ""

    viewport_tag = soup.find("meta", attrs={"name": "viewport"})
    viewport_content = viewport_tag.get("content", "") if viewport_tag else ""

    html_tag = soup.find("html")
    lang = html_tag.get("lang", "") if html_tag else ""

    scripts = soup.find_all("script")
    stylesheets = soup.find_all("link", rel="stylesheet")

    forms = soup.find_all("form")
    form_inputs = [
        inp for inp in soup.find_all("input")
        if inp.get("type") not in ("hidden", "submit", "button", "reset")
    ]
    inputs_without_labels = 0
    for inp in form_inputs:
        inp_id = inp.get("id")
        has_label = (
            bool(soup.find("label", attrs={"for": inp_id})) if inp_id else False
        )
        if not has_label and not inp.get("aria-label") and not inp.get("aria-labelledby"):
            inputs_without_labels += 1

    return {
        "title": title,
        "meta_description": meta_desc,
        "h1_tags": h1_tags,
        "h2_tags": h2_tags,
        "h3_tags": h3_tags,
        "total_images": total_images,
        "images_without_alt": images_without_alt,
        "internal_links_count": len(set(internal)),
        "external_links_count": len(set(external)),
        "word_count": word_count,
        "text_sample": text_content[:3000],
        "og_title": _meta(prop="og:title"),
        "og_description": _meta(prop="og:description"),
        "canonical": canonical,
        "robots_meta": _meta(name="robots"),
        "has_viewport": viewport_tag is not None,
        "viewport_content": viewport_content,
        "lang": lang,
        "aria_role_count": len(soup.find_all(attrs={"role": True})),
        "aria_label_count": len(soup.find_all(attrs={"aria-label": True})),
        "aria_labelledby_count": len(soup.find_all(attrs={"aria-labelledby": True})),
        "forms_count": len(forms),
        "inputs_without_labels": inputs_without_labels,
        "scripts_total": len(scripts),
        "inline_scripts": sum(1 for s in scripts if not s.get("src")),
        "external_scripts": sum(1 for s in scripts if s.get("src")),
        "stylesheets_count": len(stylesheets),
        "has_schema": bool(soup.find_all("script", attrs={"type": "application/ld+json"})),
        "has_favicon": bool(soup.find("link", rel=lambda r: r and "icon" in r)),
        "html_size_kb": round(len(html) / 1024, 1),
    }


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

async def fetch_content_node(state: TestState) -> dict:
    url = state["url"]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT, follow_redirects=True, headers=headers
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text[:MAX_CONTENT_LENGTH]
    except httpx.TimeoutException:
        msg = f"Request timed out after {REQUEST_TIMEOUT}s"
        return {"status": "failed", "error": msg, "progress_updates": [f"✗ {msg}"]}
    except httpx.HTTPStatusError as e:
        msg = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
        return {"status": "failed", "error": msg, "progress_updates": [f"✗ {msg}"]}
    except Exception as e:
        return {"status": "failed", "error": str(e), "progress_updates": [f"✗ {e}"]}

    soup = BeautifulSoup(html, "html.parser")
    page_data = _extract_page_data(soup, url, html)

    return {
        "html_content": html,
        "page_data": page_data,
        "status": "running",
        "progress_updates": [
            f"✓ Page fetched ({page_data['html_size_kb']} KB, {page_data['word_count']} words)"
        ],
    }


def _make_first_skill_node(skill):
    """Node for skills that run before others (runs_first=True).
    Stores findings in state.requirements so subsequent skills can use them."""
    async def first_skill_node(state: TestState) -> dict:
        if state.get("status") == "failed":
            return {}
        llm = get_llm()
        try:
            result = await skill.analyze(state["url"], state.get("page_data", {}), llm)
            score = float(result.get("score", 5.0))
            findings = result.get("findings", [])
            return {
                "requirements": "\n".join(findings),
                "skill_results": [{
                    "skill_name": skill.name,
                    "status": "completed",
                    "score": score,
                    "findings": findings,
                    "details": result.get("details", ""),
                    "is_requirements": True,
                }],
                "progress_updates": [f"✓ {skill.name} — requirements extracted"],
            }
        except Exception as e:
            return {
                "requirements": "",
                "skill_results": [{
                    "skill_name": skill.name,
                    "status": "failed",
                    "score": None,
                    "findings": [],
                    "details": "",
                    "error": str(e),
                    "is_requirements": True,
                }],
                "progress_updates": [f"✗ {skill.name} failed: {e}"],
            }

    first_skill_node.__name__ = f"skill_{skill.name.lower().replace(' ', '_')}"
    return first_skill_node


def _make_skill_node(skill):
    """Node for regular skills. Receives requirements context from state."""
    async def skill_node(state: TestState) -> dict:
        if state.get("status") == "failed":
            return {}
        llm = get_llm()
        requirements = state.get("requirements", "")
        try:
            result = await skill.analyze(state["url"], state.get("page_data", {}), llm, requirements)
            score = float(result.get("score", 5.0))
            return {
                "skill_results": [{
                    "skill_name": skill.name,
                    "status": "completed",
                    "score": score,
                    "findings": result.get("findings", []),
                    "details": result.get("details", ""),
                }],
                "progress_updates": [f"✓ {skill.name} — {score:.1f}/10"],
            }
        except Exception as e:
            return {
                "skill_results": [{
                    "skill_name": skill.name,
                    "status": "failed",
                    "score": None,
                    "findings": [],
                    "details": "",
                    "error": str(e),
                }],
                "progress_updates": [f"✗ {skill.name} failed: {e}"],
            }

    skill_node.__name__ = f"skill_{skill.name.lower().replace(' ', '_')}"
    return skill_node


async def generate_report_node(state: TestState) -> dict:
    url = state["url"]
    skill_results = state.get("skill_results", [])

    if state.get("status") == "failed":
        report = {
            "url": url,
            "status": "failed",
            "error": state.get("error", "Unknown error"),
            "overall_score": None,
            "skill_results": [],
            "summary": f"Testing failed: {state.get('error', 'Unknown error')}",
        }
        return {"report": report, "status": "failed", "progress_updates": ["✗ Could not complete testing"]}

    # Exclude requirements-type results from the overall quality score
    scores = [r["score"] for r in skill_results if r.get("score") is not None and not r.get("is_requirements")]
    overall = round(sum(scores) / len(scores), 1) if scores else None

    summary = ""
    if skill_results and GOOGLE_API_KEY:
        try:
            llm = get_llm()
            lines = "\n".join(
                f"- {r['skill_name']}: {r.get('score', 'N/A')}/10 — "
                + "; ".join(r.get("findings", [])[:3])
                for r in skill_results
            )
            resp = await llm.ainvoke([HumanMessage(content=(
                f"Summarize these automated test results for {url} in 2-3 sentences, "
                f"highlighting the most critical issues and key strengths:\n\n{lines}\n\n"
                f"Overall score: {overall}/10"
            ))])
            summary = resp.content
        except Exception:
            summary = f"Testing completed. Overall score: {overall}/10"

    report = {
        "url": url,
        "status": "completed",
        "overall_score": overall,
        "requirements": state.get("requirements", ""),
        "skill_results": skill_results,
        "summary": summary,
    }
    return {
        "report": report,
        "overall_score": overall or 0.0,
        "status": "completed",
        "progress_updates": [f"✓ Report ready — overall score {overall}/10"],
    }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph():
    all_skills = discover_skills()
    # runs_first skills execute before others and populate state.requirements
    first_skills = [s for s in all_skills if s.runs_first]
    other_skills = [s for s in all_skills if not s.runs_first]

    workflow = StateGraph(TestState)
    workflow.add_node("fetch_content", fetch_content_node)
    workflow.add_node("generate_report", generate_report_node)

    # Build ordered list of all node names: first_skills then other_skills
    ordered_names: list[str] = []

    for skill in first_skills:
        node_name = "skill_" + skill.name.lower().replace(" ", "_").replace("-", "_")
        ordered_names.append(node_name)
        workflow.add_node(node_name, _make_first_skill_node(skill))

    for skill in other_skills:
        node_name = "skill_" + skill.name.lower().replace(" ", "_").replace("-", "_")
        ordered_names.append(node_name)
        workflow.add_node(node_name, _make_skill_node(skill))

    workflow.set_entry_point("fetch_content")

    if ordered_names:
        first = ordered_names[0]

        def route_after_fetch(state: TestState) -> str:
            return "generate_report" if state.get("status") == "failed" else first

        workflow.add_conditional_edges(
            "fetch_content",
            route_after_fetch,
            {"generate_report": "generate_report", first: first},
        )
        for i in range(len(ordered_names) - 1):
            workflow.add_edge(ordered_names[i], ordered_names[i + 1])
        workflow.add_edge(ordered_names[-1], "generate_report")
    else:
        workflow.add_edge("fetch_content", "generate_report")

    workflow.add_edge("generate_report", END)
    return workflow.compile()


graph = build_graph()
