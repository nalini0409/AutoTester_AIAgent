# Feature Backlog

## BL-001 — Requirements-Driven Testing
**Priority:** High  
**Status:** Backlog

Restructure the LangGraph so `RequirementsSkill` runs first and its inferred requirements become context for every subsequent skill. Currently all skills run as peers with no awareness of each other.

**Changes needed:**
- Add a `requirements_analysis` node before the skill fan-out in `graph.py`
- Extend `TestState` to carry a `requirements` field
- Pass requirements context into each skill's `analyze()` prompt so they test *against* the inferred spec
- Surface requirements prominently in the final report (not just as another skill card)

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
