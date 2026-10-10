from __future__ import annotations

from collections import Counter
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

from .models import RequirementCandidate
from .requirements import priority_band, static_priority_proxy


NAVY = RGBColor(17, 33, 51)
BLUE = RGBColor(0, 102, 177)
LIGHT_BLUE = RGBColor(229, 241, 249)
WHITE = RGBColor(255, 255, 255)
INK = RGBColor(30, 38, 46)
MUTED = RGBColor(91, 105, 117)
PAPER = RGBColor(246, 248, 250)
LINE = RGBColor(210, 218, 225)
RED = RGBColor(183, 38, 48)
AMBER = RGBColor(210, 126, 0)
GREEN = RGBColor(31, 122, 80)

BAND_COLOURS = {
    "Critical review": (RED, WHITE),
    "High": (AMBER, WHITE),
    "Medium": (BLUE, WHITE),
    "Low": (RGBColor(221, 227, 232), INK),
}


def _background(slide, colour: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = colour


def _panel(slide, x, y, width, height, *, fill=PAPER, line=LINE, radius=True):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, x, y, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(0.75)
    return shape


def _textbox(
    slide, x, y, width, height, text, *, size=16, colour=INK, bold=False,
    align=PP_ALIGN.LEFT, margin=0.04, auto_fit=True,
):
    shape = slide.shapes.add_textbox(x, y, width, height)
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    if auto_fit:
        frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = str(text)
    run.font.name = "Aptos"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = colour
    return shape


def _metric(slide, x, y, width, label, value, *, value_colour=INK):
    shape = _panel(slide, x, y, width, Inches(0.78), fill=WHITE)
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.12)
    frame.margin_right = Inches(0.10)
    frame.margin_top = Inches(0.08)
    frame.margin_bottom = Inches(0.06)
    label_paragraph = frame.paragraphs[0]
    label_run = label_paragraph.add_run()
    label_run.text = label.upper()
    label_run.font.name = "Aptos"
    label_run.font.size = Pt(8)
    label_run.font.bold = True
    label_run.font.color.rgb = MUTED
    value_paragraph = frame.add_paragraph()
    value_paragraph.space_before = Pt(2)
    value_run = value_paragraph.add_run()
    value_run.text = str(value)
    value_run.font.name = "Aptos Display"
    value_run.font.size = Pt(18)
    value_run.font.bold = True
    value_run.font.color.rgb = value_colour
    return shape


def _effective_priority(requirement: RequirementCandidate) -> tuple[float, str, str]:
    score = requirement.priority_score
    basis = requirement.priority_score_basis
    band = requirement.review_band
    if score is None:
        score = static_priority_proxy([requirement.average_sentiment], requirement.distinct_signal_count)
        basis = "static_evidence_proxy"
    if band == "Unscored":
        band = priority_band(
            score,
            severe_safety=requirement.taxonomy_category == "C04" and requirement.average_sentiment <= -80,
        )
    return score, band, basis


def _ranked(requirements: list[RequirementCandidate]) -> list[RequirementCandidate]:
    band_order = {"Critical review": 0, "High": 1, "Medium": 2, "Low": 3}
    return sorted(
        requirements,
        key=lambda item: (band_order[_effective_priority(item)[1]], -_effective_priority(item)[0], item.title),
    )


def _detail_selection(ranked: list[RequirementCandidate], limit: int = 20) -> list[RequirementCandidate]:
    """Keep the portfolio leaders while reserving detail slides for collected external sources."""
    if len(ranked) <= limit:
        return ranked
    reserve = min(6, limit)
    selected = list(ranked[:limit - reserve])
    selected_ids = {item.requirement_id for item in selected}
    external_order = ("Reddit", "BIMMERPOST", "German_Car_Forum", "Bimmerforums", "Competitor_Web")
    covered = {source for item in selected for source in item.evidence_source_counts}
    for source in external_order:
        if source in covered:
            continue
        candidate = next(
            (
                item for item in ranked
                if item.requirement_id not in selected_ids and source in item.evidence_source_counts
            ),
            None,
        )
        if candidate is not None:
            selected.append(candidate)
            selected_ids.add(candidate.requirement_id)
            covered.update(candidate.evidence_source_counts)
        if len(selected) == limit:
            return selected
    selected.extend(item for item in ranked if item.requirement_id not in selected_ids)
    return selected[:limit]


def _set_cell(cell, text, *, size=10, bold=False, colour=INK, fill=WHITE, align=PP_ALIGN.LEFT):
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    cell.margin_left = Inches(0.07)
    cell.margin_right = Inches(0.07)
    cell.margin_top = Inches(0.04)
    cell.margin_bottom = Inches(0.04)
    frame = cell.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = str(text)
    run.font.name = "Aptos"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = colour


