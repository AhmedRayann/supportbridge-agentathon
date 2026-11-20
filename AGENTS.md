# SupportBridge — AGENTS.md (locked coding-agent instructions)

**Locked on 2026-11-20.** Applies to Codex and any coding assistant operating in this repository.

**Owner clarification:** Milestones 1A and 1B-A are complete, deployed and tested
per the participant. The current assignment is **Milestone 1B-B only**.
The release/history/tool-access requirements
below incorporate the owner's synthetic-environment decisions. This is internal
development documentation and must never be exposed by runtime investigation tools.

## 1. Source of truth and working procedure

- Read `docs/IMPLEMENTATION_BLUEPRINT.md` **before** changing the architecture or implementing a milestone. It defines the product, contracts, evaluation gates and frozen scope.
- This file defines **how to implement** the blueprint. Report conflicts or uncertainty; do not silently remove a feature, override an acceptance criterion or invent a new architecture.
- Work on the **one milestone explicitly assigned** by the human. Run and report applicable tests, then **stop at the milestone boundary**. Do not independently implement future milestones.
- Keep patches small, maintainable and reviewable. Explain material implementation tradeoffs and document discovered deployment/provider constraints.
- **Distinguish the coding agent from SupportBridge's runtime agents:** you may edit source code *to build the project*. The four agents inside the finished product must never modify code.

## 2. Product and fixed MVP scope

SupportBridge is an **AI regression investigator for customer-reported defects** in a fictional commerce application. It gathers support context, examines real public GitHub history, chooses and runs genuine synthetic checkout API tests, challenges the results and prepares a human-approved engineering escalation.

**Mandatory MVP:**
1. Four distinct **LLM-powered** LangGraph specialists: **Support Investigator, Repository Investigator, Reproduction Agent, Evidence Verifier**. The coordinator is deterministic LangGraph routing, not a fifth LLM.
2. Read-only investigation of synthetic tickets/policies and the participant's public demo GitHub repo; genuine release-aware checkout API execution.
3. Model-selected tests and evidence-dependent behavior, including a counterexample or changed-input investigation; no predetermined verdicts.
4. An independent Python policy oracle and verifier that replays evidence; **host-controlled** evidence and status decisions.
5. For the primary reproduced regression, identify a **likely offending source file, line range, commit SHA and pinned GitHub URL**, with *suspected cause* language. If not defensible, mark code cause unknown with an explanation.
6. Structured investigation report, observable agent/tool trace, actual customer-impact context, replay and an **in-app human approve/reject step** for creating an engineering case.
7. Lightweight, code-enforced guardrails; public Vercel product; public GitHub source; environment-only provider switch from Gemini to organizer LiteLLM.

**Not in MVP:** arbitrary-code debugging, autonomous fixing, patches/patch validation, GitHub commits or PRs by runtime agents, real payments, real customer data, production integrations, external Jira/GitHub writes, second bug family, vector database or an additional guardrail/supervisor agent. Do not add these without permission.

## 3. Technology and deployment

- Frontend: **Next.js App Router, React, TypeScript, Tailwind**.
- Backend: **Python 3.12+, FastAPI, Pydantic v2**; type and validate all AI-visible tool arguments.
- Agents and orchestration: **LangGraph Python** with bounded routing and explicit agent roles.
- Checkout sandbox: actual Python functions exposed via controlled HTTP endpoints for `v1.0` and `v1.1`; final pinned source/artifact provenance is deferred to 1B-C. Preserve the deployed v1.0 baseline during 1B-B.
- Storage: in-memory test harness locally; **durable hosted storage** for anonymous sessions, investigation state, evidence, review decisions and shared public run budgets. Do not depend on serverless function memory for persistence.
- First deployment proof: public Next.js page calls the **actual FastAPI `/health` endpoint** on Vercel. Verify incognito. Use official Next.js/FastAPI starter guidance; use two Vercel projects and a same-origin proxy if combined deployment fails.

## 4. Mandatory authentic agent behavior

