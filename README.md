# EHL Hackathon

The automotive data gathering and signal classification step is contained in [automotive_data_pipeline](automotive_data_pipeline/README.md).

That folder includes the Python implementation, setup instructions, automated tests, diagnostic probes, test results, and local test artifacts.

## BMW product-manager data foundation

Stages 1–2: PostgreSQL migrations and a source-preserving synthetic configurator CSV importer. No web app, scoring or production deployment is included.

## Project idea

Trace BMW product evidence through source snapshots. Preserve synthetic session activity separately from customer evidence and real sales.

## Key features

- Shared C01–C10 categories, model/market identity and G60/G68 grouping.
- Versioned, hashed source assets and raw records with source coordinates.
- Validated CSV imports, quarantine reasons and transactional writes.
- PostgreSQL integration tests for reimport, constraints and rollback.

## Getting started

Requires Python 3.10+ and PostgreSQL 18 (tested). Original assets are archived under `data/assets/<sha256>` outside PostgreSQL. Back up both the database and asset directory. Do not commit credentials or local data.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Configure a development BMW_DATABASE_URL securely.
# The isolated workspace demo uses:
$env:BMW_DATABASE_URL='postgresql://bmw_test@127.0.0.1:55432/bmw_demo'
.\.venv\Scripts\python.exe bmwdb.py migrate
.\.venv\Scripts\python.exe bmwdb.py validate 'generated/bmw_synthetic_configurator_logs (1).csv' --report reports/configurator_validation.json
.\.venv\Scripts\python.exe bmwdb.py import 'generated/bmw_synthetic_configurator_logs (1).csv' --report reports/configurator_import.json
```

Repeat import returns `reimport=true`, the same version ID and unchanged counts. Changed hashes create new snapshots. Queries must select an explicit version; never sum repeated sessions across snapshots. Validation/import exits with status 2 when rows are quarantined. Valid sessions and all raw records commit together. Database errors roll back the import. Header/encoding errors reject the file before writes.

## Tests and local cluster

```powershell
$env:BMW_TEST_DATABASE_URL='postgresql://bmw_test@127.0.0.1:55432/postgres'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests create and drop random schemas in the configured **test** database. Without this variable PostgreSQL tests explicitly skip. No SQLite substitute is used.

The workspace `.local-postgres` cluster uses trust authentication for disposable development data, listening only on 127.0.0.1:55432. Never put sensitive or production data there. It is stopped after implementation. Start/stop it explicitly:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D .local-postgres -l .local-postgres/server.log -o '-h 127.0.0.1 -p 55432' -w start
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D .local-postgres -m fast -w stop
```

See [data dictionary](database/DATA_DICTIONARY.md) and [validation record](database/VALIDATION.md). Existing sources remain unchanged. Catalogue/feedback extraction, analysis and PM decisions are subsequent stages.

## Team

<!-- Add team members and their roles here. -->
- To be added.
