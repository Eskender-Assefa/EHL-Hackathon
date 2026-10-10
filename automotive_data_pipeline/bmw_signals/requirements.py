from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .bmw_topics import GENERIC_TOPICS
from .models import FilteredSignal, RequirementCandidate, ScoringInputs
from .pipeline import PAIN_TYPES, PRAISE_TYPE, UNCLASSIFIED_TOPIC

EFFORT_DEFAULTS = {
    "C01": ("body_platform", 50), "C02": ("electronics_thermal", 15),
    "C03": ("software_ux", 0), "C04": ("electronics_thermal", 15),
    "C05": ("interior_trim", 5), "C06": ("body_platform", 50),
    "C07": ("software_ux", 0), "C08": ("interior_trim", 5),
    "C09": ("electronics_thermal", 15), "C10": ("software_ux", 0),
}
EFFORT_PENALTIES = dict(software_ux=0, interior_trim=5, electronics_thermal=15, body_platform=50)
BAND_ORDER = {"Critical review": 0, "High": 1, "Medium": 2, "Low": 3, "Unscored": 4}

# Thresholds for observed BMW workbook feedback. A topic raised by a handful of people is counted
# and reported (see summarise_exclusions) but not proposed as a requirement.
OBSERVED_SOURCE = "BMW_Workbook"
MIN_RESPONDENTS = 15
MIN_REGION_SAMPLE = 15
MIN_SEVERE_SAFETY = 3
# Other sources (synthetic scenarios, configured web collection) keep the original loose gates.
OTHER_MIN_RESPONDENTS = 1
OTHER_MIN_REGION_SAMPLE = 2
OTHER_MIN_SEVERE_SAFETY = 1

SAFETY_CATEGORY = "C04"
SEVERE_SENTIMENT = -80
SEVERE_TYPE = "Defect"
CONFLICT_SPREAD = 60
LOW_VOLUME_BELOW = 5
LOW_GROUNDEDNESS_BELOW = 0.7
MIXED_SHARE = 0.3
PRESERVE_RATIO = 2
ALL_MARKETS = "All markets"
COMPETITOR_SOURCE = "Competitor_Web"


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


def _conflict(regional: dict[str, list[FilteredSignal]], min_region_sample: int) -> tuple[bool, float, list[str]]:
    """Regions disagree only if each side has enough respondents to mean something."""
    means = {
        region: sum(s.sentiment_score for s in group) / len(group)
        for region, group in regional.items() if len(group) >= min_region_sample
    }
    if len(means) < 2:
        return False, 0.0, []
    spread = max(means.values()) - min(means.values())
    return spread >= CONFLICT_SPREAD, min(1.0, spread / 200), list(means)


def _unique_signals(signals: list[FilteredSignal]) -> list[FilteredSignal]:
    unique = {}
    for signal in signals:
        key = signal.source_record_id or signal.signal_id
        unique.setdefault(key, signal)
    return list(unique.values())


def _is_pain(signal: FilteredSignal) -> bool:
    if signal.feedback_types:
        return any(kind in PAIN_TYPES for kind in signal.feedback_types)
    return signal.sentiment_score < 0


def _is_praise(signal: FilteredSignal) -> bool:
    if signal.feedback_types:
        return PRAISE_TYPE in signal.feedback_types
    return signal.sentiment_score > 0


def _is_severe(signal: FilteredSignal) -> bool:
    return SEVERE_TYPE in signal.feedback_types or signal.sentiment_score <= SEVERE_SENTIMENT


def _gates(group: list[FilteredSignal], min_respondents: int, min_region_sample: int, min_severe_safety: int):
    if all(signal.source_platform == OBSERVED_SOURCE for signal in group):
        return min_respondents, min_region_sample, min_severe_safety
    return OTHER_MIN_RESPONDENTS, OTHER_MIN_REGION_SAMPLE, OTHER_MIN_SEVERE_SAFETY


def _statement(branch: list[FilteredSignal], pain: int, praise: int, platform: str) -> str:
    topic = branch[0].topic
    if any(signal.classification_basis == "bmw_label" for signal in branch):
        if pain > praise:
            action = "Improve"
        elif praise >= PRESERVE_RATIO * pain:
            action = "Preserve"
        else:
            action = "Review mixed feedback on"
        return f"{action} '{topic}' for {platform} customers."
    statements = [signal.requirement_statement for signal in branch if signal.requirement_statement]
    return Counter(statements).most_common(1)[0][0] if statements else f"Review {topic.lower()} for {platform} customers."


