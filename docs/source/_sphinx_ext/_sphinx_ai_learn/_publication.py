# scikitplot/_externals/_sphinx_ext/_sphinx_ai_learn/_publication.py
#
# flake8: noqa: D213
#
# Authors: The scikit-plots developers
# SPDX-License-Identifier: BSD-3-Clause

"""Deterministic, review-first publication planning for canonical AI Learn JSON.

Publication is deliberately Sphinx-free and RST-free. Browser drafts become a
revision-bound proposal over the canonical JSON tree; repository/provider
adapters may then submit that JSON diff for human review. The build-time
materializer is the only component allowed to derive RST from accepted JSON.
"""

from __future__ import annotations

import copy
import hashlib
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ._materialize import (
    canonical_prompt_json_files,
    canonical_record_json_files,
    canonical_skill_json_files,
    load_content_tree,
    skill_subject,
    validate_interaction_registry,
)
from ._registry import canonical_detail_section_id
from ._schema import (
    CATALOG_CONTRACT,
    LearnValidationError,
    canonical_bytes,
    timestamp,
    validate_catalog,
)

PUBLICATION_CONTRACT = "learn.publication.v2"
RECORD_DRAFT_CONTRACT = "learn.record-creation-draft.v1"
PAGE_OVERVIEW_DRAFT_CONTRACT = "learn.page-overview-draft.v1"
TOPIC_PROMPT_DRAFT_CONTRACT = "learn.topic-prompt-draft.v1"
SKILL_DRAFT_CONTRACT = "learn.skill-draft.v1"
MAX_OPERATIONS = 32
_ID_SAFE = re.compile(r"[^a-z0-9-]+")


def _require_object(value, *, path):
    if not isinstance(value, dict):
        raise LearnValidationError(f"{path}: expected object")
    return value


def _bounded_text(value, *, path, limit, empty=False):
    if not isinstance(value, str) or len(value) > limit:
        raise LearnValidationError(f"{path}: invalid text")
    value = value.strip()
    if not empty and not value:
        raise LearnValidationError(f"{path}: text is required")
    return value


def _bounded_string_list(value, *, path, maximum=20, limit=1000):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise LearnValidationError(f"{path}: invalid list")
    result = []
    for index, item in enumerate(value):
        result.append(_bounded_text(item, path=f"{path}[{index}]", limit=limit))
    return result


def _slug(value):
    result = _ID_SAFE.sub("-", value.casefold()).strip("-")
    result = re.sub(r"-+", "-", result)
    return result[:48].strip("-") or "record"


def suggested_artifact_id(draft, *, existing_ids=()):
    """Return a stable, human-readable candidate ID for one unpublished draft.

    Identity deliberately does *not* hash the whole draft: provenance timestamps,
    regenerated prose, and other mutable metadata must not silently change the
    proposed record identity.  The title-derived base is used when available;
    deterministic numeric suffixes are reserved only for catalog collisions.
    Once a publication transaction is prepared, its explicit ``record_id`` is
    the identity and must be retained even if the title is edited later.
    """
    draft = _require_object(draft, path="draft")
    kind = _bounded_text(draft.get("kind"), path="draft.kind", limit=32)
    title = _bounded_text(draft.get("title"), path="draft.title", limit=200)
    if kind not in {"topic", "source", "problem", "skill", "topic-prompt"}:
        raise LearnValidationError("draft.kind: unsupported publication kind")
    if isinstance(existing_ids, (str, bytes)):
        raise LearnValidationError(
            "existing_ids: expected an iterable of identifiers",
        )
    try:
        occupied = {str(value) for value in existing_ids}
    except TypeError as exc:
        raise LearnValidationError(
            "existing_ids: expected an iterable of identifiers",
        ) from exc
    prefix = {
        "problem": "problem",
        "source": "source",
        "skill": "skill",
        "topic": "topic",
    }.get(kind, "")
    slug = _slug(title)
    base = (f"{prefix}-{slug}" if prefix else slug)[:64].rstrip("-_")
    if base not in occupied:
        return base
    suffix_number = 2
    while suffix_number <= 9999:  # ruff: ignore[magic-value-comparison]
        suffix = f"-{suffix_number}"
        candidate = base[: 64 - len(suffix)].rstrip("-_") + suffix
        if candidate not in occupied:
            return candidate
        suffix_number += 1
    raise LearnValidationError("existing_ids: too many identifier collisions")


