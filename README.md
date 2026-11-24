# SupportBridge

SupportBridge will investigate customer-reported regressions in a fictional
commerce application. Milestone 1A provides a deployed Next.js frontend and Python
health endpoint. The synthetic checkout quote service supports releases **v1.0**
and **v1.1** through a shared API contract.
Milestone 2A adds packaged support evidence and read-only Python retrieval tools
for later agent integration.
Milestone 2B adds pinned GitHub source/history access and actual checkout HTTP
experiment tools. No LLM agents or investigation workflow are implemented yet.

The checkout application and any customer incidents used in the demonstration
are synthetic. There are no real customers, payment operations, tax, currency
conversion, inventory or shopping-cart persistence. AI agents, model clients and
database persistence are not implemented yet.

Milestone 1A is complete at <https://supportbridge-agentathon.vercel.app/>:
the participant confirmed a working frontend and Python health response.
`/health` is application liveness only. Checkout v1.0 and v1.1 are both committed,
deployed and production-verified per the participant: eight successful production
checkout requests were run with PowerShell after the local 1B-B verification.

## Files and request path

- `frontend/`: Next.js App Router, React, TypeScript, Tailwind CSS and health client tests.
- `backend/main.py`: FastAPI application with a Pydantic v2 health response.
- `backend/sandbox/`: strict quote models, release dispatch and versioned calculations.
- `backend/sandbox/release_manifest.json`: pinned historical source identities.
- `backend/oracle/`: independent host-side policy calculations and comparisons.
- `backend/evidence/`: typed source records and packaged synthetic tickets, policies and payment events.
- `backend/tools/support_corpus.py`: five bounded, read-only evidence retrieval functions.
- `backend/tools/github_read.py`: restricted GitHub source/history and source comparison.
- `backend/tools/experiments.py`: selected checkout HTTP execution and observations.
- `backend/tests/`: pytest health, checkout, provenance and retrieval checks.
- `vercel.json`: combined Vercel Services deployment and public routing.
- `.env.example`: safe variable names/placeholders; no credentials are needed in 1A.
- `AGENTS.md` and `docs/IMPLEMENTATION_BLUEPRINT.md`: locked implementation instructions.

The browser requests `/svc/api/health` on its own origin. Locally, Next.js proxies
that path to Python on port 8000. With Vercel Services, the deployment routes it
directly to the Python service, preserving the full path. Both Python `/health`
and `/svc/api/health` return HTTP 200 and:

```json
{"status":"ok","service":"supportbridge-api"}
```

The health response and browser request disable caching. The browser checks the
response contract and uses a five-second request timeout.

## Local setup

Requirements: Node.js 22+ with npm, and Python **3.12+**. Vercel Python is pinned
to 3.13 in `backend/.python-version`; local verification uses Python 3.13.

`backend/pyproject.toml` declares project metadata and runtime dependencies for
Python project installers. `backend/requirements.txt` retains the same exact
runtime pins for the existing local pip commands, and `requirements-dev.txt`
includes that file plus test tools. Keep the runtime pins synchronized when
updating dependencies; do not leave `pyproject.toml` as a tooling-only manifest.

