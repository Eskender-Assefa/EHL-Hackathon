from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from .models import EvidenceRef, FilteredSignal


def generate_neue_klasse_scenario(seed: int, generated_at: datetime | None = None) -> list[FilteredSignal]:
    """Create an explicitly hypothetical EU/CN demo. It is never represented as observed evidence."""
    generated_at = generated_at or datetime.now(timezone.utc)
    rows = [
        ("EU", "C07", "Physical Controls", -82, "Touchscreen-only climate controls require too many glances while driving.", "Provide direct, low-distraction access to frequently used climate controls."),
        ("EU", "C07", "Physical Controls", -75, "Drivers want persistent physical or haptic shortcuts for core cabin functions.", "Provide direct, low-distraction access to frequently used climate controls."),
        ("CN", "C07", "Physical Controls", 72, "Customers value the integrated touchscreen workflow and customizable digital shortcuts.", "Preserve customizable digital shortcuts while validating distraction performance."),
        ("CN", "C07", "Physical Controls", 64, "The full digital control concept is perceived as modern and easy to personalize.", "Preserve customizable digital shortcuts while validating distraction performance."),
        ("EU", "C02", "Charging Speed", -78, "Winter motorway drivers report that charging predictability matters more than peak advertised speed.", "Deliver predictable fast-charging performance across European winter motorway use."),
        ("EU", "C02", "Charging Speed", -68, "Route planning should show reliable arrival state of charge and charger availability.", "Deliver predictable fast-charging performance across European winter motorway use."),
        ("CN", "C02", "Charging Speed", -74, "Urban customers expect rapid charging sessions to fit short high-frequency journeys.", "Deliver predictable rapid charging for high-frequency Chinese urban use."),
        ("CN", "C02", "Charging Speed", -70, "Charging speed consistency is more valuable than a single laboratory peak.", "Deliver predictable rapid charging for high-frequency Chinese urban use."),
    ]
    output = []
    for index, (region, category, topic, sentiment, text, requirement) in enumerate(rows, start=1):
        digest = hashlib.sha256(f"{seed}|{index}|{text}".encode()).hexdigest()
        timestamp = generated_at - timedelta(days=(int(digest[:4], 16) % 55))
        record_id = f"SYN{seed}{index}"
        uri = f"synthetic://showroom/{seed}"
        output.append(FilteredSignal(
            signal_id=digest[:24], source_platform="Synthetic", source_url=uri,
            timestamp=timestamp.isoformat(), target_platform="Neue_Klasse",
            taxonomy_category=category, cleaned_verbatim_text=text, sentiment_score=sentiment,
            confidence=0.25, topic=topic, requirement_statement=requirement,
            scope_layer="hypothetical_later", region=region, source_record_id=record_id,
            credibility_weight=0.35,
            evidence=[EvidenceRef(source_uri=uri, locator=f"scenario row {index}", record_id=record_id, quote=text)],
        ))
    return output
