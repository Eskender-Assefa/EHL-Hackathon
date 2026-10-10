# BMW evidence-to-requirement pipeline

This folder turns BMW source material, customer feedback, web/forum posts, competitor pages, and clearly labelled synthetic scenarios into evidence-linked product-requirement candidates. It follows the supplied BMW baseline rule: fixed catalogue facts, changing customer requirements, and hypothetical competitor/synthetic scenarios stay separate.

The pipeline supports F70, G60, G70, and Neue_Klasse and maps every extracted aspect to exactly one C01-C10 primary category. It preserves secondary tags without using them to inflate mention counts.

## Verified project status

The repository was tested with the supplied BMW files using the deterministic rules engine. The latest full run produced these exact results:

| Result | Observed value |
| --- | ---: |
| Workbook tag rows read | 13,771 |
| Distinct feedback IDs | 10,128 |
| Deduplicated raw records, including 78 fixed baseline pages and one live BYD release | 10,207 |
| Discrete aspect signals | 24,988 |
| Product requirements across all C01-C10 categories | 282 |
| Regional conflict flags | 43 |
| Priority bands | 9 Critical review; 125 High; 93 Medium; 55 Low |
| `Unscored` requirements | 0 |
| Sales-volume context rows | 12 |
| Customer-study context rows | 1,003 |
| Python tests | 56 passed |
| Frontend validation | Next.js production build passed; 0 npm audit vulnerabilities |
| PowerPoint export | 22 slides; 81,891 bytes; includes the live BYD URL |

All 282 observed requirements lack at least one complete dated 30-day history, validated sales-causality input, or competitor two-year ROI input. They receive a clearly labelled static-evidence proxy score based only on absolute sentiment severity and distinct source volume, while every missing business input remains visible as a blindspot. Safety escalation remains independent of the proxy score. Seven benchmark requirements cite the collected BYD release, and the deck reserves a detail slide for available external evidence even when it ranks below the top 20. See [TEST_RESULTS.md](TEST_RESULTS.md) for the commands, limitations, and detailed output.

## Classification by BMW labels

Workbook rows that carry BMW labels are classified from those labels, not from words in the comment: `Feedback Type` decides polarity and `Vfc level2 Name` is the topic. [`bmw_signals/bmw_topics.py`](bmw_signals/bmw_topics.py) maps the 225 BMW topics to C01-C10; that table is a project judgement and should be reviewed. Keyword rules still cover unlabelled rows and web sources, and requirements built from them carry a warning.

The CLI applies three gates to observed workbook feedback: 15 distinct respondents before a topic is proposed (`--min-respondents`), 15 per region before a regional conflict is flagged, and three defect reports with negative average sentiment before a C04 topic is escalated. Respondents left out are counted in `exclusions.json`. The static priority proxy counts complaints only, so a topic customers mostly praise is worded as a strength to preserve and does not rank as high priority.

The files in `output/published` predate this change and still reflect keyword classification. Regenerate them with `run-all` and the saved external raw file before quoting their numbers.

## Fastest complete demo

From the repository root, build the evidence set and start the API:

```powershell
cd automotive_data_pipeline
python -m pip install -e .
python -m bmw_signals.cli run-local --material-dir ../material --engine rules --output output/local
python -m bmw_signals.cli serve --data-dir output/local --port 8000
```

In a second PowerShell terminal, start the cockpit:

```powershell
cd automotive_data_pipeline/frontend
npm.cmd install
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

Open `http://localhost:3000`. Select F70, G60, or G70 to inspect requirements derived from the supplied evidence. The cockpit starts on Neue_Klasse; click **Do It Now** to create the clearly labelled hypothetical EU/CN demonstration data for that platform.

The end-to-end data path is:

```text
BMW workbooks/PDFs + configured web sources
    -> provenance-preserving raw records
    -> deduplicated, single-aspect C01-C10 signals
    -> thresholded and scored product requirements
    -> PM decisions + hash-chained audit log + PowerPoint export
```

A canonical copy of the verified generated results is committed under [`output/published`](output/published). It contains the requirement matrix, evidence manifest, structured context, collection and processing audits, fixed baselines, immutable audit events, run summary, and board deck. Raw records and aspect-level signals remain reproducible through `run-all`; they are omitted from Git because the two JSON files add about 88 MB and contain the same source evidence expanded at record level.

## What works

The implementation now provides:

