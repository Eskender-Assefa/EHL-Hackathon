# Foundation data dictionary

| Records | Meaning and keys |
|---|---|
| brands, models, variants | Canonical identity; null variant means unknown. Trim labels never imply a derivative or powertrain. G68 exists for group support only. |
| model_groups, group_members | G60_G68 aggregate identity; do not distribute grouped sales to individual models. |
| markets, market_aliases | DE/GB/US/CN countries plus separate EU group; reviewed aliases preserve Europe_UK → GB. |
| categories, features, attributes | Stable C01–C10 project taxonomy, not an official BMW standard. Features and attributes await reviewed extraction. |
| datasets | Unique source namespace and evidence kind. External IDs are not global primary keys. |
| source_assets | Unique SHA-256; original filename/location and content-addressed archival path. Originals live outside PostgreSQL. |
| dataset_versions | Unique dataset/asset snapshot, origin observed/synthetic/unknown and timezone-aware ingestion time. |
| source_records | Unique version/record number and version/external ID. Raw strings remain JSONB. CSV coordinates start at 2 and represent logical records, not physical lines for multiline CSV. Duplicate IDs are quarantined, retained in raw payloads, and assigned relational external ID null. |
| evidence_locations | CSV coordinates; page and workbook sheet/cell slots for later parsers. |
| scenarios | One synthetic scenario per snapshot; unknown generator, prompt, sampling, score, timestamp and attachment definitions remain null. |
| ingestion_runs, validation_issues | Parser version, start/end time, report and per-record quarantine reasons. Reimport returns the existing snapshot. |
| configurator_sessions | Stable identity and version-scoped external ID; raw/parsed timestamps, region, trim label, terminal stage, attachment boolean, synthetic score and option arrays. No purchase/customer identity or inferred session start/end. |
| configurator_session_options | One row per session/viewed SA code with selection flag. All codes remain unresolved. |
| reviewed_option_mappings | Future catalogue-backed model/variant/market/edition mapping with evidence and reviewer. No mapping is populated or applied by this importer; context-aware attachment is a later migration. |

Raw records inherit origin from their dataset version. Composite foreign keys enforce synthetic session/scenario lineage and prevent source/version mismatches. Review status and scope layer are independent; review does not change origin. CSV checks reject repeated codes or selected-not-viewed options. Failed rows remain raw records without normalized sessions.

Transaction advisory locks serialize imports and migrations independently. Migration checksums prevent silent edits to applied files. Requirements, PM actions, roles and append-only decision auditing belong to later stages.

Archival writes precede the database transaction. Failed imports may leave an unreferenced content-addressed file, which reimport safely reuses. Files are retained, never automatically deleted. Back up both PostgreSQL and `data/assets`.

No growth, ROI, causal uplift or priority is computed. Package attachment and completion remain independent fields. Future metrics must expose origin, numerator, denominator, period, filters and dataset version.
