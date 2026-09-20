"""Weekly newsletter scheduler.

Runs `run_newsletter_agent(goal, mode="autonomous")` once a week at a fixed
weekday/hour. Recomputes the next slot on every startup, so a restart just
re-targets the next occurrence.

ponytail: in-process asyncio loop, single worker, no persistence. A missed run
(server down at the slot) is skipped, not caught up. Move to APScheduler +
a job store, or system cron calling `run.py`, if you need catch-up or multi-worker.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

# Default: every Monday 09:00 local. Override via env.
WEEKDAY = int(os.getenv("NEWSLETTER_WEEKDAY", "0"))  # 0=Mon .. 6=Sun
HOUR = int(os.getenv("NEWSLETTER_HOUR", "9"))
GOAL = os.getenv(
    "NEWSLETTER_GOAL",
    "Create a weekly newsletter on the latest AI agent news "
    "and send it to our subscribers.",
)


def _seconds_until_next(now: datetime) -> float:
    """Seconds from `now` to the next WEEKDAY at HOUR:00 (strictly future)."""
    target = now.replace(hour=HOUR, minute=0, second=0, microsecond=0)
    days_ahead = (WEEKDAY - now.weekday()) % 7
    target += timedelta(days=days_ahead)
    if target <= now:
        target += timedelta(days=7)
    return (target - now).total_seconds()


async def _weekly_loop():
    while True:
        delay = _seconds_until_next(datetime.now(timezone.utc))
        await asyncio.sleep(delay)
        try:
            from run import run_newsletter_agent  # lazy: keep import cost off startup

            # run_newsletter_agent is blocking (LLM + network) -> off the loop.
            await asyncio.to_thread(run_newsletter_agent, GOAL, "autonomous")
        except Exception as exc:  # one bad run must not kill the loop
            print(f"[scheduler] weekly run failed: {exc}")


def start(app):
    """Attach the weekly loop to a FastAPI app's lifespan."""

    @app.on_event("startup")
    async def _launch():
        app.state.newsletter_task = asyncio.create_task(_weekly_loop())

    @app.on_event("shutdown")
    async def _stop():
        task = getattr(app.state, "newsletter_task", None)
        if task:
            task.cancel()


if __name__ == "__main__":  # self-check: schedule math, no network
    base = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)  # Sunday 12:00
    s = _seconds_until_next(base)
    got = base + timedelta(seconds=s)
    assert got.weekday() == WEEKDAY and got.hour == HOUR, got
    # exactly at the slot -> jump a full week, never 0
    at_slot = datetime(2026, 9, 21, HOUR, 0, tzinfo=timezone.utc)  # Monday HOUR:00
    assert _seconds_until_next(at_slot) == 7 * 24 * 3600
    print("scheduler self-check ok")