def _draft_section_id(value, *, fallback, path):
    """Normalize historical v1 browser IDs to the stricter catalog ID grammar."""
    raw = _bounded_text(value, path=path, limit=64, empty=True).casefold()
    raw = re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-_")
    if not raw:
        raw = fallback
    if not raw[0].isalpha():
        raw = "section-" + raw
    return raw[:64].rstrip("-_")


def _section(row, *, path, fallback):
    row = _require_object(row, path=path)
    allowed = {"id", "title", "body"}
    if set(row) - allowed or not {"id", "title", "body"}.issubset(row):
        raise LearnValidationError(f"{path}: unexpected or missing fields")
    return {
        "id": _draft_section_id(row["id"], fallback=fallback, path=f"{path}.id"),
        "title": _bounded_text(row["title"], path=f"{path}.title", limit=200),
        "body": _bounded_text(
            row["body"], path=f"{path}.body", limit=50000, empty=True
        ),
        "citations": [],
        "links": [],
    }


def _append_list_section(sections, section_id, title, values):
    if not values or any(row["id"] == section_id for row in sections):
        return
    sections.append(
        {
            "id": section_id,
            "title": title,
            "body": "\n".join(f"- {value}" for value in values),
            "citations": [],
            "links": [],
        }
    )


def record_from_draft(  # ruff: ignore[too-many-branches]
    draft,
    *,
    record_id,
    created_at,
    metadata_reviewed=False,
):
    """Convert a browser creation draft into one validated catalog subject.

    Model-authored body text remains plain text.  It is never treated as RST or
    HTML.  Source drafts retain a human metadata-review gate.
    """
    draft = _require_object(draft, path="draft")
    if draft.get("contract") != RECORD_DRAFT_CONTRACT:
        raise LearnValidationError("draft.contract: unsupported record draft")
    kind = _bounded_text(draft.get("kind"), path="draft.kind", limit=32)
    if kind not in {"topic", "source", "problem"}:
        raise LearnValidationError("draft.kind: unsupported record publication kind")
    common_fields = {
        "contract",
        "kind",
        "title",
        "summary",
        "domains",
        "sections",
        "provenance",
    }
    kind_fields = {
        "topic": {
            "evidence_gaps",
            "related_questions",
        },
        "source": {
            "url",
            "metadata_questions",
            "requires_metadata_review",
            "suggested_attachment",
        },
        "problem": {
            "status",
            "evidence_needed",
        },
    }[kind]
    unexpected = set(draft) - common_fields - kind_fields
    if unexpected:
        raise LearnValidationError(
            "draft: unexpected fields: " + ", ".join(sorted(unexpected))
        )
    if kind == "problem" and draft.get("status", "open") != "open":
        raise LearnValidationError("draft.status: expected open")
    if "provenance" in draft and not isinstance(draft["provenance"], dict):
        raise LearnValidationError("draft.provenance: expected object")
    if "suggested_attachment" in draft and not isinstance(
        draft["suggested_attachment"], dict
    ):
        raise LearnValidationError("draft.suggested_attachment: expected object")
    title = _bounded_text(draft.get("title"), path="draft.title", limit=200)
    summary = _bounded_text(
        draft.get("summary", ""), path="draft.summary", limit=2000, empty=True
    )
    domains = _bounded_string_list(
        draft.get("domains", []), path="draft.domains", maximum=20, limit=64
    )
    raw_sections = draft.get("sections", [])
    if (
        not isinstance(raw_sections, list)  # lint
        or len(raw_sections) > 32  # ruff: ignore[magic-value-comparison]
    ):
        raise LearnValidationError("draft.sections: invalid list")
    sections = [
        _section(row, path=f"draft.sections[{index}]", fallback=f"section-{index + 1}")
        for index, row in enumerate(raw_sections)
    ]
    if len({row["id"] for row in sections}) != len(sections):
        raise LearnValidationError("draft.sections: duplicate section identifier")

    subject = {
        "id": _bounded_text(record_id, path="record_id", limit=64),
        "kind": kind,
        "title": title,
        "summary": summary,
        "domains": domains,
        "related": [],
        "sections": sections,
        "created_at": timestamp(created_at, "created_at"),
    }

    if kind == "topic":
        _append_list_section(
            subject["sections"],
            "knowledge-gaps",
            "Knowledge Gaps",
            _bounded_string_list(
                draft.get("evidence_gaps", []),
                path="draft.evidence_gaps",
                maximum=20,
                limit=800,
            ),
        )
        _append_list_section(
            subject["sections"],
            "continue-learning",
            "Continue Learning",
            _bounded_string_list(
                draft.get("related_questions", []),
                path="draft.related_questions",
                maximum=20,
                limit=800,
            ),
        )

    if kind == "source":
        subject["url"] = _bounded_text(
            draft.get("url"),
            path="draft.url",
            limit=2048,
        )
        questions = _bounded_string_list(
            draft.get("metadata_questions", []),
            path="draft.metadata_questions",
            maximum=20,
            limit=500,
        )
        if draft.get("requires_metadata_review") is not True:
            raise LearnValidationError(
                "draft.requires_metadata_review: expected explicit source review gate"
            )
        if not metadata_reviewed:
            raise LearnValidationError(
                "draft.metadata_review: source metadata must be reviewed before publication"
            )
        _append_list_section(
            subject["sections"], "metadata-review", "Metadata Review", questions
        )
    elif kind == "problem":
        subject["status"] = "open"
        _append_list_section(
            subject["sections"],
            "evidence-needed",
            "Evidence Needed",
            _bounded_string_list(
                draft.get("evidence_needed", []),
                path="draft.evidence_needed",
                maximum=20,
                limit=800,
            ),
        )

    probe = validate_catalog(
        {"contract": CATALOG_CONTRACT, "revision": "draft-probe", "subjects": [subject]}
    )
    return probe["subjects"][0]


