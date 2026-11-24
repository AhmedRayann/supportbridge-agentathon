# Milestone 2B results: technical investigation tools

Verified **2026-11-24 (Asia/Karachi)** with Python **3.13.14**. This milestone
provides independently callable Python tools, not LLM agents or orchestration.
No commit, push, deployment, tag modification or work on 2C/3 was performed.

Baseline: `5f07e579a53787d1c8df8c2f618755eb9b038327`, the committed 2A implementation.
Existing historical milestone reports retain their original status and results.

## Added and modified files

Added:

- `backend/tools/github_read.py`: manifest-driven identities, genuine historical
  GitHub source reads, scoped history and local source comparison.
- `backend/tools/experiments.py`: caller-selected checkout HTTP execution.
- `backend/tools/investigation_models.py`: immutable typed observations,
  source lines, release identities and sanitized errors.
- `backend/tools/_config.py`: fixed manifest loading and validated backend-only
  configuration, exact source allowlists and approved sandbox origins.
- `backend/tools/_http.py`: small private streaming HTTP helper shared by the
  two adapters, with explicit limits and failure handling.
- `backend/tests/test_github_read.py` and `backend/tests/test_experiments.py`:
  156 focused mocked/security and ASGI integration tests.
- `docs/MILESTONE_2B_RESULTS.md`: this report.

Modified:

- `backend/pyproject.toml`, `backend/requirements.txt` and
  `backend/requirements-dev.txt`: promote the existing `httpx==0.28.1` pin from
  development-only to both runtime manifests, removing its redundant dev entry.
- `.env.example`: explain active backend settings, process-environment loading,
  manifest defaults, full-SHA overrides, explicit sandbox origin and host budgets.
- `AGENTS.md`, `docs/IMPLEMENTATION_BLUEPRINT.md` and `README.md`: current 2B
  scope, tool contracts, usage, security boundaries and deferred integration work.

No changes to sandbox releases/contracts/router/manifest, oracle, evidence data or
models, the five support-corpus tools, main/API routes, frontend, Vercel routing,
repository-provenance specification or historical reports.

## Functions and typed results

| Signature | Result | Purpose |
| --- | --- | --- |
| `list_checkout_releases()` | `ReleaseList` | Synchronous packaged identity listing; not a live verification claim. |
| `await get_checkout_source(release: ReleaseId, path: SourcePath)` | `SourceResult` | Fetch exact approved historical GitHub content, verify calculation hash and preserve line provenance. |
| `await get_checkout_history(release: ReleaseId, path: SourcePath, limit: HistoryLimit = 5)` | `HistoryResult` | Retrieve one bounded path-scoped page and project only approved release identities/dates/source links. |
| `await compare_checkout_sources(from_release: ReleaseId, to_release: ReleaseId)` | `SourceComparison` | Retrieve two actual source snapshots and produce an explicitly labeled local unified diff. |
| `await run_checkout_quote(release: ReleaseId, subtotal_cents: Cents, discount_percent: Percent, *, reserve_experiment: Callable[[int], Awaitable[bool]] \| None = None)` | `CheckoutObservation` | Execute a selected quote and record the actual HTTP observation. The callback is trusted host integration only. |

All arguments are validated by strict Pydantic `validate_call`; unexpected
arguments fail validation. Releases are exactly `v1.0` and `v1.1`, history limits
are strict integers 1–5, and source-path inputs are strings of 1–200 characters
subject to exact membership checks. Subtotal and percentage use the existing
checkout bounds and reject floats, booleans and numeric strings.

Outputs are immutable Pydantic models with tuple collections. Serialize through
`.model_dump(mode="json")` or `.model_dump_json()`. Network calls are async and
work with both `backend.tools.*` package imports and `tools.*` service-root imports.
No module imports the oracle or calculation modules. Importing the existing
quote contracts does not execute either release implementation.

## GitHub access and source integrity

The fixed module-relative `backend/sandbox/release_manifest.json` remains the
authority for owner/repository, tags, historical SHAs, calculation paths/URLs and
SHA-256. There are no duplicated historical SHA constants in runtime tools.
Blank GitHub environment values resolve from the manifest. Explicit
`DEMO_GITHUB_OWNER`, `DEMO_GITHUB_REPO`, `DEMO_SOURCE_PREFIX` and release-ref
overrides must match it; release overrides must be full SHAs rather than mutable
branches or tag names. Source scope is validated against the manifest's exact
calculation suffixes and shared contract/router paths.

Only these combinations are accepted:

| Source | Approved snapshot |
| --- | --- |
| `backend/sandbox/releases/v1_0.py` | v1.0 commit only |
| `backend/sandbox/releases/v1_1.py` | v1.1 commit only |
| `backend/sandbox/models.py` | Either approved commit |
| `backend/sandbox/router.py` | Either approved commit |

