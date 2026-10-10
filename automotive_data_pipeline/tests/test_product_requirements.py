import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from pptx import Presentation

from bmw_signals.audit import append_event, verify_audit
from bmw_signals.cli import _write_requirements
from bmw_signals.cockpit import create_app
from bmw_signals.deck import export_deck
from bmw_signals.local_ingestion import _pdf_publication_timestamp, ingest_feedback_workbook
from bmw_signals.models import EvidenceRef, FilteredSignal, ScoringInputs
from bmw_signals.pipeline import RuleBasedEvaluator, process
from bmw_signals.requirements import build_requirements
from test_pipeline import post


def signal(identifier, *, region="EU", sentiment=-70, timestamp=None, topic="Touchscreen", scope="variable_later"):
    return FilteredSignal(
        signal_id=identifier, source_platform="BMW_Workbook", source_url="bmw-file://feedback.xlsx",
        timestamp=timestamp, target_platform="G60", taxonomy_category="C07",
        cleaned_verbatim_text=f"Evidence {identifier}", sentiment_score=sentiment,
        confidence=0.8, topic=topic, requirement_statement="Improve touchscreen usability for G60 customers.",
        scope_layer=scope, region=region, source_record_id=identifier,
        evidence=[EvidenceRef(source_uri="bmw-file://feedback.xlsx", locator=f"Feedback_Explorer!row {identifier}", record_id=identifier)],
    )


class LocalIngestionTests(unittest.TestCase):
    def test_feedback_ids_are_collapsed_with_all_row_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "G60_feedback_hackathon.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Feedback_Explorer"
            sheet.append(["ID", "Source", "Brand", "Sales Description", "Country", "Derivate (e-code)", "Engine Type", "Feedback Type", "Customer Feedback", "Vfc level2 3 Name", "Vfc level2 Name", "Vfc level3 Name"])
            sheet.append(["G60-1", "A", "BMW", "5", "US", "G60", "BEV", "Likes", "Seats are good but touchscreen is slow.", "Seats", "Seats", "Like"])
            sheet.append(["G60-1", "A", "BMW", "5", "US", "G60", "BEV", "Difficult to Use", "Seats are good but touchscreen is slow.", "Touch screen", "Touch screen", "Not friendly"])
            sheet.append(["G60-2", "A", "BMW", "5", "GB", "G60", "ICE", "Defect", "Software crashes every morning.", "Software", "Software", "Malfunction"])
            workbook.save(path)
            posts, manifest = ingest_feedback_workbook(path)
        self.assertEqual(len(posts), 2)
        self.assertEqual(manifest["tagged_rows"], 3)
        self.assertEqual(manifest["duplicates_collapsed"], 1)
        self.assertEqual(len(posts[0].evidence), 2)
        self.assertEqual(posts[0].feedback_types, ["Likes", "Difficult to Use"])
        self.assertEqual(posts[0].region, "US")
        self.assertEqual(posts[1].region, "EU")

    def test_optionlist_date_with_pdf_spacing(self):
        self.assertEqual(_pdf_publication_timestamp("Ausgabe 2, 22.06. 2026"), "2026-06-22T00:00:00+00:00")


class RuleEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_mixed_feedback_is_split_and_scored(self):
        raw = post(post_body="The seats are comfortable, but the touch screen menu is terrible.")
        signals, audit = await process([raw], RuleBasedEvaluator())
        self.assertEqual([item.taxonomy_category for item in signals], ["C05", "C07"])
        self.assertGreater(signals[0].sentiment_score, 0)
        self.assertLess(signals[1].sentiment_score, 0)
        self.assertEqual(audit[0]["status"], "accepted")

    async def test_duplicate_scope_includes_platform_and_valid_record_wins(self):
        evaluator = RuleBasedEvaluator()
        valid = post(source_record_id="same")
        other_platform = post(source_record_id="same", target_platform="G70")
        signals, audit = await process([post(source_record_id="same", target_platform=None), valid, other_platform], evaluator)
        self.assertEqual({item.target_platform for item in signals}, {"G60", "G70"})
        self.assertEqual([item["status"] for item in audit], ["quarantined", "accepted", "accepted"])


