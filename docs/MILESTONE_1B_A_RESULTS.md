# Milestone 1B-A — checkout v1.0

**Current status:** the participant confirmed 1B-A was committed, deployed and
tested against the production checkout API at
<https://supportbridge-agentathon.vercel.app/>. The supplied baseline SHA
`a4eeea911604494f693e027cdaca5f2da2f78a7e` exists locally and was HEAD before 1B-B
work began. The original local-only verification record below is historical and
its pending-commit/deployment statements are superseded by this confirmation.

Local implementation is complete and ready for human review. Only `v1.0` is
implemented. No commit, push, deployment, release tag or manifest was created.
No v1.1 module or behavioral change was introduced.

The checkout application and incidents are synthetic. This internal verification
document, its assertions and oracle source are outside future runtime tool access.

## Implemented files

New:

- `backend/sandbox/__init__.py`
- `backend/sandbox/models.py`: strict Pydantic v2 request/response contracts.
- `backend/sandbox/router.py`: allowlisted release dispatch and actual quote route.
- `backend/sandbox/releases/__init__.py`
- `backend/sandbox/releases/v1_0.py`: executable release-specific calculations.
- `backend/oracle/__init__.py`
- `backend/oracle/shipping_contract.py`: independent expected results and comparisons.
- `backend/tests/conftest.py`: async API-client fixtures.
- `backend/tests/test_checkout.py`: direct release, API, input and service-root tests.
- `backend/tests/test_shipping_contract.py`: oracle expectations and comparisons.
- This results document.

Modified:

- `backend/main.py`: register checkout router. Conditional package-relative/local
  imports support both the documented `backend.main:app` local command and Vercel's
  `main:app` from the backend service root. Both import modes are exercised by tests.
  Existing health functions, paths, response bodies and headers are unchanged.
- `AGENTS.md` and `docs/IMPLEMENTATION_BLUEPRINT.md`: exact release identifiers,
  phased history/provenance gates, neutral source/history, no-spoiler boundary,
  independent oracle, future Python tool allowlist, portable repository settings,
  rounding/input contract and stop conditions.
- `.env.example`: reserved nonsecret repository/sandbox configuration names and
  blank future pinned references; not loaded by the checkout application.
- `README.md`: synthetic disclosure, quote contract/example and local setup/status.
- `docs/MILESTONE_1A_RESULTS.md`: participant-confirmed successful deployment and
  health response, preserving the earlier packaging issue as history.

## Calculation and validation decisions

`POST /svc/api/sandbox/quote` accepts exactly `release`, `subtotal_cents` and
`discount_percent`. The only supported release identifier is `v1.0`; unknown
identifiers return HTTP 422 before dispatch. No dynamic imports or external
network destinations are accepted. The API has no payment/file-write/code-execution
operations. Responses use `Cache-Control: no-store`.

Subtotals: strict integer USD cents, inclusive range 0–100,000,000 (USD 1,000,000).
Discounts: strict whole-number percentages, inclusive range 0–100. Strings,
booleans, floats (including integral-valued floats), extra/missing fields and
out-of-range values are rejected with structured HTTP 422 validation errors.

Round the merchandise discount half up to a cent, then subtract it from the
original subtotal. The implementation uses integer multiplication and division;
for example a one-cent subtotal at 50% produces a one-cent discount. Shipping
eligibility uses the original subtotal, with free shipping starting at 10,000
cents inclusive. Otherwise shipping is 750 cents. Discounted merchandise plus
shipping gives the total. A zero subtotal is accepted and still incurs shipping;
100% discount does not change eligibility. No floating-point money, tax or FX.

The oracle imports no checkout code, models, constants or helpers. It calculates
discount rounding separately using quotient/remainder and independently derives
eligibility, shipping and total. `compare_quote()` checks every returned amount
against trusted original inputs, returning immutable expectations and mismatched
field names; it rejects missing/non-integer amounts. Release provenance remains
a separate host concern. The quote API does not import or call the oracle, and
there is no oracle HTTP route. Future tools must exclude oracle/internal docs and
assertions using enforced Python allowlists; these tools are not implemented here.

