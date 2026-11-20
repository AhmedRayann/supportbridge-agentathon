# SupportBridge

SupportBridge will investigate customer-reported regressions in a fictional
commerce application. Milestone 1A provides a deployed Next.js frontend and Python
health endpoint. **Milestone 1B-A** adds a local, testable checkout quote service
for release **v1.0**.

The checkout application and any customer incidents used in the demonstration
are synthetic. There are no real customers, payment operations, tax, currency
conversion, inventory or shopping-cart persistence. AI agents, model clients and
database persistence are not implemented yet.

Milestone 1A is complete at <https://supportbridge-agentathon.vercel.app/>:
the participant confirmed a working frontend and Python health response.
`/health` is application liveness only. The new checkout endpoint has **not been
deployed or verified in production** during this assignment.

## Files and request path

- `frontend/`: Next.js App Router, React, TypeScript, Tailwind CSS and health client tests.
- `backend/main.py`: FastAPI application with a Pydantic v2 health response.
- `backend/sandbox/`: strict quote models, release dispatch and v1.0 calculations.
- `backend/oracle/`: independent host-side policy calculations and comparisons.
- `backend/tests/`: pytest health checks.
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
Shipping is free for original merchandise subtotals of at least 10,000 cents;
otherwise it is 750 cents. Discounts do not apply to shipping. Zero subtotal is
valid and incurs 750 cents shipping; 100% discount does not change eligibility.

Only `v1.0` is currently supported. Missing/extra fields, unsupported releases,
negative/out-of-range values, booleans, numeric strings and floats return
structured HTTP 422 errors. Requests calculate genuine quotes without external
network calls or side effects. Reloading the frontend still performs only its
existing health check; no storefront UI is included.

For macOS/Linux, use `python3.13 -m venv .venv`, `.venv/bin/python` instead of
`.\.venv\Scripts\python.exe`, and `npm` instead of `npm.cmd`.

## Environment and secrets

`BACKEND_URL` remains the only setting used by the frontend. It is a **nonsecret origin**, read
by Next.js configuration on the server. It defaults to `http://127.0.0.1:8000`
in development. To override it, place just this setting in
`frontend/.env.local`. Rewrites are resolved at build time in production:
redeploy after changing it. Leave it unset for combined Vercel Services.

The provider, token, database and budget names in the root `.env.example` reserve
the locked blueprint's future backend configuration. They are not loaded,
validated or used yet. AI runs are disabled in the example until their controls
exist. Health and checkout work without provider credentials; no provider factory
is implemented. Future repository integration settings in `.env.example` are
reserved and not read by checkout: `DEMO_GITHUB_OWNER`, `DEMO_GITHUB_REPO`,
`DEMO_SOURCE_PREFIX`, `SANDBOX_API_BASE_URL`, `DEMO_RELEASE_V1_0_REF` and
`DEMO_RELEASE_V1_1_REF`. Do not populate pinned references with invented values.

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
[`docs/MILESTONE_1B_A_RESULTS.md`](docs/MILESTONE_1B_A_RESULTS.md).

Milestone 1A is participant-confirmed complete. Milestone 1B-A stops at a tested
v1.0 baseline ready for human review and a distinct commit. No commits, pushes,
deployments, release tags or manifest are created in this assignment. Subsequent
release work and provenance/deployment verification require separate assignments.
