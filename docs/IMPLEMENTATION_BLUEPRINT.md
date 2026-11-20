# SupportBridge — FINAL Implementation Blueprint v1.2 (Locked MVP)

**Locked:** 20 November 2026 (PKT). Registration confirmed complete by participant.  
**Status:** Approved implementation baseline. No implementation/deployment is implied by this document.  
**Target:** Feature freeze 26 November; organizer LiteLLM verification and submission 27–29 November 2026.  
**Submission:** One public Vercel production URL, one public participant-owned GitHub repository, project summary ≤600 characters.  
**Source of truth:** This blueprint defines *what to build*. Root [`AGENTS.md`](../AGENTS.md) defines *how coding agents must work*. If they disagree, stop and resolve the conflict rather than silently dropping a requirement.

> **Scope freeze:** The four specialist agents, genuine API experiments, independent evidence verification, **likely code file/line identification**, bounded safety controls and **human-approved engineering escalation** are required. The runtime agents **never modify code**. New features need explicit owner approval; implementation details may evolve to satisfy tests and deployment constraints.

## A. Product definition and promises

**Working name:** SupportBridge — AI Regression Detective.

**One-sentence pitch:** SupportBridge uses a team of AI agents to turn vague customer-reported software failures into reproducible, evidence-backed engineering cases by investigating support records, inspecting repository changes, running controlled API experiments, and independently checking the results.

**Buyer hypothesis:** Commerce software vendors or service firms with L2/L3 support-engineering teams, an accessible test environment, and recurring checkout/order escalations. Initial commercial vehicle could be a client-specific accelerator, not a general autonomous debugging SaaS. Paid demand is unvalidated.

**Demonstrated capability (MVP):** Find a reproducible shipping-policy regression between two controlled checkout releases and prepare a reviewable escalation. **Do not claim** unrestricted product debugging, a proven production root cause, integration to real customer systems, or autonomous code fixes.

**The central value:** A reproducible API request and response, an independent expected-result assertion citing a policy, a previous/current release comparison, a **pinned likely source file/line/commit**, and an engineering case a human can act on.

**Outcomes:** `verified_regression`, `not_reproduced_in_tested_scope`, `insufficient_evidence`, or `environment_blocked`. Never equate “not reproduced in tested scope” with “no defect exists.” The code-cause assessment is separate: `suspected` or `unknown` unless additional independently sufficient evidence is available; this MVP makes **no claim of causal proof through patching**.

## B. Scope contract

### Must ship (P0)

1. Public application with polished entry point, a seed complaint, and a short explanation of synthetic data.
2. Small real Python checkout application with two pinned executable release behaviors; quote endpoint and a synthetic payment-event ledger.
3. Independent, policy-derived expected-result checker that does not import the implementation under test; integer USD cents.
4. Synthetic tickets and business policies, versioned and searchable by real Python tools.
5. Read-only GitHub tools for one allowlisted, participant-owned **public** repository: commits, compare, file-at-SHA.
6. LangGraph Python with **four distinct LLM-powered specialists**: Support Investigator, Repository Investigator, Reproduction Agent and Evidence Verifier. A deterministic LangGraph coordinator routes work and enforces budgets; it is not a fifth model. All four are part of the locked MVP. If time prevents the fourth, disclose a scope exception explicitly rather than claiming the four-agent target was met.
7. Live experiment tool execution with immutable evidence IDs, request/response details, version/fixture identifiers, independent assertions, and one model-driven revision after contradictory observations.
8. Four honest result statuses: `verified_regression`, `not_reproduced_in_tested_scope`, `insufficient_evidence`, and `environment_blocked`; never convert execution errors into a verified finding.
9. Investigation workspace, agent/tool activity, source-linked evidence inspector, release comparison, replay with changed supported inputs, and a human-approved escalation saved in a session-scoped queue.
10. Secure model adapter for Gemini during development and the organizers' LiteLLM model at submission. Global run/call/token caps, input/tool validation, and secrets only on server.
11. Public Vercel production deployment with durable run data and isolation; public GitHub source and README.
12. **Code location is required for supported, reproducible regressions:** Repository Investigator identifies the most credible changed file, line span, commit SHA and pinned GitHub permalink; the verdict distinguishes a *suspected causal code change* from the independently *verified behavioral regression*. If no defensible location exists, report `unknown` with a reason—never fabricate one.
13. Lightweight enforced guardrails: untrusted-input handling, tool allowlists, strict parameter validation, read-only GitHub access, no arbitrary commands/network destinations, bounded model/test/runtime budgets, evidence-gated verdicts, session isolation, and explicit human approval before saving an escalation.
14. Judge-facing business outcome: a usable support-to-engineering handoff with customer impact, actual investigation duration, evidence and next action. Any ROI numbers are clearly labeled illustrative, not measured.

