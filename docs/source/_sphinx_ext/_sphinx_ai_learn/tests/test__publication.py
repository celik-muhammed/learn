"""Review-first publication mutates canonical JSON only."""

from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path

import pytest

from _sphinx_ext._sphinx_ai_learn._materialize import load_content_tree
from _sphinx_ext._sphinx_ai_learn._publication import (
    PUBLICATION_CONTRACT,
    apply_publication,
    prompt_from_draft,
    skill_from_draft,
    publication_plan,
    record_from_draft,
    suggested_artifact_id,
)
from _sphinx_ext._sphinx_ai_learn._publication_cli import main as publication_cli
from _sphinx_ext._sphinx_ai_learn._schema import LearnValidationError

SOURCE = Path(__file__).resolve().parents[3] / "learn-ai"


def _json_only_copy(tmp_path):
    root = tmp_path / "learn-ai"
    for source in SOURCE.rglob("*.json"):
        target = root / source.relative_to(SOURCE)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return root


def _apply_plan(root, plan):
    for relative in plan["deleted"]:
        (root / relative).unlink(missing_ok=True)
    for relative, raw in plan["files"].items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def topic_draft():
    return {
        "contract": "learn.record-creation-draft.v1",
        "kind": "topic",
        "title": "Introduction to Supervised Learning",
        "summary": "A bounded draft.",
        "domains": ["machine-learning"],
        "sections": [
            {"id": "summary", "title": "Summary", "body": "Draft summary."}
        ],
        "evidence_gaps": ["Need a benchmark."],
        "related_questions": ["How does regularization change the result?"],
    }


def prompt_draft():
    return {
        "contract": "learn.topic-prompt-draft.v1",
        "kind": "topic-prompt",
        "title": "Counterfactual Check",
        "description": "Test claims against plausible counterfactuals.",
        "instruction": (
            "Use only available evidence to identify counterfactual checks and "
            "state unsupported gaps explicitly."
        ),
    }


def skill_draft():
    return {
        "contract": "learn.skill-draft.v1",
        "kind": "skill",
        "title": "Source Triangulation",
        "description": "Compare claims across multiple available sources.",
        "instruction": (
            "Compare independently available sources, preserve disagreements, "
            "and state when the available evidence is insufficient."
        ),
    }


def test_record_draft_maps_auxiliary_topic_fields_without_rst_interpretation():
    record = record_from_draft(
        topic_draft(),
        record_id="topic-supervised-learning-a1b2c3d4",
        created_at="2026-09-24T00:00:00Z",
    )
    by_id = {row["id"]: row for row in record["sections"]}
    assert by_id["knowledge-gaps"]["body"] == "- Need a benchmark."
    assert "regularization" in by_id["continue-learning"]["body"]
    assert all(row["citations"] == [] for row in record["sections"])


def test_historical_numeric_section_ids_are_normalized_at_draft_boundary():
    draft = topic_draft()
    draft["sections"] = [
        {"id": "1", "title": "First", "body": "One"},
        {"id": "2", "title": "Second", "body": "Two"},
    ]
    record = record_from_draft(
        draft,
        record_id="topic-numeric-sections-a1b2c3d4",
        created_at="2026-09-24T00:00:00Z",
    )
    assert [row["id"] for row in record["sections"][:2]] == [
        "section-1",
        "section-2",
    ]


def test_record_draft_rejects_unknown_fields_and_source_review_is_explicit():
    draft = topic_draft()
    draft["browser_selected_repo_path"] = "../../unexpected.rst"
    with pytest.raises(LearnValidationError, match="unexpected fields"):
        record_from_draft(
            draft,
            record_id="topic-safe-boundary",
            created_at="2026-09-24T00:00:00Z",
        )

    source = {
        "contract": "learn.record-creation-draft.v1",
        "kind": "source",
        "title": "Source",
        "summary": "Summary",
        "domains": ["machine-learning"],
        "sections": [],
        "url": "https://example.com/paper",
        "metadata_questions": ["Confirm publication date"],
        "requires_metadata_review": True,
    }
    with pytest.raises(LearnValidationError, match="reviewed"):
        record_from_draft(
            source,
            record_id="source-paper-a1b2c3d4",
            created_at="2026-09-24T00:00:00Z",
        )
    record = record_from_draft(
        source,
        record_id="source-paper-a1b2c3d4",
        created_at="2026-09-24T00:00:00Z",
        metadata_reviewed=True,
    )
    assert record["sections"][-1]["id"] == "metadata-review"


