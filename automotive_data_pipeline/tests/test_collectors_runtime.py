import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch
from bmw_signals.collectors import CollectionConfig, PageConfig, RedditConfig, collect


class Manager:
    def __init__(self, value):
        self.value = value
    async def __aenter__(self):
        return self.value
    async def __aexit__(self, *args):
        pass


class CollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_success_and_failure_cleanup(self):
        html = '<article><time datetime="2026-10-01T00:00:00Z"></time><div class="body">Seats are comfortable</div></article>'
        good = types.SimpleNamespace(url="https://www.bimmerpost.com/thread", goto=AsyncMock(return_value=types.SimpleNamespace(status=200)),
                                     wait_for_selector=AsyncMock(), content=AsyncMock(return_value=html), close=AsyncMock())
        bad = types.SimpleNamespace(goto=AsyncMock(return_value=types.SimpleNamespace(status=403)), close=AsyncMock())
        context = types.SimpleNamespace(new_page=AsyncMock(side_effect=[good, bad]), close=AsyncMock())
        browser = types.SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
        chromium = types.SimpleNamespace(launch=AsyncMock(return_value=browser))
        module = types.ModuleType("playwright.async_api")
        module.async_playwright = lambda: Manager(types.SimpleNamespace(chromium=chromium))
        parent = types.ModuleType("playwright")
        pages = [PageConfig(source_platform="BIMMERPOST", url="https://www.bimmerpost.com/thread", target_platform="F70", post_selector="article", body_selector=".body"),
                 PageConfig(source_platform="Bimmerforums", url="https://www.bimmerforums.com/thread", post_selector="article", body_selector=".body")]
        with patch.dict(sys.modules, {"playwright": parent, "playwright.async_api": module}):
            posts, errors = await collect(CollectionConfig(pages=pages, concurrency=1))
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].target_platform, "F70")
        self.assertEqual(errors, [{"source_url": pages[1].url, "status": "collection_failed", "reason": "ValueError"}])
        for obj in [good, bad, context, browser]:
            obj.close.assert_awaited_once()

    async def test_reddit_submission_comments_and_limits(self):
        comment = types.SimpleNamespace(body="The charging is fast", created_utc=1790812800, score=5, permalink="/r/BMW/comments/a/b")
        comments = types.SimpleNamespace(replace_more=AsyncMock(), list=lambda: [comment, comment])
        submission = types.SimpleNamespace(title="G60", selftext="The seats are comfortable", created_utc=1790812800, score=10, permalink="/r/BMW/comments/a", comments=comments)
        async def search(*args, **kwargs):
            yield submission
        reddit = types.SimpleNamespace(subreddit=AsyncMock(return_value=types.SimpleNamespace(search=search)))
        module = types.ModuleType("asyncpraw")
        module.Reddit = lambda **kwargs: Manager(reddit)
        with patch.dict(sys.modules, {"asyncpraw": module}), patch.dict(os.environ, {"REDDIT_CLIENT_ID": "fixture", "REDDIT_CLIENT_SECRET": "fixture", "REDDIT_USER_AGENT": "fixture"}):
            posts, errors = await collect(CollectionConfig(reddit=[RedditConfig(subreddit="BMW", query="G60", target_platform="G60", comment_limit=1)]))
        self.assertFalse(errors)
        self.assertEqual(len(posts), 2)
        self.assertEqual([p.score for p in posts], [10, 5])
        self.assertEqual(posts[1].source_url, "https://www.reddit.com/r/BMW/comments/a/b")
        self.assertEqual(posts[1].timestamp, "2026-10-01T00:00:00+00:00")
        comments.replace_more.assert_awaited_once_with(limit=0)

    async def test_reddit_source_failure_audit(self):
        module = types.ModuleType("asyncpraw")
        module.Reddit = lambda **kwargs: Manager(types.SimpleNamespace(subreddit=AsyncMock(side_effect=RuntimeError("fixture"))))
        with patch.dict(sys.modules, {"asyncpraw": module}), patch.dict(os.environ, {"REDDIT_CLIENT_ID": "fixture", "REDDIT_CLIENT_SECRET": "fixture", "REDDIT_USER_AGENT": "fixture"}):
            posts, errors = await collect(CollectionConfig(reddit=[RedditConfig(subreddit="BMW", query="G60", target_platform="G60")]))
        self.assertFalse(posts)
        self.assertEqual(errors, [{"subreddit": "BMW", "status": "collection_failed", "reason": "RuntimeError"}])

    async def test_missing_reddit_credentials_are_audited_without_crashing(self):
        with patch.dict(os.environ, {}, clear=True):
            posts, errors = await collect(CollectionConfig(reddit=[RedditConfig(subreddit="BMW", query="G60", target_platform="G60")]))
        self.assertFalse(posts)
        self.assertEqual(errors[0]["status"], "collection_skipped")
        self.assertEqual(errors[0]["reason"], "MissingCredentials")