### Nice to have (P1, only if P0 is stable)

- A second defect family (idempotent order retries **or** time-zone export boundary); pick only one.
- Additional held-out cases, more responsive activity streaming, visual diff, richer evidence timeline.
- Single-agent baseline with same tools for agent-orchestration comparison.

### Explicit exclusions

No arbitrary repository debugging, arbitrary URL fetching, model-generated runnable code, shell commands, production payments, live customer integrations, full helpdesk replacement, browser automation, self-deploying code fixes, autonomous production writes, private employer/client code, or a vector database. **No runtime source edits, patches, commits, pull requests, or automated fix validation**, even as a stretch feature. No external GitHub/Jira issue creation in the core: escalation saves only to our application's synthetic queue after human approval. These restrictions apply to *running SupportBridge agents*; Codex may of course edit project source while developing the product.

## C. Demonstration domain contract

**Shipping policy:** Free shipping when *pre-discount merchandise subtotal* is **at least USD 100.00**. Otherwise shipping is USD 7.50. Percent discount applies to merchandise. Taxes, multiple currencies, and actual payment capture are excluded. Currency and rounding behavior documented; money stored/calculated as integer cents.

**Sample cart:** subtotal USD 110.00; 15% discount = USD 16.50; merchandise after discount USD 93.50. Correct release calculates free shipping from USD 110.00 and returns total **USD 93.50**. Faulty release uses USD 93.50 to determine eligibility and adds USD 7.50, total **USD 101.00**.

**Control A:** Same USD 110.00 cart with 5% discount → USD 104.50 on *both* releases; no added shipping.  
**Control B:** USD 80.00 cart with 15% discount → USD 68.00 merchandise + USD 7.50 shipping = **USD 75.50** on *both* releases.  
**Boundary:** Exactly USD 100.00 before discount qualifies for free shipping; document inclusive threshold.

**Misleading evidence:** An older resolved duplicate-payment ticket. Agent may suspect it, but the current synthetic transaction has only **one** payment event and the unexpected amount appears as a **shipping line item** in the quote. Never force the model to pick the wrong hypothesis; stage a realistic ambiguity and let it decide.

**Realness:** Execution is genuine against deployed application endpoints; all tickets, product data, policy and payment ledger are fictional. GitHub reads are actual API calls to our own public demo repository; cache hits are labeled. The production-impact and causal-commit claims remain unverified.

### Version provenance

Create normal Git history for the demo checkout: baseline correct implementation, meaningful release change that introduces regression, and additional benign commits. Pin two SHAs/tags. At build time, package two immutable checkout implementations derived from the corresponding versions, with a checked `release_manifest.json` mapping release ID → source SHA → artifact hash. Validate correspondence in tests. A test must call the actual versioned implementation, not an endpoint returning a canned diagnosis. Keep evaluation answer keys outside all agent-readable paths.

## D. Architecture

```
Browser / Next.js (Vercel production domain)
    │
    ├── Investigation workspace, synthetic checkout, results, approval queue
    │
    └── /svc/api/* (Vercel Services routing, or same-origin proxy)
              │
              ▼
         Python FastAPI
              │
              ├── LangGraph StateGraph + deterministic coordinator
              │      ├─ Support Investigator ── searchTickets/readPolicy
              │      ├─ Repository Investigator ── GitHub read-only tools
              │      ├─ Reproduction Agent ── allowlisted experiment tool
              │      └─ Evidence Verifier ── immutable evidence + fresh replay
              │
              ├── Synthetic checkout V1/V2 HTTP routes + payment ledger
              ├── Separate oracle/assertion library
              ├── Gemini/LiteLLM model adapter (server-only)
              └── Managed PostgreSQL (sessions, stages, runs, evidence, approvals)
```