def test_suggested_identity_ignores_mutable_draft_content_and_handles_prompts():
    first = topic_draft()
    second = copy.deepcopy(first)
    second["summary"] = "Regenerated prose must not silently change identity."
    assert suggested_artifact_id(first) == "topic-introduction-to-supervised-learning"
    assert suggested_artifact_id(second) == suggested_artifact_id(first)
    assert suggested_artifact_id(
        first,
        existing_ids={
            "topic-introduction-to-supervised-learning",
            "topic-introduction-to-supervised-learning-2",
        },
    ) == "topic-introduction-to-supervised-learning-3"
    assert suggested_artifact_id(prompt_draft()) == "counterfactual-check"
    assert suggested_artifact_id(skill_draft()) == "skill-source-triangulation"


def test_prompt_draft_requires_review_owned_registry_metadata():
    prompt = prompt_from_draft(
        prompt_draft(),
        prompt_id="counterfactual-check",
        author="community",
        order=140,
        default_enabled=False,
    )
    assert prompt["id"] == "counterfactual-check"
    assert prompt["order"] == 140
    assert prompt["default_enabled"] is False
    assert "Generation contract:" not in prompt["instruction"]


def test_skill_draft_requires_review_owned_registry_metadata():
    skill = skill_from_draft(
        skill_draft(),
        skill_id="skill-source-triangulation",
        author="community",
        order=60,
        default_enabled=False,
    )
    assert skill["id"] == "skill-source-triangulation"
    assert skill["order"] == 60
    assert skill["default_enabled"] is False
    assert skill["domains"] == []
    assert skill["related"] == []
    assert "Generation contract:" not in skill["instruction"]