From the repository root, using PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
Set-Location frontend
npm.cmd ci
Set-Location ..
```

If `py` is unavailable, substitute the full path to a Python 3.12+ executable.
`npm.cmd` avoids PowerShell's script execution-policy restriction on `npm.ps1`.

Start Python in one terminal, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Start Next.js in another terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

Open <http://localhost:3000>. The page should change from
"Checking Python API…" to "Python API connected." and show the actual response.
No `.env` file is required for health or checkout in this default local setup.

## Synthetic checkout API

With Python running, send a real quote request:

```powershell
$quote = '{"release":"v1.0","subtotal_cents":11000,"discount_percent":15}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/svc/api/sandbox/quote -Method Post -ContentType application/json -Body $quote
```

Response:

```json
{
  "release": "v1.0",
  "subtotal_cents": 11000,
  "discount_percent": 15,
  "discount_cents": 1650,
  "discounted_subtotal_cents": 9350,
  "shipping_cents": 0,
  "total_cents": 9350
}
```

All amounts are integer USD cents. Subtotals must be 0–100,000,000 cents and
discounts must be whole percentages 0–100 inclusive. Round the merchandise
discount half up to the nearest cent using integer arithmetic, then subtract it.
The business policy specifies free shipping for original merchandise subtotals
of at least 10,000 cents;
otherwise it is 750 cents. Discounts do not apply to shipping. Zero subtotal is
valid and incurs 750 cents shipping; 100% discount does not change eligibility.

Exactly `v1.0` and `v1.1` are supported. Set `release` to select the
implementation; the request/response fields are the same for both. The example
above uses v1.0. Missing/extra fields, unsupported releases,
negative/out-of-range values, booleans, numeric strings and floats return
structured HTTP 422 errors. Requests calculate genuine quotes without external
network calls or side effects. Reloading the frontend still performs only its
existing health check; no storefront UI is included.

For macOS/Linux, use `python3.13 -m venv .venv`, `.venv/bin/python` instead of
`.\.venv\Scripts\python.exe`, and `npm` instead of `npm.cmd`.

## Synthetic support evidence and Python tools

The packaged HarborCart Demo corpus contains **six tickets** with six support
notes, **three approved versioned policy documents** with nine numbered sections,
and **thirteen recorded payment events** across five orders. It includes an
incomplete complaint, promotion questions, historical payment activity and
authorization/capture distinctions. All records are fictional; the ledger is
separate from the stateless checkout API and performs no payment operations.

Import from the repository root:

```python
from backend.tools.support_corpus import (
    get_order_payment_events,
    get_policy_document,
    get_support_ticket,
    search_policy_documents,
    search_support_tickets,
)

matches = search_support_tickets("SAVE15", limit=3)
print([match.ticket.ticket_id for match in matches.matches])
# ['TKT-1001', 'TKT-1003']

print(get_order_payment_events("ORD-4101").model_dump(mode="json"))
```

| Function | Typed result |
| --- | --- |
| `search_support_tickets(query: str, limit: int = 5)` | `TicketSearchResult` |
| `get_support_ticket(ticket_id: str)` | `TicketResult` |
| `search_policy_documents(query: str, limit: int = 5)` | `PolicySearchResult` |
| `get_policy_document(document_id: str)` | `PolicyResult` |
| `get_order_payment_events(order_id: str)` | `OrderPaymentEvents` |

These functions return immutable Pydantic models. Use `.model_dump(mode="json")`
for JSON-compatible dictionaries or `.model_dump_json()` for JSON strings.
Imports also work as `from tools.support_corpus import ...` with `backend/` as
the service import root. Fixed data paths are relative to the module, independent
of the working directory or Git metadata.

Search accepts 1–200 characters, requires a letter/number, rejects control
characters, and limits results to a strict integer from 1–10. It counts distinct
shared case-insensitive alphanumeric tokens across content and metadata; any
query term may match. Scores descend, ties sort by source ID. There is no stemming,
semantic matching or special-case diagnostic ranking. For example, `duplicate`
returns `TKT-1002`, `authorization` returns `TKT-1005`, and `astronomy nebula`
returns no matches. Policy search also returns matching section IDs.

Exact lookups accept only `TKT-####`, `POL-###` or `ORD-####` IDs. Valid unknown
IDs yield a null record or empty event list. Invalid arguments raise Pydantic
`ValidationError`; unavailable or malformed packaged data raises `EvidenceDataError`
rather than returning misleading empty results. No paths, URLs or extra operation
arguments are accepted.

Results preserve original text, reported values, timestamps and source IDs.
Unknown customer details remain null. Payment results contain underlying events
in timestamp/ID order and `coverage="recorded_events_only"`; absent records are
not proof that no charge occurred. Policy results preserve approval, revision,
effective dates and scope. Future assertion hosts must establish that a policy
is approved and applicable before using it as authority.

