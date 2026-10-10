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
from .taxonomy import TAXONOMY

EFFORT_DEFAULTS = {
    "C01": ("body_platform", 50), "C02": ("electronics_thermal", 15),
    "C03": ("software_ux", 0), "C04": ("electronics_thermal", 15),
    "C05": ("interior_trim", 5), "C06": ("body_platform", 50),
    "C07": ("software_ux", 0), "C08": ("interior_trim", 5),
    "C09": ("electronics_thermal", 15), "C10": ("software_ux", 0),
}

CATEGORY_NAMES = {
    "C01": "Power & Performance", "C02": "Energy & Emissions", "C03": "Price",
    "C04": "Safety", "C05": "Comfort", "C06": "Exterior", "C07": "Software",
    "C08": "Interior Design", "C09": "Automation", "C10": "Miscellaneous",
}

ACTION_RULES = {
    "C01": (
        (r"\b(transmission|shift|gear)\b", "Refine transmission shift logic for smoother, more predictable response"),
        (r"\b(steering|handling|driving dynamics)\b", "Calibrate steering and chassis response for predictable handling"),
        (r"\b(acceleration|throttle)\b", "Deliver consistent accelerator response across normal driving conditions"),
        (r"\b(xdrive|drivetrain)\b", "Improve xDrive traction response and driveline consistency across changing road conditions"),
        (r"\b(engine|motor|power)\b", "Deliver consistent powertrain response across normal driving conditions"),
    ),
    "C02": (
        (r"\b(charging|charger|dc fast)\b", "Improve charging speed consistency and make charge progress easier to predict"),
        (r"\b(range|consumption|energy)\b", "Improve real-world range prediction and energy-use transparency"),
        (r"\b(battery|thermal)\b", "Stabilize battery performance across temperature and charging conditions"),
        (r"\b(emission)\w*", "Reduce real-world energy use and make emissions performance transparent"),
    ),
    "C03": (
        (r"\b(subscription)\b", "Replace recurring feature fees with transparent ownership and purchase options"),
        (r"\b(package|option pack|bundl)\w*", "Simplify option packages and expose the price of each customer benefit"),
        (r"\b(price|cost|expensive|value for money|msrp)\b", "Improve price transparency and perceived value across configurations"),
    ),
    "C04": (
        (r"false.?positive.*(collision|warning|alert)|(collision|warning|alert).*false.?positive", "Reduce false-positive triggers in forward-collision warning alerts"),
        (r"\b(collision warning|forward.collision)\b", "Improve collision-warning detection and provide timely, explainable alerts"),
        (r"\b(blind spot)\b", "Improve blind-spot alert timing and directional clarity"),
        (r"\b(emergency braking|brake|braking)\b", "Improve emergency-braking intervention consistency and driver feedback"),
        (r"\b(seat belt)\b", "Improve seat-belt restraint performance and status feedback"),
        (r"\b(airbag|crash|collision)\b", "Strengthen occupant protection and collision-event response"),
    ),
    "C05": (
        (r"\b(seat|massage)\b", "Improve seat support and long-distance ergonomic comfort"),
        (r"\b(climate|air conditioning|hvac)\b", "Reduce climate-control noise and improve cabin temperature consistency"),
        (r"\b(ride|suspension|vibration|noise)\b", "Reduce cabin vibration and harshness without compromising body control"),
        (r"\b(comfort)\b", "Improve ride and cabin comfort consistency during everyday use"),
    ),
    "C06": (
        (r"\b(headlight|taillight|lighting)\b", "Refine exterior lighting performance and visual signature"),
        (r"\b(paint|trim)\b", "Increase exterior-finish durability under normal ownership conditions"),
        (r"\b(wheel|grille|roof|styling|exterior)\b", "Refine exterior detailing while preserving aerodynamic performance"),
    ),
    "C07": (
        (r"\b(menu|submenu|touch ?screen|idrive)\b", "Flatten the iDrive menu hierarchy and shorten access to frequently used controls"),
        (r"\b(crash|freeze|freezes|bug|reboot|glitch|operating system)\b", "Improve infotainment stability and recover cleanly from software faults"),
        (r"\b(carplay|android auto|bluetooth|connectivity)\b", "Stabilize phone pairing, reconnection, and wireless projection"),
        (r"\b(ota|update)\b", "Make over-the-air updates reliable, transparent, and recoverable"),
        (r"\b(navigation)\b", "Improve navigation accuracy and reduce interaction steps for route changes"),
        (r"\b(instrument cluster)\b", "Improve instrument-cluster information hierarchy and glance readability"),
    ),
    "C08": (
        (r"\b(display placement|screen placement|dashboard)\b", "Reposition cockpit displays for clear sightlines and comfortable reach"),
        (r"\b(storage|center console)\b", "Increase usable cabin storage and simplify center-console access"),
        (r"\b(leather|upholstery|trim|material)\b", "Improve perceived interior material quality and wear resistance"),
        (r"\b(ambient light)\w*", "Refine ambient lighting coverage and control consistency"),
    ),
    "C09": (
        (r"\b(parking assistant|automated parking)\b", "Improve automated-parking path confidence and intervention transparency"),
        (r"\b(lane change)\b", "Make assisted lane changes predictable and easy to confirm or cancel"),
        (r"\b(highway assistant|hands free|autonomous|automated driving|cruise control)\b", "Improve assisted-driving availability and communicate operating boundaries clearly"),
    ),
    "C10": (
        (r"\b(dealer|service|handover)\b", "Standardize dealer handover and service-status communication"),
        (r"\b(warranty)\b", "Clarify warranty coverage, exclusions, and claim status"),
        (r"\b(trunk|door|key|accessory)\b", "Improve everyday access and accessory usability"),
        (r"\b(general)\b", "Resolve recurring ownership pain points with clear end-to-end accountability"),
    ),
}

