"""Human-readable tables for inventory receipts."""

from __future__ import annotations


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def inventory_markdown(receipt: dict) -> str:
    rows = ["| repo | state | branch | dirty | stashes | unique commits | worktrees | at risk |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for repo in receipt["repos"]:
        if repo["state"] != "ok":
            rows.append(f"| {_cell(repo['name'])} | {repo['state']} ({repo['reason']}) "
                        "| | | | | | |")
            continue
        head = repo["head"]
        branch = head["branch"] or ("(detached)" if head["detached"] else "(unborn)")
        summary = repo["summary"]
        trees = len(repo["worktrees"])
        missing = summary["missing_worktrees"]
        unreadable = summary["unreadable_worktrees"]
        notes = [f"{missing} missing"] * bool(missing) + [f"{unreadable} unreadable"] * bool(unreadable)
        tree_cell = f"{trees}" + (f" ({', '.join(notes)})" if notes else "")
        rows.append("| " + " | ".join(_cell(v) for v in (
            repo["name"], "ok", branch, summary["dirty_paths"], summary["stashes"],
            summary["unique_commits"], tree_cell, "yes" if summary["at_risk"] else "no",
        )) + " |")
    lines = [*rows, ""]
    for repo in receipt["repos"]:
        if repo["state"] == "ok" and repo["summary"]["branches_with_unique_commits"]:
            names = ", ".join(repo["summary"]["branches_with_unique_commits"])
            lines.append(f"- {_cell(repo['name'])}: branches with commits on no remote: {names}")
    lines.append("Remote refs are as of each repo's last fetch; nothing was fetched.")
    return "\n".join(lines) + "\n"