def test_create_record_plan_is_json_only_deterministic_and_exact(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    draft = topic_draft()
    record_id = suggested_artifact_id(
        draft, existing_ids=(row["id"] for row in tree.catalog["subjects"])
    )
    publication = {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": tree.catalog["revision"],
        "operations": [
            {
                "op": "create-record",
                "record_id": record_id,
                "created_at": "2026-09-24T00:00:00Z",
                "draft": draft,
            }
        ],
    }
    first = publication_plan(root, publication)
    second = publication_plan(root, copy.deepcopy(publication))
    assert first == second
    assert first["contract"] == "learn.publication-plan.v2"
    assert first["deleted"] == []
    assert first["files"]
    assert all(name.endswith(".json") for name in first["files"])
    assert not any(name.endswith(".rst") for name in first["files"])
    assert any(name.endswith("/index.json") for name in first["files"])

    _apply_plan(root, first)
    loaded = load_content_tree(root)
    assert loaded.catalog["revision"] == first["revision"]
    assert record_id in loaded.routes


def test_new_topic_with_custom_sections_and_interaction_slots_projects_valid_tree(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    draft = topic_draft()
    draft["sections"] = [
        {"id": str(index), "title": f"Custom {index}", "body": f"Body {index}"}
        for index in range(1, 6)
    ]
    record_id = "topic-custom-capacity"
    publication = {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": tree.catalog["revision"],
        "operations": [
            {
                "op": "create-record",
                "record_id": record_id,
                "created_at": "2026-09-24T03:30:00Z",
                "draft": draft,
            }
        ],
    }
    plan = publication_plan(root, publication)
    assert len(plan["files"]) == 36
    _apply_plan(root, plan)
    projected = load_content_tree(root)
    assert projected.catalog["revision"] == plan["revision"]
    subject = next(row for row in projected.catalog["subjects"] if row["id"] == record_id)
    assert len(subject["sections"]) > 32
    assert any(row["id"] == "skill-check-reference" for row in subject["sections"])
    assert any(row["id"] == "eli14" for row in subject["sections"])


def test_section_patch_and_evidence_attachment_change_only_section_json(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    topic = next(row for row in tree.catalog["subjects"] if row["kind"] == "topic")
    source = next(row for row in tree.catalog["subjects"] if row["kind"] == "source")
    publication = {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": tree.catalog["revision"],
        "operations": [
            {
                "op": "upsert-section",
                "subject_id": topic["id"],
                "section_id": "summary",
                "title": "Summary",
                "body": "A reviewed replacement summary.",
            },
            {
                "op": "attach-source",
                "subject_id": topic["id"],
                "section_id": "summary",
                "section_title": "Summary",
                "source_id": source["id"],
                "locator": "Reviewed locator",
            },
        ],
    }
    plan = publication_plan(root, publication)
    assert len(plan["files"]) == 1
    relative = next(iter(plan["files"]))
    assert relative.endswith("/summary.json")
    payload = json.loads(plan["files"][relative])
    assert payload["section"]["body"] == "A reviewed replacement summary."
    assert {"source_id": source["id"], "locator": "Reviewed locator"} in payload[
        "section"
    ]["citations"]


def test_new_topic_prompt_fans_out_atomically_to_every_topic(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    topics = [row for row in tree.catalog["subjects"] if row["kind"] == "topic"]
    publication = {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": tree.catalog["revision"],
        "operations": [
            {
                "op": "create-topic-prompt",
                "prompt_id": "counterfactual-check",
                "author": "community",
                "order": 140,
                "default_enabled": False,
                "draft": prompt_draft(),
            }
        ],
    }
    plan = publication_plan(root, publication)
    assert len(plan["files"]) == 1 + 2 * len(topics)
    assert "topic-prompts/counterfactual-check/index.json" in plan["files"]
    assert sum(name.endswith("/topic-prompts/counterfactual-check.json") for name in plan["files"]) == len(topics)
    assert sum(name.endswith("/index.json") and name.startswith("topics/") for name in plan["files"]) == len(topics)

    _apply_plan(root, plan)
    loaded = load_content_tree(root)
    assert loaded.catalog["revision"] == plan["revision"]
    assert loaded.prompts[-1]["id"] == "counterfactual-check"


def test_new_skill_fans_out_atomically_to_every_topic(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    topics = [row for row in tree.catalog["subjects"] if row["kind"] == "topic"]
    publication = {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": tree.catalog["revision"],
        "operations": [
            {
                "op": "create-skill",
                "skill_id": "skill-source-triangulation",
                "author": "community",
                "order": 60,
                "default_enabled": False,
                "draft": skill_draft(),
            }
        ],
    }
    plan = publication_plan(root, publication)
    assert len(plan["files"]) == 1 + 2 * len(topics)
    assert "skills/skill-source-triangulation/index.json" in plan["files"]
    assert sum(
        name.endswith("/skills/skill-source-triangulation.json")
        for name in plan["files"]
    ) == len(topics)
    assert sum(
        name.endswith("/index.json") and name.startswith("topics/")
        for name in plan["files"]
    ) == len(topics)
    assert all(name.endswith(".json") for name in plan["files"])

    _apply_plan(root, plan)
    loaded = load_content_tree(root)
    assert loaded.catalog["revision"] == plan["revision"]
    assert loaded.skills[-1]["id"] == "skill-source-triangulation"
    assert loaded.routes["skill-source-triangulation"] == "skills/skill-source-triangulation/index"


def test_publication_rejects_cross_registry_and_structural_interaction_collisions(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    existing_skill = tree.skills[0]
    cross = {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": tree.catalog["revision"],
        "operations": [
            {
                "op": "create-topic-prompt",
                "prompt_id": existing_skill["id"],
                "author": "community",
                "order": 140,
                "default_enabled": False,
                "draft": prompt_draft(),
            }
        ],
    }
    with pytest.raises(LearnValidationError, match="must be disjoint"):
        publication_plan(root, cross)

    structural = copy.deepcopy(cross)
    structural["operations"][0]["prompt_id"] = "summary"
    with pytest.raises(LearnValidationError, match="structural section"):
        publication_plan(root, structural)


def test_publication_refuses_stale_base_revision_and_bad_source_target(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    topic = next(row for row in tree.catalog["subjects"] if row["kind"] == "topic")
    stale = {
        "contract": PUBLICATION_CONTRACT,
        "base_revision": "stale",
        "operations": [
            {
                "op": "upsert-section",
                "subject_id": topic["id"],
                "section_id": "summary",
                "title": "Summary",
                "body": "New",
            }
        ],
    }
    with pytest.raises(LearnValidationError, match="canonical tree changed"):
        publication_plan(root, stale)

    bad = copy.deepcopy(stale)
    bad["base_revision"] = tree.catalog["revision"]
    bad["operations"] = [
        {
            "op": "attach-source",
            "subject_id": topic["id"],
            "section_id": "summary",
            "section_title": "Summary",
            "source_id": topic["id"],
            "locator": "Example",
        }
    ]
    with pytest.raises(LearnValidationError, match="Source"):
        publication_plan(root, bad)


def test_review_bundle_cli_contains_json_only(tmp_path):
    root = _json_only_copy(tmp_path)
    draft_path = tmp_path / "draft.json"
    bundle = tmp_path / "bundle"
    draft_path.write_text(json.dumps(topic_draft()), encoding="utf-8")
    publication_cli(
        [
            str(root),
            str(draft_path),
            str(bundle),
            "--created-at",
            "2026-09-24T00:00:00Z",
        ]
    )
    manifest = json.loads((bundle / "publication-plan.json").read_text())
    assert manifest["contract"] == "learn.publication-review-bundle.v2"
    assert manifest["files"]
    assert all(name.endswith(".json") for name in manifest["files"])
    assert all(name.startswith("docs/source/learn-ai/") for name in manifest["files"])


def test_review_bundle_cli_supports_skill_without_record_timestamp(tmp_path):
    root = _json_only_copy(tmp_path)
    draft_path = tmp_path / "skill-draft.json"
    bundle = tmp_path / "skill-bundle"
    draft_path.write_text(json.dumps(skill_draft()), encoding="utf-8")
    publication_cli([str(root), str(draft_path), str(bundle)])
    manifest = json.loads((bundle / "publication-plan.json").read_text())
    assert manifest["files"]
    assert all(name.endswith(".json") for name in manifest["files"])
    assert any(
        name.endswith("skills/skill-source-triangulation/index.json")
        for name in manifest["files"]
    )


def test_review_bundle_cli_rejects_duplicate_json_keys(tmp_path):
    root = _json_only_copy(tmp_path)
    draft = tmp_path / "draft.json"
    draft.write_text(
        '{"contract":"learn.record-creation-draft.v1","kind":"topic",'
        '"title":"One","title":"Two"}',
        encoding="utf-8",
    )
    with pytest.raises(LearnValidationError, match="duplicate JSON key"):
        publication_cli(
            [
                str(root),
                str(draft),
                str(tmp_path / "bundle"),
                "--created-at",
                "2026-09-24T00:00:00Z",
            ]
        )


def test_reviewed_transport_request_reuses_canonical_publication_planner(tmp_path):
    from _sphinx_ext._sphinx_ai_learn._publication_request_cli import plan_publication_request

    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    draft = topic_draft()
    draft["provenance"] = {"base_revision": tree.catalog["revision"]}
    request = {
        "contract": "learn.publication-request.v1",
        "action": "publish",
        "draft": draft,
        "base_revision": tree.catalog["revision"],
        "created_at": "2026-09-25T01:00:00Z",
        "artifact_id": "auto",
        "author": "community",
        "default_enabled": False,
    }
    plan = plan_publication_request(root, request)
    assert plan["base_revision"] == tree.catalog["revision"]
    assert plan["files"]
    assert all(path.endswith(".json") for path in plan["files"])
    assert not plan["deleted"]


def test_reviewed_source_request_requires_explicit_metadata_review(tmp_path):
    from _sphinx_ext._sphinx_ai_learn._publication_request_cli import plan_publication_request

    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    draft = {
        "contract": "learn.record-creation-draft.v1",
        "kind": "source",
        "title": "Reviewed source",
        "summary": "Summary",
        "domains": ["statistics"],
        "sections": [{"id": "overview", "title": "Overview", "body": "Notes"}],
        "url": "https://example.org/source",
        "metadata_questions": [],
        "requires_metadata_review": True,
        "provenance": {"base_revision": tree.catalog["revision"]},
    }
    request = {
        "contract": "learn.publication-request.v1",
        "action": "publish",
        "draft": draft,
        "base_revision": tree.catalog["revision"],
        "created_at": "2026-09-25T01:00:00Z",
        "artifact_id": "auto",
    }
    with pytest.raises(LearnValidationError, match="metadata_reviewed"):
        plan_publication_request(root, request)
    request["metadata_reviewed"] = True
    plan = plan_publication_request(root, request)
    assert plan["files"]
    assert all(path.endswith(".json") for path in plan["files"])


def test_reviewed_publication_workflow_separates_dry_run_and_json_only_write_authority():
    root = Path(__file__).resolve().parents[5]
    workflow_path = root / ".github" / "workflows" / "ai-learn-publish.yml"
    text = workflow_path.read_text()
    assert "transport-test:" in text
    assert "permissions:\n      contents: read" in text
    assert "validate-plan-and-open-pr:" in text
    assert "contents: write" in text
    assert "pull-requests: write" in text
    assert "inputs.operation == 'test' &&" in text
    assert "inputs.operation == 'publish' &&" in text
    assert text.count("github.repository == 'scikit-plots/learn' &&") == 2
    assert text.count("github.ref_name == github.event.repository.default_branch") == 2
    assert "AI_LEARN_BASE_BRANCH: ${{ github.event.repository.default_branch }}" in text
    assert "persist-credentials: false" in text
    assert "persist-credentials: true" not in text
    assert "Publication changed forbidden repository paths" in text
    assert "Non-JSON staged path detected" in text
    assert "docs/source/learn-ai" in text
    assert "install -m 700 .github/scripts/ai-learn-git-askpass.sh" in text
    assert "GIT_ASKPASS: ${{ runner.temp }}/ai-learn-git-askpass.sh" in text
    assert text.count("GH_TOKEN: ${{ github.token }}") >= 3
    assert text.count("GH_REPO: ${{ github.repository }}") >= 2
    assert "GIT_TERMINAL_PROMPT: '0'" in text
    assert "git push origin HEAD:\"$BRANCH\"" in text
    assert "branch_reusable=true" in text
    assert "--state closed" in text
    assert "--state merged" in text
    assert "Refusing to create a second review for the same deterministic request id." in text
    assert "refusing to treat a Git transport/authentication failure as branch absence" in text
    assert "Reserved publication branch contains forbidden paths" in text
    assert "Reserved publication branch does not match the current reviewed JSON plan" in text
    assert "Recovered matching AI Learn publication branch; PR creation will be retried." in text
    assert "gh pr create" in text
    assert "https://x-access-token" not in text


def test_reviewed_publication_git_askpass_is_prompt_scoped_and_fail_closed():
    root = Path(__file__).resolve().parents[5]
    helper = root / ".github" / "scripts" / "ai-learn-git-askpass.sh"
    assert helper.is_file()

    env = os.environ.copy()
    env["GH_TOKEN"] = "test-publication-token"

    username = subprocess.run(
        ["/bin/sh", str(helper), "Username for 'https://github.com':"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert username.stdout.strip() == "x-access-token"
    assert "test-publication-token" not in username.stdout

    password = subprocess.run(
        ["/bin/sh", str(helper), "Password for 'https://x-access-token@github.com':"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert password.stdout.strip() == "test-publication-token"

    unknown = subprocess.run(
        ["/bin/sh", str(helper), "Unexpected prompt"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert unknown.returncode != 0
    assert unknown.stdout == ""

    missing_env = env.copy()
    missing_env.pop("GH_TOKEN", None)
    missing = subprocess.run(
        ["/bin/sh", str(helper), "Password for 'https://github.com':"],
        check=False,
        capture_output=True,
        text=True,
        env=missing_env,
    )
    assert missing.returncode != 0
    assert missing.stdout == ""
