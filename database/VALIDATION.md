# Implementation validation

Validated 10 October 2026 with Python 3.10 and PostgreSQL 18.
Source: `generated/bmw_synthetic_configurator_logs (1).csv`.
SHA-256: `c0679f8023efa0487d72d8cbaf6d5c22ca4f4e02cd07cd94721f7adfd4933ce3`.

| Check | Result |
|---|---:|
| Valid sessions / quarantined rows | 240 / 0 |
| F70 / G60 / G70 | 112 / 90 / 38 |
| Session-option views / selections | 1,534 / 709 |
| Distinct option codes | 12 |
| Completed / Engine_Selection / Packages_Step / Summary_Checkout | 186 / 23 / 17 / 14 |

Integration tests use isolated PostgreSQL schemas for fresh/repeated migrations, uniqueness, broken foreign keys, import/reimport counts, null variants, synthetic lineage, changed-hash snapshots, quarantined raw rows and rollback on injected database failure. Unit tests cover malformed JSON, invalid boolean, selected-not-viewed options, empty selections, missing timezone, non-finite scores and conflicting duplicate IDs.

This validates file structure and implementation behavior, not BMW availability or observed demand. Workbooks, catalogue facts, scoring and PM workflows remain subsequent stages.

Final execution: **7 tests passed**, including 4 PostgreSQL integration tests, with no skips. The isolated `bmw_demo` database was migrated and populated, then reimported: version ID remained 1. Direct SQL confirmed 240 sessions, 1,534 session-option rows and 709 selected rows after reimport. The test cluster was stopped; demo data remains in `.local-postgres`. JSON import/reimport reports are in `reports/` (local, ignored by Git).
