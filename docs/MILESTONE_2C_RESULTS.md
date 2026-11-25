# Milestone 2C results: durable investigation infrastructure

Verified locally on **2026-11-24 (Asia/Karachi)** with Python **3.13.14**,
psycopg **3.3.9** and real PostgreSQL **16.16**. No LLM agent, provider client,
automatic diagnosis or graph workflow was implemented. No commit, push,
deployment, hosted-service provisioning or tag mutation was performed.

The owner confirmed 2B is committed/pushed/deployed. Historical reports are
preserved; this report records new local verification separately.
Baseline commit: `4174b5aa5ff49a1e1a3b081eacd6135dfd6cb675`.

## Files added and modified

Added:

- `backend/storage/__init__.py`: package marker.
- `backend/storage/database.py`: validated settings, safe errors, bounded
  connections and short PostgreSQL transaction contexts.
- `backend/storage/models.py`: strict lifecycle/state, findings, session, lease,
  evidence, event, execution, reservation and review contracts.
- `backend/storage/safety.py`: bounded canonical JSON, content hashes and rejection
  of credential/private-reasoning payloads.
- `backend/storage/migrations/001_initial.sql`: schema and immutable-record triggers.
- `backend/storage/migrate.py`: explicit transactional checksum-checked migrations.
- `backend/storage/repository.py`: ownership, idempotency, leases/fences, ordered
  events, immutable evidence, atomic reservations, usage and review persistence.
- `backend/storage/execution.py`: trusted recording context wrapping existing tools.
- `backend/storage/router.py`: session bootstrap and investigation create/read API.
- `backend/tests/test_storage_contracts.py`: 44 database-independent checks.
- `backend/tests/test_storage_postgres.py`: 28 actual PostgreSQL integration checks.
- `docs/MILESTONE_2C_RESULTS.md`: this report.

Modified:

- `backend/main.py`: register only the storage router and safe error handler.
- `backend/pyproject.toml` and `backend/requirements.txt`: matching
  `psycopg[binary]==3.3.9` runtime pin. Requirements-dev inherits it.
- `backend/tests/test_release_manifest.py`: extend the exact API-path assertion
  to the five authorized 2C routes; preserve all historical source/hash checks.
- `.env.example`, `AGENTS.md`, `docs/IMPLEMENTATION_BLUEPRINT.md` and `README.md`:
  active scope, setup, configuration, contracts, safety and deferred findings.

Checkout source/contracts/router/manifest, oracle, corpus/data/models, all ten
existing tools, frontend, Vercel configuration and historical reports are unchanged.

## PostgreSQL schema and connection design

| Tables | Purpose |
| --- | --- |
| `sb_schema_migrations` | Applied versions and source checksums. |
| `sb_sessions` | Credential hashes and fixed expiry. |
| `sb_controls` | Durable serialization row for global admission. |
| `sb_investigations` | Owned lifecycle, state, counters, limits and nullable findings. |
| `sb_stage_executions` | Stage keys, leases, fences and completion hashes. |
| `sb_tool_executions` | Real submitted arguments, results and evidence links. |
| `sb_evidence` | Immutable observations, provenance and hashes. |
| `sb_events` | Immutable ordered timeline. |
| `sb_usage_reservations` | Experiment/model reservations and observed usage. |
| `sb_review_drafts`, `sb_reviews`, `sb_escalations` | Eligible drafts, final human decisions and approved cases. |

PostgreSQL is authoritative. There is no memory/SQLite/file-backed substitute.
No database connection or migration runs at module import/application startup.
Only storage-dependent routes fail when configuration/storage is unavailable;
health and direct checkout keep working.

The twelve tables are:

