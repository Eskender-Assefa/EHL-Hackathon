# Build the BMW Frontend-to-Database Integration

You are working in my existing VS Code repository:
`C:\Users\bunty\Desktop\BMB Sales Assistant`.

Implement the connection, not just a plan. Build a working local hackathon MVP. Preserve existing work and use the current repository's conventions. Do not deploy publicly, train a model, buy services, reset a database, or make paid AI requests as part of setup or tests.

## 1. Inputs and objective

The editable frontend handoff is here:
`C:\Users\bunty\Documents\Codex\2026-10-10\hi-x20\outputs\BMW_frontend_handoff`.

Read its README, CONNECTION_MAP and VERIFICATION. Adopt its `frontend/` directory into this repository after checking for newer frontend work. Preserve the original reference. If the handoff has moved, locate it or ask me for its location; do not invent its contents. The original reference also exists at:
`C:\Users\bunty\Downloads\BMW_G60_Problems_Updated.html`.

This is real HTML/CSS/JavaScript source, not a remotely hosted app. Make the existing product-manager workspace use a Python backend and one PostgreSQL database. Support G60, G70 and F70 with the same baseline taxonomy. Preserve the useful table, evidence detail, filters and audit workflow; no landing page or unnecessary React rewrite.

The core journey is: select model and market -> inspect source-linked evidence -> draft a requirement -> review priority when available -> PM approves, edits, rejects or postpones with a reason -> decision and audit survive reload and server restart.

## 2. Inspect and reuse before changing anything

Read applicable repository instructions, `git status`, root README, dependency files, `bmwdb.py`, database migrations/data dictionary/validation notes and tests. Read `automotive_data_pipeline/README.md`, its taxonomy, signal schemas and known limitations. Inventory current implementation without printing credentials or reading `api.txt` or secret files.

At handoff time the repo already contained a Python/psycopg PostgreSQL foundation and a CSV importer, plus a separate collection/classification pipeline. The foundation uses bigint identities and unqualified tables. The earlier generated `BMW_database_package.zip` uses a different schema design. **Do not blindly restore that SQL into this database, create a competing parallel schema, modify applied migration files, or overwrite teammate work.** Treat the current repo and its migration ledger as authoritative. Reuse useful parsers/contracts from earlier artifacts only through tested adapters and forward migrations.

Check whether an HTTP backend has since been added and extend it. If none exists, add FastAPI with compatible pinned dependencies and the existing psycopg stack. Keep changes within this integration. Do not introduce an ORM solely for this task. Do not assume all tables or imports described in older documents already exist.

Use `BMW_DATABASE_URL` only on the server. There is a documented disposable loopback PostgreSQL setup in the repo; inspect its instructions before using it. Never start, stop, reset or migrate an unrelated database. Tests need a separately configured test database or isolated test schemas with explicit cleanup.

## 3. Architecture and editable files

Serve the frontend and API from one local HTTP origin, for example `http://127.0.0.1:8765`, choosing a different free port if occupied. The browser calls the API; only the backend talks to PostgreSQL. Keep API routes before a static catch-all and serve only the frontend directory, not the repository root, archives or credential files.

Use small modules following existing conventions: an HTTP app, typed request/response schemas, database queries, workflow services, and frontend API/rendering modules. Centralize browser fetch/error handling. SQL must be parameterized. Reuse connection handling and transactions appropriately; do not block an async route with synchronous database work.

Retain a clearly isolated offline demo/reference. Connected mode must load from the API and must never silently fall back to embedded data or browser-local decisions. `localStorage` may retain display preferences only. Keys, connection strings and provider secrets must never enter browser code, API responses, exports or logs.

## 4. Shared data and evidence contracts

Keep existing stable IDs and these categories: C01 Power & Performance; C02 Energy & Emissions; C03 Price; C04 Safety; C05 Comfort; C06 Exterior; C07 Software; C08 Interior Design; C09 Automation; C10 Miscellaneous. Category is separate from scope layer (`fixed`, `variable`, `hypothetical`), provenance (`observed`, `synthetic`, `unknown`), and review status. Start with fixed-scope evidence, preserving expansion paths for later layers.

Resolve conflicting category definitions across the frontend and pipeline explicitly, especially C04/C09. Record a versioned mapping or flag ambiguous records for review; do not silently relabel everything or treat Miscellaneous as approved classification.

Use existing versioned datasets, hashed assets, raw records and source locations. Extend missing feedback/catalogue ingestion with forward migrations and tested adapters, preserving raw values, sheet/row or PDF page and document edition. Repeated feedback IDs on tagged rows need a parent feedback record plus tag/mention rows, not dropped duplicates. Do not use the current source-record external-ID uniqueness to discard legitimate repeated tags. Undated Excel records remain undated; do not run them through a collector validator that rejects every missing publication date.

