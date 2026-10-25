"""
FastAPI backend for WorkflowWeaver.

Endpoints:
  GET  /api/templates          -> list workflow templates
  POST /api/workflows/run      -> kick off a run, returns run_id
  GET  /api/workflows/stream/{run_id} -> SSE stream of execution events
  GET  /api/workflows/{run_id}/report -> fetch the final report (after completion)
  GET  /api/workflows/history  -> list past runs (in-memory for this scaffold)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import compiled_graph
from app.config import settings
from app.models import WorkflowRunRequest
from app.observability import WorkflowTrace
from app.templates import TEMPLATES, get_template

app = FastAPI(title="WorkflowWeaver API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory run store (swap for Redis/DB in production).
_runs: dict[str, dict] = {}
_run_queues: dict[str, asyncio.Queue] = {}


@app.get("/api/templates")
async def list_templates():
    return [t.model_dump() for t in TEMPLATES]


@app.post("/api/workflows/run")
async def start_run(req: WorkflowRunRequest):
    run_id = str(uuid.uuid4())
    description = req.description
    if req.template_id:
        tmpl = get_template(req.template_id)
        if not tmpl:
            raise HTTPException(404, f"Unknown template_id: {req.template_id}")
        description = description or tmpl.example_prompt

    queue: asyncio.Queue = asyncio.Queue()
    _run_queues[run_id] = queue
    _runs[run_id] = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}

    asyncio.create_task(_execute_run(run_id, description, req.config))
    return {"run_id": run_id}


async def _execute_run(run_id: str, description: str, config: dict):
    queue = _run_queues[run_id]
    trace = WorkflowTrace(run_id=run_id, description=description)

    initial_state = {
        "run_id": run_id,
        "description": description,
        "config": {**config, "_trace": trace},
        "plan": [],
        "current_step_index": 0,
        "completed_steps": [],
        "critical_failure": False,
        "failure_reason": None,
        "rolled_back_step_ids": [],
        "last_event": None,
        "final_status": None,
    }

    try:
        async for event in compiled_graph.astream(initial_state):
            for node_name, node_output in event.items():
                last_event = node_output.get("last_event") if node_output else None
                if last_event:
                    payload = {
                        "type": last_event["type"],
                        "run_id": run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": _jsonable(last_event["payload"]),
                    }
                    await queue.put(payload)
                    if last_event["type"] == "report":
                        _runs[run_id]["report"] = last_event["payload"]
                        _runs[run_id]["status"] = last_event["payload"]["status"]
    except Exception as e:
        await queue.put(
            {
                "type": "error",
                "run_id": run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {"error": str(e)},
            }
        )
        _runs[run_id]["status"] = "failed"
    finally:
        await queue.put(None)  # sentinel: stream done


def _jsonable(obj):
    return json.loads(json.dumps(obj, default=str))


@app.get("/api/workflows/stream/{run_id}")
async def stream_run(run_id: str):
    if run_id not in _run_queues:
        raise HTTPException(404, "Unknown run_id")

    async def event_generator():
        queue = _run_queues[run_id]
        while True:
            item = await queue.get()
            if item is None:
                yield {"event": "done", "data": "{}"}
                break
            yield {"event": item["type"], "data": json.dumps(item)}

    return EventSourceResponse(event_generator())


@app.get("/api/workflows/{run_id}/report")
async def get_report(run_id: str):
    run = _runs.get(run_id)
    if not run or "report" not in run:
        raise HTTPException(404, "Report not ready or run_id unknown")
    return run["report"]


@app.get("/api/workflows/history")
async def history():
    return [{"run_id": rid, **{k: v for k, v in r.items() if k != "report"}} for rid, r in _runs.items()]


@app.get("/health")
async def health():
    return {"status": "ok"}
