import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx

from .audit import append_event, verify_audit
from .collectors import CollectionConfig, collect
from .deck import export_deck
from .local_ingestion import ingest_local_materials, ingest_structured_context
from .models import FilteredSignal, RawPost, RequirementCandidate
from .pipeline import LLMEvaluator, RuleBasedEvaluator, process
from .requirements import build_requirements, load_scoring_inputs


def write(path, records):
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_raw_files(paths) -> list[RawPost]:
    records = []
    for path in paths or []:
        records.extend(RawPost.model_validate(item) for item in json.loads(Path(path).read_text(encoding="utf-8-sig")))
    return records


async def _process_records(posts, engine):
    if engine == "rules":
        return await process(posts, RuleBasedEvaluator())
    async with httpx.AsyncClient(timeout=90) as client:
        evaluator = LLMEvaluator(client, os.environ["LLM_ENDPOINT"], os.environ["LLM_API_KEY"], os.environ["LLM_MODEL"])
        return await process(posts, evaluator)


def _write_requirements(directory: Path, signals: list[FilteredSignal], inputs_path=None):
    requirements, baseline = build_requirements(signals, load_scoring_inputs(inputs_path))
    requirements_path = directory / "requirements.json"
    previous = {}
    if requirements_path.exists():
        previous = {item.requirement_id: item for item in (
            RequirementCandidate.model_validate(value)
            for value in json.loads(requirements_path.read_text(encoding="utf-8"))
        )}
    for item in requirements:
        if item.requirement_id in previous:
            item.status = previous[item.requirement_id].status
            item.pm_rationale = previous[item.requirement_id].pm_rationale
    write(requirements_path, [item.model_dump() for item in requirements])
    write(directory / "fixed_baseline_signals.json", [item.model_dump() for item in baseline])
    audit_path = directory / "audit.jsonl"
    verify_audit(audit_path)
    for item in requirements:
        prior = previous.get(item.requirement_id)
        if prior is None or prior.model_dump() != item.model_dump():
            append_event(
                audit_path, actor="AI Pipeline", requirement_id=item.requirement_id,
                action="Propose" if prior is None else "Recompute", field_changed="requirement",
                previous_value=prior.model_dump() if prior else None, new_value=item.model_dump(),
                justification="Generated from evidence-linked signals" if prior is None else "Deterministic recomputation after source or formula change",
            )
    return requirements


async def run(args):
    directory = Path(getattr(args, "output", Path(getattr(args, "destination", "output/result")).parent))
    directory.mkdir(parents=True, exist_ok=True)
    if args.command == "collect":
        config = CollectionConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8-sig"))
        posts, audit = await collect(config)
        write(directory / "raw.json", [post.model_dump() for post in posts])
        write(directory / "collection_audit.json", audit)
        return bool(audit)
    if args.command == "ingest-local":
        posts, manifest = ingest_local_materials(args.material_dir)
        write(directory / "raw.json", [post.model_dump() for post in posts])
        write(directory / "source_manifest.json", manifest)
        write(directory / "structured_context.json", ingest_structured_context(args.material_dir))
        return False
    if args.command == "process":
        posts = [RawPost.model_validate(item) for item in json.loads(Path(args.input).read_text(encoding="utf-8-sig"))]
        signals, audit = await _process_records(posts, getattr(args, "engine", "llm"))
        write(directory / "signals.json", [signal.model_dump() for signal in signals])
        write(directory / "processing_audit.json", audit)
        return any(record["status"] == "quarantined" for record in audit)
    if args.command == "build-requirements":
        signals = [FilteredSignal.model_validate(item) for item in json.loads(Path(args.signals).read_text(encoding="utf-8-sig"))]
        _write_requirements(directory, signals, args.scoring_inputs)
        return False
    if args.command in {"run-local", "run-all"}:
        posts, manifest = ingest_local_materials(args.material_dir)
        collection_audit = []
        if args.command == "run-all":
            external_posts = _load_raw_files(args.external_raw)
            if args.config:
                config = CollectionConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8-sig"))
                collected, collection_audit = await collect(config)
                external_posts.extend(collected)
            if not args.config and not args.external_raw:
                raise ValueError("run-all requires --config and/or --external-raw")
            posts.extend(external_posts)
            by_source = {}
            for post in external_posts:
                by_source[post.source_platform] = by_source.get(post.source_platform, 0) + 1
            manifest.append({"kind": "ExternalCollection", "records": len(external_posts), "records_by_source": by_source})
            write(directory / "collection_audit.json", collection_audit)
        write(directory / "raw.json", [post.model_dump() for post in posts])
        write(directory / "source_manifest.json", manifest)
        write(directory / "structured_context.json", ingest_structured_context(args.material_dir))
        signals, audit = await _process_records(posts, args.engine)
        write(directory / "signals.json", [signal.model_dump() for signal in signals])
        write(directory / "processing_audit.json", audit)
        _write_requirements(directory, signals, args.scoring_inputs)
        return bool(collection_audit) or any(record["status"] == "quarantined" for record in audit)
    if args.command == "export-deck":
        requirements = [RequirementCandidate.model_validate(item) for item in json.loads(Path(args.requirements).read_text(encoding="utf-8-sig"))]
        export_deck(requirements, args.destination)
        return False
    raise ValueError(f"Unsupported command {args.command}")


def main():
    parser = argparse.ArgumentParser(description="Build evidence-linked BMW product requirements")
    sub = parser.add_subparsers(dest="command", required=True)
    collection = sub.add_parser("collect", help="Collect configured web and Reddit sources")
    collection.add_argument("--config", required=True)
    local = sub.add_parser("ingest-local", help="Ingest supplied Feedback_Explorer workbooks and OptionLists")
    local.add_argument("--material-dir", default="../material")
    processing = sub.add_parser("process", help="Split and classify raw records")
    processing.add_argument("--input", required=True)
    processing.add_argument("--engine", choices=("llm", "rules"), default="llm")
    requirements = sub.add_parser("build-requirements", help="Aggregate signals into scored requirement candidates")
    requirements.add_argument("--signals", required=True)
    requirements.add_argument("--scoring-inputs")
    complete = sub.add_parser("run-local", help="Run local ingestion, deterministic processing, and requirement aggregation")
    complete.add_argument("--material-dir", default="../material")
    complete.add_argument("--engine", choices=("llm", "rules"), default="rules")
    complete.add_argument("--scoring-inputs")
    all_sources = sub.add_parser("run-all", help="Combine BMW files with collected or previously saved external sources")
    all_sources.add_argument("--material-dir", default="../material")
    all_sources.add_argument("--config", help="Live Reddit/web collection configuration")
    all_sources.add_argument("--external-raw", action="append", default=[], help="Previously collected raw.json; repeat for multiple files")
    all_sources.add_argument("--engine", choices=("llm", "rules"), default="rules")
    all_sources.add_argument("--scoring-inputs")
    deck = sub.add_parser("export-deck", help="Generate an executive PowerPoint")
    deck.add_argument("--requirements", required=True)
    deck.add_argument("--destination", default="output/BMW_requirements_board_deck.pptx")
    serve = sub.add_parser("serve", help="Run the PM cockpit API")
    serve.add_argument("--data-dir", default="output")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    for command in (collection, local, processing, requirements, complete, all_sources):
        command.add_argument("--output", default="output")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        from .cockpit import create_app
        uvicorn.run(create_app(args.data_dir), host=args.host, port=args.port, workers=1)
        return
    raise SystemExit(int(asyncio.run(run(args))))


if __name__ == "__main__":
    main()
