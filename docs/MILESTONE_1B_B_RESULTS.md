# Milestone 1B-B — checkout v1.1

Verified locally on 21 November 2026 (PKT). Ready for a separate human-reviewed
release commit. No commit, push, deployment, release tag or final manifest was
created. Milestone 1B-C has not started.

This is internal development/test documentation. Future runtime repository tools
must exclude it, the oracle, evaluation expectations and other internal docs as
specified in the blueprint. Checkout source and release descriptions remain neutral.

## Implementation and preservation

Added `backend/sandbox/releases/v1_1.py`: a parallel executable pricing module
using the same integer-cent discount rounding as v1.0, then deriving shipping
from discounted merchandise. It contains no scenario-specific totals or diagnosis
comments. The two modules have straightforward source differences: version
docstring, shipping operand and returned release identifier.

Modified `backend/sandbox/models.py` to allow exactly `v1.0` and `v1.1`, and
`backend/sandbox/router.py` to dispatch both through the same quote endpoint.
All request/response fields, input limits and strict validation remain intact.
Dispatch stays an explicit static mapping with no dynamic imports or external URLs.

The participant supplied baseline commit
`a4eeea911604494f693e027cdaca5f2da2f78a7e`; it exists locally and was HEAD at the
start of this assignment. Tests compare v1.0 and oracle source to that actual
commit with CRLF/LF normalized. Neither file was edited:

- `backend/sandbox/releases/v1_0.py` still calculates eligibility from the original subtotal.
- `backend/oracle/shipping_contract.py` still independently applies the approved policy.

`backend/main.py`, health tests, existing oracle tests, dependency manifests,
Python runtime selection, `vercel.json`, environment examples and the frontend
are unchanged from the baseline. These were checked against Git, not assumed.
The existing portability settings and future Python-enforced investigation
allowlists remain documented; no repository tools or external services were added.

## Automated tests

`backend/tests/test_checkout.py` retains the v1.0 calculation/API assertions,
changes the now-supported v1.1 invalid-release case to v1.2, tests malformed field
and missing-field requests for both supported releases, and tests service-root
`main:app` imports with each release. Existing malformed-JSON and independent
oracle import tests are retained.

New `backend/tests/test_checkout_releases.py` covers 27 hand-checked input sets
for both releases using direct calculations and HTTPX ASGI requests: required
scenarios, original and discounted threshold boundaries, crossing/non-crossing
discounts, zero discount, 100% discount, zero/capped subtotal and half-cent
rounding. Response fields and types, release identity and cache headers are checked.
Two source-preservation cases verify v1.0 and oracle against the baseline.

Another 28 cases cover 14 subtotals × two releases, each iterating all 101 allowed
discount percentages (2,828 comparisons). These verify general calculation
behavior and the exact oracle mismatch condition. The existing v1.0 matrix adds
808 comparisons. Tests do not treat the expected policy mismatch as a pytest
failure: v1.1 must disagree on `shipping_cents` and `total_cents` precisely when
the original subtotal qualifies but discounted merchandise falls below 10,000.
Discount and merchandise amounts must still match policy.

## Actual commands and results

Windows, Python 3.13.14, existing virtual environment. Commands ran from the
repository root. No dependency installation or upgrade was needed.

| Command/check | Actual result |
| --- | --- |
| `.venv\Scripts\python.exe -m ruff format backend/tests/test_checkout.py backend/tests/test_checkout_releases.py backend/sandbox/releases/v1_1.py` | One new test file formatted; two files already formatted. |
| `.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests` | **220 passed, 0 failed**, 1.82s; no warnings. |
| `.venv\Scripts\python.exe -m ruff check backend` | **All checks passed.** |
| `.venv\Scripts\python.exe -m ruff format --check backend` | **15 files already formatted.** |
| `.venv\Scripts\python.exe -m pip check` | **No broken requirements found.** |
| Inline `tomllib`, `packaging`, `importlib.metadata` checks | Runtime manifest lists agree; installed FastAPI 0.165.0, Pydantic 2.14.4 and Uvicorn 0.54.0 satisfy the unchanged pins. |
| Inline comparison with `git show a4eeea911604494f693e027cdaca5f2da2f78a7e:<path>` | v1.0, oracle, main application, health/oracle tests, dependencies, Python runtime, environment examples and Vercel config unchanged; frontend diff empty. |
| `.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8765` | Real local server started with the Vercel-style import; stopped after smoke checks. |
| Inline HTTPX client against `http://127.0.0.1:8765` | **24 quote requests returned 200**, both health routes returned 200, unsupported v1.2 returned 422. Assertions included oracle results. |
| `git -c safe.directory=D:/Agent-A-Thon/supportbridge-agentathon diff --check` | Passed; only LF-to-CRLF normalization notices. |

