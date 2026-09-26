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
    assert len(tree.catalog["subjects"]) == 50
    assert len(tree.prompts) == 13
    assert len(tree.skills) == 5
    assert len(tree.source_digests) == 677
    assert len(rendered) == len(tree.source_digests)
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
    _, first = materialize(root)
    assert len(first) == 677
    tracked = root / first[0]
    before = tracked.stat().st_mtime_ns
    _, second = materialize(root)
    assert second == ()
    assert tracked.stat().st_mtime_ns == before


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
    _, changed = materialize(root)
    assert len(changed) == 677
    generated = {p.relative_to(root): p.read_bytes() for p in root.rglob("*.rst")}
    expected = render_materialized(load_content_tree(SOURCE))
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