FALLBACK_ACTIONS = {
    "C01": "Improve {topic} response and consistency under real-world driving conditions",
    "C02": "Improve {topic} efficiency and real-world predictability",
    "C03": "Make {topic} transparent and easier to evaluate before purchase",
    "C04": "Improve {topic} performance while reducing unnecessary driver alerts",
    "C05": "Improve {topic} comfort and consistency during everyday use",
    "C06": "Improve {topic} durability and visual execution",
    "C07": "Reduce interaction effort and failures in {topic}",
    "C08": "Improve {topic} ergonomics, usability, and perceived quality",
    "C09": "Improve {topic} predictability and communicate system state clearly",
    "C10": "Improve the end-to-end experience for {topic}",
}

SOURCE_PRESENTATION_ORDER = (
    "Reddit", "BMW_Workbook", "BIMMERPOST", "Competitor_Web",
    "German_Car_Forum", "Bimmerforums", "Synthetic", "BMW_PDF",
)

# Gates for observed BMW workbook feedback. The CLI applies them; library callers opt in.
OBSERVED_SOURCE = "BMW_Workbook"
MIN_RESPONDENTS = 15
MIN_REGION_SAMPLE = 15
MIN_SEVERE_SAFETY = 3
SEVERE_SENTIMENT = -80
SEVERE_TYPE = "Defect"
MIXED_SHARE = 0.3
PRESERVE_RATIO = 2


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


def _conflict(regional: dict[str, list[FilteredSignal]], min_region_sample: int = 2) -> tuple[bool, float]:
    means = [
        sum(s.sentiment_score for s in group) / len(group)
        for region, group in regional.items()
        if region not in {"Unknown", "Global / Unassigned"} and len(group) >= min_region_sample
    ]
    if len(means) < 2:
        return False, 0.0
    spread = max(means) - min(means)
    return spread >= 60, min(1.0, spread / 200)


def _unique_signals(signals: list[FilteredSignal]) -> list[FilteredSignal]:
    unique = {}
    for signal in signals:
        key = (signal.source_platform, signal.source_record_id) if signal.source_record_id else (signal.source_platform, signal.signal_id)
        unique.setdefault(key, signal)
    return list(unique.values())


