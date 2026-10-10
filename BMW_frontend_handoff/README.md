# BMW Frontend Handoff

## What you already have

`BMW_G60_Problems_Updated.html` is a real source-code file, not just a design link. The `file:///` address opens that file on your computer. It contains the page, styling, JavaScript, and embedded demo records.

This handoff separates that code into editable files. It preserves the prototype's data and main layout, fixes a startup crash caused by references to removed controls, and adds an explicit offline status. It is **not yet connected to a working backend**.

```text
BMW_frontend_handoff/
  CODEX_INTEGRATION_PROMPT.md  Task to give Codex in your existing VS Code project
  CONNECTION_MAP.md           Current gaps and the intended connection
  VERIFICATION.md             Checks performed and limitations
  SOURCE_INSPECTION.json      Counts and source fingerprint
  frontend/
    index.html               Page structure
    styles.css               Styling
    js/app.js                Existing interactions and API calls
    demo-data/               Embedded prototype data, separated from UI code
  reference/
    original_prototype.html  Unmodified copy of the supplied HTML
```

Open `frontend/index.html` to preview the current prototype. Keep its neighboring folders with it. It does not need a server for this local preview; research and database actions are not connected.

## How the connection should work

```text
Browser: HTML + CSS + JavaScript
               |
               | HTTP requests and JSON responses
               v
Python backend: validation, permissions, business rules
               |
               | Parameterized SQL
               v
One PostgreSQL database: evidence, requirements, decisions, audit

Original Excel/PDF/CSV files -> existing asset archive, linked from PostgreSQL
```

The browser must not receive database passwords or AI keys. It calls the backend, which queries PostgreSQL. Once implemented, open the backend's local HTTP address, not `file:///`, to use connected mode.

For this project, reuse the existing Python/psycopg foundation. If there is still no HTTP framework in the repository, FastAPI is a suitable small addition. Serve the frontend and API from the same local origin to keep setup simple. [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/), [origin/CORS guidance](https://fastapi.tiangolo.com/tutorial/cors/).

## Use in VS Code

Open your existing `C:\Users\bunty\Desktop\BMB Sales Assistant` project. Give Codex the full contents of `CODEX_INTEGRATION_PROMPT.md`, or ask it to read that file at this handoff's location and implement it. The prompt tells Codex where this frontend lives and to bring it into the project.

The project already has `bmwdb.py`, PostgreSQL migrations, and an automotive collection pipeline. This handoff does not replace them. Its prompt explicitly asks Codex to inspect the current repository and extend its existing database rather than blindly restore the earlier generated SQL package.

Have only one agent make the integration changes at a time. The other can review the changes without editing the same files concurrently.

## Important boundaries

- The extracted files preserve the original demo, including simulated priority/feasibility and browser-local state. Those are not verified database results.
- The HTML embeds 200 configurator sessions, 5,005 feedback tag rows, 249 catalogue entries, and 12 example problems. These are counts of embedded objects, not verified customer counts or approved specifications.
- Its 200 sessions are not the same dataset snapshot as the previously supplied 240-session synthetic CSV. Do not merge them implicitly.
- The original has duplicate rendering functions, G60-specific text in a multi-model interface, and workflow controls that need completion. The prompt includes these repairs.
- No VS Code project files, database contents, credentials, or original source files were changed by this handoff.
- No paid AI calls or live web collection were performed. Database connectivity, server execution, and persisted PM decisions are work for the integration implementation.

The resulting MVP should let a PM select G60/G70/F70, examine source-linked evidence, draft a requirement, record a reasoned decision, and see that decision after refreshing the browser or restarting the server.
