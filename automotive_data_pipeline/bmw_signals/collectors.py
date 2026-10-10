import asyncio
import hashlib
import os
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from pydantic import Field, field_validator
from .models import Platform, RawPost, Region, Source, StrictModel

HOSTS = {
    "BIMMERPOST": ("bimmerpost.com",),
    "Bimmerforums": ("bimmerforums.com",),
    "German_Car_Forum": ("germancarforum.com",),
    "Competitor_Web": ("mercedes-benz.com", "mercedes-benz.co.uk", "mercedes-benz.de", "byd.com", "bydauto.com.cn"),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def source_record_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


class PageConfig(StrictModel):
    source_platform: Source
    url: str
    target_platform: Platform | None = None
    benchmark_context: str | None = None
    region: Region = "Unknown"
    country: str | None = None
    post_selector: str
    body_selector: str
    title_selector: str = "h1"
    timestamp_selector: str = "time"
    timestamp_attribute: str | None = "datetime"
    timestamp_format: str | None = None
    timestamp_timezone: str | None = None
    fallback_timestamp: str | None = None
    score_selector: str | None = None
    permalink_selector: str | None = None
    wait_selector: str | None = None

    @field_validator("fallback_timestamp")
    @classmethod
    def validate_fallback_timestamp(cls, value):
        if value is None:
            return value
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("fallback_timestamp must include a timezone")
        return parsed.isoformat()


class RedditConfig(StrictModel):
    subreddit: str
    query: str
    target_platform: Platform
    region: Region = "Unknown"
    country: str | None = None
    limit: int = Field(default=25, ge=1, le=500)
    comment_limit: int = Field(default=100, ge=0, le=1000)
    fetch_author_reputation: bool = True


class CollectionConfig(StrictModel):
    pages: list[PageConfig] = Field(default_factory=list)
    reddit: list[RedditConfig] = Field(default_factory=list)
    concurrency: int = Field(default=3, ge=1, le=10)


def check_url(url, source):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(host == h or host.endswith("." + h) for h in HOSTS.get(source, ())):
        raise ValueError("URL does not belong to the configured official source")


def extract(html, config, final_url):
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one(config.title_selector)
    title = title_node.get_text(" ", strip=True) if title_node else ""
    results = []
    for index, node in enumerate(soup.select(config.post_selector), 1):
        body = node.select_one(config.body_selector)
        if body is None:
            continue
        # Quotes must not be attributed to the author of the enclosing post.
        for noise in body.select("script, style, nav, footer, blockquote, .signature, .bbCodeBlock--quote"):
            noise.decompose()
        stamp = node.select_one(config.timestamp_selector)
        timestamp = config.fallback_timestamp
        if stamp:
            raw = stamp.get(config.timestamp_attribute) if config.timestamp_attribute else stamp.get_text(strip=True)
            if raw:
                try:
                    parsed = datetime.strptime(raw, config.timestamp_format) if config.timestamp_format else datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if parsed.tzinfo is None and config.timestamp_timezone:
                        from zoneinfo import ZoneInfo
                        parsed = parsed.replace(tzinfo=ZoneInfo(config.timestamp_timezone))
                    if parsed.tzinfo is not None:
                        timestamp = parsed.isoformat()
                except ValueError:
                    pass
        score_node = node.select_one(config.score_selector) if config.score_selector else None
        score = None
        if score_node:
            try:
                score = int(score_node.get_text(strip=True).replace(",", ""))
            except ValueError:
                pass
        link = node.select_one(config.permalink_selector) if config.permalink_selector else None
        url = urljoin(final_url, link.get("href", "")) if link else final_url
        identity_url = url if link else f"{url}#record-{index}"
        check_url(url, config.source_platform)
        results.append(RawPost(
            source_platform=config.source_platform, source_url=url,
            thread_title=title, post_body=body.get_text(" ", strip=True),
            timestamp=timestamp, score=score, target_platform=config.target_platform,
            collected_at=now(), benchmark_context=config.benchmark_context,
            source_record_id=source_record_id(identity_url),
            scope_layer="hypothetical_later" if config.source_platform == "Competitor_Web" else "variable_later",
            region=config.region, country=config.country,
        ))
    if not results:
        raise ValueError("No posts extracted; check selectors or access restrictions")
    return results


async def collect(config: CollectionConfig):
    posts, errors = [], []
    semaphore = asyncio.Semaphore(config.concurrency)

    async def page_job(context, page_config):
        async with semaphore:
            page = await context.new_page()
            try:
                check_url(page_config.url, page_config.source_platform)
                response = await page.goto(page_config.url, wait_until="domcontentloaded", timeout=60000)
                if response is None or response.status >= 400:
                    raise ValueError("Source returned an unsuccessful response")
                check_url(page.url, page_config.source_platform)
                await page.wait_for_selector(page_config.wait_selector or page_config.post_selector, timeout=15000)
                return extract(await page.content(), page_config, page.url)
            finally:
                await page.close()

    if config.pages:
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="BMWSignalsResearch/0.1")
            try:
                results = await asyncio.gather(*(page_job(context, p) for p in config.pages), return_exceptions=True)
                for page_config, result in zip(config.pages, results):
                    if isinstance(result, Exception):
                        errors.append({"source_url": page_config.url, "status": "collection_failed", "reason": type(result).__name__})
                    else:
                        posts.extend(result)
            finally:
                await context.close()
                await browser.close()
    if config.reddit:
        required = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            errors.extend({
                "subreddit": item.subreddit,
                "status": "collection_skipped",
                "reason": "MissingCredentials",
                "missing": missing,
            } for item in config.reddit)
            return posts, errors
        import asyncpraw
        async with asyncpraw.Reddit(client_id=os.environ["REDDIT_CLIENT_ID"], client_secret=os.environ["REDDIT_CLIENT_SECRET"], user_agent=os.environ["REDDIT_USER_AGENT"]) as reddit:
            async def reddit_job(item):
                async with semaphore:
                    records = []
                    reputation_cache = {}
                    async def reputation(author):
                        if not item.fetch_author_reputation or author is None:
                            return None
                        name = str(author)
                        if name in reputation_cache:
                            return reputation_cache[name]
                        try:
                            await author.load()
                            value = int(getattr(author, "link_karma", 0)) + int(getattr(author, "comment_karma", 0))
                        except Exception:
                            value = None
                        reputation_cache[name] = value
                        return value
                    subreddit = await reddit.subreddit(item.subreddit)
                    async for submission in subreddit.search(item.query, sort="new", limit=item.limit):
                        def record(body, created, score, permalink, author_reputation):
                            url = "https://www.reddit.com" + permalink
                            return RawPost(source_platform="Reddit", source_url=url,
                                           thread_title=submission.title, post_body=body,
                                           timestamp=datetime.fromtimestamp(created, timezone.utc).isoformat(),
                                           score=score, author_reputation=author_reputation,
                                           source_record_id=source_record_id(url),
                                           target_platform=item.target_platform, collected_at=now(),
                                           region=item.region, country=item.country, credibility_weight=0.75)
                        records.append(record(submission.selftext, submission.created_utc, submission.score, submission.permalink, await reputation(getattr(submission, "author", None))))
                        if item.comment_limit:
                            await submission.comments.replace_more(limit=0)
                            for comment in submission.comments.list()[:item.comment_limit]:
                                records.append(record(comment.body, comment.created_utc, comment.score, comment.permalink, await reputation(getattr(comment, "author", None))))
                    return records
            results = await asyncio.gather(*(reddit_job(r) for r in config.reddit), return_exceptions=True)
            for item, result in zip(config.reddit, results):
                if isinstance(result, Exception):
                    errors.append({"subreddit": item.subreddit, "status": "collection_failed", "reason": type(result).__name__})
                else:
                    posts.extend(result)
    return posts, errors
