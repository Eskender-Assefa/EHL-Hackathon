# Frontend integration verification

Implemented 10 October 2026. The intended environment was the existing disposable workspace PostgreSQL 18 cluster, database `bmw_demo`, on loopback port 55432. Forward migration `002_evidence_workflow.sql` was applied; original migration 001 and its historical ledger hash were preserved. Source asset files remain outside the database.

| Connected source | Parent evidence | Raw/tag rows | Origin |
|---|---:|---:|---|
| F70 feedback | 2,128 | 4,076 | unknown |
| G60 feedback | 4,000 | 5,005 | unknown |
| G70 feedback | 4,000 | 4,690 | unknown |
| F70/G60/G70 catalogue page extracts | 23 / 28 / 27 | 78 pages | published source observed; extraction unreviewed |
| Synthetic configurator CSV | 240 sessions | 1,534 option records; 709 selected | synthetic |

No browser example problems, 200-session embedded snapshot, sales workbook, studies or live web findings were imported. Connected requirements start empty; browser workflow fixtures use separately cleaned test schemas.

Executed: 17 repository database/API tests and 34 existing pipeline fixture tests passed. The browser suite used isolated synthetic fixtures and blocked external network. It passed connected pagination, escaped malicious evidence, source detail, manual draft, PM approval, stale-revision 409 and recovery, audit after reload, persistence after actual backend restart, model/China/search/Unscored/refresh controls, honest provider unavailability, simulated database-error responses without fallback, and desktop/mobile overflow assertions. Desktop 1440×1000 and mobile 390×844 screenshots were visually inspected; no overlap or page-wide overflow. Wide evidence tables scroll internally. No JavaScript page errors occurred.

API checks exercised parent/tag idempotency, dataset snapshots, unknown/synthetic origins, null variant and country applicability, synthetic zero-denominator versus zero-success metrics, missing-target approval validation, edit/reject/postpone, server identity and CSRF permission checks, parameter validation, protected paths, transactional rollback and persistent audit. The migration checksum rejects actual changes and accepts identical LF/CRLF SQL.

All remaining limits are explicit: page-level catalogue context awaits reviewed structured parsing, keyword classifications are provisional, no approved priority policy exists, optional research/classification/uploads are disabled, and identity is an explicitly enabled localhost development PM. The app uses restricted role `bmw_demo_app`, not the development database owner/superuser. See [startup/API instructions](../backend/README.md).
