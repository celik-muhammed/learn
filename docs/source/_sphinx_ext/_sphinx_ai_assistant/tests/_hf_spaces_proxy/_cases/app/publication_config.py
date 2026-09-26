from __future__ import annotations

from scikitplot._externals._sphinx_ext._sphinx_ai_assistant.tests._paths import RUNTIME_ROOT

import json
import os
import subprocess
import sys

PROXY = RUNTIME_ROOT / "_hf_spaces_proxy"


def _probe(env_updates: dict[str, str | None]) -> dict[str, object]:
    env = os.environ.copy()
    for name in (
        "AI_LEARN_PUBLICATION_MODE",
        "AI_LEARN_GITHUB_TOKEN",
        "AI_RECORD_STORAGE_TOKEN_GITHUB_MIRROR",
        "CONTRIBUTION_REVIEW_MODE",
        "RECORD_STORAGE_TARGETS",
        "DATASET_TARGETS_JSON",
        "TRAINING_DATASET_REPO",
        "AI_RECORD_STORAGE_TOKEN_HF_PRIMARY",
    ):
        env.pop(name, None)
    for name, value in env_updates.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    code = (
        "import json, app; "
        "print(json.dumps({"
        "'publication_mode': app.AI_LEARN_PUBLICATION_MODE,"
        "'publication_policy_mode': app.AI_LEARN_PUBLICATION_POLICY.mode,"
        "'publication_ready': app._learn_publication_capability()['ready'],"
        "'token_env': app.AI_LEARN_GITHUB_TOKEN_ENV,"
        "'contribution_review_mode': app.CONTRIBUTION_REVIEW_MODE,"
        "'storage_ids': [t.id for t in app._STORAGE.targets],"
        "'storage_roles': [t.role for t in app._STORAGE.targets],"
        "'storage_repos': [t.repo for t in app._STORAGE.targets]"
        "}))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROXY,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout.strip())


def test_publication_and_contribution_review_defaults_are_current_policy():
    out = _probe({})
    assert out == {
        "publication_mode": "github",
        "publication_policy_mode": "github",
        "publication_ready": False,
        "token_env": "",
        "contribution_review_mode": "provider-pr",
        "storage_ids": ["hf-primary", "github-mirror"],
        "storage_roles": ["primary", "mirror"],
        "storage_repos": [
            "scikit-plots/ai-assistant-contributions",
            "scikit-plots/ai-assistant-records",
        ],
    }


def test_publication_uses_mirror_token_only_as_ordered_fallback():
    out = _probe({"AI_RECORD_STORAGE_TOKEN_GITHUB_MIRROR": "mirror-test-token"})
    assert out["publication_ready"] is True
    assert out["token_env"] == "AI_RECORD_STORAGE_TOKEN_GITHUB_MIRROR"


def test_dedicated_publication_token_has_precedence_over_fallback():
    out = _probe({
        "AI_LEARN_GITHUB_TOKEN": "dedicated-test-token",
        "AI_RECORD_STORAGE_TOKEN_GITHUB_MIRROR": "mirror-test-token",
    })
    assert out["publication_ready"] is True
    assert out["token_env"] == "AI_LEARN_GITHUB_TOKEN"


def test_explicit_modes_override_defaults_and_invalid_review_mode_fails_closed():
    disabled = _probe({
        "AI_LEARN_PUBLICATION_MODE": "disabled",
        "CONTRIBUTION_REVIEW_MODE": "ledger",
    })
    assert disabled["publication_policy_mode"] == "disabled"
    assert disabled["contribution_review_mode"] == "ledger"

    invalid = _probe({"CONTRIBUTION_REVIEW_MODE": "typo"})
    assert invalid["contribution_review_mode"] == "ledger"


def test_default_registry_keeps_learn_publication_out_of_record_coordinator():
    code = (
        "import json; from _utils import _shared_logic as s; "
        "registry=json.loads(s.DEFAULT_TARGET_REGISTRY); "
        "records=json.loads(s.DEFAULT_RECORD_STORAGE_TARGETS); "
        "print(json.dumps({"
        "'all_ids':[t['id'] for t in registry],"
        "'record_ids':[t['id'] for t in records],"
        "'publication':s.DEFAULT_AI_LEARN_PUBLICATION_TARGET,"
        "'token_envs':list(s.DEFAULT_AI_LEARN_GITHUB_TOKEN_ENVS)"
        "}))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROXY,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )
    out = json.loads(proc.stdout.strip())
    assert out["all_ids"] == ["hf-primary", "github-mirror", "github-learn-ai"]
    assert out["record_ids"] == ["hf-primary", "github-mirror"]
    assert out["publication"]["role"] == "primary"
    assert out["publication"]["authority"] == "learn-ai-publication"
    assert out["publication"]["paths"] == {
        "root": "docs/source",
        "prefix": "docs/source/learn-ai",
    }
    assert out["publication"]["max_body_bytes"] == 49152
    assert out["publication"]["rate_limit_per_hour"] == 6
    assert out["token_envs"] == [
        "AI_LEARN_GITHUB_TOKEN",
        "AI_RECORD_STORAGE_TOKEN_GITHUB_MIRROR",
    ]


def test_legacy_training_repo_still_beats_bundled_record_defaults():
    out = _probe({"TRAINING_DATASET_REPO": "example-org/legacy-records"})
    assert out["storage_ids"] == ["hf-primary"]
    assert out["storage_roles"] == ["primary"]
    assert out["storage_repos"] == ["example-org/legacy-records"]


def test_explicit_record_topology_still_beats_bundled_record_defaults():
    explicit = json.dumps([
        {
            "id": "custom-primary",
            "provider": "github",
            "role": "primary",
            "repo": "example-org/custom-records",
            "token_env": "AI_RECORD_STORAGE_TOKEN_CUSTOM",
        }
    ])
    out = _probe({"RECORD_STORAGE_TARGETS": explicit})
    assert out["storage_ids"] == ["custom-primary"]
    assert out["storage_repos"] == ["example-org/custom-records"]
