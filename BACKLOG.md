# Feature Backlog

## BL-001 — Requirements-Driven Testing
**Priority:** High  
**Status:** Done ✅

Restructure the LangGraph so `RequirementsSkill` runs first and its inferred requirements become context for every subsequent skill. Currently all skills run as peers with no awareness of each other.

**Changes needed:**
- Add a `requirements_analysis` node before the skill fan-out in `graph.py`
- Extend `TestState` to carry a `requirements` field
- Pass requirements context into each skill's `analyze()` prompt so they test *against* the inferred spec
- Surface requirements prominently in the final report (not just as another skill card)

---

## BL-003 — Editable Requirements UI (Two-Phase Analysis Flow)
**Priority:** High  
**Status:** Backlog

Add a two-phase UI flow: requirements are generated and shown first, user can edit them, then the full analysis runs using the edited requirements as context for every skill.

**Changes needed:**
- `app/graph.py`: add `requirements: str` to `TestState`; build separate `analysis_graph` (excludes `RequirementsSkill`); add `get_requirements(url)` coroutine for phase 1
- `app/skills/base_skill.py`: add `requirements=""` param to `analyze()` signature
- All skill files: inject requirements into LLM prompt when provided
- `app/main.py`: add `GET /api/requirements?url=` (phase 1 SSE) and `POST /api/analyze` with `{url, requirements}` body (phase 2 SSE)
- `frontend/index.html`: add editable requirements card between URL input and results
- `frontend/styles.css`: style requirements editor (textarea + edit/proceed buttons)
- `frontend/app.js`: implement two-phase flow — call `/api/requirements` first, show editable card, then POST `/api/analyze` with edited requirements

---

## BL-002 — Website Traversal (Multi-Page Analysis)
**Priority:** Medium  
**Status:** Backlog

Currently the agent analyzes only the single submitted URL. Traversal would give a much richer signal — e.g. accessibility failures on a form page, SEO issues on inner pages.

**Changes needed:**
- After fetching the root URL, extract all internal links from `page_data`
- Concurrently fetch up to N additional pages (configurable, default 5) using `httpx`
- Merge page data across all visited pages before passing to skills (union headings, sum image counts, aggregate links, etc.)
- Store list of visited URLs in state and surface them in the report
- Add `MAX_CRAWL_PAGES` to `config.py` and `.env.example`