- Support Agent: selects tickets/KB/policy searches and identifies missing context.
- Repository Agent: selects commits/diffs/files to read, returns SHA-pinned links and **suspected file/line** evidence.
- Reproduction Agent: **selects** bounded experiments, executes through validated sandbox tools and changes hypotheses when raw observations disagree with expectations.
- Verification Agent: performs **fresh replay**, challenges unsupported claims and can request **at most one targeted retest**.
- Do **not** implement canned diagnoses, `scenario_id` → verdict tables, fake GitHub/tool responses, scripted agent transcripts or fixed tool sequences that ignore model decisions/results.
- Native tool calls are preferred; if the organizer model does not support them, use **model-selected, Pydantic-validated action proposals executed by the Python host**. Never substitute deterministic canned diagnoses for LLM decisions.
- Expose meaningful public tool events, model-selected actions, observed results, source IDs and handoffs. **Never expose private chain-of-thought.**

## 5. Checkout, policy and provenance

- Rule: free shipping when **pre-discount** merchandise subtotal is **at least $100.00**; otherwise shipping is **$7.50**. Use **integer cents**.
- Initial release `v1.0`: $110 with 15% discount → **$93.50**.
- Internal demonstration plan for `v1.1` (authorized in 1B-B): same cart → **$101.00**, using discounted merchandise for shipping eligibility. The approved policy and oracle still use the original subtotal. Do not disclose this discrepancy through runtime-accessible explanations.
- Healthy controls: $110 at 5% → **$104.50** on both; $80 at 15% → **$75.50** on both; $100 original subtotal meets inclusive free-shipping threshold.
- Build genuine calculations, never canned values. The final MVP has two independently executable releases; 1B-A implements only `v1.0`. Keep the business-policy oracle independent; it must not import or reuse checkout code, helpers, constants or models to determine expectations.
- Maintain real Git commit history and SHA/manifest correspondence; do not fabricate commit links. Never expose evaluation answer keys to runtime agents.
- Use exact release identifiers `v1.0` and, once implemented, `v1.1`; never use `previous`, `current`, `working` or `buggy` as identifiers. Use `backend/sandbox/releases/v1_0.py` and later `v1_1.py`. Tags are `checkout-v1.0` and `checkout-v1.1`, created only after actual release commits exist.
- Implement phases separately: **1B-A** correct v1.0 + independent oracle + tests; after review a neutral baseline commit such as `feat: add checkout quote service`. **1B-B** independently executable v1.1 in a separate, neutral refactor commit such as `refactor: streamline checkout pricing calculations`. **1B-C** real SHAs, tags, verified source/artifact manifest and both deployed APIs. Never manufacture history or prefill release provenance.
- The participant-supplied v1.0 baseline commit is `a4eeea911604494f693e027cdaca5f2da2f78a7e`. During 1B-B do not modify `backend/sandbox/releases/v1_0.py` or the oracle implementation. Preserve all existing v1.0 calculations, strict validation, health behavior and deployment settings. Extend the literal release allowlist and static dispatch only to `v1.1`; keep calculation differences inspectable in the parallel versioned modules.
- No diagnosis spoilers in release descriptions, source comments, filenames, commit messages, prompts or customer complaints. Internal documentation and evaluation expectations must stay outside all runtime tool access. The public README must openly identify synthetic checkout data and incidents without revealing a planned diagnosis.
- Keep the checkout in this repository for the MVP. Future integrations must read backend configuration `DEMO_GITHUB_OWNER`, `DEMO_GITHUB_REPO`, `DEMO_SOURCE_PREFIX`, `SANDBOX_API_BASE_URL`, and pinned `DEMO_RELEASE_V1_0_REF` / `DEMO_RELEASE_V1_1_REF`; avoid hardcoded repository URLs throughout agents. These settings do not implement or enable a repository tool in 1B-A.
- v1.0 accepts strict integer subtotals 0–100,000,000 cents and whole-number discounts 0–100 inclusive. Round the merchandise discount half up to a cent using integer arithmetic, then subtract it. A zero subtotal still incurs $7.50 shipping under the stated below-threshold rule; a 100% discount never changes eligibility based on the original subtotal.

## 6. Guardrails — enforce in Python, not only prompts