- asynchronous Reddit collection with score and optional author-karma credibility inputs;
- rendered web-page collection for BIMMERPOST, Bimmerforums, German Car Forum, and official Mercedes-Benz/BYD pages;
- automated ingestion of all supplied `Feedback_Explorer` workbooks and F70/G60/G70 OptionList PDFs;
- row-level, page-level, and URL-level evidence citations;
- one-feedback-ID counting even when a workbook repeats that ID across tag rows;
- exact-excerpt aspect splitting, C01-C10 classification, sentiment from -100 to +100, and source credibility weighting;
- verbatim-first category precedence that keeps digital menus and bugs in C07, physical display placement in C08, and reserves C04 for explicit safety evidence;
- professional requirement titles in the form `G60 (C07): Flatten the iDrive menu hierarchy...`;
- a deterministic offline rules engine and an optional chat-completions LLM engine;
- 30-day current/prior mention windows and velocity multiplier for dated observations;
- deterministic priority scoring, official review bands, evidence/honesty scores, blindspots, and regional conflict branches;
- a FastAPI PM decision API plus a Next.js cockpit for Approve, Edit, Reject, and Postpone actions;
- mandatory rationale for Edit, Reject, and Postpone;
- a chronological SHA-256 hash-chained audit log;
- a manual, explicitly hypothetical Neue Klasse EU/CN scenario trigger;
- PowerPoint board-deck export.

External evidence follows the same processing and requirement-aggregation path as workbook evidence. Citations are selected round-robin by source so a high-volume workbook cannot crowd Reddit, forum, or competitor URLs out of an evidence box. Competitor records enrich benchmark support but do not increase customer mention counts or change customer sentiment. A stable source-record ID ensures that splitting one long page into many aspects still counts it as one publication.

See [GAP_ANALYSIS.md](GAP_ANALYSIS.md) for the requirement-by-requirement assessment and [TEST_RESULTS.md](TEST_RESULTS.md) for exact observed results.

## Scope separation

| Layer | Meaning | Examples |
| --- | --- | --- |
| `fixed_now` | Versioned published baseline fact | OptionList page text, price/equipment/specification evidence |
| `variable_later` | Observed customer requirement signal | Feedback workbook ID, Reddit comment, forum post |
| `hypothetical_later` | Scenario or competitor benchmark | Mercedes/BYD feature, synthetic Neue Klasse showroom scenario |

Fixed OptionList facts are written to `fixed_baseline_signals.json`; they do not automatically become customer requirements. Competitor facts never become BMW capabilities. Synthetic records use `synthetic://` citations, low confidence, and an explicit warning.

## Calculation contract

Every mixed comment is split into exact contiguous excerpts. Each excerpt receives one primary category, optional secondary tags, a polarity score in `[-100, 100]`, and confidence in `[0, 1]`. Forum complaints shorter than 15 words are discarded when they contain only one negative aspect. Curated BMW workbook records are retained.

Repeated workbook rows are merged by their original `ID`. All row citations and source tags are preserved, but frequency and priority count that ID once per requirement topic.

The requirement signal threshold is:

```text
signal_threshold = distinct_feedback_count
                   × mean_source_credibility
                   × mean_absolute_sentiment_severity
```

The default threshold is `0.5`. Reddit credibility starts lower than curated BMW evidence, then receives bounded boosts from upvotes and author karma when available.

For dated data:

```text
V = min(3.0, 1 + log10(1 + current_30d_mentions / max(previous_30d_mentions, 1)))
customer_urgency = max(0, -average_sentiment / 100) × 100 × V
priority = customer_urgency + sales_causality[0..30]
           + competitor_roi[0..25] - effort_penalty[0..50]
```

Effort defaults are `software_ux=0`, `interior_trim=5`, `electronics_thermal=15`, and `body_platform=50`. Inputs can be overridden in a scoring-input JSON file.

When any required business input is absent, the static ranking fallback is:

```text
severity = mean(abs(signal_sentiment)) / 100
volume = min(1, log(1 + distinct_source_count) / log(21))
static_priority_proxy = 100 × severity × volume
```

The output marks this with `priority_score_basis="static_evidence_proxy"`; it does not substitute fabricated velocity, causality, or ROI values. Complete inputs use `priority_score_basis="complete_formula"`. Severe negative C04 evidence is escalated to `Critical review`. Bands are Critical review `>=85`, High `>=60`, Medium `>=30`, and Low `<30`.

The Evidence & Honesty Index is:

```text
EHI = 100 × clamp(0.55 × groundedness
                  + 0.45 × logarithmic_evidence_volume
                  - 0.30 × regional_conflict_penalty, 0, 1)
```

The rules engine uses its classifier confidence as the groundedness proxy. This is not a DeBERTa/NLI entailment score. Use the LLM/NLI integration and human sampling before production decisions.

## Install

From the repository root:

```powershell
cd automotive_data_pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m playwright install chromium
```

For Reddit, set `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT`. For the LLM engine, set `LLM_ENDPOINT`, `LLM_API_KEY`, and `LLM_MODEL`. Do not commit credentials.

## Run the supplied BMW data

The complete deterministic local run needs no API credentials:

```powershell
python -m bmw_signals.cli run-local --material-dir ../material --engine rules --output output/local
```

This writes:

