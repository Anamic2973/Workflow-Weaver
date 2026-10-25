"""Pydantic models for API requests/responses."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    ROLLED_BACK = "rolled_back"


class WorkflowRunRequest(BaseModel):
    description: str = Field(..., description="Natural language workflow description")
    template_id: Optional[str] = Field(None, description="Optional pre-built template id")
    config: dict[str, Any] = Field(default_factory=dict, description="workspace/folder/channel overrides")


class WorkflowStep(BaseModel):
    id: str
    tool: str  # notion | google_drive | calendar | teams | planner
    action: str
    description: str
    status: StepStatus = StepStatus.PENDING
    attempt: int = 0
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str
    example_prompt: str
    tools_used: list[str]


class ExecutionEvent(BaseModel):
    """Shape of every SSE event streamed to the frontend."""
    type: str  # plan | step_start | step_update | step_end | rollback | report | error
    run_id: str
    timestamp: str
    payload: dict[str, Any]


class ExecutionReport(BaseModel):
    run_id: str
    description: str
    started_at: str
    finished_at: str
    status: str  # success | partial_failure | failed
    steps: list[WorkflowStep]
    rolled_back_steps: list[str] = Field(default_factory=list)
    langfuse_trace_url: Optional[str] = None
