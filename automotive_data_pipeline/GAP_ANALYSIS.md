# Gap analysis against the comprehensive product requirements

Assessment date: 2026-10-10. Scope: `automotive_data_pipeline` and the supplied repository material.

## Original implementation verdict

The original folder did not produce a comprehensive product-requirements list. It produced only JSON excerpts with a C01-C10 code. It had no local-file ingestion, sentiment, velocity, priority formula, evidence locations, confidence, scope layers, PM workflow, regional conflict handling, or audit integrity. Its deduplication also ran before metadata validation and used body text alone, so an invalid record could suppress a valid copy and identical text across two platforms could lose one platform.

No live source configuration, Reddit credentials, LLM credentials, or collected dataset was present. Therefore the web code was a configurable collector framework, not evidence that external scraping had succeeded.

## Current requirement coverage

| Requirement | Status | Implementation and honest boundary |
| --- | --- | --- |
| C01-C10 taxonomy | Implemented | Strict Pydantic literal; one primary category and optional secondary tags. |
| BMW files plus external ingestion | Implemented | `Feedback_Explorer`, OptionLists, sales/study context, Async PRAW, Playwright/BeautifulSoup. Live selectors/credentials still require deployment configuration. |
| Aspect splitting and sentiment | Implemented | Exact excerpts; `[-100,+100]`; deterministic rules or LLM. Rules engine is a baseline, not production NLI. |
| Signal threshold | Implemented | Distinct-ID frequency × credibility × absolute severity. Upvotes and optional author karma influence bounded credibility. |
| 30-day velocity | Implemented for dated sources | Supplied feedback workbooks contain no dates; their velocity is correctly unknown. |
| Deterministic priority | Implemented | Urgency + sales `[0,30]` + ROI `[0,25]` − effort `[0,50]`; missing components yield `Unscored`. |
| Official priority bands | Implemented | Critical review, High, Medium, Low, Unscored; severe C04 evidence escalates to review. |
| Evidence grid | Implemented | Workbook sheet/row/ID, PDF page, or original URL on every requirement. |
| Three scope layers | Implemented | Fixed, variable, and hypothetical records stay separate. |
| Multiple-tag inflation prevention | Implemented | 13,771 tagged rows collapse to 10,128 feedback IDs while every original row citation/tag remains. |
| PM cockpit | Implemented | Next.js cards and FastAPI decisions: Approve/Edit/Reject/Postpone. |
| Mandatory override justification | Implemented | Edit/Reject/Postpone fail without rationale. |
| Honesty and uncertainty | Implemented | EHI, confidence labels, warnings, missing-data blindspots, conflict branches. Groundedness currently uses evaluator confidence, not a DeBERTa NLI deployment. |
| Immutable audit | Partially implemented | Application writes append-only SHA-256 hash-chain and detects tampering. Regulatory immutability requires WORM/ledger infrastructure. |
| PowerPoint export | Implemented | `python-pptx` CLI and API endpoint. |
| Manual synthetic trigger | Implemented | Background endpoint produces labelled hypothetical Neue Klasse EU/CN signals and scenario inputs. |
| Regional derivative branching | Implemented | Sentiment spread of 60+ with at least two records per region produces separate region variants. |
| Out-of-scope guardrails | Implemented | Homologation/regulatory certification and deep component-engineering phrases are filtered. |

## Actual supplied-data result

The verified deterministic local run processed:

- 13,771 workbook tag rows;
- 10,128 distinct customer-feedback IDs after correct ID-level consolidation;
- 78 OptionList PDF pages;
- 12 sales-volume rows and 1,003 customer-study rows retained with provenance;
- 10,206 total raw analysis records;
- 24,953 discrete aspect signals;
- 78 fixed baseline signals kept out of customer-demand ranking;
- 238 requirement candidates spanning all ten C01-C10 categories;
- 29 candidates with detected regional conflict;
- 17 C04 candidates containing at least one severe negative safety signal escalated to Critical review;
- 221 remaining candidates left Unscored because dated velocity, validated take-rate causality, and competitor ROI are absent.

This is the desired honest behavior. Assigning complete priorities from these files alone would fabricate three required inputs.

## Remaining data gaps

1. The feedback workbooks have no event timestamps, so they cannot support rolling 30-day acceleration.
2. The sales workbook contains annual regional volumes, not experimental take-rate causality.
3. No supplied source establishes competitor two-year project ROI.
4. There is no observed Neue Klasse customer-feedback file in the repository. The demo trigger is synthetic and labelled as such.
5. Customer-study rows are ingested with cell provenance but not yet semantically normalized into the priority formula.
6. PDF extraction reports rotated-text warnings and some German glyph corruption. Page provenance is preserved, but production-grade catalogue parsing needs layout/OCR review.
7. No live external scrape or real LLM request could be verified without source configuration and credentials.
8. The Next.js client source is implemented; a dependency install/build must be run in the deployment environment.
