"""LangGraph state schema shared across all nodes in the workflow graph."""
from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict
import operator


class ActionStep(TypedDict):
    id: str
    tool: str          # "notion" | "google_drive" | "calendar" | "teams"
    action: str         # e.g. "create_page", "create_document", "create_event", "post_message"
    description: str
    args: dict[str, Any]
    status: str          # pending | running | success | failed | retrying | rolled_back
    attempt: int
    result: Optional[dict[str, Any]]
    error: Optional[str]
    rollback_action: Optional[str]   # e.g. "delete_page" — None if not reversible


class WorkflowState(TypedDict):
    run_id: str
    description: str
    config: dict[str, Any]

    # Populated by the planner node
    plan: list[ActionStep]

    # Index of the step currently being executed
    current_step_index: int

    # Accumulates step results as they complete (reducer = list append)
    completed_steps: Annotated[list[ActionStep], operator.add]

    # Set when a step exhausts retries -> triggers rollback branch
    critical_failure: bool
    failure_reason: Optional[str]

    rolled_back_step_ids: list[str]

    # Emitted for SSE streaming — the API layer reads this after each node
    last_event: Optional[dict[str, Any]]

    final_status: Optional[str]   # success | partial_failure | failed
