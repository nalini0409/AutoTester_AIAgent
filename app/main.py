"""FastAPI application — serves the frontend and streams test results via SSE."""
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.graph import graph

app = FastAPI(title="AutoTester AI")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


# ---------------------------------------------------------------------------
# SSE test endpoint
# ---------------------------------------------------------------------------

@app.get("/api/test")
async def run_test(url: str, request: Request):
    """Stream test progress and final report as Server-Sent Events."""

    async def event_stream():
        initial_state = {
            "url": url,
            "html_content": "",
            "page_data": {},
            "skill_results": [],
            "progress_updates": [],
            "report": {},
            "overall_score": 0.0,
            "status": "running",
            "error": "",
        }

        yield f"data: {json.dumps({'type': 'started', 'url': url})}\n\n"

        try:
            async for chunk in graph.astream(initial_state):
                if await request.is_disconnected():
                    break

                for node_name, node_output in chunk.items():
                    if not isinstance(node_output, dict):
                        continue

                    for msg in node_output.get("progress_updates", []):
                        yield f"data: {json.dumps({'type': 'progress', 'message': msg, 'node': node_name})}\n\n"

                    for result in node_output.get("skill_results", []):
                        yield f"data: {json.dumps({'type': 'skill_result', 'result': result})}\n\n"

                    if node_name == "generate_report" and "report" in node_output:
                        yield f"data: {json.dumps({'type': 'report', 'data': node_output['report']})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/skills")
async def list_skills():
    """Return the list of active skills."""
    from app.skills import discover_skills
    skills = discover_skills()
    return {"skills": [{"name": s.name, "description": s.description} for s in skills]}


# ---------------------------------------------------------------------------
# Serve frontend static files (must come after API routes)
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