def prompt_from_draft(
    draft,
    *,
    prompt_id,
    author,
    order,
    default_enabled=False,
):
    """Convert one reviewed browser prompt draft to a canonical prompt definition."""
    draft = _require_object(draft, path="draft")
    allowed = {"contract", "kind", "title", "description", "instruction", "provenance"}
    if set(draft) - allowed:
        raise LearnValidationError("draft: unexpected topic-prompt fields")
    if (
        draft.get("contract") != TOPIC_PROMPT_DRAFT_CONTRACT
        or draft.get("kind") != "topic-prompt"
    ):
        raise LearnValidationError("draft.contract: unsupported topic-prompt draft")
    if "provenance" in draft and not isinstance(draft["provenance"], dict):
        raise LearnValidationError("draft.provenance: expected object")
    prompt_id = _bounded_text(prompt_id, path="prompt_id", limit=64)
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", prompt_id):
        raise LearnValidationError("prompt_id: invalid identifier")
    if (
        isinstance(order, bool)  # lint
        or not isinstance(order, int)  # lint
        or not 0 <= order <= 10_000  # ruff: ignore[magic-value-comparison]
    ):
        raise LearnValidationError("order: expected integer from 0 to 10000")
    if not isinstance(default_enabled, bool):
        raise LearnValidationError("default_enabled: expected boolean")
    title = _bounded_text(draft.get("title"), path="draft.title", limit=200)
    return {
        "id": prompt_id,
        "title": title,
        "author": _bounded_text(author, path="author", limit=200),
        "description": _bounded_text(
            draft.get("description", ""), path="draft.description", limit=2000
        ),
        "instruction": _bounded_text(
            draft.get("instruction"), path="draft.instruction", limit=20_000
        ),
        "empty_message": f"No one has generated a {title} result for this topic yet.",
        "default_enabled": default_enabled,
        "order": order,
    }