Exact membership rejects traversal, encoded traversal/separators, absolute paths,
URLs, unapproved files and cross-release calculation paths before HTTP. No tool
accepts arbitrary repository, hostname, SHA, method or headers.

Source reads use the [GitHub Contents API](https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#get-repository-content)
with `ref=<full SHA>`, not a local file or mutable `main`. They require a matching
file path/type, Base64 encoding, bounded declared size and matching decoded size.
Calculation content must match the manifest's SHA-256 exactly; a mismatch returns
an error without source content. Shared files expose their calculated hash with
`manifest_hash_verified=null`, since the manifest records no hash for those files.
Returned provider URLs are ignored; source/line permalinks are constructed from
the approved repository, full SHA, path and actual line number.

History uses the [GitHub commit-list API](https://docs.github.com/en/rest/commits/commits?apiVersion=2022-11-28#list-commits)
with both the approved `sha` and `path`. Only approved release commit SHAs with
that path allowed are retained. Results omit messages, authors, emails,
provider URLs, file lists, patches, signatures and unrelated metadata. Coverage
is honestly labeled `single_page_approved_release_commits_only`; this is not a
complete arbitrary repository history browser, and pagination links are not followed.

Comparison calls only the Contents API for the requested release files. It never
downloads a broad GitHub compare/commit-detail payload. `difflib.unified_diff`
compares the real retrieved source text locally and labels the result
`local_unified_diff_of_github_sources`. It does not claim that v1.0 was edited in
place or that this is a historical Git patch. Both snapshots retain numbered
lines, hashes and pinned links. External content is marked `untrusted_data`.

There is no fallback after missing sources, failed HTTP or hash validation.
No internal README/docs/oracle/tests/evaluation files can be requested through
the Python tool interfaces. The manifest supplies identity metadata only.

## Live GitHub results, separate from mocked tests

Six actual read-only REST requests succeeded, all with HTTP 200:

1. Get v1.0 calculation source.
2. Get v1.1 calculation source.
3. Get one v1.1 source-path-scoped history page, limit 3.
4. Compare v1.0 to v1.1: two additional Contents requests.
5. Get v1.0 shared models with `GITHUB_TOKEN` explicitly removed in the smoke
   process, independently confirming public unauthenticated access.

| Release calculation | Lines | Verified SHA-256 |
| --- | --- | --- |
| v1.0 | 19 | `1f3c5449179b230ac37d8e7fd12434c070ff4d497c8a703b70f64045ff66a572` |
| v1.1 | 19 | `d630bbc1dc139deed48c75eb88620101d64e497556e867d1802142afe6f734e0` |

Pinned line examples returned by the tools:

- [v1.0 line 9](https://github.com/AhmedRayann/supportbridge-agentathon/blob/a4eeea911604494f693e027cdaca5f2da2f78a7e/backend/sandbox/releases/v1_0.py#L9).
- [v1.1 line 9](https://github.com/AhmedRayann/supportbridge-agentathon/blob/c8473e4fcdb3f71630301c13c37fbf742c2a14ef/backend/sandbox/releases/v1_1.py#L9).

The scoped history result contained:

```json
{
  "commit_sha": "c8473e4fcdb3f71630301c13c37fbf742c2a14ef",
  "committed_at": "2026-11-20T19:14:23Z",
  "source_path": "backend/sandbox/releases/v1_1.py",
  "source_url": "https://github.com/AhmedRayann/supportbridge-agentathon/blob/c8473e4fcdb3f71630301c13c37fbf742c2a14ef/backend/sandbox/releases/v1_1.py"
}
```

The live comparison succeeded with **two unified-diff hunk headers**, covering
the module docstring and the function region (including its release field).
An excerpt from that local source comparison, not a historical Git patch:

```diff
@@ -6,10 +6,10 @@
 def calculate_quote(request: QuoteRequest) -> QuoteResponse:
     discount_cents = (request.subtotal_cents * request.discount_percent + 50) // 100
     discounted_subtotal_cents = request.subtotal_cents - discount_cents
-    shipping_cents = 0 if request.subtotal_cents >= 10_000 else 750
+    shipping_cents = 0 if discounted_subtotal_cents >= 10_000 else 750
```

The unauthenticated shared-model read returned 29 lines at the v1.0 SHA and
calculated hash `7ae97ad0e3c65012d3467e338efbfe9dd6fa31a1e41e2f0a58db2c7be590bc11`.
It correctly did not claim manifest hash verification for this shared source.
These calls were run from the local adapter; no deployed investigation agent exists.

## Actual checkout HTTP results

Every invocation constructs `POST <SANDBOX_API_BASE_URL>/svc/api/sandbox/quote`
internally and sends only release/subtotal/percentage as JSON. Response schema
and echoed inputs must match. No oracle or business-policy assertion is called.
Malformed, mismatched, oversized, redirected, HTTP-error and unavailable responses
remain errors rather than successful quotes. No raw upstream error body or
exception string is returned. Request status remains available even when a later
read timeout occurs. Observations include UTC execution timestamp and measured
elapsed milliseconds.

Four **real local socket HTTP** requests were executed against a temporarily
started Uvicorn service on `http://127.0.0.1:56994`. The owned process was started
without a visible window, health-checked and terminated after the smoke checks.
These are distinct from the ASGI-transport tests, which exercise the actual app
in process without proving socket connectivity.

| Release | Subtotal cents | Discount % | Discount cents | Discounted merchandise | Shipping | Total | HTTP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v1.0 | 11000 | 15 | 1650 | 9350 | 0 | 9350 | 200 |
| v1.1 | 12500 | 20 | 2500 | 10000 | 0 | 10000 | 200 |
| v1.0 | 8000 | 15 | 1200 | 6800 | 750 | 7550 | 200 |
| v1.1 | 10000 | 0 | 0 | 10000 | 0 | 10000 | 200 |

Three **real production HTTP** requests were executed against
`https://supportbridge-agentathon.vercel.app`:

| Release | Subtotal cents | Discount % | Discount cents | Discounted merchandise | Shipping | Total | HTTP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v1.0 | 12500 | 20 | 2500 | 10000 | 0 | 10000 | 200 |
| v1.1 | 11000 | 15 | 1650 | 9350 | 750 | 10100 | 200 |
| v1.1 | 8000 | 15 | 1200 | 6800 | 750 | 7550 | 200 |

For example, the first production call returned this actual observation:

```json
{
  "status": "success",
  "request": {"release": "v1.0", "subtotal_cents": 12500, "discount_percent": 20},
  "method": "POST",
  "path": "/svc/api/sandbox/quote",
  "url": "https://supportbridge-agentathon.vercel.app/svc/api/sandbox/quote",
  "executed_at": "2026-11-24T06:12:06.495579Z",
  "elapsed_ms": 3077.653,
  "http_status": 200,
  "response": {
    "release": "v1.0", "subtotal_cents": 12500, "discount_percent": 20,
    "discount_cents": 2500, "discounted_subtotal_cents": 10000,
    "shipping_cents": 0, "total_cents": 10000
  },
  "error": null
}
```

These smoke timings measure individual adapter executions only, not LLM
investigation latency. Production requests verify the existing checkout API and
local client connectivity, **not deployment of the new adapter code**.

## HTTP safety, environment and future budgets

HTTPX 0.28.1 is the only runtime dependency change; its previously installed pin
is now declared in both runtime manifests and inherited by requirements-dev.
No install, frontend, Python-version or Vercel configuration change was needed.

Backend configuration is read from the process environment, never automatically
from `.env` files. The example file contains no credentials. GitHub's origin and
REST endpoints are fixed internally. Optional `GITHUB_TOKEN` is held in a hidden
`SecretStr` field and used only on GitHub requests. Checkout sends no credentials.
Configuration errors are sanitized and fail without attempting network access.

`SANDBOX_API_BASE_URL` is required for the experiment adapter. Accepted values
are exactly the approved production HTTPS origin or `http://localhost` /
`http://127.0.0.1` with optional port 1–65535 and optional trailing slash. Other
remote hosts, userinfo, paths, queries, fragments, alternate schemes and encoded
target tricks fail validation. There is no automatic environment switch.

The private helper uses HTTPX [timeouts](https://www.python-httpx.org/advanced/timeouts/)
and [streaming response reads](https://www.python-httpx.org/quickstart/#streaming-responses):
5-second inactivity timeout and a 15-second `asyncio.timeout` covering the full
request/stream. Decoded response bodies are capped at 256 KiB; source bodies are
additionally limited to 32 KiB. Redirect following, environment proxies and
automatic retries are disabled. Responses/clients close on success and failure.
Rate limits, unavailable environments, HTTP failures, invalid responses and
source-hash mismatches remain explicit safe errors. No write GitHub method is used.

The optional host-only `reserve_experiment` callback receives maximum **8** and
must atomically reserve a durable per-investigation slot, returning `True` to
proceed. Denial/failure blocks HTTP. A focused test demonstrates eight allowed
reservations and a denied ninth; another verifies reservation failure stays
blocked and does not leak its exception. The production durable budget host is
future work. Bind the callback before exposing a three-argument model wrapper;
never expose the callback or mutable counter to an LLM. Without it these tools
are unbudgeted manual/local operations. Failures/replays must count toward the
future shared limit; there is no global in-memory budget implementation in 2B.

## Executed checks and commands

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests/test_github_read.py backend/tests/test_experiments.py -q
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
.\.venv\Scripts\python.exe -m pip check
```

| Check | Actual result |
| --- | --- |
| New focused tool tests | **156 passed**, 0 failed |
| Full backend, including existing checkout, oracle, health, provenance and evidence tests | **503 passed**, 0 failed, 0 skipped |
| Exported backend without `.git` | **498 passed, 5 Git-history tests skipped**, 0 failed |
| Ruff lint | **All checks passed** |
| Ruff format | **30 files already formatted** |
| Installed dependencies | **No broken requirements found** |
| Runtime manifest parity | Exact matching four dependency pins; installed FastAPI 0.165.0, Pydantic 2.14.4, Uvicorn 0.54.0 and HTTPX 0.28.1 satisfy them |
| Import modes | Package and service-root imports pass from unrelated cwd without Git or importing oracle/calculation modules |
| Real GitHub reads | **6 requests, all HTTP 200**; both calculation hashes match, scoped history/comparison succeed and unauthenticated shared read succeeds |
| Real checkout HTTP | **4 local + 3 production, all HTTP 200** with validated observations |
| Protected-path comparison | Nine protected path groups have no diff against baseline |
| Final scope/whitespace audit | Exactly 15 intended files; Git diff check and all-file whitespace audit pass (Markdown hard breaks preserved) |

The tests cover strict inputs, allowed/denied paths and refs, scoped history
projection containing deliberately excluded payloads, SHA provenance, hashes,
actual line/link mapping, malformed source/JSON, nested JSON, errors/rate limits,
timeout/slow streaming, size limits, redirects, absent source, no fallback,
both releases with independently selected cart inputs, actual ASGI calculations,
budget integration and no oracle dependency. Local fixture source files in
mocked tests are explicitly mock data, not presented as live GitHub observations.
Initial lint findings were import ordering/long lines; these were corrected
before the passing checks. The final focused and full test runs have no failures.

Additional checks used PowerShell here-strings piped to
`.\.venv\Scripts\python.exe -`:

- Parse TOML/requirements and inspect installed versions with `tomllib`,
  `packaging` and `importlib.metadata`.
- Compare `git diff HEAD --` for sandbox, oracle, evidence, support tools, main,
  frontend, Vercel config, the 2A report and repository-provenance document.
- Copy only `backend/` excluding caches into an owned temporary directory,
  assert `.git` absent, and run the full pytest command with the existing Python.
  Check the resolved temporary path before cleanup; no real `.git` was moved.
- Execute the six live GitHub requests and three production quotes above;
  explicitly remove `GITHUB_TOKEN` in the unauthenticated smoke process.
- Launch a hidden, owned Uvicorn subprocess on a free localhost port, wait for
  `/health`, perform four real HTTP experiments, then terminate/wait for it.
- Audit the exact fifteen changed/new paths, final newlines and whitespace,
  preserving existing two-space Markdown hard breaks. `git diff --check` also
  passed; Git emitted only Windows LF/CRLF conversion notices.

Formatting during development used `python -m ruff format` on only the new
technical tool/test files (the unchanged support-tool file remained unchanged).
Two import-order fixes used `python -m ruff check --fix` on the new tests.
No frontend checks were run because frontend files did not change. No production
adapter invocation or Vercel deployment was performed.

## Limitations and remaining integration work

- History is one bounded page of approved release commits, without full commit
  messages, arbitrary older commits, broad compare metadata or pagination.
- Shared source has no manifest-recorded hash, so only calculation source claims
  manifest hash verification. GitHub responses remain externally retrieved data.
- There is no source cache; repeated calls consume GitHub rate limits. Failures
  return errors and do not retry or substitute local content.
- Runtime origins/paths are deliberately narrow; moving the demo requires a
  reviewed manifest/configuration/origin update, not caller-supplied targets.
- The eight-experiment durable reservation host, immutable per-run evidence IDs,
  unified evidence ledger, verification/assertions, agents and orchestration are
  later integration work. A reservation callback alone is not a durable store.
- Milestone 3 integration should test natural paraphrases such as "double
  charged"; current lexical search can miss them. Its implementation is unchanged.
- Later payment validation should settle capture/authorization amount semantics
  before constraining captures above authorization amounts. No payment data or
  validation was changed in 2B.
- Keep active milestone wording fresh after human commits; retain historical
  reports unchanged. The new modules are locally import/export tested but have
  not been deployed on Vercel. No local check failures remain.

Include the eight added files and seven modified files described above in the
reviewed commit. Recommended message:

```text
feat: add GitHub investigation and checkout experiment tools
```

Stop after Milestone 2B for human review.
