# Gap analysis against the comprehensive product requirements

Assessment date: 2026-10-10. Scope: `automotive_data_pipeline`, the supplied repository material, and the live source check documented in `TEST_RESULTS.md`.

## Original implementation verdict

The original folder emitted JSON excerpts with a C01-C10 code. It lacked local-file ingestion, sentiment, velocity, priority scoring, evidence locations, confidence, scope layers, PM workflow, regional conflict handling, audit integrity, and professional PowerPoint output. Its web collector was configurable, but there was no path that merged collected records into the local requirement matrix.

## Current requirement coverage

| Requirement | Status | Implementation and honest boundary |
| --- | --- | --- |
| C01-C10 taxonomy | Implemented | One strict primary category plus optional secondary tags. Verbatim-first rules reserve C04 for explicit safety evidence. |
| BMW files plus external ingestion | Implemented | `run-all` merges Feedback Explorer, OptionLists, Reddit, supported forums, and official Mercedes/BYD pages before one processing step. Live access still depends on credentials and source controls. |
| Aspect splitting and sentiment | Implemented | Exact excerpts; `[-100,+100]`; deterministic rules or LLM. Stable source-record IDs keep multiple aspects from inflating publication counts. |
| Signal threshold | Implemented | Distinct-record frequency × credibility × absolute severity. Upvotes and optional author karma affect bounded credibility. |
| 30-day velocity | Implemented for dated sources | Workbook feedback has no dates, so its velocity remains unknown. |
| Deterministic priority | Implemented | Complete formula uses urgency + sales `[0,30]` + ROI `[0,25]` − effort `[0,50]`. Static exports use a labelled severity-volume proxy when business inputs are absent. |
| Official priority bands | Implemented | Critical review, High, Medium, and Low. Static evidence no longer produces uniform `Unscored` output. |
| Evidence grid | Implemented | Workbook sheet/row/ID, PDF page, or original URL. Requirement and deck evidence is selected round-robin by source. |
| Competitor metric separation | Implemented | Competitor facts support benchmarking but do not change customer sentiment, demand counts, or velocity. |
| Three scope layers | Implemented | Fixed, variable, and hypothetical records remain separate. |
| Multiple-tag inflation prevention | Implemented | 13,771 tagged rows collapse to 10,128 feedback IDs while every source row remains cited. |
| Professional requirement titles | Implemented | Titles follow `[Model] (Cxx): [actionable solution]`; generic keyword titles are removed. |
| PM cockpit | Implemented | Next.js and FastAPI support Approve, Edit, Reject, and Postpone. |
| Mandatory override justification | Implemented | Edit, Reject, and Postpone fail without rationale. |
| Honesty and uncertainty | Implemented | EHI, confidence labels, warnings, input blindspots, conflict branches, and explicit score basis. Groundedness uses evaluator confidence rather than deployed DeBERTa NLI. |
| Immutable audit | Partially implemented | The application writes an append-only SHA-256 hash chain and detects tampering. Regulatory immutability still requires WORM or ledger infrastructure. |
| PowerPoint export | Implemented | 16:9 executive deck, proxy score fallback, source counts, wrapped URLs, high-contrast evidence panels, and a reserved detail slot for collected external evidence. |
| Manual synthetic trigger | Implemented | Produces labelled hypothetical Neue Klasse EU/CN signals and inputs. |
| Regional derivative branching | Implemented | A sentiment spread of at least 60 with two records per region creates variants. |
| Out-of-scope guardrails | Implemented | Homologation/certification and deep component-engineering phrases are filtered. |

## Verified supplied-data plus live-BYD result

- 10,128 distinct workbook feedback records and 78 OptionList pages;
- one live official BYD competitor release;
- 10,207 raw records and 24,988 aspect signals;
- 282 requirement candidates across every category;
- category distribution: C01 37, C02 31, C03 20, C04 13, C05 32, C06 22, C07 53, C08 21, C09 18, C10 35;
- review bands: 9 Critical review, 125 High, 93 Medium, 55 Low, and zero Unscored;
- seven requirements with BYD evidence, each counting the long BYD page once;
- 43 regional conflicts and zero presentation regions named `Unknown`;
- a 22-slide, 81,891-byte deck containing the live BYD URL.

## Remaining data and deployment gaps

1. Workbook feedback has no event timestamps, so it cannot support rolling 30-day acceleration.
2. The sales workbook contains annual regional volumes rather than experimental take-rate causality.
3. No supplied source establishes a finance-approved competitor two-year ROI.
4. There is no observed Neue Klasse customer-feedback file; the cockpit scenario remains explicitly synthetic.
5. Customer-study rows retain cell provenance but are not semantically normalized into the priority formula.
6. PDF extraction reports rotated-text warnings and some glyph corruption; production catalogue parsing needs layout/OCR review.
7. The live BYD page succeeded. BIMMERPOST timed out at access verification, German Car Forum and Mercedes rejected automation, and Reddit credentials were absent. Those sources were audited, not fabricated or bypassed.
8. Real LLM/NLI semantic accuracy still needs an authorized endpoint, labelled evaluation set, and human review.
