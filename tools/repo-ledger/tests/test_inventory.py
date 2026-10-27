"""Inventory reports local-only work, never changes a repository, never runs repo code."""

import json
from pathlib import Path

import pytest

from repo_ledger import cli, gitcmd, inventory
from conftest import commit, git


def receipt(capsys, *argv):
    code = cli.main(["inventory", "--json", *argv])
    out = capsys.readouterr().out
    return code, json.loads(out)


def snapshot(git_dir: Path) -> dict:
    return {str(p): (p.stat().st_mtime_ns, p.stat().st_size)
            for p in sorted(git_dir.rglob("*")) if p.is_file()}


def test_clean_pushed_repo_is_not_at_risk(make_repo, capsys):
    repo = make_repo()
    code, data = receipt(capsys, "--check", str(repo))
    assert code == 0
    entry = data["repos"][0]
    assert entry["state"] == "ok"
    assert entry["head"]["branch"] == "main"
    assert entry["branches"][0]["upstream"] == "origin/main"
    assert entry["summary"] == {
        "unique_commits": 0, "branches_with_unique_commits": [], "stashes": 0,
        "dirty_paths": 0, "missing_worktrees": 0, "unreadable_worktrees": 0,
        "at_risk": False,
    }
    assert data["fetched"] is False
    assert data["schema"] == "repo-ledger.inventory/1"


def test_unpushed_and_local_only_branches_are_counted(make_repo, capsys):
    repo = make_repo()
    commit(repo, "ahead.txt")
    git(repo, "switch", "-q", "-c", "local-only")
    commit(repo, "local.txt")
    git(repo, "switch", "-q", "main")
    code, data = receipt(capsys, "--check", str(repo))
    assert code == 1
    entry = data["repos"][0]
    by_name = {b["name"]: b for b in entry["branches"]}
    assert by_name["main"]["ahead"] == 1
    assert by_name["main"]["unique_commits"] == 1
    assert by_name["local-only"]["upstream"] is None
    assert by_name["local-only"]["unique_commits"] == 2
    assert entry["summary"]["unique_commits"] == 2  # union, not a sum
    assert entry["summary"]["branches_with_unique_commits"] == ["local-only", "main"]
    assert entry["summary"]["at_risk"] is True


def test_repo_without_remote_counts_every_commit(make_repo, capsys):
    repo = make_repo(pushed=False)
    _, data = receipt(capsys, str(repo))
    assert data["repos"][0]["remotes"] == []
    assert data["repos"][0]["summary"]["unique_commits"] == 1


def test_dirty_files_and_stashes_are_counted(make_repo, capsys):
    repo = make_repo()
    (repo / "file.txt").write_text("changed\n")
    git(repo, "stash", "-q")
    (repo / "staged.txt").write_text("s\n")
    git(repo, "add", "staged.txt")
    (repo / "file.txt").write_text("unstaged\n")
    (repo / "new file.txt").write_text("u\n")
    _, data = receipt(capsys, str(repo))
    entry = data["repos"][0]
    assert entry["stashes"] == 1
    main_tree = entry["worktrees"][0]
    assert main_tree["main"] is True
    assert main_tree["dirty"] == {"staged": 1, "unstaged": 1, "untracked": 1, "conflicted": 0}
    assert entry["summary"]["dirty_paths"] == 3
    assert entry["summary"]["at_risk"] is True


def test_linked_worktrees_are_listed_with_their_own_dirty_state(make_repo, tmp_path, capsys):
    repo = make_repo()
    linked = tmp_path / "linked tree"
    git(repo, "worktree", "add", "-q", "-b", "feature", str(linked))
    (linked / "wip.txt").write_text("w\n")
    gone = tmp_path / "gone tree"
    git(repo, "worktree", "add", "-q", "--detach", str(gone))
    git(repo, "worktree", "lock", str(gone))
    import shutil
    shutil.rmtree(gone)
    _, data = receipt(capsys, str(repo))
    trees = {Path(t["path"]).name: t for t in data["repos"][0]["worktrees"]}
    assert trees["linked tree"]["branch"] == "feature"
    assert trees["linked tree"]["dirty"]["untracked"] == 1
    assert trees["gone tree"]["exists"] is False
    assert trees["gone tree"]["locked"] is True
    assert trees["gone tree"]["dirty"] is None
    assert data["repos"][0]["summary"]["missing_worktrees"] == 1
    assert data["repos"][0]["summary"]["dirty_paths"] == 1