Do not invent customers, dates, currencies, variants, option mappings, availability or facts. Preserve unknown origin where not established. Preserve model groups such as G60/G68 in aggregate sources. Published German catalogue facts must not automatically apply to every market/variant. An extracted statement is not a human-reviewed specification.

Expose explicit dataset-version selection/current-version policy so repeated snapshots are not summed together. Idempotent reimport of the same asset must not inflate counts. Count unique source feedback records separately from tag rows; do not label either count as unique customers without evidence. Preserve statement-level positive and negative evidence, not only complaints.

The HTML contains 200 embedded configurator sessions, 5,005 feedback tag rows, 249 catalogue entries and 12 example problems. These are prototype-object counts, not verified database facts. The supplied synthetic CSV has a different 240-session snapshot. Prefer the existing validated database import; keep any demo import under a separate namespace/version, never implicitly merge sessions by ID across these datasets. Compute displayed counts from the actual selected cohort.

For configurator metrics return numerator, denominator, cohort, origin and version. A nonzero denominator with zero successes is 0%; a zero denominator is unavailable. Do not call synthetic selection activity actual sales or a calibrated probability. Preserve unresolved option-code mappings until reviewed for model/variant/market/edition.

## 5. Missing workflow records and priority

If absent, add source-linked problem proposals, requirement versions, evidence links, assessments, PM decisions and append-only application audit. Reuse existing concepts rather than adding duplicate equivalents. A problem summary and an actionable requirement are distinct; give both stable persistent IDs.

Support manual proposals from selected evidence first. If using heuristic grouping or AI extraction, store its algorithm/model/prompt version and mark the result provisional. Do not seed the 12 browser example problems as observed or approved requirements. Requirements need measurable target, unit, conditions, acceptance test and owner when applicable; missing information is `needs_specification`, not a made-up zero or an assumed target.

Priority is not a fixed category ranking. Calculate on the server only when a versioned policy and necessary inputs are explicitly approved. Preserve factor values, weights, rationale, evidence and policy version. Without them return `unscored` with null scores, not invented P1/P2/P3. A missing score is not lowest priority. Provide an Unscored filter enabled by default.

The prototype has multiple inconsistent scoring formulas and simulated feasibility penalties, including a fixed penalty for external findings. Do not promote these to official customer priorities. A demo policy may be separately labeled as an analyst scenario, with assumptions visible and no implication of real manufacturing feasibility. Flag possible safety issues for human review without making a regulatory determination or hiding short serious complaints as noise.

## 6. API contract

Use a documented `/api/v1` API with named fields and typed validation, not the legacy positional feedback tuples. Reconcile exact names with existing code and document the final contract. At minimum provide:

- `GET /api/v1/health`: database readiness plus separate optional-provider capabilities; no secrets. Return an honest unavailable state if the database is down.
- `GET /api/v1/models`, `/markets`, `/categories`, `/datasets`: valid filters and available dataset versions; include China when present in the data rather than copying the incomplete hardcoded market menu.
- `GET /api/v1/feedback`, `/catalogue-facts`, `/problems`, `/requirements`: bounded pagination, validated filters and deterministic sorting; detail endpoints with linked source evidence.
- `GET /api/v1/configurator/metrics`: version-aware aggregates for the selected model/market and optional dates; bounded paginated session details if needed.
- `POST /api/v1/requirements`: draft from existing evidence with validated category, model, market and scope; include evidence IDs.
- `POST /api/v1/requirements/{id}/actions`: PM approve/edit/reject/postpone with required rationale and expected revision; edits create a new content revision; postponement records a review date or explicit unscheduled state.
- `GET /api/v1/requirements/{id}/audit`: persistent decision history and revision changes; scoped export from persisted records.

Use IDs as opaque strings in JSON so bigint IDs are not truncated in JavaScript. Lists return `items`, pagination metadata and the effective filter/version selection. Records carry provenance, review status, scope layer and source coordinates where relevant. Do not expose private filesystem paths as downloadable URLs. Return consistent safe errors, including validation errors, permission failures and HTTP 409 for stale edits.

The old `/api/database/import` button is a database read. Rename it Refresh and make it read-only. Real import operations are separate explicit commands/jobs with validation reports and idempotency. CSV import can reuse the tested existing importer; do not copy the browser's weaker validation. Add bounded CSV/JSON/XLSX/PDF upload adapters only when supported and tested. Hide unsupported SQLite/database upload controls; never execute uploaded SQL or trust a client path.

Optional research/classification endpoints must be explicit jobs, persist run status/provenance and return disabled/unavailable when not configured. No automatic AI call from a health check, page load, filter change or successful database refresh. Do not imply a Claude Pro login supplies an application API credential.

## 7. Real PM decisions and security

Use server-established identity and authorization. A client string such as `actor: Product Manager` is not authentication. For this localhost hackathon, an explicitly enabled development identity is acceptable only when clearly labeled non-production and bound to loopback; it must be fixed by server configuration, not supplied by the browser. Do not add fake production authentication.

