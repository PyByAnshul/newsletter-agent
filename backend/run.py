"""Newsletter Agent entry point.

One call runs the whole job:

    run_newsletter_agent(goal)                      # fully autonomous
    run_newsletter_agent(goal, mode="human")        # human-in-the-loop (console)
"""

import uuid
from pprint import pprint

from langgraph.types import Command

from app.graph.workflow import build_workflow


def run_newsletter_agent(goal, mode="autonomous", max_revisions=2, trace=False):
    """Run the agent end to end.

    mode="autonomous": plan -> research -> summarize -> write -> review -> (revise
    loop) -> send, with no human input.
    mode="human": same, but pauses after review for console approval before send.
    """
    workflow = build_workflow(mode=mode)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    state = {"goal": goal, "mode": mode, "max_revisions": max_revisions}

    def drain(stream):
        for update in stream:
            if "__interrupt__" in update:
                _handle_interrupt(workflow, update["__interrupt__"], config, trace)
                return
            node, changes = next(iter(update.items()))
            if trace:
                print(f"\n===== COMPLETED: {node} =====")
                pprint(changes, sort_dicts=False)

    drain(workflow.stream(state, config, stream_mode="updates"))
    return workflow.get_state(config).values


def _handle_interrupt(workflow, interrupts, config, trace):
    payload = interrupts[0].value
    print("\n===== HUMAN REVIEW =====")
    print(f"Subject: {payload.get('subject')}")
    print(f"Reviewer score: {payload.get('review_score')}")
    print(f"Reviewer feedback: {payload.get('review_feedback')}")
    print(f"\n{payload.get('newsletter')}\n")

    choice = input("Approve and send? [y] / request changes [n]: ").strip().lower()
    if choice == "n":
        feedback = input("What should change? ").strip()
        decision = {"approved": False, "feedback": feedback}
    else:
        decision = {"approved": True, "feedback": ""}

    # Resume; may hit the gate again after a rewrite -> keep draining.
    for update in workflow.stream(Command(resume=decision), config, stream_mode="updates"):
        if "__interrupt__" in update:
            _handle_interrupt(workflow, update["__interrupt__"], config, trace)
            return
        node, changes = next(iter(update.items()))
        if trace:
            print(f"\n===== COMPLETED: {node} =====")
            pprint(changes, sort_dicts=False)


if __name__ == "__main__":
    goal = (
        "Create a weekly newsletter on the latest AI agent news "
        "and send it to our subscribers."
    )
    final = run_newsletter_agent(goal, mode="autonomous", trace=True)
    print(f"\nDone. Sent={final.get('sent')} -> {final.get('output_path')}")
