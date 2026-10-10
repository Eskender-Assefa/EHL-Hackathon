# Verification results — 2026-10-10

Environment: Windows, PowerShell, Python 3.12.8, Node.js 24.14.0, Next.js 16.4.0.

## Python suite

Command run from `automotive_data_pipeline`:

```text
python -m unittest discover -s tests -v
```

Final result:

```text
Ran 47 tests in 0.511s
OK
```

There were zero failures, errors, or skips. FastAPI emitted a `StarletteDeprecationWarning` about its current test-client compatibility layer; it did not affect execution. One asyncio debug line reported a test task taking 0.313 seconds.

Covered behavior includes:

- source-domain allowlists and rendered-page extraction;
- Async PRAW submission/comment metadata and source failure isolation;
- LLM HTTP success, 401 behavior, 429 retry, 500 exhaustion, malformed JSON, and invalid schema responses;
- exact aspect splitting, sentiment polarity, taxonomy validation, and low-effort filtering;
- distinct workbook-ID consolidation with every original row citation preserved;
- missing-data handling, stable identifiers, and platform-aware deduplication;
- velocity and deterministic priority calculation with complete inputs;
- `Unscored` behavior when velocity/causality/ROI are absent;
- regional-conflict derivative branching;
- fixed-baseline separation;
- audit-chain tamper detection;
- PM decision rationale enforcement;
- labelled Neue Klasse synthetic trigger;
- PowerPoint generation.

The LLM HTTP tests use a mocked transport. Collector runtime tests use mocked external APIs. They verify control flow and schemas, not live semantic accuracy.

## Real supplied-data run

Command:

```text
python -m bmw_signals.cli run-local --material-dir ../material --engine rules --output output/final-verification
```

Exit code: `0`.

Observed outputs:

| Measure | Result |
| --- | ---: |
| Feedback workbook tag rows | 13,771 |
| Distinct feedback IDs | 10,128 |
| Repeated tag rows collapsed for counting | 3,643 |
| OptionList pages | 78 |
| Total raw records | 10,206 |
| Accepted raw records | 10,206 |
| Quarantined raw records | 0 |
| Discrete aspect signals | 24,953 |
| Fixed baseline signals | 78 |
| Requirement candidates | 238 |
| Regional conflicts | 29 |
| Critical-review safety candidates | 17 |
| Unscored candidates | 221 |
| Requirements with unknown velocity | 238 |
| Sales context rows | 12 |
| Customer-study rows | 1,003 |

Requirement coverage by taxonomy:

```text
C01 31   C02 16   C03 14   C04 24   C05 28
C06 17   C07 44   C08 20   C09 17   C10 27
```

The three OptionList publication dates were recovered correctly:

```text
F70  2026-05-28
G60  2026-06-22
G70  2026-05-28
```

`pypdf` warned that rotated text on some pages may be incomplete. The pipeline retained page-level provenance. This warning remains a material limitation for detailed catalogue fact extraction.

All 238 observed-data requirements have unknown velocity because the feedback workbooks contain no event timestamp. The 221 non-escalated candidates remain `Unscored` because the supplied data also lacks validated take-rate causality and competitor two-year ROI. This is intentional missing-data behavior.

## PowerPoint

Command:

```text
python -m bmw_signals.cli export-deck --requirements output/final-verification/requirements.json --destination output/final-verification/BMW_board_deck.pptx
```

Result: exit code `0`, 53,244-byte `.pptx`, 22 slides, reopened successfully with `python-pptx`.

## Next.js cockpit

Dependency installation initially found two vulnerabilities in the broad Next.js 15 range. Versions were updated to current registry releases: Next.js 16.4.0 and React/ReactDOM 19.3.0. A second audit reported zero vulnerabilities.

Command:

```text
npm.cmd run build
```

Result: exit code `0`. The production build compiled, passed TypeScript, generated three static pages, and prerendered `/` plus `/_not-found`.

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

## Unverified external behavior

No live Reddit/forum/competitor scrape or real LLM classification was run because the repository has no source selector configuration or credentials. The collector, schemas, retry behavior, and browser rendering have automated coverage, but current live-site access and semantic model accuracy require a configured deployment test.
