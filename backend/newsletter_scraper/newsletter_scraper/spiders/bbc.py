from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import scrapy


class BbcSpider(scrapy.Spider):
    name = "bbc"

    allowed_domains = [  # noqa: RUF012
        "bbc.com",
        "bbc.co.uk",
    ]

    _default_start_urls = [  # noqa: RUF012
        "https://www.bbc.com/news",
        "https://www.bbc.com/sport",
        "https://www.bbc.com/business",
        "https://www.bbc.com/technology",
        "https://www.bbc.com/health",
        "https://www.bbc.com/culture",
        "https://www.bbc.com/arts",
        "https://www.bbc.com/travel",
        "https://www.bbc.com/future-planet",
        "https://www.bbc.com/audio",
        "https://www.bbc.com/video",
        "https://www.bbc.com/live",
    ]

    custom_settings = {  # noqa: RUF012
        "ROBOTSTXT_OBEY": False,
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
            "Referer": "https://www.bbc.com/",
            "Upgrade-Insecure-Requests": "1",
        },

        "CONCURRENT_REQUESTS": 32,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,

        "DOWNLOAD_DELAY": 0.1,
        "RANDOMIZE_DOWNLOAD_DELAY": True,

        "RETRY_TIMES": 2,

        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 0.5,
        "AUTOTHROTTLE_MAX_DELAY": 5,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 8,
    }

    current_window = timedelta(hours=48)

    def __init__(self, query=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if query:
            self.start_urls = [f"https://www.bbc.com/search?{urlencode({'q': query})}"]
            self._is_search = True
        else:
            self.start_urls = self._default_start_urls
            self._is_search = False

    def parse(self, response):
        if self._is_search:
            for article in response.css("a[data-testid='internal-link']"):
                href = article.attrib.get("href")
                if not href:
                    continue
                url = response.urljoin(href)
                category = urlparse(url).path.strip("/").split("/")[0] or "search"
                yield scrapy.Request(url, callback=self.parse_article, meta={"category": category})
            return

        category = urlparse(response.url).path.strip("/").split("/")[0] or "news"

        for article in response.css("a[data-testid='internal-link']"):

            title = (
                article.css("h3::text").get()
                or article.css("p::text").get()
            )

            href = article.attrib.get("href")

            if not title or not href:
                continue

            url = response.urljoin(href)

            yield scrapy.Request(
                url,
                callback=self.parse_article,
                meta={"category": category},
            )

    def parse_article(self, response):
        title = response.css("h1::text").get()
        published_at = (
            response.css("time[datetime]::attr(datetime)").get()
            or response.css("meta[property='article:published_time']::attr(content)").get()
        )

        if not self._is_current(response.url, published_at):
            return

        paragraphs = response.css(
            "main p::text"
        ).getall()

        content = "\n".join(
            p.strip()
            for p in paragraphs
            if p.strip()
        )

        yield {
            "url": response.url,
            "title": title.strip() if title else None,
            "category": response.meta["category"],
            "published_at": published_at or "",
            "content": content,
        }

    def _is_current(self, url, published_at):
        if "/live/" in url:
            return True
        if not published_at:
            return False

        try:
            published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            return False

        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        return now - self.current_window <= published <= now + timedelta(hours=1)