class RequirementTests(unittest.TestCase):
    def test_missing_inputs_remain_unscored(self):
        requirements, baseline = build_requirements([signal("A"), signal("B")])
        self.assertFalse(baseline)
        self.assertEqual(requirements[0].review_band, "Unscored")
        self.assertIsNone(requirements[0].priority_score)
        self.assertEqual(len(requirements[0].blindspots), 3)

    def test_complete_inputs_produce_deterministic_priority(self):
        signals = [
            signal("A", timestamp="2026-09-01T00:00:00Z"),
            signal("B", timestamp="2026-09-15T00:00:00Z"),
            signal("C", timestamp="2026-10-01T00:00:00Z"),
        ]
        inputs = {"G60|C07|touchscreen": ScoringInputs(sales_causality_score=20, competitor_roi_score=10, effort_class="software_ux")}
        requirements, _ = build_requirements(signals, inputs)
        item = requirements[0]
        self.assertIsNotNone(item.velocity_multiplier)
        self.assertIsNotNone(item.priority_score)
        self.assertEqual(item.effort_penalty, 0)
        self.assertGreater(item.priority_score, 30)

    def test_regional_conflict_creates_variants(self):
        signals = [signal("EU1", region="EU", sentiment=-90), signal("EU2", region="EU", sentiment=-80),
                   signal("CN1", region="CN", sentiment=70), signal("CN2", region="CN", sentiment=60)]
        requirements, _ = build_requirements(signals)
        self.assertEqual({item.region_variant for item in requirements}, {"EU", "CN"})
        self.assertTrue(all(item.regional_conflict for item in requirements))
        self.assertTrue(all(item.confidence_label == "Uncertain / Conflict Flag" for item in requirements))

    def test_fixed_baseline_does_not_become_customer_requirement(self):
        requirements, baseline = build_requirements([signal("P1", scope="fixed_now")])
        self.assertFalse(requirements)
        self.assertEqual(len(baseline), 1)


class AuditCockpitDeckTests(unittest.TestCase):
    def test_audit_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "audit.jsonl"
            append_event(path, actor="AI", requirement_id="REQ1", action="Propose", field_changed="requirement", previous_value=None, new_value="x", justification="fixture")
            self.assertEqual(len(verify_audit(path)), 1)
            path.write_text(path.read_text(encoding="utf-8").replace('"new_value": "x"', '"new_value": "tampered"'), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_audit(path)

    def test_decisions_require_rationale_and_append_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            requirements, _ = build_requirements([signal("A"), signal("B")])
            (directory / "requirements.json").write_text(json.dumps([item.model_dump() for item in requirements]), encoding="utf-8")
            client = TestClient(create_app(directory))
            identifier = requirements[0].requirement_id
            self.assertEqual(client.post(f"/api/requirements/{identifier}/decision", json={"actor": "PM", "action": "Reject", "justification": ""}).status_code, 400)
            response = client.post(f"/api/requirements/{identifier}/decision", json={"actor": "PM", "action": "Postpone", "justification": "Await dated evidence"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["requirement"]["status"], "Postponed")
            self.assertEqual(client.get("/api/audit/verify").json()["events"], 1)

    def test_powerpoint_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            requirements, _ = build_requirements([signal("A"), signal("B")])
            destination = export_deck(requirements, Path(temporary) / "deck.pptx")
            self.assertTrue(destination.exists())
            self.assertGreaterEqual(len(Presentation(destination).slides), 3)

    def test_manual_trigger_creates_labelled_neue_klasse_scenario(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "requirements.json").write_text("[]", encoding="utf-8")
            (directory / "signals.json").write_text("[]", encoding="utf-8")
            client = TestClient(create_app(directory))
            response = client.post("/api/trigger-synthetic", json={"actor": "PM", "seed": 7, "justification": "Demo regional branching"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("hypothetical", response.json()["warning"])
            generated = client.get("/api/requirements").json()
            self.assertTrue(generated)
            self.assertEqual({item["target_platform"] for item in generated}, {"Neue_Klasse"})
            self.assertTrue(all(any("synthetic" in warning.lower() for warning in item["warnings"]) for item in generated))

    def test_pipeline_recompute_preserves_pm_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            signals = [signal("A"), signal("B")]
            generated = _write_requirements(directory, signals)
            client = TestClient(create_app(directory))
            response = client.post(f"/api/requirements/{generated[0].requirement_id}/decision", json={"actor": "PM", "action": "Approve", "justification": ""})
            self.assertEqual(response.status_code, 200)
            _write_requirements(directory, signals)
            saved = json.loads((directory / "requirements.json").read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["status"], "Approved")
