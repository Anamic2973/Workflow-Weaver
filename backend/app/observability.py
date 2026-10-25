"""
Langfuse instrumentation.

Every LLM call and tool invocation in the LangGraph agent is wrapped in a
Langfuse span so the full run — planning, each tool call, retries, rollback —
shows up as one trace per workflow execution.
"""
from __future__ import annotations

import functools
import time
from typing import Any, Callable

from langfuse import Langfuse

from app.config import settings

_langfuse_client: Langfuse | None = None


def get_langfuse() -> Langfuse:
    global _langfuse_client
    if _langfuse_client is None:
        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
    return _langfuse_client


class WorkflowTrace:
    """One Langfuse trace per workflow run, with a span per node/tool call."""

    def __init__(self, run_id: str, description: str):
        self.client = get_langfuse()
        self.trace = self.client.trace(
            id=run_id,
            name="workflowweaver-run",
            input={"description": description},
            metadata={"model": settings.LLM_MODEL},
        )

    def span(self, name: str):
        return self.trace.span(name=name)

    def generation(self, name: str, model: str, input_: Any, output: Any, usage: dict | None = None):
        self.trace.generation(
            name=name,
            model=model,
            input=input_,
            output=output,
            usage=usage or {},
        )

    def score_step(self, step_id: str, success: bool):
        self.trace.score(name=f"step_success::{step_id}", value=1.0 if success else 0.0)

    def finalize(self, output: Any):
        self.trace.update(output=output)
        self.client.flush()

    @property
    def url(self) -> str:
        try:
            return self.trace.get_trace_url()
        except Exception:
            return f"{settings.LANGFUSE_HOST}/trace/{self.trace.id}"


def traced_tool_call(tool_name: str):
    """Decorator to wrap MCP tool calls with span timing + error capture."""

    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, trace: WorkflowTrace | None = None, **kwargs):
            start = time.time()
            span = trace.span(name=f"tool::{tool_name}") if trace else None
            try:
                result = await fn(*args, **kwargs)
                if span:
                    span.end(output=result, metadata={"latency_s": time.time() - start})
                return result
            except Exception as e:
                if span:
                    span.end(output={"error": str(e)}, level="ERROR", metadata={"latency_s": time.time() - start})
                raise

        return wrapper

    return decorator
