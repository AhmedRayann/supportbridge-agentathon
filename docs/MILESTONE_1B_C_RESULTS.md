# Milestone 1B-C — release provenance

Prepared and checked on 21 November 2026 (PKT). Provenance artifacts are ready for
human review. Tag creation/push and peeled remote-target verification remain
pending. No commit, push, deployment, tag mutation or history rewrite was performed.
The next milestone has not started.

Internal development record: future runtime tools must exclude this report and
all internal assertions/specifications from LLM retrieval.

## Authoritative identities and manifest

Repository: `AhmedRayann/supportbridge-agentathon`.
Manifest: `backend/sandbox/release_manifest.json`, schema version 1.

| Release | Actual historical commit | Source path | Intended annotated tag |
| --- | --- | --- | --- |
| v1.0 | `a4eeea911604494f693e027cdaca5f2da2f78a7e` | `backend/sandbox/releases/v1_0.py` | `checkout-v1.0` |
| v1.1 | `c8473e4fcdb3f71630301c13c37fbf742c2a14ef` | `backend/sandbox/releases/v1_1.py` | `checkout-v1.1` |

The manifest stores those identities, full-SHA source URLs and source SHA-256:

- v1.0: `1f3c5449179b230ac37d8e7fd12434c070ff4d497c8a703b70f64045ff66a572`
- v1.1: `d630bbc1dc139deed48c75eb88620101d64e497556e867d1802142afe6f734e0`

Hashes were calculated from actual historical Git blobs, not invented. Current
calculation modules match those blobs with CRLF/LF normalization for Windows.
These are module source identities, not a hash of the entire deployment. The
closed manifest schema includes no diagnosis, scenarios, expected failures,
oracle details or preselected outcomes. `tag` names the intended reference without
claiming it exists. No API route or runtime manifest/Git loader was added.

## Independent Git history verification

Commands were run before modifying files. In this shared workspace the coding
account used `git -c safe.directory=D:/Agent-A-Thon/supportbridge-agentathon` for
read-only Git operations; no global Git setting was changed. The commands below
show the substantive arguments after that prefix.

`git log -2 --format='%H %s'` identified these actual commits (also shown by the
initial four-commit log):

```text
c8473e4fcdb3f71630301c13c37fbf742c2a14ef refactor: streamline checkout pricing calculations
a4eeea911604494f693e027cdaca5f2da2f78a7e feat: add checkout quote service
```

```powershell
git cat-file -t a4eeea911604494f693e027cdaca5f2da2f78a7e
git cat-file -t c8473e4fcdb3f71630301c13c37fbf742c2a14ef
git merge-base --is-ancestor a4eeea911604494f693e027cdaca5f2da2f78a7e c8473e4fcdb3f71630301c13c37fbf742c2a14ef
git ls-tree a4eeea911604494f693e027cdaca5f2da2f78a7e backend/sandbox/releases/v1_0.py
git ls-tree c8473e4fcdb3f71630301c13c37fbf742c2a14ef backend/sandbox/releases/v1_1.py
```

Actual outputs: both object types `commit`; ancestry command no stdout, exit 0.
Historical source entries:

```text
100644 blob 7584d05679f199e1783a9b899a6da654240d4dad backend/sandbox/releases/v1_0.py
100644 blob 035288a605c505988bac1f0911eb29a59d3fa8a4 backend/sandbox/releases/v1_1.py
```

The actual scoped history command:

```powershell
git diff --name-status a4eeea911604494f693e027cdaca5f2da2f78a7e c8473e4fcdb3f71630301c13c37fbf742c2a14ef -- backend/sandbox/
```

returned:

```text
M backend/sandbox/models.py
A backend/sandbox/releases/v1_1.py
M backend/sandbox/router.py
```

There is no historical one-line edit to v1.0. The parallel modules have meaningful
calculation differences that are already covered by the existing two-release
API/oracle tests. Source files, dispatch, validation and the approved policy were
not changed to manufacture a diff or outcome.

## GitHub verification performed in 1B-C

These full-SHA canonical source URLs independently returned HTTP 200 using HTTPX:

- [v1.0 source](https://github.com/AhmedRayann/supportbridge-agentathon/blob/a4eeea911604494f693e027cdaca5f2da2f78a7e/backend/sandbox/releases/v1_0.py)
- [v1.1 source](https://github.com/AhmedRayann/supportbridge-agentathon/blob/c8473e4fcdb3f71630301c13c37fbf742c2a14ef/backend/sandbox/releases/v1_1.py)

The corresponding `raw.githubusercontent.com` URLs also returned HTTP 200, with
byte-for-byte equality to the local historical Git blobs and the source hashes
above. This was an ad hoc verification, not an application GitHub client/tool.
The web-reader tool initially returned cache misses; direct HTTPX checks succeeded.

The [full-SHA comparison URL](https://github.com/AhmedRayann/supportbridge-agentathon/compare/a4eeea911604494f693e027cdaca5f2da2f78a7e...c8473e4fcdb3f71630301c13c37fbf742c2a14ef)
returned HTTP 200 too. Future investigators must read both pinned implementations
and cite their actual lines; broad comparison responses must be filtered to the
approved paths before any LLM exposure.

## Tag inspection and human follow-up

Actual local inspection command:

```powershell
git for-each-ref --format='%(refname:short) %(objecttype) %(objectname) %(*objectname)' refs/tags/checkout-v1.0 refs/tags/checkout-v1.1
```

Actual output: empty, exit 0. Neither local tag exists.

Actual remote command, checked initially and again after implementation:

```powershell
git ls-remote --tags origin 'refs/tags/checkout-v1.0' 'refs/tags/checkout-v1.0^{}' 'refs/tags/checkout-v1.1' 'refs/tags/checkout-v1.1^{}'
```

Actual output: empty, exit 0 (the recorded marker was `REMOTE_TAG_QUERY_EXIT:0`).
The successful query returned no matching remote refs; it was not a network
failure. No tags have been created, pushed, deleted or overwritten in this work.

Full recheck, existing-tag handling, annotation and peeled-target checks are in
[`REPOSITORY_PROVENANCE.md`](REPOSITORY_PROVENANCE.md). After human review, and
only while the corresponding tags are still missing both locally and remotely,
the exact creation commands are:

```powershell
git tag -a checkout-v1.0 a4eeea911604494f693e027cdaca5f2da2f78a7e -m 'Checkout v1.0'
git tag -a checkout-v1.1 c8473e4fcdb3f71630301c13c37fbf742c2a14ef -m 'Checkout v1.1'
```

Stop if either command fails. Verify each object's type is `tag` and resolve:

```powershell
git cat-file -t refs/tags/checkout-v1.0
git rev-parse 'refs/tags/checkout-v1.0^{commit}'
git cat-file -t refs/tags/checkout-v1.1
git rev-parse 'refs/tags/checkout-v1.1^{commit}'
```

Targets must equal the historical commits above, never a later HEAD. Then the
human may publish only these refs, without force:

```powershell
git push --atomic origin 'refs/tags/checkout-v1.0:refs/tags/checkout-v1.0' 'refs/tags/checkout-v1.1:refs/tags/checkout-v1.1'
```

Repeat the remote query and compare the `^{}` records to the approved commits.
An annotated tag has a distinct tag-object SHA; the bare tag ref is not the
commit identity. Existing tags must be verified rather than replaced, even when
they disagree. Remote peeled-target checks and tag-URL checks remain pending
until the human publishes the tags. Instructions were parsed, not executed.

## Automated/local checks actually executed

Windows, Python 3.13.14, existing virtual environment. Commands ran from the
repository root unless stated. No dependencies were installed or upgraded.

| Command/check | Actual result |
| --- | --- |
| `.venv\Scripts\python.exe -m ruff format backend/tests/conftest.py backend/tests/test_checkout_releases.py backend/tests/test_release_manifest.py` | New test formatting applied. |
| `.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests` | **227 passed**, 0 failed/skipped, 4.63s. All original 220 cases remain covered. |
| `.venv\Scripts\python.exe -m ruff check backend` | **All checks passed.** |
| `.venv\Scripts\python.exe -m ruff format --check backend` | **16 files already formatted.** |
| `.venv\Scripts\python.exe -m pip check` | **No broken requirements found.** |
| Exported backend: `python -m pytest -c backend/pyproject.toml backend/tests -q` | **222 passed, 5 skipped**, 1.74s, with `.git` absent. Only history-dependent checks skipped. |
| Inline Git source/config comparison and `tomllib`/`packaging` dependency checks | Both calculation files, oracle, API/validation, frontend, Vercel settings, Python selection, dependency files and environment examples unchanged from v1.1 commit. Both earlier reports preserve their full original text with appended updates only. Runtime pins match installed packages. |
| PowerShell parser on fenced instruction blocks | Five blocks parsed without syntax errors; no tag commands executed. |
| `git -c safe.directory=D:/Agent-A-Thon/supportbridge-agentathon diff --check` | Passed; Git emits existing LF-to-CRLF normalization notices. |

The exported backend was copied into an owned temporary directory without Git
metadata; the complete suite was run using the existing interpreter, then the
temporary copy was removed. The FastAPI app never depends on Git. Tests skip
history checks when `.git`, Git itself or pinned history is unavailable; manifest
identity/URL/hash/dispatch/API checks remain active offline.

Seven new tests verify the closed neutral schema, exact release IDs/approved
SHAs, path scope, commit-pinned URLs, source fingerprints, static dispatch/API
surface, historical source and ancestry. The first new dispatch test attempted
to inspect an internal route object's `.path` and failed on the installed FastAPI
version. It was corrected to use the public OpenAPI paths; final results above
pass. The production application was not changed. No frontend checks were needed.

## Production evidence versus this turn's checks

The participant confirmed successful Vercel deployment and eight production
checkout requests across v1.0/v1.1 using PowerShell, performed after the original
1B-B local verification. Those production requests were not rerun by the coding
agent during 1B-C. Independent 1B-C checks cover local Git/tests/configuration and
remote GitHub source/ref availability, not a new Vercel deployment.

The original 1B-B findings were not rewritten. Its dated post-implementation
update records the real commit and participant's later production results.

## Files and remaining review

Added:

- `backend/sandbox/release_manifest.json`
- `backend/tests/test_release_manifest.py`
- `docs/REPOSITORY_PROVENANCE.md` (exact four-path future allowlist and tag procedure)
- `docs/MILESTONE_1B_C_RESULTS.md`

Modified:

- `backend/tests/conftest.py` (optional read-only history fixture)
- `backend/tests/test_checkout_releases.py` (use that fixture for existing history checks)
- `AGENTS.md`
- `docs/IMPLEMENTATION_BLUEPRINT.md`
- `README.md`
- `docs/MILESTONE_1B_A_RESULTS.md` (dated appended update)
- `docs/MILESTONE_1B_B_RESULTS.md` (dated appended update)

These eleven files are ready for human review and a provenance-artifact commit.
No checkout logic, oracle, runtime Python/configuration, Vercel or frontend change
is included. Suggested neutral message: `feat: record checkout release provenance`.

Outstanding: human tag creation/publication and remote peeled-target verification.
The four-path retrieval restrictions are a specification, not implemented tool
enforcement; GitHub tools remain for a later assignment. No other local test or
dependency issue remains. Stop before committing, pushing, creating tags or
starting the next milestone.