def test_skip_worktree_status_still_checks_the_main_tree(make_repo, tmp_path, capsys):
    repo = make_repo()
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", "-b", "feature", str(linked))
    (linked / "wip.txt").write_text("w\n")
    (repo / "main wip.txt").write_text("w\n")
    _, data = receipt(capsys, "--skip-worktree-status", str(repo))
    trees = data["repos"][0]["worktrees"]
    assert trees[0]["dirty"]["untracked"] == 1
    assert trees[1]["dirty"] is None


def test_detached_and_unborn_heads(make_repo, tmp_path, capsys):
    repo = make_repo()
    git(repo, "switch", "-q", "--detach", "HEAD")
    unborn = tmp_path / "unborn"
    unborn.mkdir()
    git(unborn, "init", "-q", "-b", "main")
    _, data = receipt(capsys, str(repo), str(unborn))
    detached, empty = data["repos"]
    assert detached["head"]["detached"] is True and detached["head"]["branch"] is None
    assert empty["head"] == {"branch": "main", "commit": None, "detached": False, "unborn": True}
    assert empty["summary"]["unique_commits"] == 0


def test_bare_repository(tmp_path, make_repo, capsys):
    make_repo()
    bare = tmp_path / "remotes" / "repo with spaces.git"
    _, data = receipt(capsys, str(bare))
    entry = data["repos"][0]
    assert entry["state"] == "ok" and entry["bare"] is True
    assert entry["worktrees"][0]["dirty"] is None


def test_missing_plain_and_nested_paths_are_named_not_crashed(make_repo, tmp_path, capsys):
    repo = make_repo()
    (repo / "sub").mkdir()
    plain = tmp_path / "plain"
    plain.mkdir()
    afile = tmp_path / "a file"
    afile.write_text("")
    code, data = receipt(capsys, "--check", str(tmp_path / "nope"), str(plain),
                         str(repo / "sub"), str(afile))
    assert code == 1
    states = [(r["state"], r["reason"]) for r in data["repos"]]
    assert states == [("missing", "path-not-found"), ("not-a-repo", "not-a-repo"),
                      ("not-a-repo", "inside-another-repo"), ("not-a-repo", "not-a-directory")]
    assert data["repos"][2]["inside"] == str(repo)


def test_scan_finds_repos_under_a_non_git_parent(make_repo, tmp_path, capsys):
    parent = tmp_path / "parent dir"
    make_repo("one", parent=parent)
    make_repo("two", parent=parent)
    (parent / "group").mkdir()
    make_repo("deep", parent=parent / "group")
    (parent / "link").symlink_to(parent / "one")
    _, shallow = receipt(capsys, "--scan", str(parent))
    assert [r["name"] for r in shallow["repos"]] == ["one", "two"]
    _, deeper = receipt(capsys, "--scan", str(parent), "--depth", "2")
    assert [r["name"] for r in deeper["repos"]] == ["deep", "one", "two"]


def test_scan_reports_a_repository_once_when_its_linked_worktree_is_nearby(make_repo, tmp_path,
                                                                          capsys):
    parent = tmp_path / "parent dir"
    repo = make_repo("main repo", parent=parent)
    git(repo, "switch", "-q", "-c", "local-only")
    commit(repo, "idea.txt")
    git(repo, "worktree", "add", "-q", str(parent / "a review tree"), "-b", "review", "main")
    _, data = receipt(capsys, "--scan", str(parent))
    assert [r["name"] for r in data["repos"]] == ["main repo"]
    assert data["repos"][0]["summary"]["unique_commits"] == 1
    assert len(data["repos"][0]["worktrees"]) == 2


def _refuse(monkeypatch, when):
    real = gitcmd.run

    def fake(repo, *args, check=True):
        if when(Path(repo), args):
            raise gitcmd.GitError("fatal: detected dubious ownership in repository at 'x'", 128)
        return real(repo, *args, check=check)

    monkeypatch.setattr(gitcmd, "run", fake)