Retrieved text is marked `content_trust="untrusted_data"`. These tools do not
interpret customer instructions, compute diagnoses, read internal source or call
the oracle. Future agents will choose their own queries and IDs; their host must
keep retrieved content as data and enforce tool permissions. There are no LLM
agents, scripted investigation, new public evidence API or provider requirements
in this milestone. Local packaging checks do not verify a new Vercel deployment.

## Technical investigation tools

These Python tools operate independently; a future agent chooses which calls to
make and what supported arguments to supply. There is no predefined investigation
sequence or policy verdict.

| Function | Behavior |
| --- | --- |
| `list_checkout_releases()` | Synchronous listing of packaged manifest identities, without claiming live verification. |
| `await get_checkout_source(release, path)` | Read approved historical GitHub source, exact text, numbered lines and pinned links. |
| `await get_checkout_history(release, path, limit=5)` | One path-scoped history page, limited to approved release commit identities and dates. |
| `await compare_checkout_sources(from_release, to_release)` | Retrieve both release files and generate a labeled local source comparison. |
| `await run_checkout_quote(release, subtotal_cents, discount_percent)` | Execute one real HTTP POST and return the validated observation. |

GitHub owner/repository, source prefix and full commit SHAs resolve from the
existing [manifest](backend/sandbox/release_manifest.json). Optional process
variables `DEMO_GITHUB_OWNER`, `DEMO_GITHUB_REPO`, `DEMO_SOURCE_PREFIX`,
`DEMO_RELEASE_V1_0_REF` and `DEMO_RELEASE_V1_1_REF` must match it exactly.
Release-ref overrides must be full SHAs. An optional backend-only `GITHUB_TOKEN`
can authenticate public read requests; it is never included in results.

Source access permits each release calculation file only at its own pinned
commit, plus `backend/sandbox/models.py` and `backend/sandbox/router.py` at either
approved commit. Paths/refs cannot expand access to README, internal documents,
tests, oracle or unrelated files. Calculation bytes must match manifest SHA-256;
shared source hashes are reported without claiming manifest hash verification.
History omits commit messages, authors, unrelated file lists and patches. The
comparison is a local unified diff of actual GitHub source snapshots, not a
historical Git patch. Returned source remains untrusted data.

Set the trusted sandbox origin explicitly in the Python process environment.
For the local Python service started above:

```powershell
$env:SANDBOX_API_BASE_URL = 'http://127.0.0.1:8000'
```

For production experiments use exactly
`https://supportbridge-agentathon.vercel.app`. Other remote origins, credentials,
paths, query strings and fragments are rejected. Local HTTP supports only
`localhost` or `127.0.0.1` with an optional port. Configuration failures raise a
sanitized `ConfigurationError`; there is no environment fallback.

Example Python calls from the repository root:

```python
import asyncio
from backend.tools.github_read import get_checkout_source
from backend.tools.experiments import run_checkout_quote

async def inspect():
    source = await get_checkout_source('v1.0', 'backend/sandbox/releases/v1_0.py')
    print(source.model_dump(mode='json'))
    quote = await run_checkout_quote('v1.0', 12500, 20)
    print(quote.model_dump(mode='json'))

asyncio.run(inspect())
```

The live smoke check returned total `10000` cents for that quote. Observations
retain selected inputs, request URL/method/path, HTTP status, quote fields,
timestamp and duration. They validate schema and echoed inputs without consulting
the oracle or deciding whether behavior follows business policy.

Requests disable redirects, retries and environment proxy configuration, use
5-second inactivity and 15-second total timeouts, and cap decoded responses at
256 KiB (individual source files: 32 KiB). There are no caller-supplied network
targets, HTTP methods or headers. Failures remain structured errors, with no raw
upstream error bodies, tokens, invented responses or local source fallback.

