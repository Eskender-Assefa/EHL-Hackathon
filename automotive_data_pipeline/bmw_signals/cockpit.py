from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .audit import append_event, verify_audit
from .deck import export_deck
from .models import FilteredSignal, RequirementCandidate, ScoringInputs
from .requirements import build_requirements, scoring_key
from .synthetic import generate_neue_klasse_scenario


class Decision(BaseModel):
    actor: str = Field(min_length=1)
    action: str
    justification: str = ""
    edited_requirement_statement: str | None = None


class TriggerRequest(BaseModel):
    actor: str = Field(min_length=1)
    seed: int = 42
    justification: str = Field(min_length=1)


def _load_requirements(path: Path) -> list[RequirementCandidate]:
    if not path.exists():
        return []
    return [RequirementCandidate.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def _save_requirements(path: Path, requirements: list[RequirementCandidate]):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps([item.model_dump() for item in requirements], ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def create_app(data_dir: str | Path = "output") -> FastAPI:
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    requirements_path = directory / "requirements.json"
    audit_path = directory / "audit.jsonl"
    app = FastAPI(title="BMW PM Cockpit API", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
    )

    @app.get("/api/requirements")
    def requirements():
        return [item.model_dump() for item in _load_requirements(requirements_path)]

    @app.post("/api/requirements/{requirement_id}/decision")
    def decide(requirement_id: str, decision: Decision):
        allowed = {"Approve": "Approved", "Edit": "Edited", "Reject": "Rejected", "Postpone": "Postponed"}
        if decision.action not in allowed:
            raise HTTPException(400, "action must be Approve, Edit, Reject, or Postpone")
        if decision.action != "Approve" and not decision.justification.strip():
            raise HTTPException(400, "justification is mandatory for Edit, Reject, and Postpone")
        if decision.action == "Edit" and not (decision.edited_requirement_statement or "").strip():
            raise HTTPException(400, "edited_requirement_statement is mandatory for Edit")
        items = _load_requirements(requirements_path)
        target = next((item for item in items if item.requirement_id == requirement_id), None)
        if target is None:
            raise HTTPException(404, "requirement not found")
        verify_audit(audit_path)
        previous = target.model_dump()
        target.status = allowed[decision.action]
        target.pm_rationale = decision.justification.strip() or None
        if decision.action == "Edit":
            target.requirement_statement = decision.edited_requirement_statement.strip()
        _save_requirements(requirements_path, items)
        event = append_event(
            audit_path, actor=decision.actor, requirement_id=requirement_id,
            action=decision.action, field_changed="requirement",
            previous_value=previous, new_value=target.model_dump(),
            justification=decision.justification or "Approved without override",
        )
        return {"requirement": target.model_dump(), "audit_event": event}

    @app.get("/api/audit/verify")
    def verify():
        events = verify_audit(audit_path)
        return {"valid": True, "events": len(events), "last_hash": events[-1]["event_hash"] if events else None}

    @app.post("/api/trigger-synthetic")
    def trigger(request: TriggerRequest, background_tasks: BackgroundTasks):
        items = _load_requirements(requirements_path)
        def generate():
            signals_path = directory / "signals.json"
            observed = [FilteredSignal.model_validate(item) for item in json.loads(signals_path.read_text(encoding="utf-8"))] if signals_path.exists() else []
            synthetic_signals = generate_neue_klasse_scenario(request.seed)
            write_signals = [item.model_dump() for item in synthetic_signals]
            (directory / "synthetic_signals.json").write_text(json.dumps(write_signals, indent=2), encoding="utf-8")
            draft, _ = build_requirements(observed + synthetic_signals)
            scenarios = {}
            for item in draft:
                key = scoring_key(item.target_platform, item.taxonomy_category, item.topic)
                digest = int(hashlib.sha256(f"{request.seed}|{key}".encode()).hexdigest()[:8], 16)
                scenarios[key] = {
                    "sales_causality_score": round((digest % 3001) / 100, 2),
                    "competitor_roi_score": round(((digest // 3001) % 2501) / 100, 2),
                    "effort_class": item.effort_class,
                    "assumptions": ["Deterministic synthetic scenario; not observed market evidence."],
                    "synthetic": True,
                }
            (directory / "synthetic_scoring_inputs.json").write_text(json.dumps(scenarios, indent=2), encoding="utf-8")
            scored, _ = build_requirements(observed + synthetic_signals, {key: ScoringInputs.model_validate(value) for key, value in scenarios.items()})
            prior = {item.requirement_id: item for item in items}
            for item in scored:
                if item.requirement_id in prior:
                    item.status = prior[item.requirement_id].status
                    item.pm_rationale = prior[item.requirement_id].pm_rationale
            _save_requirements(requirements_path, scored)
            for item in scored:
                previous = prior.get(item.requirement_id)
                if previous is None or previous.model_dump() != item.model_dump():
                    append_event(
                        audit_path, actor="Synthetic Scenario Node", requirement_id=item.requirement_id,
                        action="Propose" if previous is None else "Recompute", field_changed="requirement",
                        previous_value=previous.model_dump() if previous else None,
                        new_value=item.model_dump(),
                        justification="Manual hypothetical scenario refresh; not observed evidence.",
                    )
        background_tasks.add_task(generate)
        event = append_event(
            audit_path, actor=request.actor, requirement_id="SYSTEM", action="TriggerSyntheticIngestion",
            field_changed="synthetic_scoring_inputs", previous_value=None,
            new_value={"seed": request.seed, "timestamp": datetime.now(timezone.utc).isoformat()},
            justification=request.justification,
        )
        return {"status": "accepted", "warning": "Output is a hypothetical scenario, not observed evidence.", "audit_event": event}

    @app.get("/api/export-deck")
    def deck():
        destination = export_deck(_load_requirements(requirements_path), directory / "BMW_requirements_board_deck.pptx")
        return FileResponse(destination, filename=destination.name)

    return app


app = create_app()
