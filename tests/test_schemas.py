"""Real tool output must validate against the published schemas."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import schema_check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_git(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    for key, value in {"HOME": str(home), "GIT_CONFIG_GLOBAL": os.devnull,
                       "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Test",
                       "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Test",
                       "GIT_COMMITTER_EMAIL": "test@example.invalid"}.items():
        monkeypatch.setenv(key, value)
    return tmp_path


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout


def run_cli(*args: str) -> tuple[int, dict]:
    out = subprocess.run([sys.executable, "-m", "repo_ledger", *args],
                         capture_output=True, text=True)
    return out.returncode, json.loads(out.stdout)


def test_inventory_receipt_matches_schema(isolated_git):
    base = isolated_git / "work dir"
    origin = isolated_git / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    repo = base / "app"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "one")
    git(repo, "remote", "add", "origin", f"https://user:secret@example.invalid/{origin.name}")
    git(repo, "switch", "-q", "-c", "local-only")
    (repo / "b.txt").write_text("b\n")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "two")
    git(repo, "worktree", "add", "-q", str(base / "tree"), "-b", "side", "main")
    (repo / "c.txt").write_text("dirty\n")
    (base / "plain").mkdir()
    (repo / "sub").mkdir()
    code, receipt = run_cli("inventory", "--json", str(repo), str(base / "absent"),
                            str(base / "plain"), str(repo / "sub"))
    assert code == 0
    assert schema_check.errors(receipt, schema_check.load("inventory")) == []
    states = [r["state"] for r in receipt["repos"]]
    assert states == ["ok", "missing", "not-a-repo", "not-a-repo"]
    assert "secret" not in json.dumps(receipt)


def test_provenance_receipt_matches_schema(isolated_git):
    code, report = run_cli("provenance", "--python", sys.executable,
                           "--distribution", "pytest", "--module", "pytest")
    assert code == 0
    assert schema_check.errors(report, schema_check.load("provenance")) == []


def test_example_manifest_matches_schema():
    data = tomllib.loads((ROOT / "examples" / "manifest.example.toml").read_text())
    assert schema_check.errors(data, schema_check.load("manifest")) == []


def test_catalog_matches_schema():
    data = tomllib.loads((ROOT / "catalog" / "projects.toml").read_text())
    for project in data["project"]:
        assert isinstance(project["checked"], dt.date)
        project["checked"] = project["checked"].isoformat()
    assert schema_check.errors(data, schema_check.load("catalog")) == []


def test_checker_catches_drift():
    schema = schema_check.load("provenance")
    assert schema_check.errors({"schema": "repo-ledger.provenance/1"}, schema)
    with pytest.raises(ValueError):
        schema_check.errors(1, {"maxLength": 3})
