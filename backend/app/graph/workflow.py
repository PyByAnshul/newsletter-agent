from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    human_gate_node,
    output_node,
    planner_node,
    researcher_node,
    reviewer_node,
    summarizer_node,
    writer_node,
)
from app.graph.state import NewsletterState

# Linear step names, in display order (used by the UI / start_at / stop_after).
ORDER = ["planner", "researcher", "summarizer", "writer", "reviewer", "output"]
NODES = {
    "planner": planner_node,
    "researcher": researcher_node,
    "summarizer": summarizer_node,
    "writer": writer_node,
    "reviewer": reviewer_node,
    "output": output_node,
}

DEFAULT_MAX_REVISIONS = 2


def _route_after_review(state: NewsletterState) -> str:
    approved = state.get("approved", False)
    revisions = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", DEFAULT_MAX_REVISIONS)
    if not approved and revisions < max_revisions:
        return "writer"
    return "output"


def _route_after_gate(state: NewsletterState) -> str:
    return "output" if state.get("approved", True) else "writer"


def build_workflow(mode: str = "autonomous"):

    graph = StateGraph(NewsletterState)
    for name in ORDER:
        graph.add_node(name, NODES[name])

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "summarizer")
    graph.add_edge("summarizer", "writer")
    graph.add_edge("writer", "reviewer")

    if mode == "human":
        graph.add_node("human_gate", human_gate_node)
        graph.add_edge("reviewer", "human_gate")
        graph.add_conditional_edges(
            "human_gate", _route_after_gate, {"writer": "writer", "output": "output"}
        )
    else:
        graph.add_conditional_edges(
            "reviewer", _route_after_review, {"writer": "writer", "output": "output"}
        )

    graph.add_edge("output", END)
    # Checkpointer is required for interrupt/resume in human mode; harmless otherwise.
    return graph.compile(checkpointer=MemorySaver())
