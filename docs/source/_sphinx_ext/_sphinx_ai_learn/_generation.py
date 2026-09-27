# scikitplot/_externals/_sphinx_ext/_sphinx_ai_learn/_generation.py
#
# flake8: noqa: D213
#
# Authors: The scikit-plots developers
# SPDX-License-Identifier: BSD-3-Clause

"""Shared, Sphinx-free accepted-generation identity and feedback helpers."""

from __future__ import annotations

import copy
import hashlib

from ._schema import canonical_bytes


def generation_identifier(*, section_id, created_at, body, provenance=None):
    """Return immutable accepted-generation identity.

    Public participant credit is deliberately *not* part of identity. The same
    accepted content/provenance may accumulate additional contributors over time
    without creating duplicate generation records.
    """
    digest = hashlib.sha256(
        canonical_bytes(
            {
                "section_id": section_id,
                "created_at": created_at,
                "body": body,
                "provenance": provenance or {},
            }
        )
    ).hexdigest()[:20]
    return "generation-" + digest


def legacy_generation(subject, section):
    """Project one accepted v1 section into deterministic in-memory history."""
    body = str(section.get("body", ""))
    if not body.strip():
        return None
    created_at = subject.get("created_at") or "1970-01-01T00:00:00Z"
    provenance = {"authorship": "legacy-import"}
    generation = {
        "id": generation_identifier(
            section_id=section["id"],
            created_at=created_at,
            body=body,
            provenance=provenance,
        ),
        "created_at": created_at,
        "body": body,
        "citations": copy.deepcopy(section.get("citations", [])),
        "links": copy.deepcopy(section.get("links", [])),
        "contributors": list(section.get("contributors") or ["Anonymous"]),
        "provenance": provenance,
        "feedback": [],
    }
    if section.get("review"):
        generation["review"] = copy.deepcopy(section["review"])
    return generation


def section_generation_id(subject, section):
    """Return one canonical feedback target, or ``""`` for no accepted text."""
    active = section.get("active_generation_id")
    if isinstance(active, str) and active:
        return active
    generation = legacy_generation(subject, section)
    return generation["id"] if generation else ""


def section_generation_feedback(section, sidecar_feedback=()):
    """Return ``(score, count)`` for the active/legacy generation.

    ``sidecar_feedback`` contains immutable reviewed events stored outside the
    section JSON. Embedded feedback remains readable for V62 compatibility.
    """
    embedded = []
    active_id = section.get("active_generation_id")
    generations = section.get("generations") or []
    if active_id and generations:
        active = next((row for row in generations if row.get("id") == active_id), None)
        if active is not None:
            embedded = list(active.get("feedback") or [])
    feedback = [*embedded, *list(sidecar_feedback or ())]
    return sum(int(row.get("rating", 0)) for row in feedback), len(feedback)


def changed_feedback_records(previous, current):
    """Return record ids whose reviewed-feedback digest changed."""
    previous = previous or {}
    current = current or {}
    return {
        record_id
        for record_id in set(previous) | set(current)
        if previous.get(record_id) != current.get(record_id)
    }


def feedback_outdated_documents(
    *, root, routes, found_docs, consumers, previous, current
):
    """Return only documents that consume records with changed feedback.

    This helper is intentionally Sphinx-free so the invalidation policy is
    testable without importing the builder/runtime package.
    """
    changed = changed_feedback_records(previous, current)
    if not changed:
        return []
    root = str(root or "").strip("/")
    selected = set()
    consumers = consumers or {}
    routes = routes or {}
    found_docs = set(found_docs or ())
    for record_id in changed:
        selected.update(consumers.get(record_id, ()))
        route = routes.get(record_id, "")
        if not route:
            continue
        doc_route = f"{root}/{route}" if root else route
        route_prefix = doc_route.rsplit("/index", 1)[0]
        selected.update(
            docname
            for docname in found_docs
            if docname == doc_route or docname.startswith(route_prefix + "/")
        )
    return sorted(selected)
