import argparse
import asyncio
import json
import os
from pathlib import Path
import httpx
from .collectors import CollectionConfig, collect
from .models import RawPost
from .pipeline import LLMEvaluator, process


def write(path, records):
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


async def run(args):
    directory = Path(args.output)
    directory.mkdir(parents=True, exist_ok=True)
    if args.command == "collect":
        config = CollectionConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8"))
        posts, audit = await collect(config)
        write(directory / "raw.json", [p.model_dump() for p in posts])
        write(directory / "collection_audit.json", audit)
        return bool(audit)
    posts = [RawPost.model_validate(p) for p in json.loads(Path(args.input).read_text(encoding="utf-8"))]
    async with httpx.AsyncClient(timeout=90) as client:
        evaluator = LLMEvaluator(client, os.environ["LLM_ENDPOINT"], os.environ["LLM_API_KEY"], os.environ["LLM_MODEL"])
        signals, audit = await process(posts, evaluator)
    write(directory / "signals.json", [s.model_dump() for s in signals])
    write(directory / "processing_audit.json", audit)
    return any(r["status"] == "quarantined" for r in audit)


def main():
    parser = argparse.ArgumentParser(description="Collect and classify BMW customer and competitor signals")
    sub = parser.add_subparsers(dest="command", required=True)
    collection = sub.add_parser("collect")
    collection.add_argument("--config", required=True)
    processing = sub.add_parser("process")
    processing.add_argument("--input", required=True)
    for command in (collection, processing):
        command.add_argument("--output", default="output")
    raise SystemExit(int(asyncio.run(run(parser.parse_args()))))


if __name__ == "__main__":
    main()
