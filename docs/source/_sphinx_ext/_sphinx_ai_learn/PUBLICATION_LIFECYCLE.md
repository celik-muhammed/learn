# AI Learn publication lifecycle

## Authority model

AI Learn intentionally separates private generation, durable source data, and
rendered documentation:

```text
browser/local AI draft
        ↓
review + revision-bound publication transaction
        ↓
canonical JSON proposal
        ↓
GitHub pull request
        ↓
human/CI review + merge
        ↓
ReadTheDocs build
        ↓
_sphinx_ai_learn JSON → RST materialization
        ↓
Sphinx RST → HTML
        ↓
live documentation
```

The repository authority is JSON. RST and HTML are derived. There is no
`catalog.json` publication step, no publication-time RST exporter, and no model
or repository write inside the Sphinx build.

## Filesystem model

A Topic has one immutable route and granular same-stem JSON/RST artifacts:

```text
learn-ai/topics/<timestamp>-<digest>/
├── index.json / index.rst
├── topic.json / topic.rst
├── summary.json / summary.rst
├── video.json / video.rst
├── audio.json / audio.rst
├── document.json / document.rst
├── whiteboard.json / whiteboard.rst
├── topic-prompts/
│   ├── index.json / index.rst
│   ├── eli14.json / eli14.rst
│   └── knowledge-gaps.json / knowledge-gaps.rst
├── skills/
│   ├── index.json / index.rst
│   └── skill-check-reference.json / skill-check-reference.rst
├── open-problems.json / open-problems.rst
├── continue-learning.json / continue-learning.rst
├── tweets.json / tweets.rst
└── hackernews.json / hackernews.rst
```

Empty result JSON is intentional. It gives every generation target a stable
repository address before anyone generates content.

Reusable definitions live outside a specific Topic:

```text
learn-ai/topic-prompts/<prompt-id>/index.json / index.rst
learn-ai/skills/<skill-id>/index.json / index.rst
```

A definition answers *what should the interaction do?* A Topic-owned result
answers *what did this interaction produce for this subject?* Those are never
the same artifact.

## Include and toctree modes

Every `learn.record.v2` can choose `add_toctree`.

Default `false` means content composition:

```text
index.rst
  ├─ include summary.rst
  ├─ include topic-prompts/eli14.rst
  └─ include skills/skill-check-reference.rst
```

Children begin with `:orphan:` and `:no-search:` and expose a compiler sentinel.
The parent owns headings/public anchors and includes only content after that
sentinel. Child files contain no toctree.

Explicit `true` means navigation composition: the parent emits `.. toctree::`,
children omit `:orphan:`, and each child owns its standalone title/anchor.

This option changes only document composition. Canonical JSON contracts and
result locations do not change.

## Reusable interaction registries

Topic Prompts and Skills share these invariants:

- stable machine ID; display title lives in JSON;
- explicit deterministic order;
- bounded plain-text instruction/description;
- no duplicate ID or order within a registry;
- Prompt and Skill IDs are mutually disjoint;
- neither registry may reuse fixed Topic structural IDs;
- Python does not duplicate semantic definition content.

Skills may carry `domains` and graph `related` references. They are exposed as
virtual `kind="skill"` subjects in the normalized in-memory catalog so normal
related-record/navigation code can address them. That projection is not a
second repository source model.

## Publication transaction

`_publication.py` validates a transaction against the exact current semantic
tree revision. Supported logical operations include:

- `create-record` for ordinary durable records;
- `upsert-section` for a record-owned result section;
- `attach-source` for reviewed source evidence;
- `create-topic-prompt` for a reusable Prompt definition;
- `create-skill` for a reusable Skill definition.

The planner applies the transaction to normalized state and uses the same
canonical JSON projectors as `_materialize.py` to calculate the future tree.
It returns exact changed/added JSON bytes, deleted JSON paths, routes, affected
IDs, base revision, and future revision. It never emits RST.

A stale base revision is a hard failure. The caller must review/replan against
the new tree rather than silently rebasing generated content.

### Definition fan-out

Adding a Prompt or Skill is atomic across all Topics. One operation proposes:

1. the top-level reusable definition;
2. every existing Topic's updated `index.json` references; and
3. every existing Topic's empty result JSON for that interaction.

Future Topics are automatically projected with all current Prompt/Skill
definitions. Cross-registry and structural-ID collisions are rejected before a
review bundle can be produced.

## Review bundle and provider boundary

`_publication_cli.py` writes only canonical `.json` proposal files plus a
`publication-plan.json` manifest containing SHA-256 hashes, byte lengths,
routes, affected IDs, deletions, and before/after revisions.

