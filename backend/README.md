# Local frontend → API → PostgreSQL

The connected UI is `frontend/`, using the visual identity from `BMW_frontend_handoff`. That handoff and its original prototype remain an isolated offline reference. Connected mode never imports embedded demo data or browser-local decisions. FastAPI serves only `frontend/` after the `/api/v1` routes, using [StaticFiles](https://fastapi.tiangolo.com/tutorial/static-files/). The browser never connects to PostgreSQL.

## Initial setup

Run from the repository root with Python 3.10+ and PostgreSQL 18. The separate teammate collection pipeline documents Python 3.11+ for its own installation; its fixture suite was also exercised in this integration environment.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Configure BMW_DATABASE_URL securely for the intended development owner role.
.\.venv\Scripts\python.exe bmwdb.py migrate
.\.venv\Scripts\python.exe bmwdb.py import 'generated/bmw_synthetic_configurator_logs (1).csv'
.\.venv\Scripts\python.exe -m backend.ingest material
.\.venv\Scripts\python.exe -m tools.configure_local_role
```

`configure_local_role` is a development-owner command, not an HTTP endpoint. It creates the restricted `bmw_demo_app` role, grants source reads and workflow writes, and denies source writes and audit mutations. PostgreSQL authentication remains an environment responsibility. The existing disposable loopback cluster uses trust authentication; do not expose it or load sensitive data. The HTTP app refuses a superuser connection.

The migration runner now hashes normalized SQL line endings and accepts historical raw LF/CRLF hashes only for identical SQL. Existing ledger values and migration 001 are unchanged. Semantic changes still fail checksum validation.

## Start the prepared local demo

```powershell
.\tools\start_local.ps1
```

This starts only `.local-postgres` on 127.0.0.1:55432 if needed and runs a hidden API process on a free chosen loopback port. If 8765 is occupied, use the running workspace or `.\tools\start_local.ps1 -Port 8766`. It does not migrate or import on page load. Open the reported HTTP URL, not the offline file URL.

Alternatively configure the environment names from `.env.example` securely, then run `.\.venv\Scripts\python.exe -m backend` in a terminal. `.env.example` is documentation, not an automatic credential loader. `BMW_DEV_PM=1` explicitly enables the fixed **Development PM (non-production)** identity; its actor cannot be supplied by the browser. With it disabled, records are read-only. `BMW_APP_ORIGIN` must match the loopback address and `BMW_PORT`. Stop the API process you started when finished; the foreground launch supports Ctrl+C. The workspace PostgreSQL stop command remains in the root README.

## API contract

Open `/docs` for request/query schemas and `/openapi.json` for the contract. All relational bigint IDs are opaque JSON strings; revision/page/count fields are numbers. Safe errors use `{error:{code,message,issues?}}`. Validation is 422, forbidden identity/origin is 403, stale revision is 409, and database/provider unavailability is 503.

| Route | Result |
|---|---|
| GET `/api/v1/health` | Actual DB/migration readiness, separate disabled provider capabilities, development identity and anti-CSRF token |
| GET `/models`, `/markets`, `/categories`, `/datasets` under `/api/v1` | Available filters, source filenames/hashes and explicit snapshot IDs; no private asset paths |
| GET `/feedback`, `/catalogue-facts`, `/evidence`, `/problems`, `/requirements` under `/api/v1` | `items`, `total`, `page`, `page_size`, `effective_filters`; bounded pagination, deterministic ID/title sorting |
| GET the above `/{id}` | Original statements, source coordinates and evidence links; feedback parent plus all tags |
| GET `/api/v1/configurator/metrics` | Synthetic completion/option selection numerator, denominator, period, cohort, origin and selected versions |
| POST `/api/v1/requirements` | Manual source-linked problem and requirement draft in one transaction |
| POST `/api/v1/requirements/{id}/actions` | approve/edit/reject/postpone, required rationale and expected revision |
| GET `/api/v1/requirements/{id}/audit` | Stored application audit history |
| GET `/api/v1/requirements/{id}/export` | Selected persisted requirement, all content revisions and audit, preserving source origins |
| POST `/api/v1/research/jobs`, `/classification/jobs` | Explicitly disabled/unavailable; never calls a paid provider |

List filters: `model_code`, `market_code`, `unknown_market_only`, `version_id`, `category_id`, `scope_layer`, `data_origin`, `review_status`, `evidence_kind`, `priority=unscored`, `q`, `sort`, `direction`, `page`, `page_size` (max 100). Default: latest snapshot per dataset, not a union of repeated snapshots. Workflow provenance/review/kind filters match linked evidence from selected snapshots. A requirement keeps its original evidence snapshot; direct detail/audit stays accessible even after a later source version. Workflow drafts must share model/market/scope with selected evidence; unknown-market evidence does not acquire country applicability through a PM action.

Configurator filters: model, market/unknown market, dataset version, origin, optional timezone-aware `start`/`end` with `[start,end)` semantics. A nonzero denominator with no successes is 0%; no eligible sessions is unavailable. Browser evidence category/review/scope/text/kind filters hide configurator metrics because unresolved codes cannot support those joins. Unknown-origin feedback, published catalogue context and synthetic sessions remain separate measures.

Sample reads:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8765/api/v1/feedback?model_code=G60&market_code=US&page_size=20'
Invoke-RestMethod 'http://127.0.0.1:8765/api/v1/configurator/metrics?model_code=F70&market_code=CN'
```

Mutation clients first GET health for the server-generated anti-CSRF token, then send JSON with `Origin` equal to `BMW_APP_ORIGIN` and `X-BMW-CSRF`. Missing/incorrect origin or token is rejected. No actor field is accepted. All request bodies are bounded at 64 KiB. Every action advances the concurrency revision; edits reopen a requirement as draft. Terminal approve/reject states require an edit before another decision. Approval requires a numeric target, unit, conditions, acceptance test and owner. Postpone requires a future/current review date or explicit `unscheduled=true`. Content, state, decision and audit commit together using [psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html). Audit events are append-only for application access; owners/admins can override database protections.

## Source adapters and limits

- Feedback: raw workbook rows retain their own row identity. Source-scoped repeated feedback IDs form one parent plus all tag rows. Comments are undated and origin unknown. Provisional keyword mappings use `baseline-v2.0-keywords-1`; original tags and mapping status remain visible. Possible safety reports are flagged for human review without deleting short statements.
- Catalogues: all 78 pages across F70/G60/G70 are preserved as page-level text context with exact edition text and page number. They are **unreviewed extracts**, not parsed equipment availability or validated numeric facts. Market and exact variant applicability remain unknown. German-language edition context is not applied to every country. Structured reviewed catalogue fact/rule extraction remains future work.
- Pipeline: `python -m backend.ingest pipeline <local-bundle.json>` imports a raw/signal bundle into the same database. Bundle fields are `namespace`, `data_origin`, `raw` (`RawPost` records), `signals` (`FilteredSignal` records), `run` with algorithm/model/prompt/taxonomy versions, and optional URL-keyed `contexts` with market/manufacturer/comparison context. Original text, source URL, publication/capture timestamps, all aspects and run metadata survive. Missing dates and short safety reports are retained. Contexts are not deduplicated by body alone. C04/C05 conflicts with the pipeline taxonomy are explicitly left unmapped pending review; C09 remains driver assistance/automation under the shared baseline. The adapter never invokes the collectors/LLM. Collected evidence has a separate UI register; no live collected data was imported in the demo.
- Unknown metadata, unresolved option mappings and missing targets remain explicit. No artificial priority, feasibility, growth, ROI, sales uplift or calibrated probability is calculated. Approvals do not verify source facts or manufacturing feasibility. Sales/study parsers, AI jobs, user accounts and uploads are not part of this integration. No archives, SQL, credentials or arbitrary files can be uploaded or downloaded through the app.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# Configure BMW_TEST_DATABASE_URL securely for a disposable PostgreSQL test owner.
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:PYTHONPATH='automotive_data_pipeline'
.\.venv\Scripts\python.exe -m unittest discover -s automotive_data_pipeline/tests -v
Remove-Item Env:PYTHONPATH
.\.venv\Scripts\python.exe -m tools.browser_verify
```

Tests create/drop uniquely named schemas only in the explicit test target; no SQLite substitute. Browser tests require installed Edge and use a fresh headless context, isolated synthetic fixtures, restricted application role, disabled external network, and an API process stopped after the run. Screenshots and results live under ignored `reports/browser`. See [verification](../database/INTEGRATION_VALIDATION.md) for executed checks and counts. No database reset, live scraping, paid AI calls or model training was performed.