**Deployment primary:** Vercel Services public beta with `frontend/` Next.js and `backend/` FastAPI in one participant-owned repository, following the official Vercel starter. **First deployment gate (Nov 20):** deploy a minimal frontend → Python health API request on an incognito-accessible production URL. **Fallback:** two Vercel projects connected to the same repository (Next frontend plus FastAPI backend), with a same-origin Next.js proxy to the backend if Services fails. Keep the frontend domain as the sole submitted URL, with both services hosted on Vercel. Verify account/plan support and routing rather than assuming.

**Python:** 3.12+, FastAPI, Pydantic v2, httpx, LangGraph, LangChain/OpenAI-compatible model client, pytest, ruff, psycopg/Postgres checkpointer as appropriate. **Frontend:** Next.js App Router, TypeScript, Tailwind, component library only if it accelerates delivery. Avoid adding Python worker services or queues for the MVP.

**Durability:** FastAPI/Vercel is serverless. Do not rely on memory, local files, or unawaited background tasks to survive requests. Partition the investigation into **bounded client-driven stages** and persist state/evidence, with idempotency keys and one active execution lease per run. The browser can poll `/investigations/{id}/events` and call a step endpoint; refresh resumes from stored state. Store only small references/snippets in graph state; raw evidence in evidence records. Consider LangGraph Postgres checkpointer for durable graph resumability after the basic staging pattern works; application records still need separate tables.

## E. Multi-agent contracts

**Coordinator (NOT an LLM):** validates `InvestigationInput`, creates the evidence ledger, executes Support and Repository investigators independently in parallel, hands results to Reproduction, routes to Verification, allows at most one targeted loop, records terminal status and budgets. The coordinator determines *when* nodes run, not *what diagnosis they must produce*. No agent is allowed to approve/save a case without a user action.

| Agent | Unique question | Model-driven work | Tools / permissions | Output |
|---|---|---|---|---|
| 1. Support Investigator | What did customer report; what should happen? | Choose relevant queries, distinguish historical incident from applicable policy, identify missing facts | `search_tickets`, `read_policy`, `search_kb` — synthetic corpus only | `SymptomAssessment`, policy refs, support hypotheses |
| 2. Repository Investigator | What source/release changes might matter? | Select commit/diff/file reads, rank candidates with uncertainty; **identify candidate file, line range, pinned SHA/permalink** | `list_commits`, `compare_releases`, `read_file_at_sha` — own public repo, read-only | `CodeHypotheses`, suspected location or explicit `unknown`, SHAs, permalinks |
| 3. Reproduction Agent | What experiment distinguishes plausible hypotheses? | Choose bounded test plan, inspect raw execution, optionally change plan once | `run_experiment`, `read_evidence`, `read_payment_events` — allowlisted sandbox only | `TestPlan` and `TestExecution` references, behavioral hypotheses |
| 4. Evidence Verifier | Do the raw results actually support the claimed defect? | Challenge interpretation/causal claims, request one follow-up or abstain | `read_evidence`, `replay_experiment`, `read_policy`; no writes | `Verdict`, limitations, engineering escalation draft |

**True agentic criteria:** Agent 3 must choose a material experiment from multiple valid allowed operations, react when outcomes contradict initial explanations, and propose a revised test. Agent 4 must be able to reject a weak claim. The repo and support investigators must make separate evidence selections. Do not make four identical prompts or a fixed `if scenario_id == X: answer` pipeline. Deterministic tools calculate arithmetic, fetch resources, execute requests, and record pass/fail; LLMs propose investigative actions and interpret evidence. **Holdout requirement:** the same workflow must respond correctly to a changed cart/discount and to at least one missing-evidence or healthy-input case, with genuine model-selected tool calls recorded. No fabricated narrative or prefilled verdicts.

**Important nuance:** If native tool calling is unavailable on organizer model, we can accept model-generated structured action proposals validated by Pydantic and dispatched by host Python code. This is still model-selected tool execution, but must be truly result-dependent; not just a decorative prompt sequence.

## F. Shared contracts and evidence requirements

Suggested Pydantic contracts:

