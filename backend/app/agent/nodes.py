"""
Node implementations for the WorkflowWeaver LangGraph agent.

Graph shape:

    parse_intent --> plan_actions --> execute_step --(loop)--> verify_step
                                                                    |
                                            success ----------------+--- failure (retries left)
                                                |                          |
                                          next step? --yes--> execute_step |
                                                |                          v
                                                no                    retry (backoff) --> execute_step
                                                |
                                          critical failure? --yes--> rollback --> report
                                                |
                                                no
                                                v
                                             report
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from openai import OpenAI

from app.agent.state import ActionStep, WorkflowState
from app.agent.tools import calendar_tool, gdrive_tool, notion_tool, teams_tool
from app.config import settings
from app.observability import WorkflowTrace

TOOL_ACTIONS = {
    "notion": {"create_page": notion_tool.create_page, "create_action_items": notion_tool.create_action_items},
    "google_drive": {"create_document": gdrive_tool.create_document},
    "teams": {"post_message": teams_tool.post_message},
    "calendar": {"create_event": calendar_tool.create_event},
}

ROLLBACK_ACTIONS = {
    ("notion", "create_page"): ("notion", notion_tool.delete_page, "page_id"),
    ("google_drive", "create_document"): ("google_drive", gdrive_tool.delete_document, "file_id"),
    ("calendar", "create_event"): ("calendar", calendar_tool.delete_event, "event_id"),
    # Teams messages are not reversible — handled via post_correction in rollback node instead.
}

PLANNER_SYSTEM_PROMPT_TEMPLATE = """You are the planning module for WorkflowWeaver, an agent that automates \
business workflows across Notion, Google Drive, Google Calendar, and Microsoft Teams.

Today's date is {today}. Resolve relative dates ("next Monday", "tomorrow") against this date.

Given a natural-language workflow description, output a JSON array of ordered steps. Each step:
{{
  "tool": "notion" | "google_drive" | "calendar" | "teams",
  "action": "create_page" | "create_action_items" | "create_document" | "create_event" | "post_message",
  "description": "short human-readable description of this step",
  "args": {{ ...action-specific arguments... }}
}}

Argument shapes:
- notion.create_page: {{"title": str, "content": html}}
- notion.create_action_items: {{"page_id": "$step:<index>.page_id", "items": [str, ...]}}
- google_drive.create_document: {{"title": str, "content": html}}
- calendar.create_event: {{"summary": str, "start": "YYYY-MM-DDTHH:MM:SS", "end": "YYYY-MM-DDTHH:MM:SS", "description": str (optional), "attendees": [email, ...] (optional)}}
- teams.post_message: {{"title": str, "text": str, "facts": [[str,str], ...]}}

For "content" fields marked `html` above, format the body as real HTML — not one flat \
paragraph. Use <h1>/<h2>/<h3> for section headings, <p> for paragraphs, <ul>/<ol> with <li> for \
lists, and <b>/<i> for emphasis. Structure the content properly: e.g. a meeting summary should \
have a heading, a paragraph or two of narrative, and a bulleted list of decisions/owners — not \
everything crammed into a single <p>. Example: \
"<h2>Meeting Summary</h2><p>Discussed the Q3 launch timeline.</p><ul><li><b>Sarthak</b>: ship the \
payment integration by Friday</li><li><b>Anjali</b>: complete QA by Monday</li></ul>"

Only include a calendar step if the description explicitly asks to schedule/book a meeting or event.

Use "$step:<index>.<field>" to reference the output of an earlier step (0-indexed) when a later \
step needs an id produced by a previous one (e.g. attaching action items to a page just created).

