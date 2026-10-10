# Published pipeline output

`published/` is the canonical, committed result of the verified deterministic run documented in the parent [README](../README.md) and [TEST_RESULTS.md](../TEST_RESULTS.md).

It contains:

- `run_summary.json`: compact machine-readable totals and validation status;
- `source_manifest.json`: input filenames, checksums, row/page totals, and deduplication counts;
- `structured_context.json`: supplied sales-volume and customer-study context with provenance;
- `fixed_baseline_signals.json`: OptionList facts kept separate from customer requirements;
- `processing_audit.json`: accepted, discarded, and quarantined processing outcomes;
- `requirements.json`: the complete evidence-linked requirement matrix;
- `audit.jsonl`: the append-only, SHA-256 hash-chained proposal event stream;
- `BMW_board_deck.pptx`: the generated 22-slide executive deck.

The other local output directories are repeatable working artifacts and remain ignored. In particular, downloaded Playwright browsers, temporary Python packages, frontend build output, duplicate verification runs, `raw.json`, and `signals.json` should not be committed. Regenerate the full record-level output with:

```powershell
python -m bmw_signals.cli run-local --material-dir ../material --engine rules --output output/local
```
