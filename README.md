# Newsletter Agent

You give it a goal like "a weekly newsletter on the latest AI agent news" and it goes and builds one. It searches the web, pulls the articles, summarizes them, drafts the newsletter, reviews its own draft, and sends it. You can watch each step happen in the browser, or let it run on its own every week.

https://youtu.be/hgZxk_JtAVY

## How it works

The whole thing is a LangGraph pipeline. Six nodes, run in order:

1. **planner** — decides how many articles to pull and whether the output is markdown or HTML
2. **researcher** — searches the web and BBC, extracts the pages, dedupes, sorts by date
3. **summarizer** — summarizes each article (runs them in parallel)
4. **writer** — drafts the newsletter from the summaries
5. **reviewer** — scores the draft and sends it back to the writer if it's weak (up to `max_revisions` times)
6. **output** — saves the file and "sends" the email (simulated)

There are two ways to run it. Autonomous just goes end to end. Human mode pauses after the review so you can approve the draft or ask for changes before anything goes out.

## Layout

```
backend/
  app/
    graph/      # the LangGraph pipeline — state, nodes, workflow wiring
    tools/      # web search, scraper, emailer
    llm/        # the model client
    config.py   # reads LLM_* from .env
  newsletter_scraper/   # Scrapy project the researcher shells out to
  output/       # generated newsletters land here
  run.py        # CLI entry point
  server.py     # FastAPI + SSE, streams each step to the frontend
  scheduler.py  # weekly autonomous run
frontend/       # React + Vite UI
```

## Setup

Backend needs Python 3 and the deps in `backend/requirements.txt`:

```bash
cd backend
pip install -r requirements.txt
```

Copy your keys into `backend/.env`:

```
LLM_API_KEY=...
LLM_MODEL=...
LLM_BASE_URL=https://openrouter.ai/api/v1   # optional, this is the default
```

Frontend:

```bash
cd frontend
npm install
```

## Running it

One-shot from the CLI:

```bash
cd backend
PYTHONPATH=. python -m run          # autonomous, prints a trace
```

Or run the server and drive it from the UI:

```bash
cd backend
PYTHONPATH=. python -m uvicorn server:app --reload --port 8000
```

```bash
cd frontend
npm run dev                         # http://localhost:5173
```

The server exposes two SSE endpoints — `/run?goal=...&mode=autonomous` and `/resume?thread_id=...&approved=...` for the human-in-the-loop case.

## The weekly scheduler

`backend/scheduler.py` runs one autonomous job a week. It's wired into the server's lifespan, so it starts when the server starts. Default slot is Monday 09:00 UTC. Override with env vars:

| Variable | Default | Meaning |
|----------|---------|---------|
| `NEWSLETTER_WEEKDAY` | `0` | 0 = Monday … 6 = Sunday |
| `NEWSLETTER_HOUR` | `9` | hour of day, UTC |
| `NEWSLETTER_GOAL` | AI agent news goal | the prompt it runs |

One thing to know: it's an in-process loop with no persistence. If the server is down when the slot comes around, that run is just skipped — it won't catch up on the next boot. That's fine for a single always-on server. If you need catch-up or you're running multiple workers, swap it for APScheduler with a job store, or drop the loop and put `run.py` on system cron.

You can sanity-check the scheduling math without touching the network:

```bash
cd backend
PYTHONPATH=. python scheduler.py    # prints "scheduler self-check ok"
```
