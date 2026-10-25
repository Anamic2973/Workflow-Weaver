"""
Builds the compiled LangGraph state graph for a WorkflowWeaver run.

    START -> parse_intent -> plan_actions -> execute_step -> verify_step
                                                  ^               |
                                                  |     retry     |
                                                  +----------------
                                                                  |
                                       (more steps, no failure) --+--> execute_step
                                                                  |
                                       (all steps done, no crit.) +--> build_report -> END
                                                                  |
                                       (critical failure)         +--> rollback -> build_report -> END
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.agent.state import WorkflowState


def route_after_verify(state: WorkflowState) -> str:
    if state.get("critical_failure"):
        return "rollback"

    idx = state["current_step_index"]

    if idx < len(state["plan"]) and state["plan"][idx]["status"] == "retrying":
        return "execute_step"

    if idx < len(state["plan"]):
        return "execute_step"

    return "build_report"


def build_graph():
    graph = StateGraph(WorkflowState)

    graph.add_node("parse_intent", nodes.parse_intent)
    graph.add_node("plan_actions", nodes.plan_actions)
    graph.add_node("execute_step", nodes.execute_step)
    graph.add_node("verify_step", nodes.verify_step)
    graph.add_node("rollback", nodes.rollback)
    graph.add_node("build_report", nodes.build_report)

    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "plan_actions")
    graph.add_edge("plan_actions", "execute_step")
    graph.add_edge("execute_step", "verify_step")

    graph.add_conditional_edges(
        "verify_step",
        route_after_verify,
        {
            "execute_step": "execute_step",
            "rollback": "rollback",
            "build_report": "build_report",
        },
    )

    graph.add_edge("rollback", "build_report")
    graph.add_edge("build_report", END)

    return graph.compile()


compiled_graph = build_graph()
