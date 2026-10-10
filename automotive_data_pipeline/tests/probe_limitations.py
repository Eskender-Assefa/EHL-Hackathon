"""Diagnostic probes: prints observed behavior, including known limitations."""
import asyncio
import json
from bmw_signals.models import FilteredSignal
from bmw_signals.pipeline import process
from test_pipeline import Fake, post


async def main():
    aspect = dict(taxonomy_category="C05", cleaned_verbatim_text="The seats are comfortable")
    fake = Fake([aspect])
    signals, audit = await process([post(timestamp=None), post()], fake)
    print("missing_metadata_then_valid_duplicate:", json.dumps({"signals": len(signals), "statuses": [a["status"] for a in audit], "reasons": [a.get("reason") for a in audit]}))
    signals, audit = await process([post(target_platform="G60"), post(target_platform="G70")], fake)
    print("same_body_different_platform:", json.dumps({"platforms_retained": [s.target_platform for s in signals], "statuses": [a["status"] for a in audit]}))
    short = post(post_body="This car sucks")
    signals, audit = await process([short], Fake([dict(taxonomy_category="C10", cleaned_verbatim_text=short.post_body)]))
    print("model_accepts_short_complaint:", json.dumps({"signals": len(signals), "status": audit[0]["status"]}))
    signal = FilteredSignal(signal_id="abc", source_platform="Reddit", source_url="not-a-url", timestamp="2026-10-01T00:00:00Z", target_platform="G60", taxonomy_category="C05", cleaned_verbatim_text=" ", is_noise="false")
    print("weak_schema_inputs:", json.dumps(signal.model_dump()))


if __name__ == "__main__":
    asyncio.run(main())