For later agent integration, bind the host-only keyword
`reserve_experiment=async_callback` before exposing a three-argument wrapper.
The callback receives maximum `8` and must atomically reserve a durable per-run
slot, returning `True` to proceed. Denial or reservation failure blocks HTTP.
Failures and verifier replays must consume slots too. Without this hook, calls
are unbudgeted manual/local operations; no public agent endpoint, global counter
or persistent budget store exists yet.

HTTPX 0.28.1 is now a runtime dependency in both backend manifests; it previously
was development-only. No Vercel routing or frontend configuration changed.
Both backend import styles and an exported backend without Git metadata are
checked locally. Real production quote/source reads do not establish deployment
of this new adapter code.

## Release provenance

The [release manifest](backend/sandbox/release_manifest.json) records the existing
repository, historical commits, source paths, commit-pinned URLs and source hashes.
It describes source identity without prescribing an investigation result.

| Release | Historical commit | Source | Published annotated tag |
| --- | --- | --- | --- |
| v1.0 | `a4eeea911604494f693e027cdaca5f2da2f78a7e` | [v1_0.py](https://github.com/AhmedRayann/supportbridge-agentathon/blob/a4eeea911604494f693e027cdaca5f2da2f78a7e/backend/sandbox/releases/v1_0.py) | `checkout-v1.0` |
| v1.1 | `c8473e4fcdb3f71630301c13c37fbf742c2a14ef` | [v1_1.py](https://github.com/AhmedRayann/supportbridge-agentathon/blob/c8473e4fcdb3f71630301c13c37fbf742c2a14ef/backend/sandbox/releases/v1_1.py) | `checkout-v1.1` |

Both tags were absent during the original 1B-C checks and were subsequently
published by the participant. Local annotated refs and remote peeled targets
were independently verified on 2026-11-23 against the commits above. No tags
were created or changed during 2A. The future repository retrieval specification
is in [Repository provenance](docs/REPOSITORY_PROVENANCE.md).
The running FastAPI application neither calls Git nor exposes a manifest endpoint.
With an exported backend lacking `.git`, history-dependent tests skip while
manifest, checkout, validation and health tests continue to run.

## Environment and secrets

`BACKEND_URL` remains the only setting used by the frontend. It is a **nonsecret origin**, read
by Next.js configuration on the server. It defaults to `http://127.0.0.1:8000`
in development. To override it, place just this setting in
`frontend/.env.local`. Rewrites are resolved at build time in production:
redeploy after changing it. Leave it unset for combined Vercel Services.

The provider, database and budget names in root `.env.example` reserve future
backend configuration. AI runs remain disabled until their controls exist; no
provider factory is implemented. Milestone 2B tools read only the backend GitHub
and sandbox process variables described above. `.env.example` is a reference,
not an automatically loaded file: export values in PowerShell or configure them
in backend deployment settings. Health, direct checkout and corpus retrieval
continue to work without these variables or provider credentials.

Do not copy backend credentials into frontend environment files or settings.
All future credentials belong in the Python backend environment; never use
`NEXT_PUBLIC_*` for secrets. In Services mode, Vercel project environment settings
may be shared across services: verify service scoping before introducing secrets;
use the separate-backend-project fallback if backend-only isolation is unavailable.
All `.env*` files at any depth are ignored except `.env.example`.

The browser uses a same-origin route, so this setup needs no CORS allowance.
The backend grants no cross-origin browser access. The fallback also uses a
server-side same-origin proxy; do not change it to a browser cross-origin fetch.

## Checks

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
.\.venv\Scripts\python.exe -m pip check
Set-Location frontend
npm.cmd test
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

With both development servers running, independently verify the real HTTP path:

```powershell
curl.exe --fail http://127.0.0.1:8000/health
curl.exe --fail http://localhost:3000/svc/api/health
```

Both should return the same JSON above. Stop Python and reload the page to check
the unavailable state; restart Python and reload to recover.

## Vercel deployment: primary Services configuration

Prepared from the [official Next.js + FastAPI starter](https://vercel.com/templates/fast-api/next-js-fastapi-starter)
and [Services routing documentation](https://vercel.com/docs/services/routing).
The [FastAPI deployment guide](https://vercel.com/docs/frameworks/backend/fastapi)
recognizes `main.py` exporting `app`; the
[Python runtime guide](https://vercel.com/docs/functions/runtimes/python/python-version)
documents `.python-version`. No legacy `builds` configuration is used.

1. Commit and push the reviewed milestone files to the participant-owned GitHub
   repository. Verify its public visibility and check that no actual `.env` files
   are tracked. The existing remote is already configured.
2. In the participant's Vercel account, import that repository as a new project.
   Keep **Root Directory at the repository root**, so root `vercel.json` is read.
   Use the Services configuration: frontend root `frontend/` with framework
   `nextjs`, backend root `backend/` with entrypoint `main:app`.
3. Use Node.js 24.x (or another supported version >=22), npm lockfile installation
   and Next.js's default build. Python runtime is 3.13. Leave `BACKEND_URL` unset;
   do not add model keys or database credentials for 1A.
4. Deploy to Production. If using the CLI instead, install/currently update the
   Vercel CLI, run `vercel login`, then `vercel --prod` **from the repository root**.
5. Configure Production deployment protection to allow anonymous access. Open the
   stable project production domain in a fresh incognito/private browser window.
   Confirm "Python API connected." and inspect Network: `/svc/api/health` must
   return HTTP 200 with the JSON above. Also check `/health` on that domain.
6. Record the actual production URL and results. A successful local build does
   not verify cloud routing, account support or incognito access.

## Two-project fallback if Services cannot deploy

This path is prepared but has not been deployed or verified.

1. Import the same GitHub repository into a Vercel **backend** project. Set its
   Root Directory to `backend`, framework to FastAPI (or autodetection), and use
   default dependency installation from `pyproject.toml`. `main.py` exports
   `app`; `.python-version` pins 3.13. Parent `vercel.json` is not used.
2. Deploy backend Production and allow anonymous access. Verify both
   `https://<backend-production-domain>/health` and
   `https://<backend-production-domain>/svc/api/health` return HTTP 200. Health
   contains no secrets; future sensitive endpoints will need their own controls.
3. Import the repository again as the **frontend** project, Root Directory
   `frontend`, framework Next.js, default install/build commands. Set the
   nonsecret server variable `BACKEND_URL=https://<backend-production-domain>`
   in Production, without a path or trailing slash. Redeploy after setting it.
4. The existing Next.js rewrite proxies `/svc/api/*` to the backend. No browser
   keys, permissive CORS, or source edits are required. Keep future provider
   secrets exclusively in the backend project's environment settings.
5. Repeat the incognito page and Network checks on the frontend's stable
   production domain. This frontend domain is the single submitted product URL.

## Milestone boundary

Actual local commands and outcomes are recorded in
[`docs/MILESTONE_1A_RESULTS.md`](docs/MILESTONE_1A_RESULTS.md) and
[`docs/MILESTONE_1B_A_RESULTS.md`](docs/MILESTONE_1B_A_RESULTS.md), with the latest
release verification in [`docs/MILESTONE_1B_B_RESULTS.md`](docs/MILESTONE_1B_B_RESULTS.md)
and provenance checks in [`docs/MILESTONE_1B_C_RESULTS.md`](docs/MILESTONE_1B_C_RESULTS.md).
The latest evidence/retrieval results are in
[`docs/MILESTONE_2A_RESULTS.md`](docs/MILESTONE_2A_RESULTS.md).
Technical-tool checks and separate live smoke results are in
[`docs/MILESTONE_2B_RESULTS.md`](docs/MILESTONE_2B_RESULTS.md).

Milestones 1A through 1B-C are complete, including published release tags.
Milestone 2A is complete, committed and pushed per the participant. Milestone 2B
is implemented for review with local checks and separate live read/quote smoke
checks. No commit, push, deployment, tag mutation or work on 2C/3 is performed
in this assignment. Historical milestone reports retain their original status.