def _citation(evidence) -> str:
    source = evidence.source_platform or "Source"
    label = source.replace("_", " ")
    uri = evidence.source_uri
    for token in ("/", "?", "&", "="):
        uri = uri.replace(token, token + "\u200b")
    value = f"[{label}] {uri} — {evidence.locator}"
    return value if len(value) <= 180 else value[:177] + "..."


def _add_header(slide, title: str, kicker: str) -> None:
    _panel(slide, 0, 0, Inches(13.333), Inches(1.28), fill=NAVY, line=None, radius=False)
    _textbox(slide, Inches(0.55), Inches(0.18), Inches(12.2), Inches(0.28), kicker, size=9, colour=RGBColor(159, 202, 232), bold=True)
    _textbox(slide, Inches(0.55), Inches(0.48), Inches(12.2), Inches(0.62), title, size=25, colour=WHITE, bold=True)


def _add_footer(slide, page_number: int, note: str = "Evidence-linked requirement review") -> None:
    _textbox(slide, Inches(0.55), Inches(7.18), Inches(10.8), Inches(0.2), note, size=8, colour=MUTED)
    _textbox(slide, Inches(12.1), Inches(7.18), Inches(0.65), Inches(0.2), f"{page_number:02d}", size=8, colour=MUTED, align=PP_ALIGN.RIGHT)