def skill_from_draft(
    draft,
    *,
    skill_id,
    author,
    order,
    default_enabled=False,
):
    """Convert one reviewed browser skill draft to a canonical skill definition."""
    draft = _require_object(draft, path="draft")
    allowed = {"contract", "kind", "title", "description", "instruction", "provenance"}
    if set(draft) - allowed:
        raise LearnValidationError("draft: unexpected skill fields")
    if draft.get("contract") != SKILL_DRAFT_CONTRACT or draft.get("kind") != "skill":
        raise LearnValidationError("draft.contract: unsupported skill draft")
    if "provenance" in draft and not isinstance(draft["provenance"], dict):
        raise LearnValidationError("draft.provenance: expected object")
    skill_id = _bounded_text(skill_id, path="skill_id", limit=64)
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", skill_id):
        raise LearnValidationError("skill_id: invalid identifier")
    if (
        isinstance(order, bool)  # lint
        or not isinstance(order, int)  # lint
        or not 0 <= order <= 10_000  # ruff: ignore[magic-value-comparison]
    ):
        raise LearnValidationError("order: expected integer from 0 to 10000")
    if not isinstance(default_enabled, bool):
        raise LearnValidationError("default_enabled: expected boolean")
    title = _bounded_text(draft.get("title"), path="draft.title", limit=200)
    return {
        "id": skill_id,
        "title": title,
        "author": _bounded_text(author, path="author", limit=200),
        "description": _bounded_text(
            draft.get("description", ""), path="draft.description", limit=2000
        ),
        "instruction": _bounded_text(
            draft.get("instruction"), path="draft.instruction", limit=20_000
        ),
        "empty_message": f"No one has applied {title} to this topic yet.",
        "default_enabled": default_enabled,
        "order": order,
        "domains": [],
        "related": [],
    }


def _new_revision(base_revision, subjects):
    """Return a content-bound revision for the fully materialized proposal."""
    digest = hashlib.sha256(
        canonical_bytes({"base_revision": base_revision, "subjects": subjects})
    ).hexdigest()[:16]
    return "publication-" + digest