Commit each decision, requirement state/revision and audit record in one transaction. Use locking and expected-revision checks to prevent overwrites. Require rationale for every action, validate allowed state transitions, and reject stale actions with 409. Return the stored result before the UI claims success. Approved requirements do not automatically become verified catalogue facts or engineering feasibility approvals.

Human decision permissions must be distinct from ingestion/AI proposal permissions. Optional agents and future MCP tools call the same services with restricted identities; they cannot approve PM decisions or overwrite source facts. Do not leave a superuser connection or an arbitrary-SQL endpoint in the app.

Use same-origin requests and appropriate origin/CSRF protection for mutations. Escape untrusted evidence and titles, validate links as HTTP(S), prevent path traversal and arbitrary file downloads. Never use unsanitized evidence with `innerHTML`. Enforce upload size/type limits and quarantine reasons. Logs must not leak full customer records or credentials.

## 8. Frontend repairs and behavior

Consolidate the duplicate `renderList` and `renderDetail` declarations. The later definitions currently override earlier PM action controls; implement one tested rendering path and functional decision forms. Replace prompt-based decisions with accessible forms, required rationale, saving/error states and stale-revision recovery.

Replace hardcoded G60 headings, filename claims and fixed catalogue counts with data for the selected model and dataset. Prevent stale network responses from replacing a newer model/market selection. Keep model/market/evidence-source/category/scope/provenance/review/priority filters consistent across KPIs, table, detail and export. Scope unknown-market records explicitly rather than silently including them in a selected country.

Distinguish source platform from evidence kind: a forum customer post is not a controlled competitor benchmark just because of its website. Actual Mercedes/BYD data needs its own brand/model/market and comparison context; synthetic competitor scenarios remain synthetic.

Provide loading, empty, database-unavailable, validation, retry and unauthorized states. Never render fake zeros as a connection-success indicator. Show source evidence, publication date when known, capture date, version, origin, review state, model/market applicability and assessment uncertainty. Show Unscored when appropriate. UI decisions and audit must come from the server after reload; no browser-authored audit pretending to be a database record.

Keep the existing useful visual identity but make the tool compact and operational, not a marketing page. Support desktop and mobile without page-wide overflow, overlapping text or inaccessible controls; horizontal scrolling is acceptable inside the evidence table. Do not add decorative nested cards or unnecessary framework churn.

## 9. Existing collection pipeline and future expansion

Reuse `automotive_data_pipeline` through a small adapter instead of rebuilding scraping or starting a database per agent. Persist original collected text, exact extracted excerpts, source URL/timestamp when known, collection time, taxonomy version, model/market context, processing run and rejection/quarantine reasons. Preserve source metadata currently omitted from its final signal schema. Keep competitor manufacturer distinct from the BMW comparison target.

Review the pipeline's documented duplicate suppression, cross-model deduplication, missing-date and short-complaint limitations before relying on it. Do not let a quarantined record suppress a later valid one or collapse identical text across distinct contexts without retaining both relationships. Use fixtures for integration; no live scraping, paid LLM calls, login bypass or claims of verified model quality during tests. Optional provider integration must not block the database-backed PM journey.

Keep the design extensible for later variable/hypothetical requirements, synthetic Mercedes/BYD comparisons and MCP clients, but do not build these products now. One shared relational database plus the existing source-asset archive is enough for this MVP.

## 10. Verification and delivery

Run existing tests, then add focused database/API tests for the new migrations and services: idempotent imports; parent/tag counting; version filters; unknown versus synthetic provenance; market/variant applicability; metric zero-denominator behavior; unscored records; validation; transactional rollback; PM permissions; persisted audit; stale revision 409; and malicious evidence text/file paths. Use a real PostgreSQL test target, never claim SQLite or static SQL parsing proves PostgreSQL execution.

Add browser tests for model/market switching, search/sort/pagination, Unscored visibility, source detail, refresh, no silent demo fallback, unavailable optional providers, decision save/reload and concurrency conflict recovery. Verify desktop and mobile screenshots. Use synthetic fixtures and mocked external providers with network calls disabled. Database-backed decisions must survive a backend restart, not only a browser refresh.

Document startup, required environment-variable names without values, migrations, API examples, dataset selection, test setup and limitations. Keep `.env.example` placeholders only and ensure credentials/local database files are ignored. Run the local server on a free loopback port and report its URL after implementation.

Finish with a concise account of files changed, migrations applied to which intended environment, datasets actually connected, tests actually executed, skipped checks and remaining limitations. Do not say the backend is connected because a health endpoint returns a hardcoded success or because the static page opens. If infrastructure is unavailable, deliver the implementation and exact blocker without inventing a successful connection.

Reference documentation when needed: [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/), [FastAPI CORS/origins](https://fastapi.tiangolo.com/tutorial/cors/), [psycopg parameterized queries](https://www.psycopg.org/psycopg3/docs/basic/params.html).