def _balanced_evidence(signals: list[FilteredSignal]):
    """Round-robin citations by source so one high-volume source cannot dominate slides."""
    buckets = defaultdict(list)
    seen = set()
    for signal in signals:
        for evidence in signal.evidence:
            key = (evidence.source_uri, evidence.locator, evidence.record_id)
            if key in seen:
                continue
            seen.add(key)
            source = evidence.source_platform or signal.source_platform
            buckets[source].append(
                evidence if evidence.source_platform else evidence.model_copy(update={"source_platform": source})
            )
    sources = [source for source in SOURCE_PRESENTATION_ORDER if source in buckets]
    sources.extend(sorted(source for source in buckets if source not in sources))
    output = []
    index = 0
    while any(index < len(buckets[source]) for source in sources):
        for source in sources:
            if index < len(buckets[source]):
                output.append(buckets[source][index])
        index += 1
    return output


def static_priority_proxy(sentiment_scores: list[float], source_volume: int) -> float:
    """Rank static evidence without pretending missing business inputs are known."""
    if not sentiment_scores or source_volume <= 0:
        return 0.0
    severity = sum(abs(score) for score in sentiment_scores) / (100 * len(sentiment_scores))
    volume = min(1.0, math.log1p(source_volume) / math.log1p(20))
    return round(100 * severity * volume, 2)


def priority_band(score: float, *, severe_safety: bool = False) -> str:
    if severe_safety or score >= 85:
        return "Critical review"
    if score >= 60:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


def _display_region(region: str) -> str:
    return "Global / Unassigned" if region == "Unknown" else region


def _professional_action(category: str, topic: str, signals: list[FilteredSignal]) -> str:
    topic_context = topic.casefold()
    context = " ".join(signal.cleaned_verbatim_text for signal in signals).casefold()
    for pattern, action in ACTION_RULES[category]:
        if re.search(pattern, topic_context, re.I):
            return action
    for pattern, action in ACTION_RULES[category]:
        if re.search(pattern, context, re.I):
            return action
    clean_topic = re.sub(r"\s+", " ", topic).strip().casefold() or CATEGORY_NAMES[category].casefold()
    return FALLBACK_ACTIONS[category].format(topic=clean_topic)


def _professional_statement(platform: str, action: str, signals: list[FilteredSignal]) -> str:
    statements = [signal.requirement_statement.strip() for signal in signals if signal.requirement_statement]
    generic = re.compile(r"^(improve|review|preserve)\s+.{1,80}\s+for\s+(?:f70|g60|g70|neue_klasse)\s+customers\.?$", re.I)
    professional = [statement for statement in statements if not generic.match(statement)]
    if professional:
        return Counter(professional).most_common(1)[0][0]
    return f"The {platform} shall {action[0].lower() + action[1:]}."


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


def _is_observed(signals: list[FilteredSignal]) -> bool:
    return bool(signals) and all(signal.source_platform == OBSERVED_SOURCE for signal in signals)


def summarise_exclusions(signals: list[FilteredSignal], min_respondents: int = 15) -> dict:
    """Say what the requirement list leaves out, so silence is not mistaken for low priority."""
    groups = defaultdict(list)
    for signal in signals:
        if signal.scope_layer != "fixed_now" and signal.source_platform == OBSERVED_SOURCE:
            groups[(signal.target_platform, signal.taxonomy_category, _topic_key(signal.topic))].append(signal)
    unclassified: set[str] = set()
    thin_topics = thin_respondents = 0
    for group in groups.values():
        group = _unique_signals(group)
        if group[0].topic == UNCLASSIFIED_TOPIC:
            unclassified.update(signal.source_record_id or signal.signal_id for signal in group)
        elif len(group) < min_respondents:
            thin_topics += 1
            thin_respondents += len(group)
    return {
        "minimum_respondents": min_respondents,
        "unclassified_respondents": len(unclassified),
        "topics_below_minimum": thin_topics,
        "respondents_in_topics_below_minimum": thin_respondents,
        "note": "Counted but not proposed. Missing evidence is silence, not low priority.",
    }