def validate_publication(value):  # noqa: PLR0912 -- explicit contract validation
    """Validate and normalize one ordered publication transaction."""
    value = _require_object(value, path="publication")
    allowed = {"contract", "base_revision", "operations"}
    if set(value) - allowed or set(value) != allowed:
        raise LearnValidationError("publication: unexpected or missing fields")
    if value.get("contract") != PUBLICATION_CONTRACT:
        raise LearnValidationError("publication.contract: unsupported version")
    base_revision = _bounded_text(
        value.get("base_revision"), path="publication.base_revision", limit=128
    )
    raw_ops = value.get("operations")
    if not isinstance(raw_ops, list) or not (1 <= len(raw_ops) <= MAX_OPERATIONS):
        raise LearnValidationError("publication.operations: invalid list")
    operations = []
    for index, raw in enumerate(raw_ops):
        path = f"publication.operations[{index}]"
        raw = _require_object(raw, path=path)  # ruff: ignore[redefined-loop-name]
        op = raw.get("op")
        if op == "create-record":
            allowed = {"op", "record_id", "created_at", "draft", "metadata_reviewed"}
            if set(raw) - allowed or not {
                "op",
                "record_id",
                "created_at",
                "draft",
            }.issubset(raw):
                raise LearnValidationError(f"{path}: unexpected or missing fields")
            item = {
                "op": op,
                "record_id": _bounded_text(
                    raw["record_id"], path=f"{path}.record_id", limit=64
                ),
                "created_at": timestamp(raw["created_at"], f"{path}.created_at"),
                "draft": copy.deepcopy(
                    _require_object(raw["draft"], path=f"{path}.draft"),
                ),
            }
            if "metadata_reviewed" in raw:
                if not isinstance(raw["metadata_reviewed"], bool):
                    raise LearnValidationError(
                        f"{path}.metadata_reviewed: expected boolean",
                    )
                item["metadata_reviewed"] = raw["metadata_reviewed"]
            operations.append(item)
        elif op == "create-topic-prompt":
            allowed = {
                "op",
                "prompt_id",
                "author",
                "order",
                "default_enabled",
                "draft",
            }
            if set(raw) != allowed:
                raise LearnValidationError(f"{path}: unexpected or missing fields")
            if isinstance(raw["order"], bool) or not isinstance(raw["order"], int):
                raise LearnValidationError(f"{path}.order: expected integer")
            if not isinstance(raw["default_enabled"], bool):
                raise LearnValidationError(f"{path}.default_enabled: expected boolean")
            operations.append(
                {
                    "op": op,
                    "prompt_id": _bounded_text(
                        raw["prompt_id"], path=f"{path}.prompt_id", limit=64
                    ),
                    "author": _bounded_text(
                        raw["author"], path=f"{path}.author", limit=200
                    ),
                    "order": raw["order"],
                    "default_enabled": raw["default_enabled"],
                    "draft": copy.deepcopy(
                        _require_object(raw["draft"], path=f"{path}.draft")
                    ),
                }
            )
        elif op == "create-skill":
            allowed = {
                "op",
                "skill_id",
                "author",
                "order",
                "default_enabled",
                "draft",
            }
            if set(raw) != allowed:
                raise LearnValidationError(f"{path}: unexpected or missing fields")
            if isinstance(raw["order"], bool) or not isinstance(raw["order"], int):
                raise LearnValidationError(f"{path}.order: expected integer")
            if not isinstance(raw["default_enabled"], bool):
                raise LearnValidationError(f"{path}.default_enabled: expected boolean")
            operations.append(
                {
                    "op": op,
                    "skill_id": _bounded_text(
                        raw["skill_id"], path=f"{path}.skill_id", limit=64
                    ),
                    "author": _bounded_text(
                        raw["author"], path=f"{path}.author", limit=200
                    ),
                    "order": raw["order"],
                    "default_enabled": raw["default_enabled"],
                    "draft": copy.deepcopy(
                        _require_object(raw["draft"], path=f"{path}.draft")
                    ),
                }
            )
        elif op == "upsert-section":
            allowed = {"op", "subject_id", "section_id", "title", "body"}
            if set(raw) != allowed:
                raise LearnValidationError(f"{path}: unexpected or missing fields")
            operations.append(
                {
                    "op": op,
                    "subject_id": _bounded_text(
                        raw["subject_id"], path=f"{path}.subject_id", limit=64
                    ),
                    "section_id": _bounded_text(
                        raw["section_id"], path=f"{path}.section_id", limit=64
                    ),
                    "title": _bounded_text(
                        raw["title"], path=f"{path}.title", limit=200
                    ),
                    "body": _bounded_text(
                        raw["body"], path=f"{path}.body", limit=50000, empty=True
                    ),
                }
            )
        elif op == "attach-source":
            allowed = {
                "op",
                "subject_id",
                "section_id",
                "section_title",
                "source_id",
                "locator",
            }
            if set(raw) != allowed:
                raise LearnValidationError(f"{path}: unexpected or missing fields")
            operations.append(
                {
                    "op": op,
                    "subject_id": _bounded_text(
                        raw["subject_id"], path=f"{path}.subject_id", limit=64
                    ),
                    "section_id": _bounded_text(
                        raw["section_id"], path=f"{path}.section_id", limit=64
                    ),
                    "section_title": _bounded_text(
                        raw["section_title"], path=f"{path}.section_title", limit=200
                    ),
                    "source_id": _bounded_text(
                        raw["source_id"], path=f"{path}.source_id", limit=64
                    ),
                    "locator": _bounded_text(
                        raw["locator"], path=f"{path}.locator", limit=500
                    ),
                }
            )
        else:
            raise LearnValidationError(f"{path}.op: unsupported operation")
    return {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": base_revision,
        "operations": operations,
    }


def _subject_index(catalog, subject_id):
    for index, subject in enumerate(catalog["subjects"]):
        if subject["id"] == subject_id:
            return index
    raise LearnValidationError("publication: target subject does not exist")


def _canonical_section_id(subject, section_id):
    if subject["kind"] == "topic":
        return section_id
    return canonical_detail_section_id(subject["kind"], section_id)


