"""Web search tool: DuckDuckGo news search + article extraction (no API key)."""

import trafilatura
from ddgs import DDGS
from langchain_core.tools import tool


def web_search_news(query: str, max_results: int = 5) -> list[dict]:
    """Search the web for recent news matching a query and extract article text.

    Returns records shaped like the BBC scraper: title, url, source,
    published_at, content. Any page that fails to fetch/extract is skipped.
    """
    records: list[dict] = []
    with DDGS() as ddgs:
        hits = list(ddgs.news(query, max_results=max_results))

    for hit in hits:
        url = hit.get("url")
        if not url:
            continue
        downloaded = trafilatura.fetch_url(url)
        content = trafilatura.extract(downloaded) if downloaded else None
        if not content:
            content = hit.get("body", "")  # fall back to the snippet
        records.append(
            {
                "title": hit.get("title") or "Untitled article",
                "url": url,
                "source": hit.get("source") or "Web",
                "published_at": hit.get("date", ""),
                "content": content or "",
            }
        )
    return records


web_search_news_tool = tool(web_search_news)


if __name__ == "__main__":
    # ponytail: one live check — network-dependent, run manually.
    out = web_search_news("latest AI agent news", max_results=3)
    assert isinstance(out, list)
    for r in out:
        assert r["url"] and "content" in r
    print(f"ok: {len(out)} results")
