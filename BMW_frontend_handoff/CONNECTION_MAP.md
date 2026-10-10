# Connection Map

Inspected 10 October 2026. Recheck the repository before implementation because teammates may have changed it.

## What exists versus what is missing

| Part | Found | Still required |
| --- | --- | --- |
| Frontend | A self-contained HTML prototype, extracted here into editable files | Database-driven rendering, honest loading/error/empty states, complete decision controls |
| Database foundation | Existing `bmwdb.py`, checksummed migrations, hashed asset archive, synthetic CSV importer | Feedback/catalogue ingestion and typed records, requirement/workflow persistence, approved scoring policy if desired |
| Collection pipeline | `automotive_data_pipeline` Python package with collectors and signal classification | Adapter from versioned pipeline outputs to the shared database; explicit job controls |
| HTTP backend | Referenced by the HTML but not provided with it; no HTTP app found in inspected project foundation | API application that serves the frontend and calls existing database services |
| Authentication | Browser code supplies actor labels locally | Server-established PM identity and permission checks |
| Evidence and decisions | Embedded records and `localStorage` | Source-linked database evidence, transactional decisions and audit |

The repo's current foundation uses bigint identities and existing tables, while the earlier standalone database package uses a different schema design. They are not interchangeable migration sets. Adopt the current repo as authoritative and add reviewed forward migrations; use earlier artifacts as requirements and parsing references.

## Calls already written into the HTML

| Existing call | Current expectation | Integration action |
| --- | --- | --- |
| `GET /api/status` | AI/search availability booleans; can trigger automatic classification | Replace with separate database and capability readiness. No automatic paid requests |
| `POST /api/database/import` | Feedback tuples, catalogue entries, problems, sessions | This button is a read/refresh, not an import. Use explicit read endpoints with named fields |
| `POST /api/logs/postgres` | Session array | Use filtered, version-aware configurator aggregates and paginated details |
| `POST /api/logs/sqlite` | Base64 SQLite upload | Hide/disable for MVP; one PostgreSQL database does not need arbitrary database uploads |
| `POST /api/research` | Findings, warnings, rejected records | Later explicit persisted job using the existing pipeline; disabled until configured |
| `POST /api/classify-categories` | Category assignments for browser-index IDs | Optional explicit classification run against persistent IDs, with validated C01-C10 codes and provenance |

Do not build these legacy routes blindly. Update the JavaScript and implement a small, documented `/api/v1` contract together.

## Data rules that change the dashboard

1. **Scope is not priority.** C01-C10 is the shared classification; fixed/variable/hypothetical is a scope layer; highest/medium/lowest is a separately versioned assessment.
2. **Synthetic is not observed.** Keep provenance explicit and selectable. Undocumented origin remains unknown. A synthetic configurator score is not automatically customer severity or purchase probability.
3. **Raw evidence is not a requirement.** A source statement, a grouped problem, a proposed requirement and an approved PM decision are different records with links between them.
4. **Counts need denominators.** Multiple tags on one feedback record do not create multiple customers. Show record counts unless unique people are established. Ratios show numerator, denominator, cohort and version.
5. **No silent demo fallback.** A failed API call must show an error; it must not show the old embedded numbers as though they came from PostgreSQL.
6. **One identity per dimension.** Use existing model, market and category identifiers. Preserve G60/G68 grouped sales; do not attribute a group total to G60 alone.
7. **Facts depend on context.** PDF edition, market, variant, page and review status must survive extraction. An unresolved option-code mapping is not evidence of availability.
8. **Human review is separate.** Extracted or AI-classified content is not automatically reviewed, and an approved requirement is not proof of engineering feasibility.

## Implementation sequence

1. Adopt frontend files; add HTTP app and read-only database views; display connectivity clearly.
2. Extend source-preserving ingestion for the supplied evidence, without replacing the existing CSV importer.
3. Add proposed requirements and PM actions with transactional audit and concurrency checks.
4. Add transparent priority-policy support, leaving records unscored without sufficient approved inputs.
5. Integrate collection/classification behind explicit controls and persisted run records. Keep optional providers disabled when unavailable.

The MVP does not need a separate database per model, source, agent or MCP tool. Such components should share the same application services and PostgreSQL records. Files remain in the asset archive.