def apply_publication(  # ruff: ignore[too-many-branches]
    catalog,
    publication,
):
    """Apply a validated publication transaction in memory and revalidate graph."""
    current = validate_catalog(catalog)
    publication = validate_publication(publication)
    if current["revision"] != publication["base_revision"]:
        raise LearnValidationError("publication.base_revision: catalog changed")
    proposed = copy.deepcopy(current)

    for operation in publication["operations"]:
        if operation["op"] in {"create-topic-prompt", "create-skill"}:
            continue
        if operation["op"] == "create-record":
            subject = record_from_draft(
                operation["draft"],
                record_id=operation["record_id"],
                created_at=operation["created_at"],
                metadata_reviewed=operation.get("metadata_reviewed", False),
            )
            existing = next(
                (row for row in proposed["subjects"] if row["id"] == subject["id"]),
                None,
            )
            if existing is not None:
                if existing != subject:
                    raise LearnValidationError(
                        "publication.create-record: identifier collision",
                    )
                continue
            proposed["subjects"].append(subject)
            continue

        target_index = _subject_index(proposed, operation["subject_id"])
        target = proposed["subjects"][target_index]
        if target["kind"] == "skill":
            raise LearnValidationError(
                "publication: reusable Skill definitions must be changed through skill operations",
            )
        wanted = _canonical_section_id(target, operation["section_id"])
        section = next(
            (
                row
                for row in target["sections"]
                if _canonical_section_id(target, row["id"]) == wanted
            ),
            None,
        )

        if operation["op"] == "upsert-section":
            if section is None:
                target["sections"].append(
                    {
                        "id": wanted,
                        "title": operation["title"],
                        "body": operation["body"],
                        "citations": [],
                        "links": [],
                    }
                )
            else:
                section["title"] = operation["title"]
                section["body"] = operation["body"]
                section.pop("review", None)
            continue

        if operation["op"] == "attach-source":
            source = next(
                (
                    row
                    for row in proposed["subjects"]
                    if row["id"] == operation["source_id"]
                ),
                None,
            )
            if source is None or source["kind"] != "source":
                raise LearnValidationError(
                    "publication.attach-source: source_id must identify a Source"
                )
            if section is None:
                section = {
                    "id": wanted,
                    "title": operation["section_title"],
                    "body": "",
                    "citations": [],
                    "links": [],
                }
                target["sections"].append(section)
            citation = {
                "source_id": source["id"],
                "locator": operation["locator"],
            }
            if citation not in section["citations"]:
                section["citations"].append(citation)
            section.pop("review", None)

    if proposed["subjects"] == current["subjects"]:
        return current
    proposed["revision"] = _new_revision(
        publication["base_revision"], proposed["subjects"]
    )
    return validate_catalog(proposed)


def _proposed_prompts(current_prompts, publication):
    prompts = [dict(prompt) for prompt in current_prompts]
    by_id = {prompt["id"]: prompt for prompt in prompts}
    used_orders = {prompt["order"] for prompt in prompts}
    for operation in publication["operations"]:
        if operation["op"] != "create-topic-prompt":
            continue
        prompt = prompt_from_draft(
            operation["draft"],
            prompt_id=operation["prompt_id"],
            author=operation["author"],
            order=operation["order"],
            default_enabled=operation["default_enabled"],
        )
        existing = by_id.get(prompt["id"])
        if existing is not None:
            if existing != prompt:
                raise LearnValidationError(
                    "publication.create-topic-prompt: identifier collision",
                )
            continue
        if prompt["order"] in used_orders:
            raise LearnValidationError(
                "publication.create-topic-prompt: order collision",
            )
        prompts.append(prompt)
        by_id[prompt["id"]] = prompt
        used_orders.add(prompt["order"])
    return tuple(sorted(prompts, key=lambda row: (row["order"], row["id"])))


def _proposed_skills(
    current_skills,
    publication,
):
    skills = [dict(skill) for skill in current_skills]
    by_id = {skill["id"]: skill for skill in skills}
    used_orders = {skill["order"] for skill in skills}
    for operation in publication["operations"]:
        if operation["op"] != "create-skill":
            continue
        skill = skill_from_draft(
            operation["draft"],
            skill_id=operation["skill_id"],
            author=operation["author"],
            order=operation["order"],
            default_enabled=operation["default_enabled"],
        )
        existing = by_id.get(skill["id"])
        if existing is not None:
            if existing != skill:
                raise LearnValidationError(
                    "publication.create-skill: identifier collision"
                )
            continue
        if skill["order"] in used_orders:
            raise LearnValidationError("publication.create-skill: order collision")
        skills.append(skill)
        by_id[skill["id"]] = skill
        used_orders.add(skill["order"])
    return tuple(sorted(skills, key=lambda row: (row["order"], row["id"])))


