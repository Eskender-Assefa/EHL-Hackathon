from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .models import FilteredSignal, RequirementCandidate, ScoringInputs
from .taxonomy import TAXONOMY

EFFORT_DEFAULTS = {
    "C01": ("body_platform", 50), "C02": ("electronics_thermal", 15),
    "C03": ("software_ux", 0), "C04": ("electronics_thermal", 15),
    "C05": ("interior_trim", 5), "C06": ("body_platform", 50),
    "C07": ("software_ux", 0), "C08": ("interior_trim", 5),
    "C09": ("electronics_thermal", 15), "C10": ("software_ux", 0),
}


def _topic_key(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", topic.casefold()).strip("_") or "general"


def scoring_key(platform: str, category: str, topic: str) -> str:
    return f"{platform}|{category}|{_topic_key(topic)}"


def load_scoring_inputs(path: str | Path | None) -> dict[str, ScoringInputs]:
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {key: ScoringInputs.model_validate(value) for key, value in data.items()}


def _velocity(signals: list[FilteredSignal]):
    dated = []
    for signal in signals:
        if signal.timestamp:
            dated.append(datetime.fromisoformat(signal.timestamp.replace("Z", "+00:00")))
    if not dated:
        return None, None, None, None
    anchor = max(dated)
    current_start = anchor - timedelta(days=29)
    previous_start = anchor - timedelta(days=59)
    current = sum(current_start <= value <= anchor for value in dated)
    previous = sum(previous_start <= value < current_start for value in dated)
    multiplier = min(3.0, 1.0 + math.log10(1.0 + current / max(previous, 1)))
    acceleration = None if previous == 0 else (current - previous) / previous * 100
    return current, previous, round(multiplier, 4), None if acceleration is None else round(acceleration, 2)


def _conflict(regional: dict[str, list[FilteredSignal]]) -> tuple[bool, float]:
    means = [sum(s.sentiment_score for s in group) / len(group) for group in regional.values() if len(group) >= 2]
    if len(means) < 2:
        return False, 0.0
    spread = max(means) - min(means)
    return spread >= 60, min(1.0, spread / 200)


def _unique_signals(signals: list[FilteredSignal]) -> list[FilteredSignal]:
    unique = {}
    for signal in signals:
        key = signal.source_record_id or signal.signal_id
        unique.setdefault(key, signal)
    return list(unique.values())


def build_requirements(signals: list[FilteredSignal], scoring_inputs: dict[str, ScoringInputs] | None = None, threshold=0.5):
    scoring_inputs = scoring_inputs or {}
    fixed_baseline = [signal for signal in signals if signal.scope_layer == "fixed_now"]
    candidates = [signal for signal in signals if signal.scope_layer != "fixed_now"]
    base_groups = defaultdict(list)
    for signal in candidates:
        base_groups[(signal.target_platform, signal.taxonomy_category, _topic_key(signal.topic))].append(signal)
    output = []
    for (platform, category, topic_key), group in sorted(base_groups.items()):
        group = _unique_signals(group)
        regional = defaultdict(list)
        for signal in group:
            regional[signal.region].append(signal)
        conflict, conflict_penalty = _conflict(regional)
        branches = regional.items() if conflict else [(next(iter(regional)) if len(regional) == 1 else "Unknown", group)]
        for region, branch in branches:
            branch = _unique_signals(branch)
            sentiment = sum(signal.sentiment_score for signal in branch) / len(branch)
            impact = sum(abs(signal.sentiment_score) / 100 for signal in branch) / len(branch)
            credibility = sum(signal.credibility_weight for signal in branch) / len(branch)
            signal_score = len(branch) * credibility * impact
            if signal_score < threshold:
                continue
            current, previous, velocity, acceleration = _velocity(branch)
            input_key = f"{platform}|{category}|{topic_key}"
            score_input = scoring_inputs.get(input_key)
            effort_class, effort_penalty = EFFORT_DEFAULTS[category]
            sales = score_input.sales_causality_score if score_input else None
            roi = score_input.competitor_roi_score if score_input else None
            if score_input:
                effort_class = score_input.effort_class
                effort_penalty = dict(software_ux=0, interior_trim=5, electronics_thermal=15, body_platform=50)[effort_class]
            pain = max(0.0, -sentiment) / 100
            urgency = pain * 100 * (velocity if velocity is not None else 1.0)
            partial = urgency + (sales or 0) + (roi or 0) - effort_penalty
            missing = []
            if velocity is None:
                missing.append("No dated observations; 30-day velocity is unknown.")
            if sales is None:
                missing.append("No validated synthetic sales take-rate causality score.")
            if roi is None:
                missing.append("No validated competitor two-year ROI score.")
            complete = not missing
            priority = round(partial, 2) if complete else None
            severe_safety = category == "C04" and any(signal.sentiment_score <= -80 for signal in branch)
            if severe_safety:
                band = "Critical review"
            elif priority is None:
                band = "Unscored"
            elif priority >= 85:
                band = "Critical review"
            elif priority >= 60:
                band = "High"
            elif priority >= 30:
                band = "Medium"
            else:
                band = "Low"
            groundedness = sum(signal.confidence for signal in branch) / len(branch)
            verbatims = sum(signal.source_platform not in {"Competitor_Web"} for signal in branch)
            competitors = sum(signal.source_platform == "Competitor_Web" for signal in branch)
            volume = min(1.0, (math.log1p(verbatims) + math.log1p(competitors)) / 5)
            ehi = max(0.0, min(100.0, (0.55 * groundedness + 0.45 * volume - 0.30 * conflict_penalty) * 100))
            confidence_label = "Verified Evidence" if ehi >= 80 and not conflict else "Medium Evidence" if ehi >= 50 and not conflict else "Uncertain / Conflict Flag"
            statements = [signal.requirement_statement for signal in branch if signal.requirement_statement]
            statement = Counter(statements).most_common(1)[0][0] if statements else f"Review {branch[0].topic.lower()} for {platform} customers."
            evidence_by_locator = {}
            for signal in branch:
                for evidence in signal.evidence:
                    evidence_by_locator[(evidence.source_uri, evidence.locator)] = evidence
            warnings = []
            if conflict:
                warnings.append("Cross-regional sentiment conflict detected; regional derivative branches generated.")
            if len(branch) < 5:
                warnings.append("Low evidence volume: fewer than five distinct feedback records.")
            if groundedness < 0.7:
                warnings.append("Groundedness is below 70%; human validation is required.")
            if score_input and score_input.synthetic:
                warnings.append("Priority uses synthetic causality/ROI scenario inputs, not observed outcomes.")
                warnings.extend(score_input.assumptions)
            title = f"{platform} {branch[0].topic}"
            identifier = hashlib.sha256(f"{platform}|{category}|{topic_key}|{region}".encode()).hexdigest()[:16].upper()
            output.append(RequirementCandidate(
                requirement_id=identifier, target_platform=platform, taxonomy_category=category,
                title=title, requirement_statement=statement, topic=branch[0].topic,
                region_variant=region, scope_layer=branch[0].scope_layer,
                average_sentiment=round(sentiment, 2), distinct_signal_count=len(branch),
                current_30d_mentions=current, previous_30d_mentions=previous,
                velocity_multiplier=velocity, velocity_acceleration_pct=acceleration,
                signal_threshold_score=round(signal_score, 3), sales_causality_score=sales,
                competitor_roi_score=roi, effort_class=effort_class, effort_penalty=effort_penalty,
                priority_score=priority, partial_priority_score=round(partial, 2), review_band=band,
                ehi_score=round(ehi, 2), groundedness_score=round(groundedness, 4),
                evidence_volume_score=round(volume, 4), market_conflict_penalty=round(conflict_penalty, 4),
                regional_conflict=conflict, confidence_label=confidence_label,
                warnings=warnings, blindspots=missing,
                evidence=list(evidence_by_locator.values()),
            ))
    order = {"Critical review": 0, "High": 1, "Medium": 2, "Low": 3, "Unscored": 4}
    output.sort(key=lambda item: (order[item.review_band], -(item.priority_score if item.priority_score is not None else item.partial_priority_score), item.title))
    return output, fixed_baseline
