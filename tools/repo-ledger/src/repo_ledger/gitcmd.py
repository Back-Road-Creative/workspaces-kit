"""Run git read-only: no optional locks, no fsmonitor hook, no prompts, no network."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# A repository's own config can name an fsmonitor command that `git status`
# would execute. Inspecting a repository must never run code it supplies.
SAFE_CONFIG = (
    "-c", "core.fsmonitor=false",
    "-c", "core.untrackedCache=false",
    "-c", "color.ui=false",
)


def git_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        GIT_OPTIONAL_LOCKS="0",  # `git status` must not rewrite the index
        GIT_TERMINAL_PROMPT="0",
        LC_ALL="C",
        LANG="C",
    )
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env


class GitError(Exception):
    def __init__(self, stderr: str, returncode: int):
        super().__init__(stderr.strip() or f"git exited {returncode}")
        self.stderr = stderr
        self.returncode = returncode


def run(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *SAFE_CONFIG, "-C", str(repo), *args],
        capture_output=True,
        env=git_env(),
        stdin=subprocess.DEVNULL,
        timeout=120,
    )
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.decode(errors="replace"), proc.returncode)
    return proc.stdout.decode(errors="surrogateescape")


def ok(repo: Path, *args: str) -> bool:
    try:
        run(repo, *args)
    except GitError:
        return False
    return True


def version() -> str | None:
    try:
        out = subprocess.run(["git", "--version"], capture_output=True, text=True,
                             env=git_env(), timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip().removeprefix("git version ") or None


def classify_error(stderr: str) -> str:
    """Map git's refusal text to a stable reason code."""
    text = stderr.lower()
    if "dubious ownership" in text:
        return "dubious-ownership"
    if "not a git repository" in text:
        return "not-a-repo"
    if "permission denied" in text:
        return "permission-denied"
    return "git-error"
