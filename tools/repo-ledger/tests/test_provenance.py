"""Installed-origin checks must not import the inspected product."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from repo_ledger import cli
from conftest import commit

COMMIT = "a" * 40


@pytest.fixture
def consumer(tmp_path):
    venv = tmp_path / "consumer env"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    python = venv / "bin" / "python"
    site = Path(subprocess.check_output(
        [str(python), "-I", "-c", 'import sysconfig; print(sysconfig.get_path("purelib"))'],
        text=True,
    ).strip())
    package = site / "fixture_consumer"
    package.mkdir()
    (package / "__init__.py").write_text('raise RuntimeError("product was imported")\n')
    metadata = site / "fixture_consumer-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: fixture-consumer\nVersion: 1.0\n")
    (metadata / "RECORD").write_text("fixture_consumer/__init__.py,,\n")
    provenance = metadata / "direct_url.json"
    provenance.write_text(json.dumps({
        "url": "https://sensitive-token@example.invalid/private.git",
        "vcs_info": {"vcs": "git", "commit_id": COMMIT},
    }))
    return python, package, metadata, provenance


def invoke(capsys, consumer, *args):
    code = cli.main(["provenance", "--python", str(consumer[0]),
                     "--distribution", "fixture-consumer", "--module", "fixture_consumer", *args])
    out = capsys.readouterr()
    return code, out


def test_pinned_consumer_reports_origin_without_importing_or_writing(
        consumer, tmp_path, capsys, monkeypatch):
    poison = tmp_path / "working tree"
    poison.mkdir()
    (poison / "fixture_consumer.py").write_text('raise RuntimeError("cwd shadow")\n')
    monkeypatch.chdir(poison)
    monkeypatch.setenv("PYTHONPATH", str(poison))
    code, out = invoke(capsys, consumer, "--expected-commit", COMMIT)
    assert code == 0, out.err
    report = json.loads(out.out)
    assert report["schema"] == "repo-ledger.provenance/1"
    assert report["interpreter"] == str(consumer[0])
    assert report["distribution"]["commit"] == COMMIT
    assert report["module"]["origin"] == str(consumer[1] / "__init__.py")
    assert report["module"]["owned_by_distribution"] is True
    assert report["verified_pin"] is True
    assert "sensitive-token" not in out.out + out.err
    assert not list(consumer[1].rglob("*.pyc"))


@pytest.mark.parametrize("provenance", [
    {"vcs_info": {"commit_id": "b" * 40}},
    {"vcs_info": {"commit_id": COMMIT}, "dir_info": {"editable": True}},
    {},
])
def test_wrong_editable_or_unrecorded_install_cannot_verify_a_pin(consumer, provenance, capsys):
    consumer[3].write_text(json.dumps(provenance))
    code, out = invoke(capsys, consumer, "--expected-commit", COMMIT)
    assert code == 1
    assert json.loads(out.out)["verified_pin"] is False


def test_matching_metadata_without_module_ownership_fails(consumer, capsys):
    (consumer[2] / "RECORD").write_text("unrelated.py,,\n")
    code, out = invoke(capsys, consumer, "--expected-commit", COMMIT)
    assert code == 1
    report = json.loads(out.out)
    assert report["module"]["owned_by_distribution"] is False
    assert report["verified_pin"] is False


def test_missing_product_is_reported_without_installing_it(consumer, capsys):
    code = cli.main(["provenance", "--python", str(consumer[0]),
                     "--distribution", "not-installed", "--module", "not_installed"])
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["distribution"]["installed"] is False
    assert report["module"]["origin"] is None


def test_observation_reports_editable_install_without_certifying_it(consumer, capsys):
    consumer[3].write_text('{"dir_info": {"editable": true}}')
    code, out = invoke(capsys, consumer)
    assert code == 0
    report = json.loads(out.out)
    assert report["distribution"]["editable"] is True
    assert report["verified_pin"] is None


def test_malformed_metadata_is_a_failure_without_echoing_secrets(consumer, capsys):
    consumer[3].write_text("sensitive-token invalid json")
    code, out = invoke(capsys, consumer, "--expected-commit", COMMIT)
    assert code != 0
    assert "sensitive-token" not in out.out + out.err


def test_repo_head_is_the_expected_commit(consumer, make_repo, capsys):
    repo = make_repo()
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    consumer[3].write_text(json.dumps({"vcs_info": {"commit_id": head}}))
    code, out = invoke(capsys, consumer, "--repo", str(repo))
    assert code == 0, out.err
    report = json.loads(out.out)
    assert report["expected_commit"] == head and report["verified_pin"] is True
    assert report["repo"]["dirty"] is False
    commit(repo, "newer.txt")
    code, out = invoke(capsys, consumer, "--repo", str(repo))
    assert code == 1 and json.loads(out.out)["verified_pin"] is False


@pytest.mark.parametrize("args", [
    ("--module", "fixture_consumer.submodule"),
    ("--python", "relative/python"),
    ("--expected-commit", "shortsha"),
    ("--expected-commit", ""),
    ("--timeout", "0"),
    ("--timeout", "nan"),
    ("--repo", "/nonexistent-repo-ledger-path"),
    ("--repo", ".", "--expected-commit", COMMIT),
])
def test_invalid_requests_are_refused_before_launch(consumer, args, capsys):
    code, _ = invoke(capsys, consumer, *args)
    assert code == 2


def test_interpreter_timeout_is_bounded_and_reported(tmp_path, capsys):
    python = tmp_path / "slow-python"
    python.write_text("#!/bin/sh\nexec sleep 5\n")
    python.chmod(0o700)
    code, out = invoke(capsys, (python,), "--timeout", "0.05")
    assert code == 2
    assert "timed out" in out.err
