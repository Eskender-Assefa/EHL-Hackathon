# Test results — 2026-10-10

Environment: Windows PowerShell, Python 3.12.8. No application logic was changed during this testing pass. Added expanded tests and diagnostic probes.

The implementation and test artifacts were subsequently grouped into `automotive_data_pipeline/`. Run the commands in this report from that folder; timings and results below record the original test executions before the move.

After relocation, the suite was rerun from this folder: **34 tests passed in 0.398 seconds**, with zero failures/errors/skips. CLI help and Python compilation both returned exit code 0. The real browser smoke test was not rerun during relocation.

## Automated suite

Command: `python -m unittest discover -s tests -v`

Final suite run:

```text
Ran 34 tests in 0.412s
OK
```

34 passed; zero failures, errors or skips. An asyncio debug message reported a CLI test task taking 0.250 seconds; the test passed.

| Area | Tests | Observed results |
| --- | ---: | --- |
| Collector runtime with mocked APIs | 3 | Browser success plus HTTP 403 isolation; page/context/browser cleanup; Reddit submission and comment metadata; comment limit; source error audit |
| CLI output | 2 | Empty collection produced two empty JSON arrays; processing produced one valid signal and accepted/quarantined audit entries, returning failure status for quarantine |
| HTML extraction | 9 | Source allowlists, invalid host rejection, timestamp parsing, explicit timezone, missing dates, multiple posts, unwanted markup removal, scores, empty extraction, competitor context |
| LLM HTTP with MockTransport | 6 | Valid request/response: 1 request; 429 then success: 2; persistent 500: 3 then exception; 401: 1 without retry; invalid JSON then success: 2; missing choices: 3 then KeyError |
| Processing | 11 | Aspect splitting, stable IDs, post/aspect deduplication, empty/removed input, missing metadata, invalid timestamp/category/excerpt quarantine, noise audit; observed peak concurrency exactly 3 with limit 3 |
| Schema | 3 | All 200 category/platform/source combinations validated; eight invalid-field variants rejected; contradictory noise/aspect structures rejected |

All LLM and Reddit responses in this suite were synthetic. It does not measure semantic classification accuracy, spam detection quality, sentiment splitting quality, or live website selector compatibility.

## Diagnostic probes: actual gaps

Command: `$env:PYTHONPATH = (Get-Location).Path; python tests/probe_limitations.py`

These probes print observed undesirable behavior and are separate from the passing assertions:

```text
missing_metadata_then_valid_duplicate: {"signals": 0, "statuses": ["quarantined", "discarded"], "reasons": ["missing publication timestamp or target platform", "duplicate"]}
same_body_different_platform: {"platforms_retained": ["G60"], "statuses": ["accepted", "discarded"]}
model_accepts_short_complaint: {"signals": 1, "status": "accepted"}
weak_schema_inputs: {"signal_id": "abc", "source_platform": "Reddit", "source_url": "not-a-url", "timestamp": "2026-10-01T00:00:00Z", "target_platform": "G60", "taxonomy_category": "C05", "cleaned_verbatim_text": " ", "is_noise": false}
```

1. Deduplication happens before metadata validation: a quarantined post suppresses a later valid copy.
2. Deduplication uses only the body: identical text assigned to different comparison platforms keeps only the first platform.
3. The under-15-word low-effort complaint rule relies on the model; code accepts such a complaint if the model accepts it.
4. The schema accepts non-URL source strings and whitespace-only excerpts, and coerces the string `"false"` into a boolean.

These gaps remain unfixed in this testing pass.

## Other command results

- `python -m compileall -q bmw_signals tests`: exit 0, no output.
- `python -m bmw_signals.cli --help`: exit 0; displayed `collect` and `process` subcommands.
- Collection using nonexistent `missing-sources.json`: exit 1 with an uncaught `FileNotFoundError` traceback. The CLI does not present a friendly configuration error.
- No `LLM_*` or `REDDIT_*` environment variables were present.
- Playwright and Async PRAW were initially absent. Sandbox dependency download failed with Windows socket error 10013. Approved download succeeded, installing Playwright 1.63.0 and Async PRAW 8.0.3 under ignored `output/test-deps`. Pip emitted an aiohttp/open-webui conflict warning; installation was isolated to this target directory.
- The sandbox could not read those installed dependency directories. An approved external-sandbox smoke test imported them successfully but initially failed to launch Chromium because its executable was missing.

## Real browser integration

Downloaded Chromium Headless Shell 153.0.8010.12 into `output/test-browsers` and ran `tests/browser_smoke.py` with the isolated dependencies, outside the sandbox. Exit code 0, tool-reported wall time 8.897 seconds.

The actual Chromium process executed page JavaScript that inserted the post body. The page response was intercepted synthetic HTML; the LLM HTTP response was mocked. Observed output:

```json
{
  "raw_posts": 1,
  "signals": 2,
  "categories": ["C05", "C07"],
  "audit": [{
    "source_url": "https://www.bimmerpost.com/test-fixture",
    "status": "accepted",
    "signals": 2
  }]
}
```

Signal text was `The seats are comfortable` (C05) and `the touch screen menu is terrible` (C07). The output JSON is saved at `output/browser-smoke/signals.json`. This smoke test covers real browser rendering, BeautifulSoup extraction, HTTP response parsing, aspect validation and output serialization; it does not navigate a live forum or call a real LLM.

No live Reddit posts, forum posts, official competitor content or real LLM classifications have been produced in this test pass.
