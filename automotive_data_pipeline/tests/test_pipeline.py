import unittest
from bmw_signals.models import Evaluation, RawPost
from bmw_signals.pipeline import process
from bmw_signals.collectors import PageConfig, extract


def post(**changes):
    data = dict(source_platform="Reddit", source_url="https://www.reddit.com/r/BMW/comments/example",
                thread_title="G60", post_body="The seats are comfortable, but the touch screen menu is terrible.",
                timestamp="2026-10-01T10:00:00Z", target_platform="G60", collected_at="2026-10-10T10:00:00Z")
    return RawPost(**(data | changes))


class Fake:
    def __init__(self, aspects=None):
        self.aspects = aspects
        self.calls = 0

    async def evaluate(self, raw):
        self.calls += 1
        return Evaluation.model_validate(dict(is_noise=self.aspects is None, reason="fixture", aspects=self.aspects or []))


class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_split_duplicate_and_stable_ids(self):
        fake = Fake([dict(taxonomy_category="C05", cleaned_verbatim_text="The seats are comfortable"),
                     dict(taxonomy_category="C07", cleaned_verbatim_text="the touch screen menu is terrible")])
        signals, audit = await process([post(), post()], fake)
        self.assertEqual([s.taxonomy_category for s in signals], ["C05", "C07"])
        self.assertEqual(fake.calls, 1)
        self.assertEqual(audit[1]["reason"], "duplicate")
        again, _ = await process([post()], fake)
        self.assertEqual(signals, again)

    async def test_missing_metadata(self):
        fake = Fake()
        signals, audit = await process([post(timestamp=None)], fake)
        self.assertFalse(signals)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(audit[0]["status"], "quarantined")

    async def test_invalid_responses(self):
        for category, text in [("C11", "The seats are comfortable"), ("C05", "Invented")]:
            signals, audit = await process([post()], Fake([dict(taxonomy_category=category, cleaned_verbatim_text=text)]))
            self.assertFalse(signals)
            self.assertEqual(audit[0]["status"], "quarantined")

    async def test_noise(self):
        signals, audit = await process([post(post_body="This car sucks")], Fake())
        self.assertFalse(signals)
        self.assertEqual(audit[0]["status"], "discarded")

    def test_extraction(self):
        config = PageConfig(source_platform="BIMMERPOST", url="https://www.bimmerpost.com/thread",
                            post_selector="article", body_selector=".body", target_platform="F70",
                            score_selector=".score", permalink_selector="a")
        html = '<h1>F70</h1><article><time datetime="2026-10-01T10:00:00Z"></time><a href="/post/1">link</a><span class="score">12</span><div class="body">My seats feel good.<blockquote>Someone else</blockquote></div></article>'
        raw = extract(html, config, config.url)[0]
        self.assertEqual(raw.post_body, "My seats feel good.")
        self.assertEqual(raw.score, 12)
        self.assertEqual(raw.source_url, "https://www.bimmerpost.com/post/1")
        self.assertIsNotNone(raw.timestamp)