| Table | Responsibility |
| --- | --- |
| `sb_schema_migrations` | Applied version/checksum/time. |
| `sb_sessions` | Random internal IDs, credential hashes, fixed expiry. |
| `sb_controls` | One row serializing admission across independent instances. |
| `sb_investigations` | Ownership, complaint/ticket, lifecycle, small stage state, findings, limits/counters and sequence. |
| `sb_stage_executions` | Per-stage key, token, increasing fence, expiry, completion hash. |
| `sb_tool_executions` | Exact arguments/result, action key, fence, timestamps and evidence IDs. |
| `sb_evidence` | Immutable raw source observations, canonical hash and provenance. |
| `sb_events` | Immutable, monotonically numbered observable operations. |
| `sb_usage_reservations` | Auditable experiment/model reservations and nullable observed usage. |
| `sb_review_drafts` | Immutable eligible draft and independent assertion reference. |
| `sb_reviews` | One immutable final owned approval/rejection. |
| `sb_escalations` | One immutable escalation at most per approved investigation. |

Foreign keys and uniqueness constrain ownership links, idempotency, event ordering,
reservation ordinals and escalation creation. SQL triggers reject UPDATE/DELETE
on evidence, events, drafts, reviews and escalations. Runtime exposes no SQL or
arbitrary insertion API. Administrative schema/retention access remains a separate
trusted operator capability; application code does not delete records.

Each operation owns one short connection/transaction and closes it on all paths.
A process-wide semaphore caps active database connections at **four**; acquiring
it or connecting is limited to **three seconds**. This resource guard does not
store investigation state or enforce paid-call budgets. Database row locks do
that across instances. Statement timeout is **five seconds**, lock timeout **two
seconds**, and explicit migrations get a 30-second statement limit.