- `InvestigationInput`: `session_id`, `run_id`, `complaint`, optional synthetic `ticket_id`, `product_id`, release allowlist, supported cart parameters, environment, timestamp.
- `Hypothesis`: ID, claim, supporting evidence IDs, contradicting evidence IDs, information needed, candidate distinguishing test.
- `TestPlan`: selected release IDs, fixture ID, operation sequence (known DSL only), cart amount/discount and other bounded parameters, independent policy assertion ID, rationale.
- `TestResult`: host-generated execution ID, exact HTTP requests/responses, fixtures and SHAs, assertion outcomes, times, errors, source hashes.
- `Verdict`: `behavior_status` = `verified_regression` / `not_reproduced_in_tested_scope` / `insufficient_evidence` / `environment_blocked`; `cause_status` = `unknown` / `suspected` (not code-patch-verified); claims, citations, tested and untested scope, limitations.
- `EscalationDraft`: human-readable title, business impact, inputs, steps to reproduce, actual/expected responses, rule evidence, release SHA, **suspected file/line/commit/permalink when defensible, otherwise explicit unknown reason**, uncertainties, next action, approval status.

**Evidence integrity:** Host-generated ID for each artifact. Agents may cite existing evidence IDs but cannot invent IDs, modify test results, claim passed assertions, or access evaluator answer keys. Source citations must resolve in the UI. Keep pinned GitHub links and retrieval timestamps. Replays execute fresh requests in a separate session namespace.

**Tool safety:** Typed request schemas, fixed endpoint/repo/path allowlists, response size/time limits, no arbitrary URLs, no model-originated Python/JS/SQL/shell, no write GitHub credentials or mutation tools, no access to private org resources; treat retrieved tickets, documentation and repository contents as untrusted data. Include a prompt-injection fixture and a denied-tool-action test. A system prompt also states “investigation-only; never modify code,” but permission boundaries are enforced by Python tools rather than prompt text alone.

**Evidence gate:** The host independently validates existence of evidence IDs, version/source mappings, raw HTTP observations and applicable policy before issuing `verified_regression`. Independent verification uses fresh sandbox execution and a separately implemented policy checker; do not let a model set pass/fail or source identity directly.

**Human-in-the-loop (application-level MVP):** The graph finishes and persists a draft (`awaiting_approval`), then a user may approve or reject it through FastAPI. Only an approved, session-authorized, verified draft becomes a saved synthetic engineering escalation. Store the review decision and make approval idempotent. No LangGraph interrupt/resume requirement unless later justified; never silently approve.

## G. FastAPI / Frontend API surface

Suggested API contracts (names subject to adjustment in the first code milestone):

| HTTP path | Purpose |
|---|---|
| `GET /svc/api/health` | Vercel deployment smoke test |
| `GET /svc/api/cases` | Public synthetic sample complaints |
| `POST /svc/api/investigations` | Create run, reserve budget, initialize state |
| `POST /svc/api/investigations/{runId}/step` | Advance one bounded graph stage; idempotent |
| `GET /svc/api/investigations/{runId}` | Current state/status and findings |
| `GET /svc/api/investigations/{runId}/events` | Visible agent/tool events (polling MVP) |
| `GET /svc/api/investigations/{runId}/evidence/{id}` | Session-scoped raw evidence |
| `POST /svc/api/investigations/{runId}/replay` | Re-execute allowed plan with bounded input variations |
| `POST /svc/api/investigations/{runId}/approve` | Explicit, authorized human approval; persist one escalation idempotently |
| `POST /svc/api/investigations/{runId}/reject` | Human rejects draft; persist review decision without creating an escalation |
| `GET /svc/api/escalations` | Session-scoped approved case queue |
| `POST /svc/api/sandbox/quote` | Real sandbox release quote operation |
| `GET /svc/api/sandbox/payment-events` | Synthetic payment ledger, scoped |

Front-end screens:

- `/` — compelling landing/investigation start, preloaded sample case, one obvious primary action, synthetic disclosure.
- `/investigations/[id]` — step/activity timeline, parallel agent cards, changing hypotheses, actual test matrix, evidence drawers, policy and pinned GitHub file/line links, final verdict, human approval/rejection, **measured** run duration and customer-impact summary.
- `/sandbox` — interactive checkout with version and discount controls, clearly separate **raw replay** from a fresh AI investigation.
- `/cases` — approved synthetic escalations; support engineer-ready evidence record.

Do not render private model chain of thought. Show observable actions, tool names, outcomes, evidence and synthesized explanations.

## H. Storage and session strategy