## Actual verification

Environment: existing Windows virtual environment, Python 3.13.14. No dependency
installation or upgrade was necessary.

| Command/check | Actual result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests` | **108 passed, 0 failed**, final run 0.83s, no warnings. |
| `.venv\Scripts\python.exe -m ruff check backend` | **All checks passed.** |
| `.venv\Scripts\python.exe -m ruff format --check backend/sandbox backend/oracle backend/tests/conftest.py backend/tests/test_checkout.py backend/tests/test_shipping_contract.py` | **10 files already formatted.** |
| `.venv\Scripts\python.exe -m pip check` | **No broken requirements found.** |
| Inline `tomllib`, `packaging`, `importlib.metadata` checks | Runtime pins match across manifests and installed versions: FastAPI 0.165.0, Pydantic 2.14.4, Uvicorn 0.54.0. |
| Inline comparison with `git show HEAD:<path>` | `vercel.json`, runtime/dev dependency manifests, Python runtime pin, health tests and Next.js routing are unchanged. |
| `.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765` | Real local HTTP server started, then stopped after smoke checks. |
| Inline HTTPX client against `http://127.0.0.1:8765` | Both health paths returned 200 with the expected health body; four required quote scenarios returned 200; `v1.1` request returned 422. |
| `git -c safe.directory=D:/Agent-A-Thon/supportbridge-agentathon diff --check` | Passed after removing one added Markdown trailing-space finding. Git also reports LF-to-CRLF normalization notices. |

The 108 pytest cases comprise 68 checkout cases, 37 oracle cases and 3 existing
health cases. Eight oracle matrix cases each compare all 101 supported discount
percentages, giving 808 calculated release/oracle comparisons within those tests.
Coverage includes all four required scenarios, immediately below/at/above the
shipping threshold, zero and maximum discount, zero and capped subtotal,
deterministic rounding, invalid types/ranges/JSON/missing/extra fields, unsupported
releases, response structure, detection of incorrect/missing amounts, oracle
import independence and the Vercel service-root import mode. Tests use real
calculations and HTTPX ASGI requests; the separate smoke uses a real TCP/HTTP server.

The first test run passed all 108 cases but found eight Ruff import/line-length
issues. These were corrected and the final checks above passed. Frontend files
were not modified, so frontend checks were not rerun.

## Actual local request and response

The live local smoke sent:

```http
POST http://127.0.0.1:8765/svc/api/sandbox/quote
Content-Type: application/json

{"release":"v1.0","subtotal_cents":11000,"discount_percent":15}
```

Actual HTTP 200 body:

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

Additional live HTTP totals: 11,000 cents at 5% → 10,450; 8,000 cents at 15% →
7,550; 10,000 cents at 15% → 8,500. All tested v1.0 behavior follows the
authoritative shipping policy and agrees with the independent oracle.

## Baseline commit and remaining work

Include all new/modified files listed above in the human-reviewed baseline
commit. Suggested neutral message: `feat: add checkout quote service`.
Do not include ignored virtual environments, caches, secret files or build output.
No release SHA or tag is claimed or invented.

Milestone 1A's production deployment is confirmed by the participant. The new
checkout code is local only; it has not been pushed, deployed or checked on Vercel.
Local service-root import coverage cannot prove a future cloud deployment.

1B-B remains a separate assignment: implement independently executable v1.1 as a
normal pricing refactor, preserve v1.0, and prepare a separate neutral commit for
review. 1B-C will record actual SHAs, create real release references, verify the
source/artifact manifest and check both APIs in production. Future repository
tools must enforce the documented no-spoiler and destination/path boundaries.

Stop at Milestone 1B-A for human review.
