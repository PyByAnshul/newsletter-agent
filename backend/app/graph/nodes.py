import asyncio
from datetime import UTC, datetime

from langgraph.types import interrupt

from app.graph.state import (
    ArticleSummary,
    NewsletterDraft,
    NewsletterState,
    Plan,
    Review,
    SearchQueries,
)
from app.llm.client import get_llm
from app.tools.emailer import send_newsletter_email_tool
from app.tools.scrapper import scrape_bbc_query_tool
from app.tools.websearch import web_search_news_tool


def planner_node(state: NewsletterState) -> NewsletterState:
    planner = get_llm().with_structured_output(Plan)
    prompt = (
        f"For this newsletter goal, pick the article count (5-7) and output "
        f"format (markdown or html): {state['goal']}"
    )
    return {"plan": planner.invoke(prompt)}


def researcher_node(state: NewsletterState) -> NewsletterState:
    plan = state.get("plan")
    article_count = plan.article_count if plan else 5
    goal = state["goal"]

    queries = (
        get_llm().with_structured_output(SearchQueries)
        .invoke(f"Generate 2-5 short search queries to find recent news articles about: {goal}")
        .queries
    )

    seen_urls: set[str] = set()
    records: list[dict] = []
    for query in queries:
        for tool, source in (
            (scrape_bbc_query_tool, "BBC"),
            (web_search_news_tool, None),  
        ):
            try:
                hits = tool.invoke({"query": query})
            except Exception:  # noqa: BLE001,S112 - one source failing shouldn't abort research
                continue
            for record in hits:
                url = record.get("url")
                if url and url not in seen_urls and record.get("content"):
                    seen_urls.add(url)
                    records.append({**record, "source": source or record.get("source", "Web")})

    def published_at(record: dict) -> datetime:
        try:
            dt = datetime.fromisoformat(record["published_at"].replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except (ValueError, KeyError, AttributeError):
            return datetime.min.replace(tzinfo=UTC)

    records.sort(key=published_at, reverse=True)

    return {
        "search_queries": queries,
        "articles": [
            {
                "title": r.get("title") or "Untitled article",
                "url": r["url"],
                "source": r.get("source", "Web"),
                "published_at": r.get("published_at", ""),
                "content": r.get("content", ""),
                "summary": "",
            }
            for r in records[:article_count]
        ],
    }


async def _summarize_article(article: dict, goal: str, summarizer) -> dict:
    prompt = (
        f"Summarize this article in 2-4 factual sentences relevant to: {goal}\n\n"
        f"Title: {article['title']}\nContent: {article['content'][:1500]}"
    )
    result = await summarizer.ainvoke(prompt)
    return {**article, "summary": result.summary}


def summarizer_node(state: NewsletterState) -> NewsletterState:
    articles = state.get("articles", [])
    if not articles:
        return {"articles": []}

    summarizer = get_llm(max_tokens=1024).with_structured_output(ArticleSummary)

    async def summarize_all():
        return await asyncio.gather(
            *[_summarize_article(a, state["goal"], summarizer) for a in articles]
        )

    return {"articles": list(asyncio.run(summarize_all()))}


def writer_node(state: NewsletterState) -> NewsletterState:
    plan = state.get("plan")
    output_format = plan.output_format if plan else "markdown"
    articles_text = "\n\n".join(
        f"Title: {a['title']}\nSource: {a['source']}\nURL: {a['url']}\nSummary: {a['summary']}"
        for a in state.get("articles", [])
    )

    feedback = state.get("review_feedback", "")
    revision_note = (
        f"\n\nThis is a revision. Address this feedback on the previous draft:\n{feedback}\n"
        if feedback and state.get("revision_count", 0) > 0
        else ""
    )
    writer = get_llm(max_tokens=8192).with_structured_output(NewsletterDraft)
    draft = writer.invoke(
        f"Write a concise {output_format} newsletter for this goal: {state['goal']}\n\n"
        f"Use only these article summaries. Include every article's title and URL. Do not invent facts."
        f"{revision_note}\n\n"
        f"{articles_text}"
    )
    return {"subject": draft.subject, "newsletter": draft.content}


def reviewer_node(state: NewsletterState) -> NewsletterState:
    reviewer = get_llm().with_structured_output(Review)
    review = reviewer.invoke(
        f"Review this newsletter against its goal. Check factual restraint, clarity, "
        f"and whether it includes its article links.\n"
        f"Return a score from 0 to 10 and concise feedback.\n\n"
        f"Goal: {state['goal']}\nNewsletter:\n{state.get('newsletter', '')}"
    )
    return {
        "review_feedback": review.feedback,
        "review_score": review.score,
        "approved": review.score >= 7,
        "revision_count": state.get("revision_count", 0) + 1,
    }


def human_gate_node(state: NewsletterState) -> NewsletterState:
    """Human-in-the-loop pause: surface the draft + review, wait for a decision.

    Resume value: {"approved": bool, "feedback": str}. Only runs in human mode.
    """
    decision = interrupt(
        {
            "subject": state.get("subject", ""),
            "newsletter": state.get("newsletter", ""),
            "review_feedback": state.get("review_feedback", ""),
            "review_score": state.get("review_score"),
        }
    )
    feedback = (decision or {}).get("feedback", "")
    return {
        "approved": bool((decision or {}).get("approved", True)),
        "review_feedback": feedback or state.get("review_feedback", ""),
    }


def output_node(state: NewsletterState) -> NewsletterState:
    plan = state.get("plan")
    output_format = plan.output_format if plan else "markdown"
    path = send_newsletter_email_tool.invoke(
        {
            "subject": state.get("subject", "Weekly Newsletter"),
            "body": state.get("newsletter", ""),
            "output_format": output_format,
        }
    )
    return {"output_path": path, "sent": True}
