# BMW automotive signal pipeline

This folder contains the automotive data gathering and signal classification step of the hackathon project. It collects raw customer comments and competitor website text, then uses an LLM to extract individual customer or benchmarking signals into structured JSON.

It supports BMW comparison platforms F70, G60, G70 and Neue_Klasse and the supplied BMW C01–C10 taxonomy. This is a configurable pipeline implementation; it does not include a verified live dataset.

## What this step does

1. Collects Reddit submissions and comments asynchronously using Async PRAW, including title, body, publication timestamp, score, source URL and configured BMW target platform.
2. Loads configured BIMMERPOST, Bimmerforums, German Car Forum, Mercedes-Benz and BYD pages using headless Playwright. BeautifulSoup extracts post or article text and available metadata and removes quoted replies, signatures and unwanted markup.
3. Removes duplicate, empty and deleted text. Inputs lacking a publication timestamp or target platform go into quarantine.
4. Sends eligible text to a configurable LLM endpoint. The prompt asks it to reject spam, off-topic chat and short low-effort complaints, split different aspects or sentiments, and assign one C01–C10 category per aspect.
5. Validates category codes and verifies that each extracted aspect is an exact excerpt of the source body. Accepted signals receive reproducible IDs; failed or invalid responses are recorded in an audit file.
6. Writes raw records, accepted signal records, and collection/processing audit records as JSON.

Competitor text represents comparison evidence. Its configured BMW platform identifies the intended comparison, not the manufacturer of the source vehicle. Pricing shifts need historical evidence; this implementation only collects page snapshots.

## Folder contents

```text
automotive_data_pipeline/
  README.md                 Behavior, setup and limitations
  pyproject.toml            Python dependencies and CLI entry point
  bmw_signals/
    collectors.py           Asynchronous Reddit and rendered web-page collection
    models.py               Raw input, LLM response and final signal schemas
    taxonomy.py             Supplied C01–C10 definitions
    pipeline.py             Deduplication, LLM requests, retries and validation
    cli.py                  collect/process commands and JSON output
  tests/
    test_pipeline.py        Original processing/extraction tests
    test_extended.py        Schema, HTTP retry, processing and CLI tests
    test_collectors_runtime.py  Collector tests using mocked source APIs
    probe_limitations.py    Reproduces known edge-case gaps
    browser_smoke.py         Real browser with synthetic HTML and mocked LLM
  TEST_RESULTS.md            Exact test results and observed gaps
  output/                   Ignored local artifacts, test dependencies and browser
```

The repository `.gitignore` excludes generated output, credentials and Python caches. `output/` is local test material and is not needed for a fresh installation.

## Setup and usage

Requires Python 3.11+. Run these commands from the repository root to enter this folder and create an isolated environment:

```powershell
cd automotive_data_pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m playwright install chromium
python -m bmw_signals.cli collect --config sources.json --output output
python -m bmw_signals.cli process --input output/raw.json --output output
python -m unittest discover -s tests -v
```

Set `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT` environment variables for Reddit. Processing requires `LLM_ENDPOINT` (full chat-completions URL), `LLM_API_KEY`, and `LLM_MODEL`. The provider must support JSON object response format. Do not commit credentials.

Create `sources.json`:

```json
{
  "concurrency": 3,
  "reddit": [
    {"subreddit": "BMW", "query": "F70", "target_platform": "F70"},
    {"subreddit": "electricvehicles", "query": "BMW G60", "target_platform": "G60"},
    {"subreddit": "BMW", "query": "G70", "target_platform": "G70"},
    {"subreddit": "electricvehicles", "query": "BMW Neue Klasse", "target_platform": "Neue_Klasse"}
  ],
  "pages": []
}
```

Add specific forum threads, official product pages, press releases and configurator URLs to `pages`. Entries require `source_platform`, `url`, `post_selector`, and `body_selector`. Optional fields: `target_platform`, `benchmark_context`, `title_selector`, `timestamp_selector`, `timestamp_attribute`, `timestamp_format`, `timestamp_timezone`, `score_selector`, `permalink_selector`, and `wait_selector`. Selectors must match the current page DOM; body selectors are relative to each post container. Publication dates without a timezone need an explicitly configured source timezone.

Supported page sources: BIMMERPOST, Bimmerforums, German_Car_Forum and Competitor_Web. Official Mercedes-Benz and BYD domains are allowlisted in `collectors.py`; add verified regional official domains as needed. Competitor target platforms are analyst supplied comparison mappings, not claims that BMW has competitor features. Record competitor model, market and comparison rationale in `benchmark_context`.

The collector captures rendered page text. Discovery, pagination, interactive configurator selections and historical price comparisons require further adapters or explicit pages. A single price snapshot does not establish a pricing shift. Collection does not bypass logins or CAPTCHA; use sources you are permitted to access.

## Outputs

- `raw.json`: title, body, publication timestamp, score when available, source URL, platform mapping, collection time and benchmarking context.
- `signals.json`: JSON array matching `FilteredSignal`; each accepted record has one taxonomy code and `is_noise=false`.
- `collection_audit.json`: collection failures.
- `processing_audit.json`: accepted counts, discard reasons and quarantine records.

Normalized body hashes remove duplicate posts within each run. Empty and removed posts are discarded. Missing publication timestamps or platform mappings are quarantined, never invented. Remaining text passes through the LLM to filter spam, off-topic chat and low-effort complaints under 15 words and split different components or sentiments. Short factual announcements can remain actionable. Exact source excerpts and taxonomy codes are validated in code; semantic classification and splitting depend on model quality and require human sampling. Invalid responses are retried, then quarantined. The CLI exits nonzero for collection failures or quarantined processing records while preserving successful output.

The user-supplied taxonomy lives in `taxonomy.py`. C09 covers autonomous operation, automated parking and lane changes; C04 covers safety assistance. C08 covers physical display placement; C07 covers digital UI behavior. Raw scores and competitor context stay in `raw.json` because the requested signal schema has no corresponding fields. Sentiment guides splitting but is omitted from the output schema.

References: [Async PRAW](https://asyncpraw.readthedocs.io/en/stable/), [Playwright browser contexts](https://playwright.dev/python/docs/api/class-browsercontext), [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/).

No live dataset is bundled. Tests use synthetic fixtures and fake LLM responses. Credentials, current page selectors and provider behavior must be verified with live access.

## Verified results and known limitations

The testing pass ran 34 automated tests successfully and a real Chromium smoke test that extracted one JavaScript-rendered synthetic post into two signals: C05 for seat comfort and C07 for the touchscreen menu. Reddit and LLM responses were mocked; live source access and real model accuracy remain unverified. See [TEST_RESULTS.md](TEST_RESULTS.md) for exact commands and results.

Four diagnostic gaps remain: a quarantined copy can suppress a later valid duplicate; identical bodies mapped to different BMW platforms retain only the first mapping; short-complaint filtering relies on the LLM; and the schema allows invalid URL strings and whitespace-only excerpts. Missing configuration files also produce a traceback rather than a friendly CLI error.

To rerun the limitation probes from this folder:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python tests/probe_limitations.py
```

To run the real browser test in a freshly installed environment:

```powershell
python tests/browser_smoke.py
```

If reusing the downloaded local test dependencies and browser instead of a fresh environment:

```powershell
$env:PYTHONPATH = (Get-Location).Path + ';' + (Join-Path (Get-Location) 'output/test-deps')
$env:PLAYWRIGHT_BROWSERS_PATH = (Join-Path (Get-Location) 'output/test-browsers')
python tests/browser_smoke.py
```
