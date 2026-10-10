from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

from .models import BmwLabel, EvidenceRef, RawPost

UNCLASSIFIED_TAG = "no_class_found"
COUNTRY_REGION = {
    "US": "US", "CN": "CN",
    "GB": "EU", "FR": "EU", "SE": "EU", "DK": "EU", "FI": "EU",
    "NO": "EU", "ES": "EU", "LV": "EU", "DE": "EU", "AT": "EU",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_uri(path: Path) -> str:
    return f"bmw-file://{path.name}"


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_feedback_workbook(path: str | Path) -> tuple[list[RawPost], dict]:
    path = Path(path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    if "Feedback_Explorer" not in workbook.sheetnames:
        workbook.close()
        raise ValueError(f"{path.name} has no Feedback_Explorer sheet")
    sheet = workbook["Feedback_Explorer"]
    rows = sheet.iter_rows(values_only=True)
    headers = [str(value).strip() if value is not None else "" for value in next(rows)]
    required = {"ID", "Country", "Derivate (e-code)", "Customer Feedback", "Feedback Type", "Vfc level2 Name"}
    missing = required - set(headers)
    if missing:
        workbook.close()
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    column = {name: index for index, name in enumerate(headers)}
    grouped: OrderedDict[str, dict] = OrderedDict()
    tagged_rows = 0
    for row_number, values in enumerate(rows, start=2):
        tagged_rows += 1
        record_id = values[column["ID"]]
        text = values[column["Customer Feedback"]]
        platform = values[column["Derivate (e-code)"]]
        if not record_id or not text or platform not in {"F70", "G60", "G70"}:
            continue
        country = str(values[column["Country"]] or "").strip() or None
        entry = grouped.setdefault(str(record_id), {
            "text": str(text).strip(), "platform": platform, "country": country,
            "types": [], "tags": [], "labels": [], "evidence": [],
        })
        feedback_type = values[column["Feedback Type"]]
        if feedback_type and str(feedback_type) not in entry["types"]:
            entry["types"].append(str(feedback_type))
        topic = values[column["Vfc level2 Name"]]
        if feedback_type and topic and topic != UNCLASSIFIED_TAG:
            subtopic = values[column["Vfc level3 Name"]] if "Vfc level3 Name" in column else None
            entry["labels"].append(BmwLabel(
                topic=str(topic).strip(), feedback_type=str(feedback_type).strip(),
                subtopic=str(subtopic).strip() if subtopic else None, row_number=row_number,
            ))
        for name in ("Vfc level2 3 Name", "Vfc level2 Name", "Vfc level3 Name"):
            if name in column:
                tag = values[column[name]]
                if tag and tag != UNCLASSIFIED_TAG and str(tag) not in entry["tags"]:
                    entry["tags"].append(str(tag))
        entry["evidence"].append(EvidenceRef(
            source_uri=file_uri(path), locator=f"Feedback_Explorer!row {row_number}",
            record_id=str(record_id), sheet_name="Feedback_Explorer", row_number=row_number,
            quote=str(text).strip(),
        ))
    workbook.close()
    posts = [RawPost(
        source_platform="BMW_Workbook", source_url=file_uri(path),
        thread_title=f"{entry['platform']} customer feedback {record_id}", post_body=entry["text"],
        timestamp=None, target_platform=entry["platform"], collected_at=now(),
        source_record_id=record_id, scope_layer="variable_later",
        region=COUNTRY_REGION.get(entry["country"], "RoW") if entry["country"] else "Unknown",
        country=entry["country"], feedback_types=entry["types"], original_tags=entry["tags"],
        bmw_labels=entry["labels"],
        evidence=entry["evidence"], credibility_weight=1.25,
    ) for record_id, entry in grouped.items()]
    return posts, {
        "source": path.name, "kind": "Feedback_Explorer", "tagged_rows": tagged_rows,
        "distinct_feedback_ids": len(posts), "duplicates_collapsed": tagged_rows - len(posts),
        "checksum_sha256": file_checksum(path),
    }


def _pdf_publication_timestamp(text: str) -> str | None:
    match = re.search(r"(?:Ausgabe\s+\d+,\s*)?(\d{2})\.\s*(\d{2})\.\s*(\d{4})", text)
    if not match:
        return None
    day, month, year = map(int, match.groups())
    return datetime(year, month, day, tzinfo=timezone.utc).isoformat()


def ingest_option_list(path: str | Path) -> tuple[list[RawPost], dict]:
    path = Path(path)
    platform = path.name.split("_", 1)[0]
    if platform not in {"F70", "G60", "G70"}:
        raise ValueError(f"Cannot derive supported platform from {path.name}")
    reader = PdfReader(path)
    texts = [(page.extract_text(extraction_mode="layout") or "").strip() for page in reader.pages]
    publication = _pdf_publication_timestamp("\n".join(texts[:3]))
    posts = []
    for page_number, page_text in enumerate(texts, start=1):
        if not page_text:
            continue
        posts.append(RawPost(
            source_platform="BMW_PDF", source_url=file_uri(path),
            thread_title=f"{platform} OptionList page {page_number}", post_body=page_text,
            timestamp=publication, target_platform=platform, collected_at=now(),
            source_record_id=f"{platform}-OPTION-P{page_number}", scope_layer="fixed_now",
            region="EU", country="DE", evidence=[EvidenceRef(
                source_uri=file_uri(path), locator=f"PDF page {page_number}",
                record_id=f"{platform}-OPTION-P{page_number}", page_number=page_number,
                quote=page_text[:500],
            )], credibility_weight=1.5,
        ))
    return posts, {
        "source": path.name, "kind": "OptionList", "pages": len(reader.pages),
        "pages_with_text": len(posts), "publication_timestamp": publication,
        "checksum_sha256": file_checksum(path),
    }


def ingest_local_materials(material_dir: str | Path) -> tuple[list[RawPost], list[dict]]:
    material_dir = Path(material_dir)
    posts: list[RawPost] = []
    manifest: list[dict] = []
    for path in sorted(material_dir.glob("*_feedback_hackathon.xlsx")):
        records, entry = ingest_feedback_workbook(path)
        posts.extend(records)
        manifest.append(entry)
    for path in sorted(material_dir.glob("*_OptionList.PDF")):
        records, entry = ingest_option_list(path)
        posts.extend(records)
        manifest.append(entry)
    if not posts:
        raise ValueError(f"No supported Feedback_Explorer workbooks or OptionLists found in {material_dir}")
    return posts, manifest


def ingest_structured_context(material_dir: str | Path) -> dict:
    """Retain structured sales/study rows with cell-level provenance; do not invent semantics."""
    material_dir = Path(material_dir)
    output = {"sales_volumes": [], "customer_studies": []}
    sales_path = material_dir / "sales_volumes.xlsx"
    if sales_path.exists():
        workbook = load_workbook(sales_path, read_only=True, data_only=True)
        for sheet in workbook:
            rows = sheet.iter_rows(values_only=True)
            headers = [str(value) if value is not None else "" for value in next(rows)]
            for row_number, values in enumerate(rows, start=2):
                if not any(value is not None for value in values):
                    continue
                output["sales_volumes"].append({
                    "platform_sheet": sheet.title,
                    "values": {headers[index]: value for index, value in enumerate(values) if index < len(headers) and headers[index]},
                    "evidence": {"source_uri": file_uri(sales_path), "locator": f"{sheet.title}!row {row_number}", "sheet_name": sheet.title, "row_number": row_number},
                })
        workbook.close()
    study_path = material_dir / "F70_G60_G68_G70_customer_studies.xlsx"
    if study_path.exists():
        workbook = load_workbook(study_path, read_only=True, data_only=True)
        for sheet in workbook:
            for row_number, values in enumerate(sheet.iter_rows(values_only=True), start=1):
                nonempty = [{"column": index + 1, "value": value} for index, value in enumerate(values) if value is not None]
                if nonempty:
                    output["customer_studies"].append({
                        "sheet": sheet.title, "cells": nonempty,
                        "evidence": {"source_uri": file_uri(study_path), "locator": f"{sheet.title}!row {row_number}", "sheet_name": sheet.title, "row_number": row_number},
                    })
        workbook.close()
    return output
