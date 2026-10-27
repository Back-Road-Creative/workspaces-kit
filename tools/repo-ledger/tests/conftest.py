import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_git(tmp_path, monkeypatch):
    """No user or system git config, an empty HOME, fixed identities."""
    home = tmp_path / "empty home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Fixture")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "fixture@example.invalid")
    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout


def commit(repo: Path, name: str = "file.txt", text: str = "x\n") -> str:
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"add {name}")
    return git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def make_repo(tmp_path):
    """make_repo("name", pushed=True) -> a repo with one commit and a bare origin."""
    def factory(name: str = "repo with spaces", pushed: bool = True, parent: Path | None = None):
        root = parent or (tmp_path / "parent dir")
        root.mkdir(exist_ok=True)
        repo = root / name
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        commit(repo)
        if pushed:
            origin = tmp_path / "remotes" / f"{name}.git"
            origin.parent.mkdir(exist_ok=True)
            subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
            git(repo, "remote", "add", "origin", str(origin))
            git(repo, "push", "-q", "-u", "origin", "main")
        return repo
    return factory