def test_unreadable_linked_worktree_is_reported_not_crashed(make_repo, tmp_path, capsys,
                                                             monkeypatch):
    repo = make_repo()
    other = tmp_path / "other user tree"
    git(repo, "worktree", "add", "-q", "-b", "theirs", str(other))
    _refuse(monkeypatch, lambda path, args: path == other and args[0] == "status")
    code, data = receipt(capsys, "--check", str(repo))
    entry = data["repos"][0]
    assert entry["state"] == "ok"
    linked = [t for t in entry["worktrees"] if not t["main"]][0]
    assert linked["dirty"] is None and linked["status_error"] == "dubious-ownership"
    assert entry["summary"]["unreadable_worktrees"] == 1
    assert code == cli.EXIT_FINDING  # unknown state is never reported as safe


def test_git_failure_after_open_is_a_refusal_not_a_crash(make_repo, capsys, monkeypatch):
    repo = make_repo()
    _refuse(monkeypatch, lambda path, args: args[0] == "for-each-ref")
    code, data = receipt(capsys, str(repo))
    assert code == 0
    assert data["repos"][0]["state"] == "refused"
    assert data["repos"][0]["reason"] == "dubious-ownership"


def test_duplicate_targets_are_reported_once(make_repo, capsys):
    repo = make_repo()
    _, data = receipt(capsys, str(repo), str(repo))
    assert len(data["repos"]) == 1


def test_remote_credentials_are_redacted(make_repo, capsys):
    repo = make_repo()
    git(repo, "remote", "add", "mirror", "https://user:sekret-token@example.invalid/x.git")
    code = cli.main(["inventory", "--json", str(repo)])
    out = capsys.readouterr().out
    assert code == 0
    assert "sekret-token" not in out
    urls = {r["name"]: r["url"] for r in json.loads(out)["repos"][0]["remotes"]}
    assert urls["mirror"] == "https://example.invalid/x.git"


def test_inventory_writes_nothing_inside_the_repository(make_repo, tmp_path, capsys):
    repo = make_repo()
    (repo / "file.txt").write_text("dirty\n")  # forces status to want an index refresh
    git(repo, "worktree", "add", "-q", "-b", "f", str(tmp_path / "wt"))
    before = snapshot(repo / ".git")
    receipt(capsys, str(repo))
    assert snapshot(repo / ".git") == before


def test_repository_config_cannot_run_a_command(make_repo, tmp_path, capsys):
    repo = make_repo()
    marker = tmp_path / "ran"
    hook = tmp_path / "monitor.sh"
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    hook.chmod(0o755)
    git(repo, "config", "core.fsmonitor", str(hook))
    (repo / "file.txt").write_text("dirty\n")
    receipt(capsys, str(repo))
    assert not marker.exists()


def test_markdown_table_names_risky_branches(make_repo, capsys):
    repo = make_repo("pipe|name")
    git(repo, "switch", "-q", "-c", "keep-me")
    commit(repo, "k.txt")
    assert cli.main(["inventory", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "| pipe\\|name | ok | keep-me |" in out
    assert "keep-me" in out.splitlines()[-2]
    assert "nothing was fetched" in out


@pytest.mark.parametrize("stderr,reason", [
    ("fatal: detected dubious ownership in repository at '/x'", "dubious-ownership"),
    ("fatal: not a git repository (or any of the parent directories): .git", "not-a-repo"),
    ("error: Permission denied", "permission-denied"),
    ("fatal: something else", "git-error"),
])
def test_git_refusals_map_to_stable_reasons(stderr, reason):
    assert gitcmd.classify_error(stderr) == reason


def test_no_targets_is_a_usage_error(capsys):
    assert cli.main(["inventory"]) == 2
    assert "--manifest" in capsys.readouterr().err


def test_scan_of_a_file_is_a_usage_error(tmp_path, capsys):
    f = tmp_path / "f"
    f.write_text("")
    assert cli.main(["inventory", "--scan", str(f)]) == 2


def test_redact_url_keeps_scp_style_urls():
    assert inventory.redact_url("git@example.invalid:o/r.git") == "git@example.invalid:o/r.git"
    assert inventory.redact_url("ssh://git@example.invalid/o/r") == "ssh://example.invalid/o/r"