**During first prototype:** Python in-memory/JSON fixtures with local test runner; no database migration needed until functionality is proven. **Before public agent runs:** persist sessions/runs/evidence/budgets; never depend on serverless in-memory state to protect paid model usage.

**Public MVP:** managed PostgreSQL via Neon or Supabase (choice based on fastest successful connection). Minimal tables:

- `sessions(id, created_at, expires_at, usage_count)`
- `investigations(id, session_id, complaint, status, current_stage, state_json, created_at, updated_at, lease_until)`
- `evidence(id, investigation_id, kind, source_url, source_sha, payload_json, content_hash, created_at)`
- `events(id, investigation_id, sequence, agent, tool, type, payload_json, created_at)`
- `escalations(id, investigation_id UNIQUE, session_id, approved_at, payload_json)`
- `reviews(id, investigation_id UNIQUE, session_id, decision, decided_at, reviewer_note)` — approval/rejection audit trail
- `usage_records(id, investigation_id, model, input_tokens, output_tokens, amount_if_known, created_at)`

Opaque HTTP-only session cookie and server-issued scope; never rely on user-provided session IDs for authorization. Purge public synthetic runs after a short configured retention window. Avoid double writes with transaction/idempotency constraints.

## I. Model and budget strategy

Development provider: Gemini with a generic OpenAI-compatible adapter where possible. Submitted provider: SSI LiteLLM environment variables `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL`. Provider adaptation must be verified for structured outputs and tool calls; do not assume tool-calling parity. Secrets strictly server-side, never `NEXT_PUBLIC_*`.

**Target:** roughly 5–8 calls per successful investigation; **hard cap:** 10 calls including structured-output repairs, 1 hypothesis revision, <=8 experiment executions including verifier replay. Aim to keep retrieved evidence concise. The Work research suggested an illustrative typical 17,600 input + 2,800 output tokens and planning ceiling 40,000 input + 6,000 output tokens per run; treat these as **unmeasured planning figures** until observed. Formula for cost: `(input_tokens × input_price + output_tokens × output_price) / 1,000,000`, plus any provider-specific billable categories. Prices and SSI spend cap are unknown.

**Protect public budget:** 1 active investigation per anonymous session, small global concurrency cap, adjustable daily cap, maximum 1–2 new AI runs per session/day, server-side rate limits and budget reservation, stop switch, cached immutable GitHub source. Unlimited local deterministic replay need not consume LLM tokens, but it must have independent abuse limits. Clearly label recorded example runs instead of presenting them as fresh.

### Environment variables and provider switching — explicit implementation contract

**Non-negotiable:** All credentials and model-provider configuration are loaded at runtime from environment variables on the **Python/FastAPI server only**. The browser does not receive any AI provider keys. We must be able to change providers from Gemini to organizer LiteLLM by changing environment configuration and redeploying, **without editing agent, graph, tool or prompt code**.

Include a committed `.env.example` with **placeholders only** (no real tokens or account identifiers):

```dotenv
# Set one provider for each environment: gemini (development) or litellm (submission)
MODEL_PROVIDER=gemini

# Development provider: Gemini
GEMINI_API_KEY=
GEMINI_MODEL=

# Organizer-supplied competition gateway
LITELLM_BASE_URL=
LITELLM_API_KEY=
LITELLM_MODEL=

# Optional server integrations / hosted persistence
GITHUB_TOKEN=
DATABASE_URL=

# Application guardrails (tune only after measuring actual usage)
MAX_MODEL_CALLS_PER_RUN=10
MAX_EXPERIMENTS_PER_RUN=8
AI_RUNS_ENABLED=true
```

