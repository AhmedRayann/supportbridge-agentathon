# Repository provenance and future retrieval contract

Internal development specification. This document is excluded from future
runtime investigation tools. It specifies restrictions; it does not implement
or enforce a GitHub client. No such client is included in Milestone 1B-C.

## Source identity

Repository: `AhmedRayann/supportbridge-agentathon`.
Manifest: `backend/sandbox/release_manifest.json`, schema version 1.

| Release | Historical commit | Source path | Intended annotated tag |
| --- | --- | --- | --- |
| v1.0 | `a4eeea911604494f693e027cdaca5f2da2f78a7e` | `backend/sandbox/releases/v1_0.py` | `checkout-v1.0` |
| v1.1 | `c8473e4fcdb3f71630301c13c37fbf742c2a14ef` | `backend/sandbox/releases/v1_1.py` | `checkout-v1.1` |

`source_sha256` hashes the exact historical Git blob for the calculation module.
Tests compare packaged/working source with that blob, normalizing Windows CRLF
to LF. This is a source-file identity check, not a hash of the full deployment.
The manifest is neutral metadata, without outcomes, scenarios or diagnostic keys.
Its tag names are intended labels, not evidence of publication.

Canonical full-SHA source URLs are recorded in the manifest. The correct
[historical comparison](https://github.com/AhmedRayann/supportbridge-agentathon/compare/a4eeea911604494f693e027cdaca5f2da2f78a7e...c8473e4fcdb3f71630301c13c37fbf742c2a14ef)
is:

```text
https://github.com/AhmedRayann/supportbridge-agentathon/compare/a4eeea911604494f693e027cdaca5f2da2f78a7e...c8473e4fcdb3f71630301c13c37fbf742c2a14ef
```

The actual v1.1 commit adds a separate versioned implementation; it does not edit
v1.0. Investigators must retrieve both approved source snapshots, compare their
logic and cite actual line numbers at the corresponding commit. A broad compare
page also contains excluded development files. It is a human provenance link,
not permission to return its entire content to a model. Never manufacture a diff
or rewrite released source to make comparison look simpler.

## Exact future source retrieval allowlist

| Path | Approved historical snapshots | Purpose |
| --- | --- | --- |
| `backend/sandbox/releases/v1_0.py` | v1.0 commit | v1.0 calculation source |
| `backend/sandbox/releases/v1_1.py` | v1.1 commit | v1.1 calculation source |
| `backend/sandbox/models.py` | Either approved commit | Quote contract/validation |
| `backend/sandbox/router.py` | Either approved commit | Static release dispatch |

These four paths suffice for the existing calculation imports and dispatch.
`backend/sandbox/__init__.py` and `backend/sandbox/releases/__init__.py` contain
only docstrings, so their retrieval is unnecessary. `backend/main.py` is
application/health registration glue and is excluded. Do not expand access to
all files in a directory merely because it is the configured source prefix.

Future Python tools must enforce these rules before exposing data to an LLM:

- Allow only the configured public owner/repository, exact paths and approved
  immutable commit snapshots; resolve verified release refs to full SHAs.
- Normalize repository-relative POSIX paths and reject traversal, absolute paths,
  encoded separators/traversal, alternate hosts and arbitrary refs or URLs.
- Scope commit/history queries to the approved checkout paths. Filter each
  comparison/commit's file names, patches, file content and other payload fields
  before model exposure. A provider response can include excluded files even
  when the caller's intended scope is narrow. Keep only required source metadata.
- Return an honest unavailable/missing-source result when a historical path is
  absent. Do not replace it with mutable `main` content or another release.
- Apply read-only operations, input/schema validation, response/time limits and
  untrusted-data handling. No shell, arbitrary network destination or mutation.

Explicit exclusions include root `AGENTS.md`, `docs/IMPLEMENTATION_BLUEPRINT.md`,
this specification, every internal milestone report, `backend/oracle/**`,
`backend/tests/**`, `eval/**`, release evaluation fixtures, diagnostic answer keys,
and unrelated SupportBridge application/frontend/integration source. Do not
return test assertions, hidden expectations or known diagnoses through diffs,
file lists or history responses. The manifest may supply validated identity
metadata to the host; it does not expand the source retrieval allowlist.

Keep the existing portability configuration: `DEMO_GITHUB_OWNER`,
`DEMO_GITHUB_REPO`, `DEMO_SOURCE_PREFIX`, `SANDBOX_API_BASE_URL`,
`DEMO_RELEASE_V1_0_REF`, and `DEMO_RELEASE_V1_1_REF`. The initial source prefix is
`backend/sandbox/`; the four allowed paths above are the exact approved suffixes
under that prefix. Future adapters must validate configuration against approved
provenance and source scope, rather than scattering repository URLs through
agents. Moving the demo later requires an explicit reviewed metadata/configuration
change, not an architectural rewrite. No adapter is implemented here.

## Human-only annotated tag preparation and publication

At the 21 November 2026 check, neither release tag existed locally or remotely.
Recheck immediately before publication; state can change after this report.
Run commands from the repository root under the human developer's account.
These commands are instructions only and were not executed to mutate refs in 1B-C.

First inspect the exact refs and both objects:

```powershell
git cat-file -t a4eeea911604494f693e027cdaca5f2da2f78a7e
git cat-file -t c8473e4fcdb3f71630301c13c37fbf742c2a14ef
git merge-base --is-ancestor a4eeea911604494f693e027cdaca5f2da2f78a7e c8473e4fcdb3f71630301c13c37fbf742c2a14ef
if ($LASTEXITCODE -ne 0) { throw 'Release ancestry check failed' }
git for-each-ref --format='%(refname:short) %(objecttype) %(objectname) %(*objectname)' refs/tags/checkout-v1.0 refs/tags/checkout-v1.1
git ls-remote --tags origin 'refs/tags/checkout-v1.0' 'refs/tags/checkout-v1.0^{}' 'refs/tags/checkout-v1.1' 'refs/tags/checkout-v1.1^{}'
if ($LASTEXITCODE -ne 0) { throw 'Remote tag query failed; do not assume tags are absent' }
```

Both object types must be `commit`. If a tag is present, verify its peeled commit
against the table and its annotated object type. Never recreate, delete or
force-update it. A lightweight tag or wrong target needs human resolution; do not
silently repair it. If a correct remote annotated tag exists but is absent locally,
fetch only that existing ref without force, then verify it (example for v1.0):

```powershell
git fetch --no-tags origin 'refs/tags/checkout-v1.0:refs/tags/checkout-v1.0'
if ($LASTEXITCODE -ne 0) { throw 'Existing tag fetch failed' }
git cat-file -t refs/tags/checkout-v1.0
git rev-parse 'refs/tags/checkout-v1.0^{commit}'
```

Only for tags confirmed missing both locally and remotely, create each missing
annotated tag at its explicit historical commit. If either command fails, stop;
do not continue or add `--force`:

```powershell
git tag -a checkout-v1.0 a4eeea911604494f693e027cdaca5f2da2f78a7e -m 'Checkout v1.0'
if ($LASTEXITCODE -ne 0) { throw 'v1.0 tag creation failed' }
git tag -a checkout-v1.1 c8473e4fcdb3f71630301c13c37fbf742c2a14ef -m 'Checkout v1.1'
if ($LASTEXITCODE -ne 0) { throw 'v1.1 tag creation failed' }
```

Before pushing, require object type `tag` and compare the peeled commit targets:

```powershell
if ((git cat-file -t refs/tags/checkout-v1.0) -ne 'tag') { throw 'v1.0 must be annotated' }
if ((git rev-parse 'refs/tags/checkout-v1.0^{commit}') -ne 'a4eeea911604494f693e027cdaca5f2da2f78a7e') { throw 'v1.0 target mismatch' }
if ((git cat-file -t refs/tags/checkout-v1.1) -ne 'tag') { throw 'v1.1 must be annotated' }
if ((git rev-parse 'refs/tags/checkout-v1.1^{commit}') -ne 'c8473e4fcdb3f71630301c13c37fbf742c2a14ef') { throw 'v1.1 target mismatch' }
```

Publish only those two refs, with no force and no broad `--tags` push:

```powershell
git push --atomic origin 'refs/tags/checkout-v1.0:refs/tags/checkout-v1.0' 'refs/tags/checkout-v1.1:refs/tags/checkout-v1.1'
if ($LASTEXITCODE -ne 0) { throw 'Tag publication failed; inspect refs without force-updating' }
git ls-remote --tags origin 'refs/tags/checkout-v1.0' 'refs/tags/checkout-v1.0^{}' 'refs/tags/checkout-v1.1' 'refs/tags/checkout-v1.1^{}'
```

Annotated tags have separate tag-object IDs. In the final remote output,
`refs/tags/checkout-v1.0^{}` must be
`a4eeea911604494f693e027cdaca5f2da2f78a7e`, and
`refs/tags/checkout-v1.1^{}` must be
`c8473e4fcdb3f71630301c13c37fbf742c2a14ef`. Do not compare the bare tag-object
SHA to the release commit or use `ls-remote --refs`, which suppresses peeled refs.
See the official [git-tag](https://git-scm.com/docs/git-tag) and
[git-ls-remote](https://git-scm.com/docs/git-ls-remote) documentation.

Tag creation/push, remote peeled-target verification and any tag-URL checks remain
pending until performed by the human after review. The full-SHA source URLs work
independently of these tags. Do not advance to the next milestone here.
