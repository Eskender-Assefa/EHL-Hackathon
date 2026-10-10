# Verification results — 2026-10-10

Environment: Windows, PowerShell, Python 3.12.8, Node.js 24.14.0, Next.js 16.4.0.

## Python suite

Command run from `automotive_data_pipeline`:

```text
python -m unittest discover -s tests -v
```

Final result:

```text
Ran 56 tests
OK
```

There were zero failures, errors, or skips. FastAPI emitted a `StarletteDeprecationWarning` about its current test-client compatibility layer; it did not affect execution.

Covered behavior includes:

- source-domain allowlists and rendered-page extraction;
- Async PRAW submission/comment metadata, missing-credential handling, and source failure isolation;
- LLM HTTP success, 401 behavior, 429 retry, 500 exhaustion, malformed JSON, and invalid schema responses;
- exact aspect splitting, sentiment polarity, taxonomy validation, and low-effort filtering;
- verbatim-first classification for C07 software, C08 physical display placement, and strict C04 safety evidence;
- prevention of record-level workbook tags contaminating unrelated split fragments;
- distinct workbook-ID consolidation with every original row citation preserved;
- stable per-publication IDs so split web/Reddit aspects do not inflate source volume;
- missing-data handling, stable identifiers, and platform-aware deduplication;
- velocity and deterministic priority calculation with complete inputs;
- labelled static-evidence proxy scoring when velocity, causality, or ROI is absent;
- professional action titles and `Global / Unassigned` regional normalization;
- multi-source aggregation, round-robin evidence, and competitor/customer metric separation;
- `run-all` merging of local material with saved external raw data;
- regional-conflict derivative branching and fixed-baseline separation;
- audit-chain tamper detection and PM rationale enforcement;
- labelled Neue Klasse synthetic trigger;
- PowerPoint generation and external-source reservation in its 20 detail slides.

The LLM HTTP tests use a mocked transport. Collector runtime tests use mocked external APIs. A six-source integration fixture proves that BMW workbook, Reddit, BIMMERPOST, Bimmerforums, German Car Forum, and Mercedes/BYD-style competitor citations remain in `requirements.json` and the generated `.pptx`.

## Full local plus live-competitor run

Commands:

```text
python -m bmw_signals.cli collect --config sources.example.json --output output/live-sources
python -m bmw_signals.cli run-all --material-dir ../material --external-raw output/live-sources/raw.json --engine rules --output output/revision-v6
python -m bmw_signals.cli build-requirements --signals output/revision-v6/signals.json --output output/revision-v8
```

The collection command returned a nonzero status because some configured sources were audited as unavailable; it still wrote the successful BYD record and complete collection audit. `run-all` completed successfully.

| Measure | Result |
| --- | ---: |
| Feedback workbook tag rows | 13,771 |
| Distinct feedback IDs | 10,128 |
| Repeated tag rows collapsed for counting | 3,643 |
| OptionList pages | 78 |
| Live competitor pages | 1 |
| Total raw records | 10,207 |
| Accepted raw records | 10,207 |
| Quarantined raw records | 0 |
| Discrete aspect signals | 24,988 |
| Fixed baseline signals | 78 |
| Requirement candidates | 282 |
| Requirements with competitor evidence | 7 |
| Regional conflicts | 43 |
| Critical-review safety candidates | 9 |
| High-priority candidates | 125 |
| Medium-priority candidates | 93 |
| Low-priority candidates | 55 |
| Unscored candidates | 0 |
| Static-evidence proxy scores | 282 |
| Presentation regions marked `Unknown` | 0 |
| Sales context rows | 12 |
| Customer-study rows | 1,003 |

Requirement coverage by taxonomy:

```text
C01 37   C02 31   C03 20   C04 13   C05 32
C06 22   C07 53   C08 21   C09 18   C10 35
```

The raw source mix was 10,128 BMW workbook records, 78 BMW PDF pages, and one live official BYD release. The BYD page produced 35 discrete aspects and seven benchmark requirement topics. Every such requirement records exactly one `Competitor_Web` publication, confirming that aspect splitting did not inflate source volume.

The three OptionList publication dates were recovered correctly:

```text
F70  2026-05-28
G60  2026-06-22
G70  2026-05-28
```

`pypdf` warned that rotated text on some pages may be incomplete. The pipeline retained page-level provenance. This remains a material limitation for detailed catalogue fact extraction.

The supplied feedback workbooks contain no event timestamp and provide neither validated take-rate causality nor competitor two-year ROI. The pipeline keeps those inputs absent and exposes them as blindspots. For static review it assigns a labelled proxy score equal to normalized mean absolute sentiment severity multiplied by logarithmically normalized distinct source volume. This produces useful ranking without representing missing business inputs as observed evidence.

The strict classifier reduced C04 from the original 24 groups to 13. The resulting distribution contains 53 C07 software requirements and 21 C08 interior-design requirements. No generated title uses the old `Improve [keyword] for [model] customers` template.

## PowerPoint

Command:

```text
python -m bmw_signals.cli export-deck --requirements output/revision-v8/requirements.json --destination output/revision-v8/BMW_board_deck.pptx
```

Result: exit code `0`, 81,891-byte `.pptx`, 22 slides, and a successful `python-pptx` reopen. Microsoft PowerPoint rendered all 22 slides to 1600×900 PNG files. The title, overview, and detail slides, including the long BYD citation slide, were visually inspected for wrapping, clipping, contrast, padding, evidence readability, and long-title handling. The deck contains the live `media.byd.com` citation and contains neither `Unscored` nor `Region: Unknown`.

## Next.js cockpit

Command:

```text
npm.cmd run build
```

Result: exit code `0`. The production build compiled, passed TypeScript, generated three static pages, and prerendered `/` plus `/_not-found`. `npm audit` reported zero vulnerabilities.

## Regression probes

Command:

```text
$env:PYTHONPATH = (Get-Location).Path
python tests/probe_limitations.py
```

Observed result:

```text
invalid_then_valid_record: invalid record quarantined; later valid record accepted
same_body_different_platform: G60 and G70 records both accepted
short_complaint: zero signals; discarded below low-effort threshold
```

## Live external-source result

The checked-in [`sources.example.json`](sources.example.json) was run through Chromium. The official BYD media release returned HTTP 200 and yielded one 7,411-character competitor record dated `2026-03-05T00:00:00+00:00`. BIMMERPOST timed out at its access-verification page, German Car Forum and the Mercedes-Benz Group page rejected automated access, and all four Reddit searches were marked `collection_skipped / MissingCredentials`. The collector produced a structured audit for all seven unavailable source jobs and did not bypass access controls.

This run proves live BYD ingestion and end-to-end citation in the deck. It does not claim that Reddit, BIMMERPOST, German Car Forum, or Mercedes content was collected in this environment. Their aggregation behavior is verified with the automated six-source fixture; a deployment with Reddit API credentials and source-approved forum access must rerun `run-all` to place their real URLs in `requirements.json` and the board deck.