- `raw.json`: deduplicated source records with scope, country/region, original tags, scores, and evidence;
- `source_manifest.json`: source checksums, row/page totals, and deduplication counts;
- `structured_context.json`: sales-volume and customer-study rows with cell-level provenance;
- `signals.json`: discrete C01-C10 aspects with sentiment, confidence, credibility, and citations;
- `processing_audit.json`: accepted, discarded, and quarantined source outcomes;
- `fixed_baseline_signals.json`: OptionList-derived fixed baseline pages;
- `requirements.json`: thresholded requirements, formula inputs, priority band, EHI, warnings, blindspots, and evidence;
- `audit.jsonl`: hash-chained initial proposal events.

The offline rules engine is deterministic and useful for a repeatable demo. For stronger semantic splitting and requirement wording:

```powershell
python -m bmw_signals.cli process --input output/local/raw.json --engine llm --output output/llm
python -m bmw_signals.cli build-requirements --signals output/llm/signals.json --output output/llm
```

## Collect web and Reddit data

Create a source configuration such as:

```json
{
  "concurrency": 3,
  "reddit": [
    {"subreddit": "BMW", "query": "F70", "target_platform": "F70", "limit": 25},
    {"subreddit": "electricvehicles", "query": "BMW Neue Klasse", "target_platform": "Neue_Klasse", "limit": 25}
  ],
  "pages": []
}
```

Then run:

```powershell
python -m bmw_signals.cli collect --config sources.json --output output/web
```

To ingest local files and external sources in one requirement matrix and deck input, use either live collection or previously saved raw files:

```powershell
python -m bmw_signals.cli run-all --material-dir ../material --config sources.json --engine rules --output output/all-sources
# or, after a separate collection run
python -m bmw_signals.cli run-all --material-dir ../material --external-raw output/web/raw.json --engine rules --output output/all-sources
python -m bmw_signals.cli export-deck --requirements output/all-sources/requirements.json --destination output/all-sources/BMW_board_deck.pptx
```

[`sources.example.json`](sources.example.json) contains r/BMW, r/electricvehicles, BIMMERPOST, German Car Forum, Mercedes-Benz, and BYD examples. Page entries require `source_platform`, `url`, `post_selector`, and `body_selector`. Optional selectors cover title, timestamp, a timezone-aware publication fallback, score, permalink, and wait target. Dates without a timezone need `timestamp_timezone`. Forum selectors must be verified against the current site DOM. The collector respects login/CAPTCHA boundaries and reports failures; it does not bypass access controls. Missing Reddit credentials are recorded as `collection_skipped` instead of aborting local processing.

## Add validated scoring inputs

Keys use `platform|category|normalized_topic`:

```json
{
  "G60|C07|touchscreen": {
    "sales_causality_score": 20,
    "competitor_roi_score": 12,
    "effort_class": "software_ux",
    "assumptions": ["Validated against experiment EXP-42 and finance case ROI-7."],
    "synthetic": false
  }
}
```

```powershell
python -m bmw_signals.cli build-requirements --signals output/local/signals.json --scoring-inputs scoring_inputs.json --output output/scored
```

Annual sales volumes are retained as context; they are not treated as take-rate causality. The supplied data has no competitor two-year ROI. Those values stay unknown unless explicitly supplied or generated as a synthetic scenario.

## Run the PM cockpit

Start the backend with one worker so file-backed decisions remain serialized:

```powershell
python -m bmw_signals.cli serve --data-dir output/local --port 8000
```

In another terminal:

```powershell
cd frontend
npm.cmd install
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

Open `http://localhost:3000`. The UI exposes sentiment, velocity, effort, priority, evidence, EHI, conflicts, blindspots, decisions, synthetic refresh, and deck export.

The “Do It Now” endpoint creates a deterministic hypothetical Neue Klasse EU/CN scenario plus synthetic causality/ROI inputs. It never presents these as observed evidence. Rebuild with real sources before using the output for a product decision.

The JSONL audit is append-only through the application and hash-chained so edits are detectable via `GET /api/audit/verify`. File permissions alone do not provide regulatory-grade immutability; production deployment needs WORM/object-lock storage or an append-only database ledger.

## Export a deck

```powershell
python -m bmw_signals.cli export-deck --requirements output/local/requirements.json --destination output/local/BMW_board_deck.pptx
```

The API also exposes `GET /api/export-deck`.

## Tests

```powershell
python -m unittest discover -s tests -v
$env:PYTHONPATH = (Get-Location).Path
python tests/probe_limitations.py
```

The source suite includes schema, HTTP retry, collector cleanup, workbook deduplication, aspect splitting, velocity/priority, regional branching, tamper detection, PM rationale, synthetic trigger, and PowerPoint tests.

References: [Async PRAW](https://asyncpraw.readthedocs.io/en/stable/), [Playwright](https://playwright.dev/python/docs/api/class-browsercontext), [openpyxl read-only mode](https://openpyxl.readthedocs.io/en/stable/optimized.html), [pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html), and [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/).
