"""Run git read-only: no optional locks, no fsmonitor hook, no prompts, no network."""

from __future__ import annotations

import os
import subprocess
import tempfile
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


def run(repo: Path, *args: str, check: bool = True, stdin: str | None = None) -> str:
    proc = subprocess.run(
        ["git", *SAFE_CONFIG, "-C", str(repo), *args],
        capture_output=True,
        env=git_env(),
        **({"input": stdin.encode(errors="surrogateescape")} if stdin is not None
           else {"stdin": subprocess.DEVNULL}),
        timeout=120,
    )
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.decode(errors="replace"), proc.returncode)
    return proc.stdout.decode(errors="surrogateescape")


def piped(repo: Path, first: tuple[str, ...], second: tuple[str, ...]) -> str:
    """``git <first> | git <second>``, streamed so a long first output is never held."""
    with tempfile.TemporaryFile() as err:
        head = subprocess.Popen(["git", *SAFE_CONFIG, "-C", str(repo), *first],
                                stdout=subprocess.PIPE, stderr=err, stdin=subprocess.DEVNULL,
                                env=git_env())
        try:
            tail = subprocess.run(["git", *SAFE_CONFIG, "-C", str(repo), *second],
                                  stdin=head.stdout, capture_output=True, env=git_env(),
                                  timeout=600)
        except BaseException:
            head.kill()
            raise
        finally:
            head.stdout.close()
            code = head.wait()
        if tail.returncode != 0:
            raise GitError(tail.stderr.decode(errors="replace"), tail.returncode)
        if code != 0:
            err.seek(0)
            raise GitError(err.read().decode(errors="replace"), code)
    return tail.stdout.decode(errors="surrogateescape")


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
