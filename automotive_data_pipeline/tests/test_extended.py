import asyncio
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from pydantic import ValidationError

from bmw_signals.cli import run
from bmw_signals.collectors import CollectionConfig, PageConfig, check_url, collect, extract
from bmw_signals.models import Evaluation, FilteredSignal
from bmw_signals.pipeline import LLMEvaluator, process
from test_pipeline import Fake, post


class SchemaTests(unittest.TestCase):
    def signal(self, **updates):
        return dict(signal_id="abc123", source_platform="Reddit", source_url="https://example.com",
                    timestamp="2026-10-01T12:00:00Z", target_platform="G60", taxonomy_category="C01",
                    cleaned_verbatim_text="Acceleration feels strong") | updates

    def test_all_categories_platforms_sources(self):
        for category in [f"C{i:02}" for i in range(1, 11)]:
            for platform in ["F70", "G60", "G70", "Neue_Klasse"]:
                for source in ["Reddit", "BIMMERPOST", "Bimmerforums", "German_Car_Forum", "Competitor_Web"]:
                    FilteredSignal(**self.signal(taxonomy_category=category, target_platform=platform, source_platform=source))

    def test_invalid_fields(self):
        for changes in [dict(signal_id="has-dashes"), dict(timestamp="yesterday"),
                        dict(timestamp="2026-10-01T12:00:00"), dict(target_platform="G80"),
                        dict(taxonomy_category="C11"), dict(source_platform="Twitter"),
                        dict(cleaned_verbatim_text=""), dict(unexpected=True)]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                FilteredSignal(**self.signal(**changes))

    def test_inconsistent_evaluation(self):
        for data in [dict(is_noise=False, reason="", aspects=[]),
                     dict(is_noise=True, reason="", aspects=[dict(taxonomy_category="C01", cleaned_verbatim_text="text")])]:
            with self.assertRaises(ValidationError):
                Evaluation(**data)


class ExtractionTests(unittest.TestCase):
    def config(self, **updates):
        return PageConfig(**(dict(source_platform="BIMMERPOST", url="https://www.bimmerpost.com/thread",
                                  post_selector="article", body_selector=".body") | updates))

    def test_allowlist(self):
        for source, url in [("BIMMERPOST", "https://f70.bimmerpost.com/a"),
                            ("Bimmerforums", "https://www.bimmerforums.com/a"),
                            ("German_Car_Forum", "https://germancarforum.com/a"),
                            ("Competitor_Web", "https://www.byd.com/a"),
                            ("Competitor_Web", "https://www.mercedes-benz.com/a")]:
            check_url(url, source)

    def test_reject_unrelated_hosts(self):
        for url in ["http://bimmerpost.com/a", "https://bimmerpost.com.evil.example/a", "https://evilbimmerpost.com/a", "file:///a"]:
            with self.assertRaises(ValueError):
                check_url(url, "BIMMERPOST")

    def test_missing_invalid_naive_timestamp(self):
        for time in ["", '<time datetime="invalid"></time>', '<time datetime="2026-10-01T12:00:00"></time>']:
            raw = extract(f'<article>{time}<div class="body">Useful text</div></article>', self.config(), self.config().url)[0]
            self.assertIsNone(raw.timestamp)

    def test_explicit_timezone(self):
        config = self.config(timestamp_timezone="UTC")
        raw = extract('<article><time datetime="2026-10-01T12:00:00"></time><div class="body">Text</div></article>', config, config.url)[0]
        self.assertEqual(raw.timestamp, "2026-10-01T12:00:00+00:00")

    def test_formatted_timestamp(self):
        config = self.config(timestamp_attribute=None, timestamp_format="%d/%m/%Y %H:%M %z")
        raw = extract('<article><time>01/10/2026 12:00 +0200</time><div class="body">Text</div></article>', config, config.url)[0]
        self.assertEqual(raw.timestamp, "2026-10-01T12:00:00+02:00")

    def test_multiple_posts_noise_score_and_missing_body(self):
        config = self.config(score_selector=".score")
        html = '<article><div class="body">First<script>bad</script><style>bad</style><nav>bad</nav><footer>bad</footer><span class="signature">bad</span></div><span class="score">1,234</span></article><article><div class="body">Second</div><span class="score">unknown</span></article><article>No body</article>'
        records = extract(html, config, config.url)
        self.assertEqual([r.post_body for r in records], ["First", "Second"])
        self.assertEqual([r.score for r in records], [1234, None])

    def test_empty_extraction(self):
        with self.assertRaises(ValueError):
            extract("<html></html>", self.config(), self.config().url)

    def test_competitor_context(self):
        config = self.config(source_platform="Competitor_Web", url="https://www.byd.com/news", target_platform="Neue_Klasse", benchmark_context="BYD charging comparison")
        raw = extract('<article><div class="body">Charging announcement</div></article>', config, config.url)[0]
        self.assertEqual(raw.benchmark_context, "BYD charging comparison")
        self.assertEqual(raw.target_platform, "Neue_Klasse")


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, responses):
        calls = []
        def handler(request):
            calls.append(json.loads(request.content))
            response = responses[min(len(calls)-1, len(responses)-1)]
            return httpx.Response(response[0], json=response[1])
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            evaluator = LLMEvaluator(client, "https://llm.example/completions", "test-key", "test-model")
            with patch("bmw_signals.pipeline.asyncio.sleep", new_callable=AsyncMock):
                try:
                    result = await evaluator.evaluate(post())
                    return result, calls, None
                except Exception as exc:
                    return None, calls, exc

    def good(self):
        return (200, {"choices": [{"message": {"content": json.dumps(dict(is_noise=False, reason="", aspects=[dict(taxonomy_category="C05", cleaned_verbatim_text="The seats are comfortable")]))}}]})

    async def test_valid_request_and_response(self):
        result, calls, error = await self.invoke([self.good()])
        self.assertIsNone(error)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.aspects[0].taxonomy_category, "C05")
        self.assertEqual(calls[0]["response_format"], {"type": "json_object"})
        self.assertEqual(json.loads(calls[0]["messages"][1]["content"])["post_body"], post().post_body)

    async def test_429_retry(self):
        result, calls, error = await self.invoke([(429, {}), self.good()])
        self.assertIsNone(error)
        self.assertEqual(len(calls), 2)

    async def test_500_exhaustion(self):
        result, calls, error = await self.invoke([(500, {})])
        self.assertIsInstance(error, httpx.HTTPStatusError)
        self.assertEqual(len(calls), 3)

    async def test_401_no_retry(self):
        result, calls, error = await self.invoke([(401, {})])
        self.assertIsInstance(error, httpx.HTTPStatusError)
        self.assertEqual(len(calls), 1)

    async def test_malformed_json_retry(self):
        bad = (200, {"choices": [{"message": {"content": "not-json"}}]})
        result, calls, error = await self.invoke([bad, self.good()])
        self.assertIsNone(error)
        self.assertEqual(len(calls), 2)

    async def test_missing_choices_exhaustion(self):
        result, calls, error = await self.invoke([(200, {})])
        self.assertIsInstance(error, KeyError)
        self.assertEqual(len(calls), 3)


class ProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_input(self):
        self.assertEqual(await process([], Fake()), ([], []))

    async def test_removed_and_empty(self):
        for body in ["", "   ", "[deleted]", "[removed]"]:
            signals, audit = await process([post(post_body=body)], Fake())
            self.assertFalse(signals)
            self.assertEqual(audit[0]["reason"], "empty or removed")

    async def test_whitespace_case_duplicate(self):
        signals, audit = await process([post(), post(post_body="  " + post().post_body.upper().replace(" ", "  "))], Fake())
        self.assertEqual(audit[1]["reason"], "duplicate")

    async def test_duplicate_aspects(self):
        aspect = dict(taxonomy_category="C05", cleaned_verbatim_text="The seats are comfortable")
        signals, audit = await process([post()], Fake([aspect, aspect]))
        self.assertEqual(len(signals), 1)

    async def test_invalid_timestamp_quarantine(self):
        signals, audit = await process([post(timestamp="invalid")], Fake([dict(taxonomy_category="C05", cleaned_verbatim_text="The seats are comfortable")]))
        self.assertFalse(signals)
        self.assertEqual(audit[0]["reason"], "ValidationError")

    async def test_concurrency_limit(self):
        class Counting:
            active = 0
            peak = 0
            async def evaluate(self, raw):
                self.active += 1
                self.peak = max(self.peak, self.active)
                await asyncio.sleep(0.001)
                self.active -= 1
                return Evaluation(is_noise=True, reason="fixture", aspects=[])
        evaluator = Counting()
        await process([post(post_body=f"Unique text {i}") for i in range(12)], evaluator, concurrency=3)
        self.assertEqual(evaluator.peak, 3)

    async def test_empty_collection(self):
        self.assertEqual(await collect(CollectionConfig()), ([], []))


class CLITests(unittest.IsolatedAsyncioTestCase):
    async def test_process_outputs_and_quarantine_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "raw.json").write_text(json.dumps([post().model_dump(), post(post_body="Other", timestamp=None).model_dump()]))
            fake = Fake([dict(taxonomy_category="C05", cleaned_verbatim_text="The seats are comfortable")])
            with patch.dict(os.environ, {"LLM_ENDPOINT": "https://example.com", "LLM_API_KEY": "test", "LLM_MODEL": "test"}), patch("bmw_signals.cli.LLMEvaluator", return_value=fake):
                failed = await run(Namespace(command="process", input=str(path / "raw.json"), output=str(path / "out")))
            self.assertTrue(failed)
            signals = json.loads((path / "out/signals.json").read_text())
            audit = json.loads((path / "out/processing_audit.json").read_text())
            self.assertEqual(len(signals), 1)
            self.assertEqual([r["status"] for r in audit], ["accepted", "quarantined"])
            FilteredSignal.model_validate(signals[0])

    async def test_collect_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "config.json").write_text("{}")
            failed = await run(Namespace(command="collect", config=str(path / "config.json"), output=str(path / "out")))
            self.assertFalse(failed)
            self.assertEqual(json.loads((path / "out/raw.json").read_text()), [])
            self.assertEqual(json.loads((path / "out/collection_audit.json").read_text()), [])