def build_requirements(signals: list[FilteredSignal], scoring_inputs: dict[str, ScoringInputs] | None = None, threshold=0.5,
                       min_respondents=1, min_region_sample=2, min_severe_safety=1):
    scoring_inputs = scoring_inputs or {}
    fixed_baseline = [signal for signal in signals if signal.scope_layer == "fixed_now"]
    candidates = [signal for signal in signals if signal.scope_layer != "fixed_now"]
    base_groups = defaultdict(list)
    for signal in candidates:
        base_groups[(signal.target_platform, signal.taxonomy_category, _topic_key(signal.topic))].append(signal)
    output = []
    for (platform, category, topic_key), group in sorted(base_groups.items()):
        group = _unique_signals(group)
        benchmarks = [signal for signal in group if signal.source_platform == "Competitor_Web"]
        demand = [signal for signal in group if signal.source_platform != "Competitor_Web"]
        observed = _is_observed(demand)
        if observed and demand[0].topic == UNCLASSIFIED_TOPIC and min_respondents > 1:
            continue
        respondents_gate = min_respondents if observed else 1
        region_gate = min_region_sample if observed else 2
        severe_gate = min_severe_safety if observed else 1
        regional = defaultdict(list)
        for signal in demand:
            regional[signal.region].append(signal)
        conflict, conflict_penalty = _conflict(regional, region_gate) if demand else (False, 0.0)
        if conflict and demand:
            branches = [
                (_display_region(region), region_group)
                for region, region_group in regional.items()
                if region not in {"Unknown", "Global / Unassigned"} and len(region_group) >= region_gate
            ]
            unassigned = [signal for region in ("Unknown", "Global / Unassigned") for signal in regional.get(region, [])]
            if unassigned:
                branches.append(("Global / Unassigned", unassigned))
        elif demand:
            region = _display_region(next(iter(regional))) if len(regional) == 1 else "Global / Unassigned"
            branches = [(region, demand)]
        else:
            benchmark_regions = {signal.region for signal in benchmarks}
            region = _display_region(next(iter(benchmark_regions))) if len(benchmark_regions) == 1 else "Global / Unassigned"
            branches = [(region, benchmarks)]
        for region, branch in branches:
            branch = _unique_signals(branch)
            if demand:
                matching_benchmarks = [
                    signal for signal in benchmarks
                    if region == "Global / Unassigned" or signal.region in {region, "Unknown", "Global / Unassigned"}
                ]
                matching_benchmarks = matching_benchmarks or benchmarks
                support = _unique_signals([*branch, *matching_benchmarks])
                metric_signals = branch
            else:
                support = branch
                metric_signals = branch
            sentiment = sum(signal.sentiment_score for signal in branch) / len(branch)
            impact = sum(abs(signal.sentiment_score) / 100 for signal in branch) / len(branch)
            credibility = sum(signal.credibility_weight for signal in branch) / len(branch)
            threshold_impact = impact if demand else max(impact, 0.5)
            signal_score = len(branch) * credibility * threshold_impact
            if signal_score < threshold:
                continue
            current, previous, velocity, acceleration = _velocity(metric_signals if demand else [])
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
            # Only complaints raise priority: praise is a reason to preserve, not to act urgently.
            priority = round(partial, 2) if complete else static_priority_proxy(
                [min(0, signal.sentiment_score) for signal in metric_signals], len(metric_signals)
            )
            priority_basis = "complete_formula" if complete else "static_evidence_proxy"
            severe_count = sum(_is_severe(signal) for signal in metric_signals)
            severe_safety = category == "C04" and severe_count >= severe_gate and (severe_gate == 1 or sentiment < 0)
            if len(metric_signals) < respondents_gate and not severe_safety:
                continue
            pain = sum(_is_pain(signal) for signal in metric_signals)
            praise = sum(_is_praise(signal) for signal in metric_signals)
            label_based = any(signal.classification_basis == "bmw_label" for signal in metric_signals)
            band = priority_band(priority, severe_safety=severe_safety)
            groundedness = sum(signal.confidence for signal in support) / len(support)
            verbatims = len(metric_signals) if demand else 0
            competitors = len(matching_benchmarks) if demand else len(benchmarks)
            volume = min(1.0, (math.log1p(verbatims) + math.log1p(competitors)) / 5)
            ehi = max(0.0, min(100.0, (0.55 * groundedness + 0.45 * volume - 0.30 * conflict_penalty) * 100))
            confidence_label = "Verified Evidence" if ehi >= 80 and not conflict else "Medium Evidence" if ehi >= 50 and not conflict else "Uncertain / Conflict Flag"
            action = _professional_action(category, branch[0].topic, support)
            statement = _professional_statement(platform, action, metric_signals)
            if label_based and praise >= PRESERVE_RATIO * max(pain, 1):
                # Customers mostly praise this topic: it is a strength to keep, not a defect to fix.
                action = f"Preserve the current strength in {branch[0].topic}"
                statement = f"The {platform} shall preserve its current customer-rated strength in '{branch[0].topic}'."
            evidence_source_counts = dict(sorted(Counter(signal.source_platform for signal in support).items()))
            warnings = []
            if conflict:
                warnings.append("Cross-regional sentiment conflict detected; regional derivative branches generated.")
            if len(branch) < 5:
                warnings.append("Low evidence volume: fewer than five distinct feedback records.")
            if groundedness < 0.7:
                warnings.append("Groundedness is below 70%; human validation is required.")
            if label_based and min(pain, praise) >= MIXED_SHARE * len(metric_signals):
                warnings.append(f"Mixed evidence: {pain} respondents complain and {praise} praise this topic. Read the quotes.")
            if branch[0].topic in GENERIC_TOPICS:
                warnings.append("Generic BMW topic covering overall impressions; it does not name one feature.")
            if observed and not label_based:
                warnings.append("Topic and polarity come from keyword rules, not BMW labels.")
            if competitors:
                warnings.append(f"Includes {competitors} competitor benchmark record{'s' if competitors != 1 else ''}; benchmark evidence does not inflate customer-demand volume or sentiment.")
            if not demand:
                warnings.append("Benchmark-only opportunity: no matching direct BMW customer signal was collected for this topic.")
            if score_input and score_input.synthetic:
                warnings.append("Priority uses synthetic causality/ROI scenario inputs, not observed outcomes.")
                warnings.extend(score_input.assumptions)
            if not complete:
                warnings.append("Priority is a static evidence proxy based on complaint severity and distinct source volume; missing business inputs remain listed as blindspots.")
            title = f"{platform} ({category}): {action}"
            identifier = hashlib.sha256(f"{platform}|{category}|{topic_key}|{region}".encode()).hexdigest()[:16].upper()
            output.append(RequirementCandidate(
                requirement_id=identifier, target_platform=platform, taxonomy_category=category,
                title=title, requirement_statement=statement, topic=branch[0].topic,
                region_variant=region, scope_layer=metric_signals[0].scope_layer,
                average_sentiment=round(sentiment, 2), distinct_signal_count=len(metric_signals),
                pain_respondents=pain, praise_respondents=praise,
                current_30d_mentions=current, previous_30d_mentions=previous,
                velocity_multiplier=velocity, velocity_acceleration_pct=acceleration,
                signal_threshold_score=round(signal_score, 3), sales_causality_score=sales,
                competitor_roi_score=roi, effort_class=effort_class, effort_penalty=effort_penalty,
                priority_score=priority, priority_score_basis=priority_basis,
                partial_priority_score=round(partial, 2), review_band=band,
                ehi_score=round(ehi, 2), groundedness_score=round(groundedness, 4),
                evidence_volume_score=round(volume, 4), market_conflict_penalty=round(conflict_penalty, 4),
                regional_conflict=conflict, confidence_label=confidence_label,
                warnings=warnings, blindspots=missing,
                evidence=_balanced_evidence(support), evidence_source_counts=evidence_source_counts,
            ))
    order = {"Critical review": 0, "High": 1, "Medium": 2, "Low": 3, "Unscored": 4}
    output.sort(key=lambda item: (order[item.review_band], -item.priority_score, item.title))
    return output, fixed_baseline