def _band(priority: float | None, severe_safety: bool) -> str:
    if severe_safety:
        return "Critical review"
    if priority is None:
        return "Unscored"
    if priority >= 85:
        return "Critical review"
    if priority >= 60:
        return "High"
    if priority >= 30:
        return "Medium"
    return "Low"


def _warnings(branch, conflict, groundedness, pain, praise, score_input) -> list[str]:
    warnings = []
    if conflict:
        warnings.append("Cross-regional sentiment conflict detected; regional derivative branches generated.")
    if len(branch) < LOW_VOLUME_BELOW:
        warnings.append("Low evidence volume: fewer than five distinct feedback records.")
    if groundedness < LOW_GROUNDEDNESS_BELOW:
        warnings.append("Groundedness is below 70%; human validation is required.")
    if min(pain, praise) >= MIXED_SHARE * len(branch):
        warnings.append(f"Mixed evidence: {pain} respondents complain and {praise} praise this topic. Read the quotes.")
    if branch[0].topic in GENERIC_TOPICS:
        warnings.append("Generic BMW topic covering overall impressions; it does not name one feature.")
    if any(signal.classification_basis == "keyword_rule" for signal in branch):
        warnings.append("Topic and polarity come from keyword rules, not BMW labels.")
    if score_input and score_input.synthetic:
        warnings.append("Priority uses synthetic causality/ROI scenario inputs, not observed outcomes.")
        warnings.extend(score_input.assumptions)
    return warnings


def _candidate(platform, category, topic_key, region, branch, conflict, conflict_penalty, score_input, min_severe_safety):
    sentiment = sum(signal.sentiment_score for signal in branch) / len(branch)
    impact = sum(abs(signal.sentiment_score) / 100 for signal in branch) / len(branch)
    credibility = sum(signal.credibility_weight for signal in branch) / len(branch)
    pain = sum(_is_pain(signal) for signal in branch)
    praise = sum(_is_praise(signal) for signal in branch)
    current, previous, velocity, acceleration = _velocity(branch)
    effort_class, effort_penalty = EFFORT_DEFAULTS[category]
    sales = score_input.sales_causality_score if score_input else None
    roi = score_input.competitor_roi_score if score_input else None
    if score_input:
        effort_class = score_input.effort_class
        effort_penalty = EFFORT_PENALTIES[effort_class]
    urgency = max(0.0, -sentiment) * (velocity if velocity is not None else 1.0)
    partial = urgency + (sales or 0) + (roi or 0) - effort_penalty
    missing = []
    if velocity is None:
        missing.append("No dated observations; 30-day velocity is unknown.")
    if sales is None:
        missing.append("No validated synthetic sales take-rate causality score.")
    if roi is None:
        missing.append("No validated competitor two-year ROI score.")
    priority = None if missing else round(partial, 2)
    severe_safety = (
        category == SAFETY_CATEGORY and sentiment < 0
        and sum(_is_severe(signal) for signal in branch) >= min_severe_safety
    )
    groundedness = sum(signal.confidence for signal in branch) / len(branch)
    competitors = sum(signal.source_platform == COMPETITOR_SOURCE for signal in branch)
    volume = min(1.0, (math.log1p(len(branch) - competitors) + math.log1p(competitors)) / 5)
    ehi = max(0.0, min(100.0, (0.55 * groundedness + 0.45 * volume - 0.30 * conflict_penalty) * 100))
    if conflict or ehi < 50:
        confidence_label = "Uncertain / Conflict Flag"
    else:
        confidence_label = "Verified Evidence" if ehi >= 80 else "Medium Evidence"
    evidence_by_locator = {}
    for signal in branch:
        for evidence in signal.evidence:
            evidence_by_locator[(evidence.source_uri, evidence.locator)] = evidence
    identifier = hashlib.sha256(f"{platform}|{category}|{topic_key}|{region}".encode()).hexdigest()[:16].upper()
    return severe_safety, RequirementCandidate(
        requirement_id=identifier, target_platform=platform, taxonomy_category=category,
        title=f"{platform} {branch[0].topic}", requirement_statement=_statement(branch, pain, praise, platform),
        topic=branch[0].topic, region_variant=region, scope_layer=branch[0].scope_layer,
        average_sentiment=round(sentiment, 2), distinct_signal_count=len(branch),
        pain_respondents=pain, praise_respondents=praise,
        current_30d_mentions=current, previous_30d_mentions=previous,
        velocity_multiplier=velocity, velocity_acceleration_pct=acceleration,
        signal_threshold_score=round(len(branch) * credibility * impact, 3), sales_causality_score=sales,
        competitor_roi_score=roi, effort_class=effort_class, effort_penalty=effort_penalty,
        priority_score=priority, partial_priority_score=round(partial, 2), review_band=_band(priority, severe_safety),
        ehi_score=round(ehi, 2), groundedness_score=round(groundedness, 4),
        evidence_volume_score=round(volume, 4), market_conflict_penalty=round(conflict_penalty, 4),
        regional_conflict=conflict, confidence_label=confidence_label,
        warnings=_warnings(branch, conflict, groundedness, pain, praise, score_input), blindspots=missing,
        evidence=list(evidence_by_locator.values()),
    )


