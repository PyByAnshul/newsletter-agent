import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from langchain_core.tools import tool

SCRAPER_DIR = Path(__file__).resolve().parents[2] / "newsletter_scraper"


def _is_current(record: dict, now: datetime | None = None) -> bool:
    if "/live/" in record.get("url", ""):
        return True
    published_at = record.get("published_at")
    if not published_at:
        return False
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    now = now or datetime.now(UTC)
    return now - timedelta(hours=48) <= published <= now + timedelta(hours=1)


def scrape_bbc_query(query: str) -> list[dict]:
    """Scrape recent BBC articles matching a search query."""
    result = subprocess.run(
        ["scrapy", "crawl", "bbc", "-a", f"query={query}", "-o", "-:json"],
        cwd=SCRAPER_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or "BBC scraper failed.")
    records = json.loads(result.stdout or "[]")
    return [r for r in records if _is_current(r)]


scrape_bbc_query_tool = tool(scrape_bbc_query)