Test breakdown: 96 existing/extended checkout tests, 84 two-release/preservation
tests, 37 existing oracle tests and three existing health tests. Frontend checks
were not rerun because no frontend files changed.

## Actual local HTTP examples

Both requests used `POST http://127.0.0.1:8765/svc/api/sandbox/quote` with JSON.

v1.0 request:

```json
{"release":"v1.0","subtotal_cents":11000,"discount_percent":15}
```

Actual HTTP 200 response:

```json
{"release":"v1.0","subtotal_cents":11000,"discount_percent":15,"discount_cents":1650,"discounted_subtotal_cents":9350,"shipping_cents":0,"total_cents":9350}
```

v1.1 request:

```json
{"release":"v1.1","subtotal_cents":11000,"discount_percent":15}
```

Actual HTTP 200 response:

```json
{"release":"v1.1","subtotal_cents":11000,"discount_percent":15,"discount_cents":1650,"discounted_subtotal_cents":9350,"shipping_cents":750,"total_cents":10100}
```

The unchanged oracle was invoked by the local verification client, not exposed
as an HTTP endpoint. Actual required-scenario results, in integer cents:

| Subtotal | Discount % | v1.0 total | v1.1 total | v1.0 oracle | v1.1 oracle |
| --- | --- | --- | --- | --- | --- |
| 11000 | 15 | 9350 | 10100 | Match | Shipping/total mismatch |
| 11000 | 5 | 10450 | 10450 | Match | Match |
| 8000 | 15 | 7550 | 7550 | Match | Match |
| 10000 | 15 | 8500 | 9250 | Match | Shipping/total mismatch |

The additional live input pairs were (9999, 0), (10001, 0), (12499, 20),
(12500, 20), (12501, 20), (19999, 50), (20000, 50) and (20001, 50). In particular,
discounted amounts 9999/10000/10001 demonstrate the inclusive threshold, and
half-up discount rounding at 19999/20001 cents demonstrates boundary behavior.

## Review and remaining limits

Include these ten files in the separate human-reviewed release commit:

- Added `backend/sandbox/releases/v1_1.py`
- Modified `backend/sandbox/models.py`
- Modified `backend/sandbox/router.py`
- Modified `backend/tests/test_checkout.py`
- Added `backend/tests/test_checkout_releases.py`
- Modified `AGENTS.md`
- Modified `docs/IMPLEMENTATION_BLUEPRINT.md`
- Modified `README.md`
- Modified `docs/MILESTONE_1B_A_RESULTS.md` (participant-confirmed baseline status)
- Added `docs/MILESTONE_1B_B_RESULTS.md`

Suggested neutral message: `refactor: streamline checkout pricing calculations`.
Keep v1.0 and the oracle out of the patch; their source is preserved.

The baseline release is deployed/tested per the participant. v1.1 remains local:
no production success is claimed for it. Local import coverage cannot prove cloud
packaging/routing; verify deployment in the separately authorized phase. Source
preservation tests require Git history containing the supplied baseline commit
(available in this checkout and a normal full clone).

No other local test or dependency issues remain. Real release SHAs/tags, final
source/artifact manifest and two-release production verification remain for
1B-C after review and a real v1.1 commit. No agents, models, GitHub tools, storage,
frontend UI, payments or other milestones were implemented. Stop at 1B-B.

## Post-implementation update — 21 November 2026 (PKT)

After the original 1B-B local implementation and 220-test verification recorded
above, the participant committed v1.1 as
`c8473e4fcdb3f71630301c13c37fbf742c2a14ef` and confirmed successful Vercel
deployment at <https://supportbridge-agentathon.vercel.app/>.

The participant then used PowerShell to run eight successful production checkout
requests across v1.0 and v1.1. The v1.0 baseline commit is
`a4eeea911604494f693e027cdaca5f2da2f78a7e`. These are participant-confirmed
production checks performed after the earlier local report, not independently
re-executed production checks by the coding agent in 1B-C.

All earlier local findings, commands and results above are preserved as history.
Independent local Git/source/URL/manifest checks during 1B-C are recorded in
`docs/MILESTONE_1B_C_RESULTS.md`. Neither checkout release nor the oracle was
modified. Historical tag creation/push and peeled remote verification remain
pending human review and publication.
