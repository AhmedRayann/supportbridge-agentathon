# Milestone 2A results: synthetic support evidence and retrieval

Verified locally on **2026-11-23 (Asia/Karachi)** using Python **3.13.14**.
Milestone 2A is ready for human review. No commit, push, deployment, tag mutation
or implementation of 2B was performed. These checks do not establish that the
new evidence files are present in a Vercel deployment.

## Files

Added:

- `backend/evidence/__init__.py`: package marker.
- `backend/evidence/models.py`: strict, immutable source and retrieval models;
  source IDs, bounded fields, timestamp, section and ledger-link validation.
- `backend/evidence/store.py`: cached loading of three fixed module-relative
  JSON files, with corpus validation and a safe operator error on failure.
- `backend/evidence/data/support_tickets.json`: six synthetic support tickets.
- `backend/evidence/data/policy_documents.json`: three approved policy documents.
- `backend/evidence/data/payment_events.json`: thirteen recorded payment events.
- `backend/tools/__init__.py`: package marker.
- `backend/tools/support_corpus.py`: five read-only retrieval functions.
- `backend/tests/test_evidence_data.py`: 34 schema, relationship and data tests.
- `backend/tests/test_support_corpus.py`: 86 retrieval and permission tests.
- `docs/MILESTONE_2A_RESULTS.md`: this report.

Updated `AGENTS.md`, `docs/IMPLEMENTATION_BLUEPRINT.md` and `README.md` for the
current milestone, evidence contracts, usage, limitations and confirmed tag
publication. The blueprint's earlier "one payment event" wording now correctly
distinguishes one successful capture from its separate authorization.

Checkout releases, oracle, historical manifest, existing API routes, dependency
manifests, environment settings, frontend and Vercel configuration are unchanged.
The existing repository-provenance specification and historical milestone reports
were preserved.

## Dataset

All data concerns the fictional **HarborCart Demo**, with no real customer
identities. The three JSON files total **12,283 bytes** in this working copy.

| Ticket | Recorded context |
| --- | --- |
| TKT-1001 | Recent SAVE15 checkout complaint, customer-reported total and suspected duplicated payment; ORD-4101, reported v1.1. |
| TKT-1002 | Historical resolved payment incident for ORD-3201, two successful captures and a subsequent refund; release unknown. |
| TKT-1003 | SAVE15 receipt clarification for ORD-4102; reported merchandise/delivery amounts and v1.1. |
| TKT-1004 | Incomplete amount complaint; no order, release, promotion or amounts supplied. |
| TKT-1005 | Pending authorization alongside a posted receipt for ORD-4103; reported v1.0. |
| TKT-1006 | Declined attempt followed by a later confirmation for ORD-4104; reported v1.0. |

There are **six support notes**, **three policies**, **nine numbered policy
sections**, and **thirteen events across five orders**. POL-100 revision 1.0
documents delivery eligibility; POL-110 revision 1.0 documents merchandise
promotions and integer-cent rounding; POL-200 revision 2.1 documents recorded
payment-event semantics. Each preserves approval, effective dates and scope.
The current corpus has no superseded/outdated-policy example; corpus expansion
and broader evaluation remain later work.

The ledger contains authorizations, successful and failed captures, and a refund.
Event links preserve order, currency, parent type, timestamp and refund amount
relationships. It is synthetic recorded activity, not payment processing or
transaction persistence behind the stateless quote API. Ticket claims remain
customer reports rather than being silently promoted to verified facts.

## Tool contracts

The functions are in `backend.tools.support_corpus`; the service-root import
`tools.support_corpus` is also supported. Argument annotations use constrained
Pydantic aliases for the primitive types shown below.

| Signature | Result model |
| --- | --- |
| `search_support_tickets(query: SearchQuery, limit: ResultLimit = 5)` | `TicketSearchResult` |
| `get_support_ticket(ticket_id: TicketId)` | `TicketResult` |
| `search_policy_documents(query: SearchQuery, limit: ResultLimit = 5)` | `PolicySearchResult` |
| `get_policy_document(document_id: DocumentId)` | `PolicyResult` |
| `get_order_payment_events(order_id: OrderId)` | `OrderPaymentEvents` |

Results are frozen Pydantic models with tuple collections. Use
`.model_dump(mode="json")` or `.model_dump_json()` for JSON serialization.
Every source record has a source type, stable ID, exact content/values, relevant
timestamps, `synthetic=true` and `content_trust="untrusted_data"`. Policy sections
have their own document-scoped IDs. These citation IDs are not a substitute for
future host-generated immutable evidence snapshots per investigation.

