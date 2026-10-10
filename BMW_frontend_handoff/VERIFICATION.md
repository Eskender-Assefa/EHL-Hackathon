# Verification and Limits

Checked locally on 10 October 2026. This verifies an editable offline frontend handoff, not an implemented backend.

## Source preservation

- `reference/original_prototype.html` is byte-identical to the supplied file.
- The extracted CSS is unchanged.
- All four extracted embedded datasets have exactly the same parsed JSON values as the original declarations: 200 configurator sessions, 5,005 feedback tag rows, 249 catalogue entries and 12 example problems.
- All five JavaScript files pass Node syntax checks.
- `SOURCE_INSPECTION.json` records source and delivered frontend fingerprints.

## Startup repair

The original HTML failed in a fresh browser context with `Cannot set properties of null (setting 'value')`. It refers to removed `#feasibility-range` and `#feasibility-value` elements. The extracted copy guards those optional controls. No scores, records or scoring formulas were changed.

An offline/not-connected status was added. Offline research/database messages no longer tell the user to run nonexistent `research_server.py` files. The unmodified original is preserved for comparison.

## Browser checks

Used Playwright with installed Microsoft Edge, fresh isolated browser contexts, and external HTTP(S) requests blocked. No live research or paid AI requests occurred.

| Check | Result |
| --- | --- |
| Repaired page loads with styles and populated table | Pass; 14 default demo problem rows, including additional seeded findings beyond the 12 internal examples |
| Unmatched search | Pass; explicit empty state and zero filtered KPI counts |
| Switch to F70 | Pass for prototype empty state; does not claim F70 evidence is connected |
| Return to G60 and select All markets | Pass; populated demo view returns |
| Sort by problem title ascending | Pass; asserted rendered title order |
| Select first problem row | Pass; detail heading matches selected row |
| Database refresh in file mode | Pass; unavailable message, no request |
| Desktop at 1440 x 1000 | Renders; document width 1440 |
| Mobile at 390 x 844 | Renders; document width 390, wide problem table scrolls internally |
| JavaScript page errors after repair | None in the exercised paths |

Desktop and mobile screenshots were visually inspected. These are smoke tests, not comprehensive accessibility, security or production-readiness certification.

## What is not implemented or verified

There is no HTTP server, PostgreSQL connection, authentication or persistent PM workflow in this handoff. No repository migrations, imports or database tests were run for this task. No files in the VS Code project or original inputs were changed.

The source remains a prototype: duplicate rendering declarations, incomplete PM controls, simulated priority/feasibility, browser-local state, embedded sample findings, G60-specific text, source classification shortcuts and placeholder API assumptions remain. The integration prompt names these issues rather than presenting them as completed features. Existing HTTP-mode code can initiate category classification after a provider-ready status response; the prompt requires removing that behavior before connected use.

The embedded records were preserved, not independently fact-checked. Frontend object counts and sample scores must not be treated as database totals, approved specifications, unique-customer counts or validated engineering decisions. Empty prototype views do not prove that a model has no customer issues.

The project inventory in CONNECTION_MAP reflects files inspected at handoff time. Its existing foundation and collection pipeline may change before Codex executes the prompt; inspect them again before editing.