- Use `backend/providers/model_factory.py` or equivalent as the **only** place that reads these provider variables and constructs the appropriate LangChain chat model/client. Agent nodes request `get_chat_model()` and remain provider-agnostic.
- Development: `MODEL_PROVIDER=gemini` with Gemini credentials configured in a local ignored `.env`; production/submission: `MODEL_PROVIDER=litellm` with the three organizer variables set in the backend's **Vercel Production environment settings**. Do not commit either key. A redeploy/restart is normally required for changes to take effect in serverless functions.
- Validate the *selected* provider's required variables on startup. Missing credentials fail safely with an operator-readable error; **never silently switch** from LiteLLM to Gemini in the submitted app. Only the selected provider's credentials are necessary in that environment.
- Include `.env`, `.env.local`, `.env.production`, `backend/.env` and analogous secret files in `.gitignore`, retaining only `.env.example`. Never print keys, send them in API responses, put them in client JavaScript or use `NEXT_PUBLIC_` for secrets. Sanitize error logs and traces.
- Vercel Services or separate Vercel projects: attach secret variables to the **Python backend service/project**, not the public Next.js frontend. Frontend uses same-origin proxy/rewrite or a nonsecret API URL; enforce CORS and allowed origins if split.
- LiteLLM compatibility isn't guaranteed by OpenAI-shaped APIs alone. On receipt of credentials, test request shape, structured-output support, tool/action proposals, role ordering, token reporting, limits, timeouts and error handling. If native tool calling is incompatible, the server may dispatch **schema-validated, model-selected action proposals** using the same tools; it must still make real organizer-model calls.
- Add smoke tests for `gemini`, `litellm`, missing selected-provider vars, invalid model name, disabled AI runs, malformed provider response and no-secret-leakage in the API or browser bundle. Test a full multi-agent investigation after the provider switch, not just `/health`.

**Provider switch acceptance test:** With no code changes, switch the backend's `MODEL_PROVIDER` to `litellm`, configure `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL` in Vercel, redeploy, and run a fresh investigation. Confirm all four specialist agents' model requests, tool calls, and final evidence were produced through the organizer gateway and the server recorded actual token usage.

## J. Dataset and reliability cases

**Initial fixtures (30–40h):** 8–12 synthetic historical tickets, 3–4 policies/KB notes (including one misleading outdated article), 2 releases with real commits, 4 cart fixtures, payment events, 6 current complaints phrased differently. **50h extension:** ~24 tickets, 6 docs, 8 meaningful commits, 12 carts, 4 tenant configurations, 24 evaluation cases.

At minimum test:

- Failing case: USD 110 / 15% discount; correct policy; regression on current release.
- Healthy control: same cart with 5% discount; must not falsely report bug.
- Below-threshold control: USD 80 / 15%; must not falsely report bug.
- Inclusive-boundary: USD 100 pre-discount; expected free shipping.
- Misleading old payment ticket: should be superseded by current payment count and quote line evidence.
- Incomplete case missing cart/version or authoritative rule: `insufficient_evidence`, request specific missing information.
- Unavailable checkout endpoint: `environment_blocked`, not 'bug reproduced'.
- Conflicting/stale policy: refuse definitive business-rule verdict unless precedence is established.
- Changed amount/discount, paraphrased complaint, renamed ticket and added irrelevant evidence: no scenario-name-based conclusion.
- Concurrent sessions, approval replay, expired session, malicious instructions in ticket/repo text.

**Quality gate (indicative, not validated):** all deterministic unit tests pass; at least 6/8 supported failure variations reproduce with evidence; no false `verified_regression` verdict on the initial negative/unknown cases; **all four LLM agents** execute authentic, visible model/tool steps; the likely code location resolves to a pinned permalink for the primary failing case; all rendered citations resolve; approval/rejection, session isolation and idempotence pass. Run repeated warm/cold live investigations and measure p50/p95 latency, costs and completion rates; don't claim a target was measured until it is. Include a denied code-write attempt and an untrusted-ticket prompt-injection test.

## K. Repository layout (participant-owned public monorepo)

```text
supportbridge/
  README.md
  AGENTS.md                      # repository-wide coding instructions
  vercel.json
  .gitignore
  .env.example                   # names only, no real keys
  frontend/
    app/
      page.tsx
      investigations/[id]/page.tsx
      sandbox/page.tsx
      cases/page.tsx
      api/                         # same-origin proxy if needed
    components/
    lib/
    package.json
  backend/
    main.py                       # FastAPI application
    requirements.txt / pyproject.toml
    agents/
      support.py
      repository.py
      reproduction.py
      verification.py
    graph/
      state.py
      workflow.py
      routing.py
    tools/
      support_corpus.py
      github_read.py
      experiments.py
      evidence.py
    sandbox/
      releases/
        previous.py
        current.py
      models.py
      api.py
      release_manifest.json
    oracle/
      shipping_contract.py
    contracts/
      investigation.py
      tests.py
      evidence.py
    storage/
    providers/
      model_factory.py              # provider switch via env, no agent changes
    data/
      support_tickets.json
      policies.json
    tests/
  eval/                            # never tool-readable
    cases.json
    test_agent_behavior.py
  docs/
    IMPLEMENTATION_BLUEPRINT.md  # THIS document
    architecture.md
    demo-script.md
    limitations.md
```

