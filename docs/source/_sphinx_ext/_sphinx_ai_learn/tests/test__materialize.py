"""Canonical JSON -> deterministic RST materialization invariants."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from _sphinx_ext._sphinx_ai_learn._materialize import (
    GENERATED_MARKER,
    canonical_prompt_json_files,
    canonical_skill_json_files,
    canonical_record_json_files,
    load_content_tree,
    materialize,
    render_materialized,
)
from _sphinx_ext._sphinx_ai_learn._schema import LearnValidationError

SOURCE = Path(__file__).resolve().parents[3] / "learn-ai"


def _json_only_copy(tmp_path):
    root = tmp_path / "learn-ai"
    for source in SOURCE.rglob("*.json"):
        target = root / source.relative_to(SOURCE)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    return root


def _first_topic(tree):
    return next(
        (rel, record)
        for rel, record in tree.records.items()
        if record["subject"]["kind"] == "topic"
    )


def test_production_tree_is_one_json_to_one_rst_and_projection_is_canonical():
    tree = load_content_tree(SOURCE)
    rendered = render_materialized(tree)
    # Preserve the known baseline without freezing a publication-driven corpus.
    # New reviewed records/prompts/skills and feedback sidecars are expected to
    # grow these collections over time.
    assert len(tree.catalog["subjects"]) >= 50
    assert len(tree.prompts) >= 13
    assert len(tree.skills) >= 5
    assert len(tree.source_digests) - len(tree.feedback_events) >= 677
    assert all(subject.get("authors") for subject in tree.catalog["subjects"] if subject["kind"] != "skill")
    assert all(prompt.get("authors") for prompt in tree.prompts)
    assert all(skill.get("authors") for skill in tree.skills)
    assert all(
        section.get("contributors")
        for subject in tree.catalog["subjects"]
        for section in subject.get("sections", [])
        if section.get("body") or section.get("citations") or section.get("links")
    )
    assert len(rendered) == len(tree.source_digests) - len(tree.feedback_events)
    assert all((SOURCE / rel).is_file() for rel in rendered)
    assert all((SOURCE / rel).read_bytes() == raw for rel, raw in rendered.items())

    assert canonical_prompt_json_files(tree.prompts) == {
        rel: (SOURCE / rel).read_bytes()
        for rel in canonical_prompt_json_files(tree.prompts)
    }
    assert canonical_skill_json_files(tree.skills) == {
        rel: (SOURCE / rel).read_bytes()
        for rel in canonical_skill_json_files(tree.skills)
    }
    for rel, record in tree.records.items():
        projected = canonical_record_json_files(
            record["subject"],
            tree.prompts,
            tree.skills,
            add_toctree=record["add_toctree"],
        )
        assert projected == {path: (SOURCE / path).read_bytes() for path in projected}


def test_materialize_is_idempotent_and_preserves_unchanged_mtime(tmp_path):
    root = _json_only_copy(tmp_path)
    expected = load_content_tree(root)
    expected_renderable = len(expected.source_digests) - len(expected.feedback_events)
    _, first = materialize(root)
    assert len(first) == expected_renderable
    tracked = root / first[0]
    before = tracked.stat().st_mtime_ns
    _, second = materialize(root)
    assert second == ()
    assert tracked.stat().st_mtime_ns == before




def test_feedback_sidecar_is_validated_scored_and_never_materialized_as_rst(tmp_path):
    from _sphinx_ext._sphinx_ai_learn._generation import section_generation_id

    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    content_revision = tree.catalog["revision"]
    content_digest = tree.content_digest
    full_digest = tree.digest
    _, baseline_changed = materialize(root)
    assert baseline_changed
    rel, record = next(
        (rel, record)
        for rel, record in tree.records.items()
        if record["subject"]["kind"] == "topic"
        and any(section["id"] == "summary" and section["body"] for section in record["subject"]["sections"])
    )
    subject = record["subject"]
    section = next(row for row in subject["sections"] if row["id"] == "summary")
    generation_id = section_generation_id(subject, section)
    feedback_id = "feedback-sidecar-0001"
    sidecar = rel.parent / "feedback" / section["id"] / generation_id / f"{feedback_id}.json"
    target = root / sidecar
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "contract": "learn.generation-feedback.v1",
                "record_id": subject["id"],
                "section_id": "summary",
                "generation_id": generation_id,
                "feedback": {
                    "id": feedback_id,
                    "rating": 4,
                    "contributor": "DataFox",
                    "mode": "detailed",
                    "comment": "Useful explanation.",
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    loaded = load_content_tree(root)
    assert loaded.catalog["revision"] == content_revision
    assert loaded.content_digest == content_digest
    assert loaded.digest != full_digest
    assert str(root / sidecar) not in loaded.dependencies
    assert loaded.feedback_dependencies[subject["id"]] == (str(root / sidecar),)
    assert subject["id"] in loaded.feedback_digests
    assert loaded.generation_feedback[(subject["id"], "summary", generation_id)] == (
        {
            "id": feedback_id,
            "rating": 4,
            "contributor": "DataFox",
            "mode": "detailed",
            "comment": "Useful explanation.",
        },
    )
    rendered = render_materialized(loaded)
    assert sidecar.with_suffix(".rst") not in rendered
    _, changed = materialize(root)
    assert changed == ()
    assert not (root / sidecar.with_suffix(".rst")).exists()


    invalid = json.loads(target.read_text(encoding="utf-8"))
    invalid["feedback"]["mode"] = "quick"
    invalid["feedback"]["rating"] = 4
    target.write_text(json.dumps(invalid, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(LearnValidationError, match="quick mode"):
        load_content_tree(root)



def test_feedback_identifier_is_globally_unique_across_embedded_and_sidecar_stores(tmp_path):
    from _sphinx_ext._sphinx_ai_learn._generation import generation_identifier

    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    section_rel, row = next(
        (rel, row)
        for rel, row in tree.sections.items()
        if row["subject"]["kind"] == "topic"
        and row["section"]["id"] == "summary"
        and row["section"].get("body")
    )
    subject = row["subject"]
    section = row["section"]
    created_at = subject.get("created_at") or "1970-01-01T00:00:00Z"
    provenance = {"authorship": "legacy-import"}
    generation_id = generation_identifier(
        section_id="summary",
        created_at=created_at,
        body=section["body"],
        provenance=provenance,
    )
    feedback_id = "feedback-global-duplicate"
    generation = {
        "id": generation_id,
        "created_at": created_at,
        "body": section["body"],
        "citations": section.get("citations", []),
        "links": section.get("links", []),
        "contributors": section.get("contributors", ["Anonymous"]),
        "provenance": provenance,
        "feedback": [
            {
                "id": feedback_id,
                "created_at": "2026-09-27T10:00:00Z",
                "rating": 1,
                "contributor": "DataFox",
                "mode": "quick",
            }
        ],
    }
    source = root / section_rel
    source.write_text(
        json.dumps(
            {
                "contract": "learn.section.v2",
                "record_id": subject["id"],
                "section": {
                    "id": "summary",
                    "title": section["title"],
                    "active_generation_id": generation_id,
                    "generations": [generation],
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    sidecar = (
        section_rel.parent
        / "feedback"
        / "summary"
        / generation_id
        / f"{feedback_id}.json"
    )
    target = root / sidecar
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "contract": "learn.generation-feedback.v1",
                "record_id": subject["id"],
                "section_id": "summary",
                "generation_id": generation_id,
                "feedback": {
                    "id": feedback_id,
                    "rating": 1,
                    "contributor": "DataFox",
                    "mode": "quick",
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        LearnValidationError,
        match="duplicate feedback identifier across canonical stores",
    ):
        load_content_tree(root)


def test_feedback_sidecar_path_is_section_scoped(tmp_path):
    from _sphinx_ext._sphinx_ai_learn._generation import section_generation_id

    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    rel, record = next(
        (rel, record)
        for rel, record in tree.records.items()
        if record["subject"]["kind"] == "topic"
        and any(section["id"] == "summary" and section["body"] for section in record["subject"]["sections"])
    )
    subject = record["subject"]
    section = next(row for row in subject["sections"] if row["id"] == "summary")
    generation_id = section_generation_id(subject, section)
    feedback_id = "feedback-wrong-section-path"
    wrong = rel.parent / "feedback" / generation_id / f"{feedback_id}.json"
    target = root / wrong
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "contract": "learn.generation-feedback.v1",
                "record_id": subject["id"],
                "section_id": "summary",
                "generation_id": generation_id,
                "feedback": {
                    "id": feedback_id,
                    "rating": 1,
                    "contributor": "Anonymous",
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LearnValidationError, match="feedback sidecar path"):
        load_content_tree(root)

def test_default_include_mode_uses_orphan_fragments_and_nested_prompt_paths(tmp_path):
    root = _json_only_copy(tmp_path)
    tree, _ = materialize(root)
    rel, record = _first_topic(tree)
    folder = root / rel.parent
    parent = (folder / "index.rst").read_text(encoding="utf-8")
    summary = (folder / "summary.rst").read_text(encoding="utf-8")
    prompt = (folder / "topic-prompts" / "eli14.rst").read_text(encoding="utf-8")
    skill_group = (folder / "skills" / "index.rst").read_text(encoding="utf-8")
    skill = (folder / "skills" / "skill-check-reference.rst").read_text(encoding="utf-8")

    assert record["add_toctree"] is False
    assert ".. include:: summary.rst" in parent
    assert ".. include:: topic-prompts/eli14.rst" in parent
    assert ".. toctree::" not in parent
    assert summary.startswith(":orphan:\n:no-search:\n")
    assert GENERATED_MARKER in summary.splitlines()[:12]
    assert ".. ai-learn-fragment-start" in summary
    assert prompt.startswith(":orphan:\n:no-search:\n")
    assert skill_group.startswith(":orphan:\n:no-search:\n")
    assert skill.startswith(":orphan:\n:no-search:\n")
    assert ".. ai-topic-skills::" in skill_group
    assert ".. _learn-" not in prompt.split(".. ai-learn-fragment-start", 1)[1]
    assert ".. _learn-" not in skill.split(".. ai-learn-fragment-start", 1)[1]


def test_toctree_mode_makes_children_navigable_without_orphan(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    rel, _ = _first_topic(tree)
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    data["add_toctree"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    _, changed = materialize(root)
    parent = path.with_suffix(".rst").read_text(encoding="utf-8")
    summary = (path.parent / "summary.rst").read_text(encoding="utf-8")
    assert ".. toctree::" in parent
    assert ".. include::" not in parent
    assert "summary" in parent
    skill = (path.parent / "skills" / "skill-check-reference.rst").read_text(encoding="utf-8")
    assert not summary.startswith(":orphan:")
    assert not skill.startswith(":orphan:")
    assert f".. _learn-{data['record']['id']}-summary:" in summary
    assert "skills/skill-check-reference" in parent
    assert any(name.endswith("/summary.rst") for name in changed)


def test_regeneration_from_json_only_is_byte_identical(tmp_path):
    root = _json_only_copy(tmp_path)
    source_tree = load_content_tree(SOURCE)
    expected = render_materialized(source_tree)
    _, changed = materialize(root)
    assert len(changed) == len(expected)
    generated = {p.relative_to(root): p.read_bytes() for p in root.rglob("*.rst")}
    assert generated == expected


def test_one_section_json_change_rewrites_only_its_owned_rst(tmp_path):
    root = _json_only_copy(tmp_path)
    tree, _ = materialize(root)
    rel, _ = _first_topic(tree)
    source = root / rel.parent / "summary.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    data["section"]["body"] += "\n\nA deterministic mutation."
    source.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _, changed = materialize(root)
    assert changed == ((rel.parent / "summary.rst").as_posix(),)


def test_handwritten_collision_is_a_hard_error_before_writes(tmp_path):
    root = _json_only_copy(tmp_path)
    target = root / "index.rst"
    target.write_text("Handwritten source.\n", encoding="utf-8")
    with pytest.raises(LearnValidationError, match="handwritten RST"):
        materialize(root)
    assert target.read_text(encoding="utf-8") == "Handwritten source.\n"
    assert len(list(root.rglob("*.rst"))) == 1


def test_orphan_canonical_json_and_path_escape_are_rejected(tmp_path):
    root = _json_only_copy(tmp_path)
    rogue = root / "topics" / "rogue.json"
    rogue.write_text(
        json.dumps(
            {
                "contract": "learn.section.v1",
                "record_id": "topic-rogue",
                "section": {
                    "id": "summary",
                    "title": "Summary",
                    "body": "",
                    "citations": [],
                    "links": [],
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(LearnValidationError, match="orphan section JSON"):
        load_content_tree(root)




def test_dangling_related_error_names_canonical_json_owner_and_target(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    rel, record = _first_topic(tree)
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    subject_id = data["record"]["id"]
    data["record"]["related"] = ["topic-missing-related-target"]
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    expected = (
        rf"{rel.as_posix()}: subject\.related: {subject_id} "
        r"-> unknown target topic-missing-related-target"
    )
    with pytest.raises(LearnValidationError, match=expected):
        load_content_tree(root)



def test_dangling_citation_error_names_section_json_owner_and_source(tmp_path):
    root = _json_only_copy(tmp_path)
    tree = load_content_tree(root)
    rel, record = _first_topic(tree)
    section_ref = next(
        ref for ref in record["section_refs"] if ref["id"] == "summary"
    )
    section_rel = rel.parent / section_ref["source"]
    path = root / section_rel
    data = json.loads(path.read_text(encoding="utf-8"))
    data["section"]["citations"] = [
        {"source_id": "source-missing-citation-target", "locator": "Section 1"}
    ]
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    subject_id = record["subject"]["id"]
    expected = (
        rf"{section_rel.as_posix()}: section\.citations: {subject_id}#summary "
        r"-> unknown source source-missing-citation-target"
    )
    with pytest.raises(LearnValidationError, match=expected):
        load_content_tree(root)

def test_symlink_json_is_rejected(tmp_path):
    root = _json_only_copy(tmp_path)
    if not hasattr(Path, "symlink_to"):
        pytest.skip("symlinks unavailable")
    target = next(root.rglob("summary.json"))
    copy = target.with_name("copy.json")
    try:
        copy.symlink_to(target.name)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(LearnValidationError, match="symlink JSON"):
        load_content_tree(root)


def test_canonical_json_rejects_duplicate_keys_and_nonfinite_numbers(tmp_path):
    root = _json_only_copy(tmp_path)
    target = root / "index.json"
    target.write_text(
        '{"contract":"learn.page.v1","contract":"learn.page.v1","view":"root","title":"AI Learn"}',
        encoding="utf-8",
    )
    with pytest.raises(LearnValidationError, match="invalid JSON"):
        load_content_tree(root)

    root = _json_only_copy(tmp_path / "nonfinite")
    target = root / "index.json"
    target.write_text(
        '{"contract":"learn.page.v1","view":"root","title":"AI Learn","description":NaN}',
        encoding="utf-8",
    )
    with pytest.raises(LearnValidationError, match="invalid JSON"):
        load_content_tree(root)


def test_rst_heading_inputs_reject_control_newlines(tmp_path):
    root = _json_only_copy(tmp_path)
    target = root / "index.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    data["title"] = "AI Learn\n.. include:: secret.rst"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    with pytest.raises(LearnValidationError, match="control characters"):
        load_content_tree(root)


def test_feedback_outdated_documents_is_record_scoped_and_tracks_external_consumers():
    from _sphinx_ext._sphinx_ai_learn._generation import feedback_outdated_documents

    found = {
        "index",
        "examples/embed",
        "learn-ai/index",
        "learn-ai/topics/example/index",
        "learn-ai/topics/example/topic-prompts/eli14",
        "learn-ai/topics/other/index",
    }
    routes = {
        "topic-example": "topics/example/index",
        "topic-other": "topics/other/index",
    }
    previous = {"topic-example": "a", "topic-other": "z"}
    current = {"topic-example": "b", "topic-other": "z"}
    consumers = {"topic-example": {"examples/embed"}}

    assert feedback_outdated_documents(
        root="learn-ai",
        routes=routes,
        found_docs=found,
        consumers=consumers,
        previous=previous,
        current=current,
    ) == [
        "examples/embed",
        "learn-ai/topics/example/index",
        "learn-ai/topics/example/topic-prompts/eli14",
    ]
    assert feedback_outdated_documents(
        root="learn-ai",
        routes=routes,
        found_docs=found,
        consumers=consumers,
        previous=current,
        current=current,
    ) == []
