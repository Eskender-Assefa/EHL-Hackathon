"""Real Chromium + rendered HTML + HTTP-mocked LLM integration smoke test."""
import asyncio
import json
from pathlib import Path

import httpx
from playwright.async_api import async_playwright
from bmw_signals.collectors import PageConfig, extract
from bmw_signals.pipeline import LLMEvaluator, process


async def main():
    url = "https://www.bimmerpost.com/test-fixture"
    html = '<h1>G60 impressions</h1><article><time datetime="2026-10-01T10:00:00Z"></time><div class="body" id="text"></div><script>document.getElementById("text").textContent = "The seats are comfortable, but the touch screen menu is terrible.";</script></article>'
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        async def serve(route):
            await route.fulfill(status=200, content_type="text/html", body=html)
        await context.route("**/*", serve)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_selector(".body")
        config = PageConfig(source_platform="BIMMERPOST", url=url, target_platform="G60", post_selector="article", body_selector=".body")
        posts = extract(await page.content(), config, page.url)
        await context.close()
        await browser.close()
    response = {"is_noise": False, "reason": "mixed aspects", "aspects": [
        {"taxonomy_category": "C05", "cleaned_verbatim_text": "The seats are comfortable"},
        {"taxonomy_category": "C07", "cleaned_verbatim_text": "the touch screen menu is terrible"}]}
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(response)}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        signals, audit = await process(posts, LLMEvaluator(client, "https://mock.example/chat", "fixture", "fixture"))
    assert len(posts) == 1 and len(signals) == 2
    assert [s.taxonomy_category for s in signals] == ["C05", "C07"]
    directory = Path("output/browser-smoke")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "signals.json").write_text(json.dumps([s.model_dump() for s in signals], indent=2), encoding="utf-8")
    print(json.dumps({"browser": "real headless Chromium", "source": "intercepted synthetic HTML with JavaScript-rendered body", "llm": "mock HTTP response", "raw_posts": len(posts), "signals": len(signals), "categories": [s.taxonomy_category for s in signals], "audit": audit}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
