# scikitplot/_externals/_sphinx_ext/_sphinx_ai_learn/_publication_request_cli.py
#
# flake8: noqa: D213
#
# Authors: The scikit-plots developers
# SPDX-License-Identifier: BSD-3-Clause

"""Validate one transported reviewed draft and build a JSON-only review bundle.

This CLI is the repository trust boundary used by the GitHub Actions publication
workflow.  It deliberately revalidates the browser/proxy envelope instead of
trusting transport-side validation.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys  # ruff: ignore[unused-import]
from pathlib import Path

from ._materialize import load_content_tree
from ._publication import (
    PAGE_OVERVIEW_DRAFT_CONTRACT,
    PUBLICATION_CONTRACT,
    RECORD_DRAFT_CONTRACT,
    SKILL_DRAFT_CONTRACT,
    TOPIC_PROMPT_DRAFT_CONTRACT,
    publication_plan,
    suggested_artifact_id,
)
from ._publication_cli import _write_bundle
from ._schema import LearnValidationError, timestamp

logger = logging.getLogger(__name__)

REQUEST_CONTRACT = "learn.publication-request.v1"
SECTION_DRAFT_CONTRACT = "learn.section-draft.v2"
_MAX_REQUEST_BYTES = 60_000


def _load_request(path):
    raw = Path(path).read_bytes()
    if not raw or len(raw) > _MAX_REQUEST_BYTES:
        raise LearnValidationError("publication request: encoded size exceeds limit")

    def duplicates(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise LearnValidationError(
                    f"publication request: duplicate JSON key {key!r}"
                )
            out[key] = value
        return out

    def nonfinite(value):
        raise LearnValidationError(
            f"publication request: non-finite number {value!r} is not allowed"
        )

    try:
        value = json.loads(
            raw,
            object_pairs_hook=duplicates,
            parse_constant=nonfinite,
        )
    except LearnValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LearnValidationError("publication request: invalid JSON") from exc
    if not isinstance(value, dict):
        raise LearnValidationError("publication request: expected object")
    return value


def _text(value, *, path, limit, empty=False):
    if not isinstance(value, str):
        raise LearnValidationError(f"{path}: expected string")
    value = value.strip()
    if not empty and not value:
        raise LearnValidationError(f"{path}: expected non-empty string")
    if len(value) > limit:
        raise LearnValidationError(f"{path}: exceeds limit")
    return value


def _request_operation(root, request):  # noqa: PLR0912
    allowed = {
        "contract",
        "action",
        "draft",
        "base_revision",
        "created_at",
        "metadata_reviewed",
        "artifact_id",
        "author",
        "order",
        "default_enabled",
        "subject_id",
        "section_id",
        "section_title",
    }
    if set(request) - allowed:
        raise LearnValidationError("publication request: unexpected fields")
    if (
        request.get("contract") != REQUEST_CONTRACT
        or request.get("action") != "publish"
    ):
        raise LearnValidationError("publication request: unsupported contract/action")
    if not {"draft", "base_revision"}.issubset(request):
        raise LearnValidationError("publication request: missing required fields")
    draft = request.get("draft")
    if not isinstance(draft, dict):
        raise LearnValidationError("publication request.draft: expected object")
    base_revision = _text(
        request.get("base_revision"),
        path="publication request.base_revision",
        limit=128,
    )
    tree = load_content_tree(root)
    if tree.catalog["revision"] != base_revision:
        raise LearnValidationError(
            "publication request.base_revision: catalog changed; regenerate/review the draft"
        )
    provenance = draft.get("provenance")
    embedded_revision = ""
    if isinstance(provenance, dict) and isinstance(
        provenance.get("base_revision"),
        str,
    ):
        embedded_revision = provenance["base_revision"].strip()
    elif isinstance(draft.get("base_revision"), str):
        embedded_revision = draft["base_revision"].strip()
    if embedded_revision and embedded_revision != base_revision:
        raise LearnValidationError("publication request: draft/base revision mismatch")

    contract = draft.get("contract")
    if contract in {
        RECORD_DRAFT_CONTRACT,
        TOPIC_PROMPT_DRAFT_CONTRACT,
        SKILL_DRAFT_CONTRACT,
    }:
        existing_ids = [subject["id"] for subject in tree.catalog["subjects"]]
        existing_ids.extend(prompt["id"] for prompt in tree.prompts)
        existing_ids.extend(skill["id"] for skill in tree.skills)
        artifact_id = request.get("artifact_id", "auto")
        if artifact_id == "auto":
            artifact_id = suggested_artifact_id(draft, existing_ids=existing_ids)
        else:
            artifact_id = _text(artifact_id, path="artifact_id", limit=64)

        if contract == TOPIC_PROMPT_DRAFT_CONTRACT:
            order = request.get("order")
            if order is None:
                order = (
                    max((prompt["order"] for prompt in tree.prompts), default=0) + 10
                )
            return tree, {
                "op": "create-topic-prompt",
                "prompt_id": artifact_id,
                "author": _text(
                    request.get("author", "community"),
                    path="author",
                    limit=200,
                ),
                "order": order,
                "default_enabled": bool(request.get("default_enabled", False)),
                "draft": draft,
            }
        if contract == SKILL_DRAFT_CONTRACT:
            order = request.get("order")
            if order is None:
                order = max((skill["order"] for skill in tree.skills), default=0) + 10
            return tree, {
                "op": "create-skill",
                "skill_id": artifact_id,
                "author": _text(
                    request.get("author", "community"),
                    path="author",
                    limit=200,
                ),
                "order": order,
                "default_enabled": bool(request.get("default_enabled", False)),
                "draft": draft,
            }
        created_at = timestamp(request.get("created_at"), "created_at")
        op = {
            "op": "create-record",
            "record_id": artifact_id,
            "created_at": created_at,
            "draft": draft,
        }
        if draft.get("kind") == "source":
            if request.get("metadata_reviewed") is not True:
                raise LearnValidationError(
                    "metadata_reviewed: explicit Source metadata review is required"
                )
            op["metadata_reviewed"] = True
        return tree, op

    if contract == PAGE_OVERVIEW_DRAFT_CONTRACT:
        subject_id = _text(
            request.get("subject_id"),
            path="subject_id",
            limit=128,
        )
        section_id = _text(
            request.get("section_id", "summary"),
            path="section_id",
            limit=128,
        )
        title = _text(
            request.get("section_title", "Summary"),
            path="section_title",
            limit=200,
        )
        body = _text(
            draft.get("body"),
            path="draft.body",
            limit=50_000,
            empty=True,
        )
        return tree, {
            "op": "upsert-section",
            "subject_id": subject_id,
            "section_id": section_id,
            "title": title,
            "body": body,
        }

    if contract == SECTION_DRAFT_CONTRACT:
        subject_id = _text(request.get("subject_id"), path="subject_id", limit=128)
        section_id = _text(request.get("section_id"), path="section_id", limit=128)
        title = _text(
            request.get("section_title", draft.get("title")),
            path="section_title",
            limit=200,
        )
        body = _text(draft.get("body"), path="draft.body", limit=50_000, empty=True)
        return tree, {
            "op": "upsert-section",
            "subject_id": subject_id,
            "section_id": section_id,
            "title": title,
            "body": body,
        }

    raise LearnValidationError("publication request.draft.contract: unsupported")


def plan_publication_request(content_root, request):
    tree, operation = _request_operation(content_root, request)
    publication = {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": tree.catalog["revision"],
        "operations": [operation],
    }
    return publication_plan(content_root, publication)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_root")
    parser.add_argument("request")
    parser.add_argument("destination")
    parser.add_argument("--repo-prefix", default="docs/source/learn-ai")
    args = parser.parse_args(argv)
    request = _load_request(args.request)
    plan = plan_publication_request(Path(args.content_root), request)
    manifest = _write_bundle(plan, args.destination, args.repo_prefix)
    logger.info(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