def export_deck(requirements: list[RequirementCandidate], destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]
    ranked = _ranked(requirements)
    detail_requirements = _detail_selection(ranked)
    rank_by_id = {item.requirement_id: index for index, item in enumerate(ranked, 1)}

    title_slide = presentation.slides.add_slide(blank)
    _background(title_slide, NAVY)
    _panel(title_slide, Inches(0.58), Inches(0.65), Inches(0.12), Inches(5.9), fill=BLUE, line=None, radius=False)
    _textbox(title_slide, Inches(1.05), Inches(1.0), Inches(10.9), Inches(0.35), "BMW PRODUCT MANAGEMENT", size=11, colour=RGBColor(159, 202, 232), bold=True)
    _textbox(title_slide, Inches(1.05), Inches(1.55), Inches(10.9), Inches(1.35), "Evidence-led product\nrequirement priorities", size=34, colour=WHITE, bold=True)
    _textbox(title_slide, Inches(1.05), Inches(3.15), Inches(10.4), Inches(0.8), "Decision-ready requirements with source traceability, transparent confidence, and explicit scoring basis.", size=18, colour=RGBColor(220, 230, 238))
    _panel(title_slide, Inches(1.05), Inches(4.45), Inches(5.5), Inches(0.78), fill=RGBColor(28, 52, 75), line=RGBColor(63, 92, 117))
    _textbox(title_slide, Inches(1.25), Inches(4.58), Inches(5.1), Inches(0.48), f"{len(ranked)} ranked candidates  •  C01–C10 taxonomy", size=14, colour=WHITE, bold=True)
    _textbox(title_slide, Inches(1.05), Inches(6.75), Inches(10.0), Inches(0.28), "Generated by the BMW automotive requirements pipeline", size=9, colour=RGBColor(159, 173, 186))

    summary = presentation.slides.add_slide(blank)
    _background(summary, WHITE)
    _add_header(summary, "Decision overview", "PORTFOLIO PRIORITIES")
    effective = [_effective_priority(item) for item in ranked]
    bands = Counter(band for _, band, _ in effective)
    proxy_count = sum(basis == "static_evidence_proxy" for _, _, basis in effective)
    conflict_count = sum(item.regional_conflict for item in ranked)
    card_width = Inches(2.88)
    for index, (label, value, colour) in enumerate((
        ("Requirements", len(ranked), INK),
        ("Critical / High", bands["Critical review"] + bands["High"], RED),
        ("Static proxy ranked", proxy_count, BLUE),
        ("Regional conflicts", conflict_count, AMBER),
    )):
        _metric(summary, Inches(0.55) + index * Inches(3.08), Inches(1.48), card_width, label, value, value_colour=colour)

    row_count = min(len(ranked), 10) + 1
    table_shape = summary.shapes.add_table(row_count, 6, Inches(0.48), Inches(2.52), Inches(12.38), Inches(4.35))
    table = table_shape.table
    for column, width in zip(table.columns, (0.55, 0.75, 1.25, 1.20, 7.40, 1.20)):
        column.width = Inches(width)
    for index, header in enumerate(("Rank", "Score", "Band", "Vehicle", "Requirement", "Evidence")):
        _set_cell(table.cell(0, index), header, size=9, bold=True, colour=WHITE, fill=NAVY, align=PP_ALIGN.CENTER if index != 4 else PP_ALIGN.LEFT)
    for row, requirement in enumerate(ranked[:10], start=1):
        score, band, _ = _effective_priority(requirement)
        band_fill, band_text = BAND_COLOURS[band]
        values = (row, f"{score:.1f}", band, requirement.target_platform, requirement.title, requirement.distinct_signal_count)
        for column, value in enumerate(values):
            fill, colour = (band_fill, band_text) if column == 2 else (WHITE if row % 2 else PAPER, INK)
            _set_cell(table.cell(row, column), value, size=9 if column == 4 else 10, bold=column in {0, 1, 2}, colour=colour, fill=fill, align=PP_ALIGN.LEFT if column == 4 else PP_ALIGN.CENTER)
    _add_footer(summary, 2, "Priority score uses the complete formula where available and a labelled static-evidence proxy otherwise")

    for page, requirement in enumerate(detail_requirements, start=3):
        score, band, basis = _effective_priority(requirement)
        slide = presentation.slides.add_slide(blank)
        _background(slide, WHITE)
        _add_header(slide, requirement.title, f"RANK {rank_by_id[requirement.requirement_id]:02d}  /  {band.upper()}")
        _panel(slide, Inches(0.55), Inches(1.52), Inches(12.23), Inches(1.0), fill=LIGHT_BLUE, line=RGBColor(181, 211, 232))
        _textbox(slide, Inches(0.76), Inches(1.67), Inches(11.8), Inches(0.7), requirement.requirement_statement, size=16, colour=INK, bold=True)

        region = None if requirement.region_variant in {"Unknown", "Global / Unassigned"} else requirement.region_variant
        evidence_records = sum(requirement.evidence_source_counts.values()) or requirement.distinct_signal_count
        metrics = (
            ("Priority", f"{score:.1f}", RED if band == "Critical review" else BLUE),
            ("Sentiment", f"{requirement.average_sentiment:+.0f}", RED if requirement.average_sentiment < 0 else GREEN),
            ("Evidence records", evidence_records, INK),
            ("Source types", len(requirement.evidence_source_counts) or 1, INK),
            ("Evidence confidence", f"{requirement.ehi_score:.0f}%", BLUE),
            ("Coverage", region or "Global", INK),
        )
        for index, (label, value, colour) in enumerate(metrics):
            _metric(slide, Inches(0.55) + index * Inches(2.05), Inches(2.77), Inches(1.85), label, value, value_colour=colour)

        _panel(slide, Inches(0.55), Inches(3.78), Inches(7.72), Inches(3.12), fill=PAPER)
        _textbox(slide, Inches(0.78), Inches(3.96), Inches(7.25), Inches(0.28), "SOURCE EVIDENCE", size=10, colour=BLUE, bold=True)
        evidence_lines = [f"{index}. {_citation(item)}" for index, item in enumerate(requirement.evidence[:6], 1)]
        evidence_text = "\n".join(evidence_lines) if evidence_lines else "No source citation was retained."
        _textbox(slide, Inches(0.78), Inches(4.34), Inches(7.2), Inches(2.25), evidence_text, size=11, colour=INK, margin=0.03)

        _panel(slide, Inches(8.52), Inches(3.78), Inches(4.26), Inches(3.12), fill=WHITE)
        basis_label = "Complete business formula" if basis == "complete_formula" else "Static evidence proxy"
        _textbox(slide, Inches(8.76), Inches(3.96), Inches(3.8), Inches(0.28), "DECISION CONTEXT", size=10, colour=BLUE, bold=True)
        source_mix = "  •  ".join(f"{source.replace('_', ' ')} {count}" for source, count in requirement.evidence_source_counts.items())
        _textbox(slide, Inches(8.76), Inches(4.28), Inches(3.8), Inches(0.28), f"Sources: {source_mix or '1 source type'}", size=9, colour=MUTED, bold=True)
        _textbox(slide, Inches(8.76), Inches(4.56), Inches(3.8), Inches(0.3), f"Score basis: {basis_label}", size=11, colour=INK, bold=True)
        context_items = [*requirement.warnings[:2], *requirement.blindspots[:2]]
        context_text = "\n".join(f"• {item}" for item in context_items) or "• No material warnings or blindspots recorded."
        _textbox(slide, Inches(8.76), Inches(4.92), Inches(3.78), Inches(1.66), context_text, size=10, colour=MUTED, margin=0.02)
        _add_footer(slide, page, f"{requirement.taxonomy_category}  •  {requirement.confidence_label}  •  {region or 'Global'}")

    presentation.save(destination)
    return destination