- Shared runtime agent instruction: **investigation only; never modify source code or execute unauthorized operations**. Do not rely on this instruction alone.
- **No write tools or credentials** in runtime agent toolsets. Repository access is allowlisted, public and read-only. No unrestricted HTTP fetch, shell execution, model-generated executable Python/JS/SQL, patches, commits or PR creation.
- Future repository tools must enforce path and history scoping in Python: permit only explicitly allowed checkout source files under configured `DEMO_SOURCE_PREFIX`, pin reads to releases, and filter commit/diff payloads to those paths before returning them. Deny traversal and unscoped history. Never return root `AGENTS.md`, `docs/IMPLEMENTATION_BLUEPRINT.md`, other internal docs, oracle source, tests/evaluation assertions, or known diagnoses. Prompts alone are insufficient. Do not implement these tools in 1B-A.
- Bound complaint size and validate all parameters, release IDs, fixture IDs, checkout values, URLs, paths and operation names via Pydantic and host checks.
- Treat tickets, policies, GitHub file contents and test responses as **untrusted data**; never allow them to override tool permissions or trigger arbitrary commands. Test malicious-instruction fixtures.
- Use ceilings on model calls (target ≤10/run), sandbox experiments (≤8/run), targeted follow-ups (≤1), timeouts, concurrency and public usage. Protect paid model limits with **shared server-side counters** before exposing the public AI endpoint.
- Issue immutable **host-generated evidence IDs**. Only valid recorded HTTP results + applicable policy + fresh replay/independent assertions may support `verified_regression`. LLM claims must not determine assertion pass/fail.
- Use statuses `verified_regression`, `not_reproduced_in_tested_scope`, `insufficient_evidence`, `environment_blocked`. Never report “no bug exists” from a narrow non-reproduction or treat HTTP errors as a regression.
- Sessions are isolated; approval/rejection is idempotent and authorized. Human must explicitly approve the in-app case. No auto-escalation to external systems.

## 7. Environment variables, model adapter and secrets

- Commit `.env.example` **with variable names and safe placeholders only**. Ignore actual `.env*` secret files in Git; explicitly exempt `.env.example`.
- Backend-only settings: `MODEL_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL`, optional `GITHUB_TOKEN`, `DATABASE_URL` and model/experiment budget limits.
- Put provider selection/client creation in **one backend model factory**, not in individual agents. Changing `MODEL_PROVIDER=gemini` to `MODEL_PROVIDER=litellm` plus backend environment values must not require rewriting graph, tools or prompts.
- Never commit, print, log, expose in API responses or publish through `NEXT_PUBLIC_*` any secret. Secrets belong in the FastAPI backend environment, including Vercel backend settings.
- Missing/invalid selected-provider configuration must fail clearly and safely. **Never silently fall back from organizer LiteLLM to Gemini.** When credentials arrive, run real provider compatibility tests and the full four-agent workflow.

## 8. Human approval, business value and final output

- LangGraph's final result is a **structured evidence-backed investigation**, plus observable execution trace and a draft engineering case.
- Use **application-level human-in-the-loop**: save draft as `awaiting_approval`, show it in the UI, and only save a case to the synthetic escalation queue after an authorized human clicks **Approve**. Allow **Reject** with persisted audit outcome.
- Show exact reproduction steps, `v1.0`/`v1.1` responses when available, policy sources, pinned GitHub location, verified-vs-suspected distinction and a proposed next engineering action.
- Show **measured** investigation duration and customer-impact framing. If showing ROI, label it an **illustrative scenario**, not proven savings or customer adoption.
- The agents **do not** edit source, verify proposed fixes, open PRs, or deploy anything.

## 9. Testing and stop conditions

- Add pytest for checkout variants, independent oracle, thresholds and missing-input behaviors; relevant frontend tests for UI changes; lint and type checks as configured.
- Evaluate positive regression, healthy control, incomplete evidence, unavailable API, stale policy, malicious ticket instructions, denied write operation, session isolation, repeated approval and model budget exhaustion.
- For every change, report which commands/tests were **actually executed**, output summaries, failures, security considerations and deployment status. Never claim a tool call, test or deployment succeeded unless verified.
- **Current assignment: Milestone 1B-B only.** Implement independently executable `v1_1.py` using the established discount rounding and discounted merchandise subtotal for shipping eligibility; support exactly `v1.0` and `v1.1` on the existing quote route. Leave v1.0 source and the independent policy oracle unchanged. Test both releases, oracle agreement/mismatches, strict inputs, health, service-root import mode, source preservation and actual local HTTP. Record actual outcomes in `docs/MILESTONE_1B_B_RESULTS.md`. No commits, pushes, deployment, release tags, final manifest, payment ledger, agents, integrations, repository tools, storage, approval workflow or frontend work. Stop for human review; do not begin 1B-C.