## L. Schedule and stop/go gates (PKT; updated at lock on Nov 20)

| Date | Focus | Exit criterion |
|---|---|---|
| Nov 20 | **Milestone 1A only:** repo + `AGENTS.md` + this blueprint; scaffold official Next.js/FastAPI starter; local and public Vercel health smoke test | Incognito-accessible frontend calls real Python `/health` successfully. If Vercel Services fails, immediately assess the two-project Vercel fallback. |
| Nov 21 | **Milestone 1B:** two actual checkout behaviors, independent oracle, real Git history, version manifest, boundary/control pytest tests | Previous/current return expected numbers and GitHub SHAs are traceable to actual implementations. |
| Nov 22 | Data corpus, allowlisted tool adapters, evidence IDs, execution DSL, read-only GitHub calls | Manual investigation can retrieve tickets/policies/diffs and execute genuine test tools without an LLM. |
| Nov 23 | Three model-driven LangGraph investigation agents, adaptive tool selection and retest | One live model-driven investigation runs and reacts to contrary evidence or changed inputs. |
| Nov 24 | Fourth LLM verifier, evidence gate, likely code file/line/commit, durable storage, human approval/rejection | Four-agent run with source-linked report and session-persisted approval state. |
| Nov 25 | Product UI, complete investigation trace, business-value framing, adversarial/negative cases, budget/secret controls | A stranger can use the deployed product; no fake evidence or unsupported claims. |
| Nov 26 | Feature freeze, smoke and holdout evaluation, latency/cost optimization, README/demo rehearsals | Stable public MVP; remaining changes limited to bug fixes and integration. |
| Nov 27–28 | Organizer LiteLLM key/model, env-only provider switch, tool/action compatibility and budget checks | Full four-agent live run through organizer model; errors and limits handled. |
| Nov 29 | Final incognito Vercel + GitHub checks; submit URLs and ≤600-char summary before 23:59 PKT | Submission confirmed; public app remains available for judging. |

**Execution discipline:** Deliver one tested milestone at a time. Checkpoint 1A is a deployed frontend-to-Python health request, *without* agents or checkout code; 1B implements checkout and version provenance. Time is tight: prioritize complete, genuine four-agent investigation over secondary bug scenarios or visual extras. A three-agent fallback may remain a useful emergency demo but must be reported as a deviation from this locked scope. Date estimates are planning targets, not promises.

## M. Judge-facing demo (target 90 seconds; do not fake timings)

| Approx. sequence | What the judge sees | Claim |
|---|---|---|
| 0–10s | A customer complaint: extra checkout charge; payment suspected | Understandable business problem |
| 10–25s | Support and Repo agent tool actions in parallel; old ticket, policy, commit evidence | Multi-agent evidence search |
| 25–40s | Payment-event test shows one event; quote breakdown shows shipping line | Model-selected experiment challenges hypothesis |
| 40–60s | Previous/current release comparison, raw HTTP requests/responses and independent failed policy assertion | Genuine regression reproduction |
| 60–75s | Verifier replays and challenges candidate source cause; pinned GitHub diff view | Evidence verification and trustworthy limits |
| 75–85s | Judge changes 15% to 5%, deterministic replay returns healthy outcome | Interactive, non-canned behavior |
| 85–90s | Human approves evidence-backed engineering case | Finished useful business artifact |

Runtime is **not measured**; do not insist on these timings. If model latency is too high, begin with a **clearly labeled previously recorded investigation** and perform a live changed-input replay, then offer full live model execution. The actual public app must still support a genuinely live agent run and be tested with organizer model.

## N. Hackathon submission checklist

- Registration: **complete**, per participant.
- Own participant GitHub repository **public**; clean history and no secrets.
- Own Vercel account; main production `.vercel.app` URL, not deployment-specific preview link; publicly accessible in incognito.
- App uses real LiteLLM model calls with participant's server-side key; cap use and keep it live until mid-December judging completes.
- Only synthetic/public data; safety controls and user consent for write actions.
- Add compelling README: product pitch, 4-agent diagram, truth labels, install/deploy instructions, one demo case, precise limitations, test command and a short evaluation table.
- Official submit form requires **public GitHub repo URL, production Vercel URL and project summary <=600 characters**. No mandatory slide deck or video identified in the published guide. Resubmission permitted before deadline; latest version is evaluated.
- Official site frames the event as the Nov 27–29 weekend; published pages reviewed here do not explicitly settle pre-kickoff implementation eligibility. Follow any explicit organizer communication on prebuilding.