def _grouped(signals: list[FilteredSignal]) -> dict[tuple[str, str, str], list[FilteredSignal]]:
    groups = defaultdict(list)
    for signal in signals:
        if signal.scope_layer != "fixed_now":
            groups[(signal.target_platform, signal.taxonomy_category, _topic_key(signal.topic))].append(signal)
    return {key: _unique_signals(group) for key, group in sorted(groups.items())}


def _branches(group: list[FilteredSignal], min_region_sample: int):
    regional: dict[str, list[FilteredSignal]] = defaultdict(list)
    for signal in group:
        regional[signal.region].append(signal)
    conflict, penalty, regions = _conflict(regional, min_region_sample)
    if conflict:
        return conflict, penalty, [(region, regional[region]) for region in regions]
    region = next(iter(regional)) if len(regional) == 1 else ALL_MARKETS
    return conflict, penalty, [(region, group)]


def build_requirements(signals: list[FilteredSignal], scoring_inputs: dict[str, ScoringInputs] | None = None,
                       threshold=0.5, min_respondents=MIN_RESPONDENTS, min_region_sample=MIN_REGION_SAMPLE,
                       min_severe_safety=MIN_SEVERE_SAFETY):
    scoring_inputs = scoring_inputs or {}
    fixed_baseline = [signal for signal in signals if signal.scope_layer == "fixed_now"]
    output = []
    for (platform, category, topic_key), group in _grouped(signals).items():
        if group[0].topic == UNCLASSIFIED_TOPIC:
            continue
        respondents_gate, region_gate, severe_gate = _gates(group, min_respondents, min_region_sample, min_severe_safety)
        conflict, conflict_penalty, branches = _branches(group, region_gate)
        score_input = scoring_inputs.get(f"{platform}|{category}|{topic_key}")
        for region, branch in branches:
            severe_safety, candidate = _candidate(
                platform, category, topic_key, region, branch, conflict, conflict_penalty, score_input, severe_gate,
            )
            if candidate.signal_threshold_score < threshold:
                continue
            if len(branch) < respondents_gate and not severe_safety:
                continue
            output.append(candidate)
    output.sort(key=lambda item: (
        BAND_ORDER[item.review_band],
        -(item.priority_score if item.priority_score is not None else item.pain_respondents),
        item.title,
    ))
    return output, fixed_baseline


def summarise_exclusions(signals: list[FilteredSignal], min_respondents=MIN_RESPONDENTS) -> dict:
    """Say what the requirement list leaves out, so silence is not mistaken for low priority."""
    unclassified: set[str] = set()
    thin_topics = thin_respondents = 0
    for group in _grouped(signals).values():
        if group[0].topic == UNCLASSIFIED_TOPIC:
            unclassified.update(signal.source_record_id or signal.signal_id for signal in group)
        elif len(group) < _gates(group, min_respondents, 0, 0)[0]:
            thin_topics += 1
            thin_respondents += len(group)
    return {
        "minimum_respondents": min_respondents,
        "unclassified_respondents": len(unclassified),
        "topics_below_minimum": thin_topics,
        "respondents_in_topics_below_minimum": thin_respondents,
        "note": "Counted but not proposed. Missing evidence is silence, not low priority.",
    }