def _catalog_with_skills(catalog, skills):
    subjects = [row for row in catalog["subjects"] if row["kind"] != "skill"]
    subjects.extend(skill_subject(skill) for skill in skills)
    return validate_catalog(
        {
            "contract": CATALOG_CONTRACT,
            "revision": catalog["revision"],
            "subjects": subjects,
        }
    )


def _current_json_files(tree):
    return {rel: (tree.root / rel).read_bytes() for rel in tree.source_digests}


def _project_json_tree(
    tree,
    catalog,
    prompts,
    skills,
):
    # Page descriptors are not mutated by publication transactions. Prompt and
    # record subtrees are projected from normalized state through the same layout
    # helpers used by the build materializer.
    files = {rel: (tree.root / rel).read_bytes() for rel in tree.pages}
    files.update(canonical_prompt_json_files(prompts))
    files.update(canonical_skill_json_files(skills))
    add_toctree = {
        row["subject"]["id"]: row["add_toctree"] for row in tree.records.values()
    }
    for subject in catalog["subjects"]:
        if subject["kind"] == "skill":
            continue
        files.update(
            canonical_record_json_files(
                subject,
                prompts,
                skills,
                add_toctree=add_toctree.get(subject["id"], False),
            )
        )
    return files


def _validate_projected_tree(files):
    """Load the exact proposed JSON tree before exposing a review plan.

    Publication is not a hot build path, so a bounded temporary filesystem pass
    is preferable to duplicating materializer validation logic. This guarantees
    that a review bundle cannot be valid to plan but invalid to build.
    """
    with tempfile.TemporaryDirectory(prefix="ai-learn-publication-") as directory:
        root = Path(directory) / "learn-ai"
        root.mkdir()
        for relative, raw in files.items():
            target = root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        return load_content_tree(root)


def publication_plan(content_root, publication):
    """Return an exact canonical-JSON repository diff for one transaction.

    The plan never contains RST. Accepted JSON is later compiled by
    ``_sphinx_ai_learn`` during Sphinx ``config-inited``.
    """
    tree = load_content_tree(content_root)
    publication = validate_publication(publication)
    if tree.catalog["revision"] != publication["base_revision"]:
        raise LearnValidationError("publication.base_revision: canonical tree changed")

    proposed_catalog = apply_publication(tree.catalog, publication)
    proposed_prompts = _proposed_prompts(tree.prompts, publication)
    proposed_skills = _proposed_skills(tree.skills, publication)
    validate_interaction_registry(proposed_prompts, proposed_skills)
    proposed_catalog = _catalog_with_skills(proposed_catalog, proposed_skills)
    current_files = _current_json_files(tree)
    proposed_files = _project_json_tree(
        tree, proposed_catalog, proposed_prompts, proposed_skills
    )
    projected_tree = _validate_projected_tree(proposed_files)

    files = {
        rel.as_posix(): raw
        for rel, raw in proposed_files.items()
        if current_files.get(rel) != raw
    }
    deleted = sorted(rel.as_posix() for rel in set(current_files) - set(proposed_files))
    routes = dict(projected_tree.routes)
    affected = set()
    for operation in publication["operations"]:
        identity = operation.get("record_id") or operation.get("subject_id")
        if identity:
            affected.add(identity)
        if operation["op"] == "create-topic-prompt":
            affected.add("topic-prompt:" + operation["prompt_id"])
            affected.update(
                subject["id"]
                for subject in proposed_catalog["subjects"]
                if subject["kind"] == "topic"
            )
        if operation["op"] == "create-skill":
            affected.add("skill:" + operation["skill_id"])
            affected.update(
                subject["id"]
                for subject in proposed_catalog["subjects"]
                if subject["kind"] == "topic"
            )

    return {
        "contract": "learn.publication-plan.v2",
        "base_revision": tree.catalog["revision"],
        "revision": projected_tree.catalog["revision"],
        "files": files,
        "deleted": deleted,
        "routes": routes,
        "previous_routes": tree.routes,
        "affected_ids": sorted(affected),
    }


def publication_now():
    """UTC timestamp helper for CLI/service adapters; never used implicitly."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
