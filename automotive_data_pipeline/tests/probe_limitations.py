"""Diagnostic probes for prior regressions and honest missing-data behavior."""
import asyncio
import json
from bmw_signals.pipeline import RuleBasedEvaluator, process
from test_pipeline import post


async def main():
    evaluator = RuleBasedEvaluator()
    signals, audit = await process([post(timestamp=None, source_record_id="same"), post(source_record_id="same")], evaluator)
    print("invalid_then_valid_record:", json.dumps({"signals": len(signals), "statuses": [a["status"] for a in audit], "reasons": [a.get("reason") for a in audit]}))
    signals, audit = await process([post(target_platform="G60", source_record_id="same"), post(target_platform="G70", source_record_id="same")], evaluator)
    print("same_body_different_platform:", json.dumps({"platforms_retained": [s.target_platform for s in signals], "statuses": [a["status"] for a in audit]}))
    short = post(post_body="This car sucks")
    signals, audit = await process([short], evaluator)
    print("short_complaint:", json.dumps({"signals": len(signals), "status": audit[0]["status"], "reason": audit[0].get("reason")}))


if __name__ == "__main__":
    asyncio.run(main())
