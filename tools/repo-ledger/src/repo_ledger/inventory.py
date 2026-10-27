"""Inspect one repository for work that exists only on this machine.

Everything here reads local state. Remote-tracking refs are whatever the last
fetch left behind; nothing is fetched, so "unique" means "not reachable from
any remote-tracking ref on this machine".
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from . import gitcmd

_USERINFO = re.compile(r"(?<=://)[^/@\s]+@")


def redact_url(url: str) -> str:
    """Drop user:password@ from a URL so a receipt never carries a token."""
    return _USERINFO.sub("", url)


def _status_counts(worktree: Path) -> dict[str, int]:
    out = gitcmd.run(worktree, "status", "--porcelain=v2", "-z", "--no-renames",
                     "--untracked-files=normal", "--ignore-submodules=dirty")
    counts = {"staged": 0, "unstaged": 0, "untracked": 0, "conflicted": 0}
    for record in out.split("\0"):
        if not record:
            continue
        kind = record[0]
        if kind == "1":
            xy = record[2:4]
            counts["staged"] += xy[0] != "."
            counts["unstaged"] += xy[1] != "."
        elif kind == "u":
            counts["conflicted"] += 1
        elif kind == "?":
            counts["untracked"] += 1
    return counts


def _worktrees(repo: Path) -> list[dict]:
    out = gitcmd.run(repo, "worktree", "list", "--porcelain", "-z")
    trees: list[dict] = []
    current: dict | None = None
    for field in out.split("\0"):
        if not field:
            if current is not None:
                trees.append(current)
                current = None
            continue
        key, _, value = field.partition(" ")
        if key == "worktree":
            current = {"path": value, "head": None, "branch": None, "detached": False,
                       "bare": False, "locked": False, "prunable": False}
        elif current is None:
            continue
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key in ("detached", "bare", "locked", "prunable"):
            current[key] = True
    if current is not None:
        trees.append(current)
    for index, tree in enumerate(trees):
        tree["main"] = index == 0
        tree["exists"] = Path(tree["path"]).is_dir()
    return trees


def _branches(repo: Path) -> list[dict]:
    fmt = "%(refname:short)%00%(objectname)%00%(upstream:short)%00%(upstream:track,nobracket)"
    out = gitcmd.run(repo, "for-each-ref", f"--format={fmt}", "refs/heads")
    branches = []
    for line in out.splitlines():
        name, sha, upstream, track = (line.split("\0") + ["", "", ""])[:4]
        ahead = behind = 0
        for part in track.split(","):
            word, _, number = part.strip().partition(" ")
            if word == "ahead":
                ahead = int(number)
            elif word == "behind":
                behind = int(number)
        unique = int(gitcmd.run(repo, "rev-list", "--count", sha, "--not", "--remotes").strip() or 0)
        branches.append({
            "name": name,
            "commit": sha,
            "upstream": upstream or None,
            "upstream_gone": track.strip() == "gone",
            "ahead": ahead,
            "behind": behind,
            "unique_commits": unique,
        })
    return branches


def _remotes(repo: Path) -> list[dict]:
    out = gitcmd.run(repo, "config", "--get-regexp", r"^remote\..*\.url$", check=False)
    remotes = []
    for line in out.splitlines():
        key, _, url = line.partition(" ")
        remotes.append({"name": key[len("remote."):-len(".url")], "url": redact_url(url)})
    return remotes


def _stash_count(repo: Path) -> int:
    if not gitcmd.ok(repo, "rev-parse", "-q", "--verify", "refs/stash"):
        return 0
    return len(gitcmd.run(repo, "stash", "list", "--format=%H").split())


def _last_fetch(common_dir: Path) -> str | None:
    fetch_head = common_dir / "FETCH_HEAD"
    try:
        stamp = fetch_head.stat().st_mtime
    except OSError:
        return None
    return _dt.datetime.fromtimestamp(stamp, _dt.timezone.utc).isoformat(timespec="seconds")


def _absolute(base: Path, text: str) -> Path:
    path = Path(text)
    return path if path.is_absolute() else (base / path)


def inspect(path: Path, name: str | None = None, worktree_status: bool = True) -> dict:
    """One receipt entry for ``path``. Never raises for repository problems."""
    entry: dict = {"name": name or path.name, "path": str(path), "state": "ok", "reason": None}
    if not path.exists():
        return {**entry, "state": "missing", "reason": "path-not-found"}
    if not path.is_dir():
        return {**entry, "state": "not-a-repo", "reason": "not-a-directory"}
    try:
        is_bare = gitcmd.run(path, "rev-parse", "--is-bare-repository").strip() == "true"
        common = gitcmd.run(path, "rev-parse", "--git-common-dir").strip()
        top = None if is_bare else gitcmd.run(path, "rev-parse", "--show-toplevel").strip()
    except gitcmd.GitError as exc:
        reason = gitcmd.classify_error(exc.stderr)
        state = "not-a-repo" if reason == "not-a-repo" else "refused"
        return {**entry, "state": state, "reason": reason}
    if top is not None and Path(top).resolve() != path.resolve():
        return {**entry, "state": "not-a-repo", "reason": "inside-another-repo", "inside": top}
    common_dir = _absolute(path, common).resolve()
    branch = gitcmd.run(path, "symbolic-ref", "-q", "--short", "HEAD", check=False).strip() or None
    head = gitcmd.run(path, "rev-parse", "-q", "--verify", "HEAD", check=False).strip() or None
    entry.update(
        bare=is_bare,
        git_common_dir=str(common_dir),
        head={"branch": branch, "commit": head, "detached": branch is None and head is not None,
              "unborn": head is None},
        remotes=_remotes(path),
        last_fetch=_last_fetch(common_dir),
        branches=_branches(path),
        stashes=_stash_count(path),
    )
    trees = _worktrees(path)
    dirty_total = 0
    for tree in trees:
        tree["dirty"] = None
        if tree["bare"] or not tree["exists"]:
            continue
        if tree["main"] or worktree_status:
            tree["dirty"] = _status_counts(Path(tree["path"]))
            dirty_total += sum(tree["dirty"].values())
    entry["worktrees"] = trees
    unique_total = int(gitcmd.run(path, "rev-list", "--count", "--branches", "--not",
                                  "--remotes").strip() or 0)
    local_only = [b["name"] for b in entry["branches"] if b["unique_commits"]]
    entry["summary"] = {
        "unique_commits": unique_total,
        "branches_with_unique_commits": local_only,
        "stashes": entry["stashes"],
        "dirty_paths": dirty_total,
        "missing_worktrees": sum(1 for t in trees if not t["exists"]),
        "at_risk": bool(unique_total or entry["stashes"] or dirty_total),
    }
    return entry


def scan(root: Path, depth: int = 1) -> list[Path]:
    """Repositories under ``root`` (itself included) down to ``depth`` levels.

    The parent does not need to be a repository. A found repository is not
    descended into; symlinked directories are not followed.
    """
    found: list[Path] = []

    def walk(directory: Path, level: int) -> None:
        if (directory / ".git").exists():
            found.append(directory)
            return
        if level >= depth:
            return
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError:
            return
        for child in children:
            if child.is_dir() and not child.is_symlink():
                walk(child, level + 1)

    walk(root, 0)
    return found