**Draft submission summary (edit after build; <600 characters):**  
"SupportBridge is a multi-agent regression investigator for software support teams. Four Python/LangGraph agents investigate customer complaints, retrieve tickets and GitHub release evidence, run live checkout API experiments, and independently verify business-rule violations. A user can replay test inputs and approve an evidence-backed engineering escalation. The public demo uses exclusively synthetic business data and a controlled checkout sandbox."

## O. First implementation assignment — execute now

**Milestone 1A only: deployment foundation.** First create the participant-owned public repository, place `AGENTS.md` at its root and this file at `docs/IMPLEMENTATION_BLUEPRINT.md`, and use the official Vercel Next.js/FastAPI starter as the reference. Scaffold Next.js/React/TypeScript/Tailwind and Python 3.12+/FastAPI/Pydantic v2, implement `/health`, a minimal frontend calling the API, `.gitignore`, `.env.example`, README and basic backend health tests. Run locally; then attempt a *real* public Vercel deployment and incognito smoke test. **Do not implement checkout, LangGraph, database or UI polish in 1A.** Stop and report actual test/deployment outcomes, changed files and blockers.

**Milestone 1A is complete only when:** (a) the frontend locally calls a real Python health endpoint, (b) backend tests pass, (c) no secrets are committed, and (d) the frontend publicly calls Python on a verified production Vercel URL. If the participant hasn't connected GitHub/Vercel yet, provide exact manual instructions and mark public deployment **pending**—never fabricate success.

**Milestone 1B follows after review:** Implement the two versioned checkout APIs, independent oracle, Git history and release artifact manifest; pass the 110/15, 110/5, 80/15 and $100 boundary tests. Still no agents during 1B.

## P. Primary reference URLs (initially verified 18 November 2026; revalidate if configurations change)

- SSI rules and rubric: https://ssi-ai-hackathon.vercel.app/rules
- SSI guide, including Python/LangGraph and submission: https://ssi-ai-hackathon.vercel.app/guide
- SSI submission page: https://ssi-ai-hackathon.vercel.app/submit
- Vercel Next.js + FastAPI starter: https://vercel.com/templates/fast-api/next-js-fastapi-starter
- Vercel Services monorepo: https://vercel.com/blog/vercel-services-run-full-stack-on-vercel
- LangGraph persistence: https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/persistence.mdx

## Q. Locked decision log (Nov 20, 2026)

1. **Four named LLM agents are in MVP**, with a deterministic LangGraph coordinator. No fifth supervisor agent.
2. **Likely offending file/line/commit with pinned GitHub URL is required** for the primary supported regression; uncertainty must be visible.
3. **Running agents have no source-modification ability.** No code edits, generated patch execution, commits or PRs. Codex editing the repository during *development* is separate from the final product's permissions.
4. **Human-in-the-loop** happens at engineering-case acceptance: the investigation finishes, then the user explicitly approves/rejects in our own app; no external write action.
5. **Four guardrail layers:** prompt/untrusted-data boundaries, Python-enforced allowlisted tools, bounded orchestration/cost, independent evidence checks. No extra guardrail LLM.
6. **Output:** a structured evidence-backed investigation result, the observable agent/tool trace, and a proposed engineering escalation. Honest statuses include verified, not reproduced in tested scope, insufficient evidence and environment blocked.
7. **Business-value proof:** customer-impact context, measured automation duration, reproducibility and handoff completeness. No invented savings metrics.
8. **Model credentials:** env-only provider selection (Gemini development, organizer LiteLLM submission) and backend-only secret storage; changing provider must not require editing graph/agents.
9. **Scope control:** one synthetic commerce checkout regression family; genuine API execution, not canned answers. A second defect family and autonomous fixes are out of this MVP.
10. **Build order:** Milestone 1A deployment first, 1B checkout second, then tools → LangGraph → verification/storage → UI → model switch and evaluation.