Search uses Unicode alphanumeric, case-folded tokens from content and metadata.
The score counts distinct shared query tokens; any token may match. Zero-score
records are dropped, then results sort by descending score and ascending source
ID. Repeated query terms do not boost a record. There is no stemming, embeddings,
external search service or scenario-specific keyword weighting.

Queries must have 1–200 characters, include a letter/number and exclude control
characters. Limits are strict integers from 1–10; booleans, floats and numeric
strings are rejected. Exact IDs accept only their fixed TKT/POL/ORD patterns.
Unexpected arguments and invalid inputs raise Pydantic `ValidationError`.
Unknown valid IDs yield null ticket/document records or an empty event tuple.
Missing/corrupt data raises `EvidenceDataError` with a generic operator-facing
message, rather than returning a fake empty result or leaking internal paths.

Policy retrieval does not automatically assert approval or applicability. A
future assertion host must check approval, effective dates and scope for the
incident. Raw events include `coverage="recorded_events_only"`; no records does
not prove no charge. Neither checkout code nor the oracle is imported by these
tools or the evidence loader.

## Actual retrieval examples

Calls executed from the repository root returned the following ticket IDs and
scores; these are projections of full typed results, not abbreviated tool APIs.

| Call | Actual matches in order |
| --- | --- |
| `search_support_tickets("SAVE15", limit=3)` | TKT-1001 (1), TKT-1003 (1) |
| `search_support_tickets("duplicate", limit=3)` | TKT-1002 (1) |
| `search_support_tickets("authorization", limit=3)` | TKT-1005 (1) |
| `search_support_tickets("declined", limit=3)` | TKT-1006 (1) |
| `search_support_tickets("astronomy nebula", limit=3)` | No matches |

`search_policy_documents("rounding", limit=2)` returned POL-110, revision 1.0,
approval status `approved`, with `matched_section_ids=["POL-110-S2"]`. That
section's exact content was:

> Represent all amounts as integer USD cents. Compute the percentage discount on merchandise and round the discount to the nearest whole cent, with half-cent ties rounded up. Subtract that rounded discount to obtain discounted merchandise. A 50% discount on one cent rounds to a one-cent discount.

`get_order_payment_events("ORD-4101").model_dump(mode="json")` returned:

```json
{
  "order_id": "ORD-4101",
  "events": [
    {
      "synthetic": true,
      "content_trust": "untrusted_data",
      "source_type": "payment_event",
      "event_id": "EVT-4101-01",
      "order_id": "ORD-4101",
      "occurred_at": "2026-11-21T09:03:00Z",
      "amount_cents": 10100,
      "currency": "USD",
      "event_type": "authorization",
      "status": "succeeded",
      "related_event_id": null
    },
    {
      "synthetic": true,
      "content_trust": "untrusted_data",
      "source_type": "payment_event",
      "event_id": "EVT-4101-02",
      "order_id": "ORD-4101",
      "occurred_at": "2026-11-21T09:03:01Z",
      "amount_cents": 10100,
      "currency": "USD",
      "event_type": "capture",
      "status": "succeeded",
      "related_event_id": "EVT-4101-01"
    }
  ],
  "coverage": "recorded_events_only"
}
```

`get_support_ticket("TKT-1004")` retained null order, release, promotion,
subtotal, percentage and total fields and its exact request-for-information note.
No missing details were generated. Tests also verified the actual historical
ORD-3201 captures and refund, other orders, exact source equality and unknown IDs.

## Commands and actual outcomes