Respond with ONLY the JSON array — no prose, no markdown fences.
"""


def _client() -> OpenAI:
    """Groq exposes an OpenAI-compatible Chat Completions API, so the
    standard OpenAI SDK works unmodified against it — just a different
    base_url and API key."""
    return OpenAI(api_key=settings.LLM_API_KEY, base_url="https://api.groq.com/openai/v1")


async def parse_intent(state: WorkflowState) -> dict:
    """Light normalization node — currently a pass-through, kept as an explicit
    graph stage so intent parsing can be extended (e.g. slot-filling, clarifying
    questions) without reshaping the graph."""
    return {"last_event": {"type": "plan", "payload": {"stage": "parsing_intent"}}}


async def plan_actions(state: WorkflowState) -> dict:
    """Calls the LLM to turn the NL description into a structured step plan."""
    trace: WorkflowTrace = state["config"]["_trace"]
    client = _client()

    start = time.time()
    system_prompt = PLANNER_SYSTEM_PROMPT_TEMPLATE.format(today=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["description"]},
        ],
    )
    raw = response.choices[0].message.content.strip()
    trace.generation(
        name="plan_actions",
        model=settings.LLM_MODEL,
        input_=state["description"],
        output=raw,
        usage={
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
            "unit": "TOKENS",
        },
    )

    import json

    try:
        raw_steps = json.loads(raw)
    except json.JSONDecodeError:
        raw_steps = []

    plan: list[ActionStep] = []
    for i, s in enumerate(raw_steps):
        tool, action = s["tool"], s["action"]
        rollback = ROLLBACK_ACTIONS.get((tool, action))
        plan.append(
            ActionStep(
                id=f"step-{i}-{uuid.uuid4().hex[:6]}",
                tool=tool,
                action=action,
                description=s.get("description", f"{tool}.{action}"),
                args=s.get("args", {}),
                status="pending",
                attempt=0,
                result=None,
                error=None,
                rollback_action=rollback[1].__name__ if rollback else None,
            )
        )

    return {
        "plan": plan,
        "current_step_index": 0,
        "last_event": {"type": "plan", "payload": {"steps": [dict(p) for p in plan]}},
    }


def _resolve_refs(args: dict, completed: list[ActionStep]) -> dict:
    """Resolve '$step:<index>.<field>' references against already-completed steps."""
    resolved = {}
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("$step:"):
            ref = v[len("$step:"):]
            idx_str, field = ref.split(".", 1)
            idx = int(idx_str)
            resolved[k] = completed[idx]["result"].get(field) if idx < len(completed) else None
        else:
            resolved[k] = v
    return resolved


async def execute_step(state: WorkflowState) -> dict:
    """Executes the current step's tool call, tracing it in Langfuse."""
    trace: WorkflowTrace = state["config"]["_trace"]
    idx = state["current_step_index"]
    step = dict(state["plan"][idx])
    step["attempt"] += 1
    step["status"] = "running"

    fn = TOOL_ACTIONS[step["tool"]][step["action"]]
    args = _resolve_refs(step["args"], state["completed_steps"])

    span = trace.span(name=f"execute::{step['tool']}.{step['action']}")
    t0 = time.time()
    try:
        result = await fn(**args)
        step["status"] = "success"
        step["result"] = result
        step["error"] = None
        span.end(output=result, metadata={"latency_s": time.time() - t0, "attempt": step["attempt"]})
        trace.score_step(step["id"], True)
    except Exception as e:
        # Some exceptions (e.g. a bare NotImplementedError) stringify to ""
        # — fall back to the type name so the report is never blank.
        message = str(e) or type(e).__name__
        step["status"] = "failed"
        step["error"] = message
        span.end(output={"error": message}, level="ERROR", metadata={"attempt": step["attempt"]})
        trace.score_step(step["id"], False)

    return {
        "plan": [step if i == idx else s for i, s in enumerate(state["plan"])],
        "last_event": {"type": "step_update", "payload": step},
    }


async def verify_step(state: WorkflowState) -> dict:
    """Decides: advance, retry with backoff, or escalate to critical failure."""
    idx = state["current_step_index"]
    step = state["plan"][idx]

    if step["status"] == "success":
        return {
            "completed_steps": [step],
            "current_step_index": idx + 1,
            "critical_failure": False,
        }

    if step["attempt"] < settings.MAX_RETRIES:
        delay = settings.RETRY_BASE_DELAY_SECONDS * (2 ** (step["attempt"] - 1))
        await asyncio.sleep(delay)
        retried = dict(step)
        retried["status"] = "retrying"
        return {
            "plan": [retried if i == idx else s for i, s in enumerate(state["plan"])],
            "last_event": {"type": "step_update", "payload": {**retried, "retry_delay_s": delay}},
        }

    # Retries exhausted -> critical failure, trigger rollback
    return {
        "critical_failure": True,
        "failure_reason": step["error"],
        "completed_steps": [step],
        "current_step_index": idx + 1,
    }


async def rollback(state: WorkflowState) -> dict:
    """Reverses previously-successful steps in reverse order; posts a Teams correction."""
    trace: WorkflowTrace = state["config"]["_trace"]
    rolled_back = []

    for step in reversed(state["completed_steps"]):
        if step["status"] != "success":
            continue
        key = (step["tool"], step["action"])
        rb = ROLLBACK_ACTIONS.get(key)
        if not rb:
            continue
        _, rb_fn, id_field = rb
        span = trace.span(name=f"rollback::{step['tool']}.{step['action']}")
        try:
            await rb_fn(step["result"][id_field])
            rolled_back.append(step["id"])
            span.end(output={"rolled_back": True})
        except Exception as e:
            span.end(output={"error": str(e)}, level="ERROR")

    try:
        await teams_tool.post_correction(
            original_title=state["description"][:80], reason=state.get("failure_reason", "unknown error")
        )
    except Exception:
        pass  # best-effort — don't let notification failure block the report

    return {
        "rolled_back_step_ids": rolled_back,
        "last_event": {"type": "rollback", "payload": {"rolled_back_step_ids": rolled_back}},
    }


async def build_report(state: WorkflowState) -> dict:
    """Assembles the final execution report and finalizes the Langfuse trace."""
    trace: WorkflowTrace = state["config"]["_trace"]

    if state.get("critical_failure"):
        # critical failure always routes through rollback before build_report,
        # so anything persisted from this run has already been reversed.
        status = "failed"
    else:
        any_failed = any(s["status"] == "failed" for s in state["completed_steps"])
        status = "partial_failure" if any_failed else "success"

    report = {
        "run_id": state["run_id"],
        "description": state["description"],
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "steps": state["completed_steps"],
        "rolled_back_steps": state.get("rolled_back_step_ids", []),
        "langfuse_trace_url": trace.url,
    }
    trace.finalize(output=report)

    return {"final_status": status, "last_event": {"type": "report", "payload": report}}
