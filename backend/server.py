
import json
import uuid
from typing import Any

from app.graph.workflow import ORDER, build_workflow
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

import scheduler

app = FastAPI()
scheduler.start(app)  # weekly autonomous run; see scheduler.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STEP_META = {
    "planner": ("Planner", "Pick article count and output format"),
    "researcher": ("Researcher", "Search web + BBC, extract, dedupe, sort"),
    "summarizer": ("Summarizer", "Summarize each article in parallel"),
    "writer": ("Writer", "Draft the newsletter from summaries"),
    "reviewer": ("Reviewer", "Score the draft, revise if weak"),
    "output": ("Output", "Send the email (simulated) and save the file"),
}


RUNS: dict[str, Any] = {}


def _digest(changes: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in changes.items():
        if isinstance(value, BaseModel):
            out[key] = value.model_dump()
        elif key == "articles":
            out[key] = [
                {k: v for k, v in a.items() if k != "content"} for a in value
            ]
        else:
            out[key] = value
    return out


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _pump(workflow, stream_input, config, thread_id: str):
    for update in workflow.stream(stream_input, config, stream_mode="updates"):
        if "__interrupt__" in update:
            payload = update["__interrupt__"][0].value
            yield _sse("interrupt", {"thread_id": thread_id, "draft": payload})
            return  
        node, changes = next(iter(update.items()))
        yield _sse("step", {"id": node, "output": _digest(changes)})

    final = workflow.get_state(config).values
    RUNS.pop(thread_id, None)
    yield _sse(
        "done",
        {
            "subject": final.get("subject", ""),
            "newsletter": final.get("newsletter", ""),
            "output_path": final.get("output_path", ""),
            "sent": final.get("sent", False),
            "revision_count": final.get("revision_count", 0),
            "format": getattr(final.get("plan"), "output_format", "markdown"),
        },
    )


def _start(goal: str, mode: str):
    steps = list(ORDER)
    if mode == "human":  
        steps.insert(steps.index("output"), "human_gate")
    yield _sse(
        "steps",
        [
            {
                "id": n,
                "label": STEP_META.get(n, ("Human review", ""))[0]
                if n != "human_gate"
                else "Human review",
                "desc": STEP_META.get(n, ("", "Approve or request changes"))[1]
                if n != "human_gate"
                else "Approve or request changes",
            }
            for n in steps
        ],
    )

    workflow = build_workflow(mode=mode)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    RUNS[thread_id] = (workflow, config)
    state = {"goal": goal, "mode": mode, "max_revisions": 2}
    try:
        yield from _pump(workflow, state, config, thread_id)
    except Exception as exc:  # noqa: BLE001 
        RUNS.pop(thread_id, None)
        yield _sse("error", {"message": str(exc)})


def _resume(thread_id: str, approved: bool, feedback: str):
    entry = RUNS.get(thread_id)
    if not entry:
        yield _sse("error", {"message": "Run expired or unknown. Start again."})
        return
    workflow, config = entry
    decision = {"approved": approved, "feedback": feedback}
    try:
        yield from _pump(workflow, Command(resume=decision), config, thread_id)
    except Exception as exc:  # noqa: BLE001
        RUNS.pop(thread_id, None)
        yield _sse("error", {"message": str(exc)})


@app.get("/run")
def run(goal: str, mode: str = "autonomous"):
    return StreamingResponse(_start(goal, mode), media_type="text/event-stream")


@app.get("/resume")
def resume(thread_id: str, approved: bool, feedback: str = ""):
    return StreamingResponse(
        _resume(thread_id, approved, feedback), media_type="text/event-stream"
    )