Executed from the repository root with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests/test_evidence_data.py backend/tests/test_support_corpus.py -q
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
.\.venv\Scripts\python.exe -m pip check
git -c safe.directory=D:/Agent-A-Thon/supportbridge-agentathon diff --check
```

| Check | Actual result |
| --- | --- |
| Focused evidence/retrieval suite | **120 passed**, 0 failed |
| Complete backend suite, including existing checkout and health integration tests | **347 passed**, 0 failed, 0 skipped |
| Ruff lint | **All checks passed** |
| Ruff format check | **23 files already formatted** |
| Installed dependency check | **No broken requirements found** |
| Git whitespace check | **Passed**, exit 0; only existing Windows LF/CRLF conversion notices |
| Runtime manifest/pin consistency | `pyproject.toml` dependencies exactly match `requirements.txt`; installed FastAPI 0.165.0, Pydantic 2.14.4 and Uvicorn 0.54.0 satisfy all pins |
| Exported backend without Git metadata | **342 passed, 5 skipped**, 0 failed; only existing Git-history tests skipped |
| Import modes and unrelated working directory | Both package and service-root imports/loaders passed in child processes; no checkout/oracle import |
| Protected-source comparison | Thirteen protected files equal baseline Git blobs after CRLF normalization; frontend has no diff |

Additional executed checks used PowerShell here-strings piped to
`.\.venv\Scripts\python.exe -`:

- Parsed TOML and requirements with `tomllib`/`packaging`, then checked installed
  versions through `importlib.metadata`.
- Compared calculation modules, sandbox models/router/manifest, oracle, main,
  Python manifests/version, Vercel config and `.env.example` to
  `git show ab68ce438f9e12b1b4698c6a261b721055c76f52:<path>`, and checked no frontend diff.
- Copied only `backend/` (excluding caches) into an owned temporary directory,
  confirmed `.git` absent and ran the complete pytest command there with the
  original environment's Python. The resolved temporary path was checked before
  cleanup; real repository metadata was never moved or removed.
- Executed the retrieval examples above and measured the three data files.

Source formatting during implementation used:

```powershell
.\.venv\Scripts\python.exe -m ruff format backend/evidence backend/tools backend/tests/test_evidence_data.py backend/tests/test_support_corpus.py
```

Early focused tests exposed two overly restrictive test expectations: lexical
any-term matching legitimately returned additional confirmation-related tickets,
and a path-shaped text query containing "shipping" legitimately matched public
policy text without reading a file. Assertions were corrected to match the
documented general search behavior. No diagnostic special cases were added.
Initial Ruff findings were corrected before the successful checks above.

Read-only tag checks also ran:

```powershell
git -c safe.directory=D:/Agent-A-Thon/supportbridge-agentathon for-each-ref --format='%(refname) %(objecttype) %(*objectname)' refs/tags/checkout-v1.0 refs/tags/checkout-v1.1
git -c safe.directory=D:/Agent-A-Thon/supportbridge-agentathon ls-remote --tags origin 'refs/tags/checkout-v1.0' 'refs/tags/checkout-v1.0^{}' 'refs/tags/checkout-v1.1' 'refs/tags/checkout-v1.1^{}'
```

Both local refs are annotated tags. Remote peeled targets are respectively
`a4eeea911604494f693e027cdaca5f2da2f78a7e` and
`c8473e4fcdb3f71630301c13c37fbf742c2a14ef`. Tag-object IDs are respectively
`5e316cf1f35673a25b793b3c5097dbadfd741556` and
`b8f74b02ec2487ae4b1ca2a40485f029075749f3`; these are not release commit IDs.

No frontend files changed, so frontend checks were not rerun. Existing backend
ASGI integration tests exercised health, release quotes and response contracts;
this milestone adds no HTTP route and made no new production request/deployment.

## Safety, limitations and later integration

The tools accept no paths, arbitrary targets, shell commands or code. Fixed data
paths and strict IDs enforce access in Python. Tests inject malicious ticket
instructions and verify they remain unchanged untrusted text, with no file,
network or shell operation or policy mutation. Tests also reject extra path
arguments on every function. The marker alone does not secure a future LLM;
its host must keep retrieved content separate from instructions and preserve
the same permission boundaries. Internal instructions, tests, oracle and
diagnostic source are never retrieved.

No result precomputes a duplicate-payment verdict, root cause, failing experiment
or investigation sequence. Policies describe business rules independently of
the oracle; historical notes describe their own order only. Future LangGraph
agents may wrap these five validated functions and select queries/IDs themselves.
No LLM or runtime agent has used the tools in this milestone.

The corpus is static, small and cached per process. Search is lexical without
stemming or semantic recall. There is no persistence, external payment feed,
runtime policy-version arbitration, evidence snapshot store, GitHub adapter,
experiment tool, LLM orchestration or public evidence API. These limitations
are intentional for 2A. Local exported-package checks prove file/import behavior,
not Vercel's future inclusion of this un-deployed change. No technical failures
remain in the executed local checks.

Include all eleven added files and the three updated documentation files in the
reviewed commit. Recommended message:

```text
feat: add synthetic support evidence and retrieval tools
```

Stop here for human review; no work on Milestone 2B has begun.
