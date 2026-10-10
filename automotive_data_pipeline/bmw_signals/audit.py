from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()
GENESIS = "0" * 64


def _canonical(event: dict) -> bytes:
    return json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_audit(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    events = []
    previous_hash = GENESIS
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            event = json.loads(line)
            supplied_hash = event.pop("event_hash", None)
            if event.get("previous_hash") != previous_hash:
                raise ValueError(f"Audit chain broken at line {line_number}: previous hash mismatch")
            calculated = hashlib.sha256(_canonical(event)).hexdigest()
            if supplied_hash != calculated:
                raise ValueError(f"Audit chain broken at line {line_number}: event hash mismatch")
            event["event_hash"] = supplied_hash
            events.append(event)
            previous_hash = supplied_hash
    return events


def append_event(path: str | Path, *, actor: str, requirement_id: str, action: str,
                 field_changed: str, previous_value, new_value, justification: str) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        events = verify_audit(path)
        event = {
            "sequence": len(events) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor.strip(), "requirement_id": requirement_id,
            "action": action, "field_changed": field_changed,
            "previous_value": previous_value, "new_value": new_value,
            "justification": justification.strip(),
            "previous_hash": events[-1]["event_hash"] if events else GENESIS,
        }
        event["event_hash"] = hashlib.sha256(_canonical(event)).hexdigest()
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event