Prepared statements are disabled, settings/search path are transaction-local,
and there is no idle client pool or background completion requirement. Use a
provider transaction-pooler URL for runtime. Hosted URLs require explicit TLS
(`require`, `verify-ca` or `verify-full`). This follows psycopg's
[transaction contexts](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
and PostgreSQL [row locking](https://www.postgresql.org/docs/current/explicit-locking.html);
provider pooling setup is described in [Neon's documentation](https://neon.com/docs/connect/connection-pooling).

## Setup and explicit migrations

Install through the preserved local command:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

Supply PostgreSQL configuration in the backend process environment; `.env.example`
is a reference and is not automatically loaded. Avoid echoing secrets:

```powershell
$env:DATABASE_URL = [System.Net.NetworkCredential]::new('', (Read-Host 'DATABASE_URL' -AsSecureString)).Password
$env:PUBLIC_APP_ORIGIN = 'http://localhost:3000'
$env:AI_RUNS_ENABLED = 'false'
.\.venv\Scripts\python.exe -m backend.storage.migrate
```

From the Vercel-style backend import root, the equivalent command is
`python -m storage.migrate`. Migrations use a transaction-level advisory lock,
record canonical LF checksums and skip previously applied identical versions.
Changing an applied migration fails; future changes need a new versioned SQL
file. No destructive migration runs at startup. The CLI was actually executed
twice against the disposable local PostgreSQL database; both returned exit 0
and `Investigation migrations applied`.

For Neon or Supabase after review:

1. In the participant's account, create a PostgreSQL database/project and keep
   its credentials private. None was provisioned by the coding agent.
2. Use the provider's direct connection with migration privileges to run the
   migration command once from a trusted development/deployment terminal.
3. Prefer a separate runtime role: SELECT/INSERT/UPDATE on mutable application
   tables, SELECT/INSERT on immutable ledger/review/escalation tables, no schema
   ownership, TRUNCATE, trigger-management or general DDL privileges.
4. Set runtime `DATABASE_URL` to the provider's compatible transaction-pooler
   string, including required TLS options, in the **Python backend environment**.
   For Supabase use a pooler compatible with the deployment's network support.
5. Set `PUBLIC_APP_ORIGIN=https://supportbridge-agentathon.vercel.app` exactly.
   Keep `AI_RUNS_ENABLED=false` until genuine agent integration is reviewed.
6. Deploy only after human review. Verify existing health/checkout first, then
   session/create/read ownership using two independent browsers. No connection
   string belongs in Next.js, `NEXT_PUBLIC_*`, source, URLs, logs or reports.

No hosted provider, pooler, production database permissions, Vercel environment
or deployment was configured or verified in this milestone.

## Contracts, ownership and available APIs

Host entry points include:

- `Store.create_session()` / `resolve_session(credential)`.
- `create_investigation(session_id, CreateInvestigation, key)` and
  `get_investigation(session_id, investigation_id)`.
- `acquire_stage(session_id, investigation_id, stage, key)`, `renew_stage`,
  `complete_stage`, `fail_stage`, `finish_investigation`.
- `validate_citations`, `get_evidence`, `list_events`, `append_event`.
- `begin_tool` / `finish_tool` for the trusted recording context.
- `reserve(session_id, lease, kind, key, *, execution_id=None, provider=None,
  model=None)` and `record_usage`.
- Trusted-host-only `record_assertion`, `prepare_review` and `decide_review`.
- `ExecutionContext(store, session_id, lease).tools_for(operation_key)`.

All persisted/returned domain models are strict and reject extra fields.
`WorkflowState.stage_outputs` holds concise stage summaries and evidence IDs;
parallel outputs merge under the investigation row lock. Lifecycle (`pending`,
`running`, `awaiting_stage`, `awaiting_review`, `completed`, `failed`,
`environment_blocked`) is separate from nullable behavior/cause findings.
The four blueprint behavioral outcomes and `unknown`/`suspected` cause classes
are retained, without computing a finding automatically.

Anonymous credentials contain 32 cryptographically random bytes. Only their
SHA-256 hashes are stored; internal session UUIDs are not credentials. Cookies
are HTTP-only, SameSite Strict, scoped to `/svc/api`, and Secure for the configured
HTTPS production origin. Session lifetime is fixed (default eight hours, bounded
five minutes–seven days), not extended on reads. All owned operations check the
server session and expiry. POST requests require the exact configured Origin and
reject `Sec-Fetch-Site: cross-site`; no arbitrary client session/owner ID is used.

| HTTP route | Result |
| --- | --- |
| `POST /svc/api/sessions` | Bootstrap/validate a session; credential only in Set-Cookie. |
| `POST /svc/api/investigations` | Create pending state (201); requires cookie and 8–80 character idempotency key. |
| `GET /svc/api/investigations/{investigation_id}` | Owned state/counters/findings and stage views; no lease tokens. |
| `GET /svc/api/investigations/{investigation_id}/events` | Ordered page, `after>=0`, `limit=1..100`, continuation cursor. |
| `GET /svc/api/investigations/{investigation_id}/evidence/{evidence_id}` | Exact owned immutable evidence. |

Errors are sanitized: invalid session 401, unowned/missing record 404, conflict
409, admission limit 429, unavailable/missing storage or disabled execution 503.
Responses disable caching. There is no public state-advance, tool execution,
evidence insertion, approval or fake successful `/step` route.

## Evidence, timeline, leases and budgets

Every actual tool response is preserved as an immutable envelope. Additional
records identify exact tickets, numbered policy sections with document metadata,
recorded payment events, SHA-pinned GitHub content/lines, source comparisons and
checkout observations. Original source IDs and timestamps remain resolvable.
The host generates evidence/execution IDs and canonical UTF-8 JSON hashes with
sorted keys, compact separators and no non-finite numbers. Raw observations
remain untrusted; future independent host assertions have a separate trust class.
Citation validation rejects nonexistent or cross-investigation IDs.

Events retain actor/stage, tool name, submitted arguments, result receipt, linked
evidence and server timestamp. Sequences increment under a row lock, atomically
with each operation. Event types also support public hypothesis revisions,
contradictions, follow-ups and verifier challenges later; none are fabricated or
seeded now. Payloads are bounded (events 16 KiB, arguments 8 KiB, state 32 KiB,
observations 1 MiB), JSON-only, and reject private-reasoning keys, credentials,
known environment secrets and credential-shaped session strings. Do not send
raw private LLM reasoning to this interface during future integration.

Support/repository leases may execute independently; reproduction follows both,
verification follows reproduction, with one named follow-up and recheck stage.
A lease has a random token, increasing fence and default 60-second expiry.
Renewal, prerequisites and result commits are transactional. Expired workers
cannot commit after recovery. Completed duplicate actions reuse stored results;
different inputs under a key conflict. An interrupted network action is left
auditable and is never blindly redispatched or refunded. Host recovery may
inspect it and choose a new bounded attempt key.

The context registry contains the existing ten tools only. The quote wrapper
accepts exactly `(release, subtotal_cents, discount_percent)`; owner, lease,
action key and callback remain trusted host bindings. PostgreSQL locks and
auditable reservations enforce shared default caps of **eight experiments** and
**ten model calls**. No model registry exposes the unbudgeted low-level primitive.
Reproduction, verification and follow-ups share the same investigation count.
HTTP failures/timeouts and interrupted reservations remain consumed. A storage
or reservation failure prevents HTTP. Counts represent reservations, including
uncertain interrupted attempts, not proof that an upstream completed or billed.

Future model reservations store provider/model/stage and nullable input/output
tokens; absent metrics stay unknown. No calls, usage, prices or costs are invented.
AI execution is disabled by default. Admission is serialized across instances:
one active run per session, configurable global active limit and session/global
rolling-24-hour creation caps. Existing per-run budgets are captured at creation.

Review readiness requires an owned successful checkout replay from the current
verification fence, a trusted host assertion referencing it, and a draft citing
that assertion's evidence. This is storage eligibility, not implementation of
the future independent oracle/verifier gate. Tests label assertion fixtures
explicitly; production code generates no assertion or verdict itself. Final
human decisions are owned, immutable and idempotent; four concurrent identical
approvals produced one escalation. Rejection creates none.

## Actual persisted manual example

A manual host integration check used local PostgreSQL, actual packaged corpus
retrieval, one real pinned GitHub read and one real production checkout HTTP
request. It did not use an LLM, execute an independent verifier or infer a diagnosis.
Records were then recovered through a **separate connection**.

Projection of the actual investigation:

```json
{
  "id": "9f1f4e2b-6284-410e-b9cc-89c1c8d8f296",
  "complaint": "Synthetic checkout amount question",
  "ticket_id": "TKT-1001",
  "current_stage": "reproduction",
  "status": "awaiting_stage",
  "experiment_count": 1,
  "model_call_count": 0,
  "experiment_limit": 8,
  "model_call_limit": 10,
  "findings": null,
  "event_sequence": 37
}
```

Actual ticket evidence metadata (payload retained exactly in PostgreSQL):

```json
{
  "id": "5c761d45-1bef-438e-969a-21e723b09906",
  "investigation_id": "9f1f4e2b-6284-410e-b9cc-89c1c8d8f296",
  "category": "support_ticket",
  "source_id": "TKT-1001",
  "observed_at": "2026-11-24T13:12:03.066705Z",
  "recorded_at": "2026-11-24T13:12:03.099151Z",
  "content_hash": "205c7570850845550301fc55ec24b187846d33463a9a8c28a1e3f295ff008a84",
  "trust": "untrusted_data",
  "execution_id": "407956f4-6aa9-428b-8ddc-75dbc6f88b92"
}
```

The exact customer message, reported release/amounts, source markers and support
note remained in `payload`; they were not replaced by this projection. Policy
sections POL-100-S1/S2/S3 and ORD-4101's underlying payment events were also
recorded. The GitHub source retrieval succeeded with the existing hash check.
The quote selected by the manual caller was v1.0, 12,500 cents, 20%; it returned
HTTP 200 and total 10,000 cents. Its reservation persisted as count 1.

Actual timeline excerpts, with omitted ranges explicitly identified:

| Sequence | Recorded operation |
| --- | --- |
| 1 | Investigation created by coordinator host. |
| 2 | Support-stage lease acquired. |
| 3–7 | `get_support_ticket` selected, arguments submitted, result received, envelope and ticket evidence inserted. |
| 8–20 | Actual policy and payment calls/results/evidence. |
| 21 | Support stage completed. |
| 22–28 | Repository stage, actual `get_checkout_source` call/evidence, completion. |
| 29 | Reproduction stage started. |
| 30–31 | `run_checkout_quote` selected and arguments submitted. |
| 32 | Experiment reservation persisted. |
| 33 | Execution outcome recorded. |
| 34 | Actual quote result receipt recorded. |
| 35–36 | Immutable envelope/checkout observation inserted. |
| 37 | Reproduction stage completed. |

Actor labels identify host stages here, not real LLM executions. This manual
test sequence is not a production investigation script. The run remained awaiting
verification with null findings. The disposable database is removed after testing;
the report preserves this verification example, not a live public investigation URL.

## Actual commands and results

Installed the runtime dependency with:

```powershell
.\.venv\Scripts\python.exe -m pip install 'psycopg[binary]==3.3.9'
```

The user started Docker Desktop after its daemon was initially unavailable.
An owned temporary `postgres:16` container, `supportbridge-2c-pg-20261124`, was
bound only to a random localhost port, without changing Docker configuration.
It used trust authentication only for this isolated local test instance, not
production. PostgreSQL reported **16.16 (Debian 16.16-1.pgdg13+1)**. Test fixtures
created/dropped only their own random `sb_test_*` schemas.

With test URL supplied privately in the Python process:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
.\.venv\Scripts\python.exe -m pip check
```

| Check | Actual result |
| --- | --- |
| Full suite with PostgreSQL enabled | **575 passed**, 0 failed, 0 skipped |
| New checks included above | **44 database-independent + 28 real PostgreSQL tests** |
| Focused earlier PostgreSQL run | **25 passed** before adding two additional eligibility/concurrent-review checks |
| Exported backend, no `.git`, real PostgreSQL enabled | **570 passed, 5 Git-history tests skipped**, 0 failed |
| Ruff lint | Passed |
| Ruff format | **40 files already formatted** |
| `pip check` | **No broken requirements found** |
| Dependency consistency | Five unique runtime pins match across both manifests and installed versions; psycopg/binary both 3.3.9 |
| Final scope/protection audit | Exactly 20 intended files; ten protected path groups unchanged; whitespace/Python structure checks passed |
| Explicit migration CLI, twice | Both exit 0; second application idempotent |
| Session-owned API | Real PostgreSQL + FastAPI ASGI tests; two independent cookie jars cannot access one another's state/events/evidence |
| Actual recorded-tool smoke | Corpus + live GitHub + live checkout observations recovered through a separate database connection |

Real PostgreSQL tests exercised independent connections, session expiry,
concurrent admission, 20 concurrent event appends, parallel stage merges,
concurrent lease acquisition, expiry/renewal/fencing and stale-result rejection,
SQL immutability, exact hashes/observations, citation ownership and fake IDs,
idempotent execution, shared budgets and review eligibility/decisions.

Budget-specific actual database results:

- Twelve concurrent experiment reservations: **eight accepted**, four denied;
  unique ordinals 1–8. These were reservations, not twelve real HTTP requests.
- Eight mocked HTTP timeouts with real PostgreSQL accounting consumed all eight
  slots; a verifier's ninth attempt was denied before HTTP. No refund occurred.
- Fourteen concurrent model reservations: **ten accepted**, four denied;
  unknown metrics stayed null. No model/provider call was made.
- Four concurrent identical human approvals persisted one escalation.
- Four independent Python processes made twelve competing experiment reservations:
  exactly eight succeeded against the same PostgreSQL counter.

Database-independent tests cover strict models/configuration, canonical hashing,
credential/private-data rejection, bounds, secure cookie/origin behavior, missing
or unavailable storage, quote-registry argument isolation and fail-closed dispatch.
Mocks in these tests are not presented as durability/concurrency proof.

The initial PostgreSQL run exposed a reservation table-name mismatch; the schema
was corrected before successful budget tests. An API test expectation was updated
to the implemented 201 creation status. Initial formatting findings were fixed.
No failures remain in the reported final runs.

Additional checks used PowerShell here-strings piped to the environment's Python:
real test-DB configuration, two migration subprocess invocations, the manual
recording smoke, and an exported-backend copy excluding caches. The export's
resolved temporary path was checked before cleanup; real `.git` was never moved.
The owned PostgreSQL container was identity/label checked, stopped and automatically
removed after the final tests. A label-filtered listing confirmed no matching
test container remained. Docker configuration was not changed.
No frontend files changed, so frontend checks were not rerun. Production Vercel
storage routes were not deployed or claimed verified.

## Environment defaults and remaining work

Required for storage: `DATABASE_URL`. Production must configure
`PUBLIC_APP_ORIGIN` to the exact HTTPS public origin. Local development may use
`http://localhost:3000`; no permissive CORS is added.

| Setting | Default |
| --- | ---: |
| `SESSION_TTL_SECONDS` | 28800 |
| `SESSION_NEW_INVESTIGATIONS_PER_DAY` | 2 |
| `MAX_GLOBAL_ACTIVE_RUNS` | 4 |
| `MAX_GLOBAL_NEW_RUNS_PER_DAY` | 20 |
| `STAGE_LEASE_SECONDS` | 60 |
| `MAX_EXPERIMENTS_PER_RUN` | 8, maximum 8 |
| `MAX_MODEL_CALLS_PER_RUN` | 10, maximum 10 |
| `AI_RUNS_ENABLED` | false |

Creation caps use rolling 24-hour windows. `TEST_DATABASE_URL` is test-only and
must point to a disposable database. Existing GitHub/sandbox settings are unchanged.
No AI key, provider selection or model service is required.

Remaining integration work: genuine four-agent tool selection/hypothesis updates,
independent verifier replay/challenge and deterministic evidence gate, real model
usage reporting, UI, public workflow/approval endpoints and reviewed hosted setup.
Session expiry denies access but no automated retention deletion/background worker
is introduced; retained-record cleanup needs an explicit privileged policy.

Preserve deferred findings: lexical searches can miss "double charged" and must
be exercised in Milestone 3; capture/authorization amount semantics need a focused
later validation pass; active status documentation must be refreshed after human
commits without rewriting historical reports. Do not register low-level unbudgeted
tools or allow models to supply host assertions or infrastructure arguments.

There is no remaining unverified local PostgreSQL concurrency/durability claim
in the checks listed above. Hosted pooling, permissions, service configuration
and Vercel deployment still require participant setup and production verification.

Recommended commit message:

```text
feat: add durable investigation state and evidence tracking
```

Stop after Milestone 2C for human review; no Milestone 3 work has begun.


## Targeted correction note - 2026-11-25 (Asia/Karachi)

The original implementation and verification report above is preserved as written.
This note records the focused correction pass before the baseline commit.

### Corrections

1. **Capacity:** separate `EXECUTION_ACTIVE` (pending, running, awaiting_stage)
   from `SESSION_OPEN` (the same states plus awaiting_review). Human review waits
   no longer consume global execution capacity. The existing one-open-run limit
   per session still includes review; session/global rolling-day creation quotas
   and the PostgreSQL admission lock are unchanged. Pending work still consumes
   capacity, preventing abandoned pending runs from accumulating without bounds.
   Three real review-ready records under a global cap of one did not block an
   eligible new visitor; four concurrent eligible visitors still admitted only one
   pending run. Review waits still count toward daily creation limits.

2. **Model calls:** host configuration and strict investigation models accept up
   to 20 calls, with the default remaining 10. Existing runs retain their captured
   limit. Concurrent reservation tests at configured limits 10, 16 and 20 accepted
   exactly the configured number and denied the four excess attempts in each run.
   No model can select its own limit through creation or quote-tool arguments.
   SQL constraints now allow at most 20 through additive migration
   `002_model_call_ceiling.sql`. Migration 001 was left byte-for-byte unchanged.
   An actual upgrade from an existing 001-only schema retained its checksum and
   rows; repeat migration and checksum-tampering rejection tests also passed.
   Apply the existing migration command before configuring budgets above ten.

3. **Session bootstrap:** only `SessionDenied` from an invalid, expired or unknown
   credential triggers a new anonymous session. Valid credentials retain their
   owner and fixed expiry, without a replacement cookie. Investigation endpoints
   still reject bad credentials, and new sessions cannot access the old owner's
   investigations. Storage/configuration errors propagate as infrastructure
   failures, without issuing a fresh credential. Cookie flags, origin validation,
   ownership checks and no-store responses remain intact.

### Capacity assessment

Four is retained as a conservative starting default, not a proven public-demo
throughput claim. `MAX_GLOBAL_ACTIVE_RUNS` remains host-configurable from 1 to
100; tests exercise a capacity of six and reject invalid bounds. Tune the value
using actual four-agent latency, provider limits and database capacity in
Milestone 3. No queue or new execution framework was introduced.

### Files in this correction pass

- `backend/storage/repository.py`
- `backend/storage/database.py`
- `backend/storage/models.py`
- `backend/storage/router.py`
- New `backend/storage/migrations/002_model_call_ceiling.sql`
- `backend/tests/test_storage_contracts.py`
- `backend/tests/test_storage_postgres.py`
- `.env.example`, `AGENTS.md`, `README.md`, `docs/IMPLEMENTATION_BLUEPRINT.md`
- This append-only note in `docs/MILESTONE_2C_RESULTS.md`

### Actual verification

An isolated `postgres:16` container reported PostgreSQL **16.16**. Only the owned
container and test schemas were used; no existing persistent database was
modified. Docker was a test dependency only. After verification, the container's
ID and label were checked, it was stopped/auto-removed, and its label-filtered
container listing was empty. Docker configuration and unrelated resources were
not changed.

Commands executed with a private, disposable `TEST_DATABASE_URL` supplied in the
Python test process:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests/test_storage_contracts.py backend/tests/test_storage_postgres.py -q -x
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
.\.venv\Scripts\python.exe -m pip check
```

| Check | Actual result |
| --- | --- |
| Focused storage suite | **107 passed**, 0 failed |
| Complete backend suite | **610 passed**, 0 failed, 0 skipped |
| Included database-independent storage tests | **66 passed** |
| Included real PostgreSQL integration tests | **41 passed** |
| Ruff lint / formatting | Passed; **40 files already formatted** |
| Dependency consistency | Five unique runtime pins match both manifests and installed versions; psycopg/binary both 3.3.9 |
| pip check | No broken requirements found |

The full suite includes the existing concurrent creation, event ordering,
lease/fencing, independent-process reservation, shared eight-experiment budget,
review/idempotency, checkout/oracle, support evidence, GitHub allowlist and health
regressions. New checks cover review-capacity admission, greater-than-ten model
budgets, SQL/Pydantic/config limits, captured budget immutability, additive
migration/checksum safety, expired/malformed/unknown cookie recovery, unchanged
valid-session expiry, isolation and failure classification. No provider/model
calls were made. GitHub regressions used their existing deterministic HTTP mocks;
no new live GitHub or production checkout smoke was needed in this correction pass.

There are no remaining local test failures. Public-demo capacity still needs real
agent measurements; hosted deployment remains unverified. No architecture,
checkout calculations, oracle, evidence recording, stage-lease design, experiment
budget, review design, frontend, Git tags or dependency versions were changed.
No hosted service was provisioned. Nothing was committed, pushed or deployed,
and Milestone 3 was not started. Stop here for human review.
