from __future__ import annotations

import json

import pytest

from _sphinx_ext._sphinx_ai_assistant._hf_spaces_proxy._utils._learn_publication import (
    LearnPublicationTransportError,
    build_publication_policy,
    capability_document,
    parse_publication_request,
    publication_request_id,
    workflow_dispatch_body,
)


def policy(mode="stub"):
    return build_publication_policy(
        mode=mode,
        repository="scikit-plots/learn",
        default_branch="main",
        canonical_prefix="docs/source/learn-ai",
        workflow="ai-learn-publish.yml",
        max_request_bytes=49_152,
    )


def overview_request():
    draft = {
        "contract": "learn.page-overview-draft.v1",
        "body": "Reviewed overview.",
        "model": "stub/test",
        "generated_at": "2026-09-25T00:00:00.000Z",
        "base_revision": "tree-abc",
        "profile": {},
        "contexts": [],
        "source_ids": [],
        "guidance": "",
    }
    return {
        "contract": "learn.publication-request.v1",
        "action": "publish",
        "draft": draft,
        "base_revision": "tree-abc",
        "subject_id": "topic-example",
    }


def test_publication_policy_is_fixed_server_side_and_capability_has_no_secret():
    p = policy("github")
    cap = capability_document(p, credential_ready=True)
    assert cap["repository"] == "scikit-plots/learn"
    assert cap["canonical_prefix"] == "docs/source/learn-ai"
    assert cap["browser_repository_override"] is False
    assert cap["browser_credentials"] is False
    assert "token" not in json.dumps(cap).lower()


def test_publication_request_rejects_repo_branch_path_secret_and_bad_json():
    p = policy()
    request = overview_request()
    for key, value in {
        "repository": "attacker/repo",
        "branch": "other",
        "path": "../../x",
        "token": "secret",
        "workflow": "evil.yml",
    }.items():
        candidate = dict(request, **{key: value})
        with pytest.raises(LearnPublicationTransportError, match="unexpected fields"):
            parse_publication_request(json.dumps(candidate).encode(), p)
    with pytest.raises(LearnPublicationTransportError, match="duplicate JSON key"):
        parse_publication_request(b'{"contract":"learn.publication-request.v1","contract":"x","action":"test"}', p)
    with pytest.raises(LearnPublicationTransportError, match="non-finite"):
        parse_publication_request(b'{"contract":"learn.publication-request.v1","action":"publish","draft":{"contract":"learn.page-overview-draft.v1","body":NaN},"base_revision":"tree-abc","subject_id":"topic-example"}', p)


def test_workflow_dispatch_is_deterministic_bounded_and_contains_no_destination_override():
    p = policy("github")
    parsed = parse_publication_request(json.dumps(overview_request()).encode(), p)
    first_id, first = workflow_dispatch_body(p, parsed)
    second_id, second = workflow_dispatch_body(p, parsed)
    assert first_id == second_id == publication_request_id(parsed)
    assert first == second
    assert first["ref"] == "main"
    assert first["inputs"]["operation"] == "publish"
    assert first["inputs"]["request_id"] == first_id
    assert len(first["inputs"]["request_json"]) < 60_000
    transported = json.loads(first["inputs"]["request_json"])
    assert "repository" not in transported
    assert "workflow" not in transported
    assert "token" not in transported


def test_test_action_is_non_mutating_minimal_envelope():
    p = policy("github")
    assert parse_publication_request(
        b'{"contract":"learn.publication-request.v1","action":"test"}', p
    ) == {"contract": "learn.publication-request.v1", "action": "test"}
    with pytest.raises(LearnPublicationTransportError, match="unexpected fields"):
        parse_publication_request(
            b'{"contract":"learn.publication-request.v1","action":"test","repository":"x/y"}', p
        )


def test_record_transport_requires_stable_created_at_field():
    p = policy()
    request = overview_request()
    request["draft"] = {
        "contract": "learn.record-creation-draft.v1",
        "kind": "topic",
        "title": "T",
        "summary": "S",
        "domains": [],
        "sections": [],
        "evidence_gaps": [],
        "related_questions": [],
        "provenance": {"base_revision": "tree-abc"},
    }
    request.pop("subject_id")
    with pytest.raises(LearnPublicationTransportError, match="created_at"):
        parse_publication_request(json.dumps(request).encode(), p)