The GitHub/Hugging Face service can reuse authenticated contribution
infrastructure, but browser clients must never choose arbitrary repository paths
or obtain repository credentials. The service receives a validated reviewed
transaction/bundle and maps it onto the fixed canonical subtree.

### Reviewed GitHub transport

The implemented publication adapter keeps repository authority out of the browser.
The browser sends a reviewed ``learn.publication-request.v1`` envelope to the
active ``publication`` endpoint only after an explicit **Open pull request**
action. ``Generate`` itself never performs a repository write.

The proxy has three fail-closed modes: ``disabled`` (default), ``stub`` (full
validation with zero GitHub writes), and ``github``. Repository identity, default
branch, canonical subtree, workflow file, and GitHub credential are server-owned
policy and cannot be overridden by a browser request. ``POST /v1/learn-publication``
with ``action=test`` verifies this policy without dispatching a publication.

In ``github`` mode the proxy may dispatch only the configured repository workflow.
It does **not** calculate canonical repository paths and does not hold direct
content/pull-request mutation logic. The checked-out repository workflow is the
second trust boundary and must:

1. reconstruct and hash-bind the exact reviewed request;
2. reject a stale semantic revision;
3. rerun ``_publication.py`` against the current canonical JSON tree;
4. apply only planner-owned ``docs/source/learn-ai/**/*.json`` paths;
5. reject every non-JSON repository mutation;
6. validate the proposed future tree with JSON→RST materialization twice in an
   isolated clean room;
7. use a deterministic request-bound branch and replay an existing open review
   instead of creating duplicate PRs; and
8. open a human-review pull request without bypassing branch protection.

The proxy GitHub token therefore needs only the permission required to dispatch
the fixed workflow. Repository ``contents`` and ``pull-requests`` write authority
belongs to the repository workflow's short-lived ``GITHUB_TOKEN``. Secrets are
never serialized into Sphinx HTML, endpoint profiles, browser storage, publication
receipts, or review bundles.

## Sphinx build boundary

At `config-inited`, `_sphinx_ai_learn` may:

- read and validate canonical JSON;
- validate record/section/interaction graph integrity;
- deterministically derive sibling RST;
- prune only extension-owned stale RST;
- preserve unchanged output mtimes; and
- expose the normalized graph to directives.

It must not:

- call text/image/audio/video models;
- fetch sources/evidence from the public network;
- create branches/PRs;
- write datasets or contribution services;
- mutate canonical JSON; or
- silently repair invalid canonical content.

Invalid canonical state fails visibly.

## Strict preview

The browser can keep a fast immediate projection for editing, but the final
"what will this page look like?" preview should exercise the real compiler:

```text
draft/proposed JSON
        ↓
temporary canonical tree
        ↓
_sphinx_ai_learn materializer
        ↓
temporary RST
        ↓
isolated Sphinx build
        ↓
HTML preview in sandboxed iframe
```

That worker should have no repository credentials and no network, and should be
bounded by input size, CPU, memory, and wall-clock limits. Cache previews by
semantic artifact/tree hash. This gives strict output parity without waiting for
GitHub review + ReadTheDocs deployment.

## Security and determinism

The compiler rejects unsafe/ambiguous inputs including duplicate JSON keys,
non-finite numbers, path traversal, symlinks, unknown contracts, invalid
ownership, orphan sections, registry collisions, bad graph references, and
handwritten RST output collisions.

Generated body text is data inside trusted directives, not arbitrary RST. This
prevents a model-generated string from introducing `raw`, `include`, `toctree`,
or other structural directives.

Graph validation is strict and diagnostic. Missing `related` subjects, missing
citation targets, and citations that resolve to a non-Source subject are aggregated
with their canonical JSON owner paths before materialization stops. Publication
validation uses the same graph rules, so an invalid future tree must be rejected
before a review bundle is returned.

Writes are atomic per file. A failed materialization never changes canonical
JSON; rerunning against the same JSON converges to the same RST. Semantic tree
hashes ignore JSON whitespace while repository serialization remains stable and
human-reviewable.

## CI contract

CI should independently require:

1. canonical JSON validation;
2. materialization with no unexpected checked-in RST diff;
3. a second materialization with zero changes;
4. Python and JavaScript static checks;
5. unit/security/publication tests;
6. a real warning-strict Sphinx build in the docs environment; and
7. preview/publication tests confirming planned revisions and JSON-only diffs.

This keeps checked-in generated RST useful for review while ensuring JSON remains
the sole durable content authority.
