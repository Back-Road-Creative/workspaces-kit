"""Command line: `repo-ledger inventory` and `repo-ledger provenance`."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from . import __version__, gitcmd, inventory, manifest, provenance, render

INVENTORY_SCHEMA = "repo-ledger.inventory/1"
EXIT_OK, EXIT_FINDING, EXIT_USAGE = 0, 1, 2


def _targets(args: argparse.Namespace) -> list[tuple[Path, str | None]]:
    targets: list[tuple[Path, str | None]] = []
    if args.manifest:
        targets += [(e.path, e.name) for e in manifest.load(Path(args.manifest))]
    for root in args.scan or ():
        root_path = Path(root).expanduser()
        if not root_path.is_dir():
            raise manifest.ManifestError(f"--scan {root}: not a directory")
        targets += [(p, None) for p in inventory.scan(root_path, args.depth)]
    targets += [(Path(p).expanduser(), None) for p in args.paths]
    seen, unique = set(), []
    for path, name in targets:
        key = str(path.absolute())
        if key not in seen:
            seen.add(key)
            unique.append((path, name))
    return unique


def _one_per_repository(entries: list[dict]) -> list[dict]:
    """Collapse entries that share a Git directory (a repo and its linked worktrees).

    Every worktree's branches, stashes and dirty state are already in each
    entry, so listing them twice would double-count. The main worktree's entry
    is kept, at the position of the first entry for that repository.
    """
    chosen: dict[str, dict] = {}
    order: list[str] = []
    for entry in entries:
        key = entry.get("git_common_dir") or f"\0{entry['path']}"
        if key not in chosen:
            chosen[key] = entry
            order.append(key)
            continue
        trees = entry.get("worktrees") or []
        if trees and Path(trees[0]["path"]).resolve() == Path(entry["path"]).resolve():
            chosen[key] = entry
    return [chosen[key] for key in order]


def cmd_inventory(args: argparse.Namespace) -> int:
    if args.depth < 0:
        print("repo-ledger: --depth must be zero or more", file=sys.stderr)
        return EXIT_USAGE
    try:
        targets = _targets(args)
    except manifest.ManifestError as exc:
        print(f"repo-ledger: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if not targets:
        print("repo-ledger: name repositories as paths, --manifest FILE or --scan DIR",
              file=sys.stderr)
        return EXIT_USAGE
    receipt = {
        "schema": INVENTORY_SCHEMA,
        "tool_version": __version__,
        "git_version": gitcmd.version(),
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "fetched": False,
        "repos": _one_per_repository(
            [inventory.inspect(p, n, worktree_status=not args.skip_worktree_status)
             for p, n in targets]),
    }
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render.inventory_markdown(receipt))
    if args.check and any(r["state"] != "ok" or r["summary"]["at_risk"]
                          or r["summary"]["unreadable_worktrees"] for r in receipt["repos"]):
        return EXIT_FINDING
    return EXIT_OK


def cmd_provenance(args: argparse.Namespace) -> int:
    expected = args.expected_commit
    repo_dirty = None
    try:
        if args.repo:
            if expected is not None:
                raise provenance.RequestError("give --expected-commit or --repo, not both")
            expected, repo_dirty = provenance.repo_head(Path(args.repo).expanduser())
        report = provenance.observe(Path(args.python), args.distribution, args.module,
                                    expected, args.timeout)
    except provenance.RequestError as exc:
        print(f"repo-ledger: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except provenance.ProbeError as exc:
        print(f"repo-ledger: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.repo:
        report["repo"] = {"path": args.repo, "dirty": repo_dirty}
    print(json.dumps(report, indent=2, sort_keys=True))
    return EXIT_OK if report["available"] and report["verified_pin"] is not False else EXIT_FINDING


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="repo-ledger",
        description="Offline, read-only ledger of local Git work and installed package origins.",
    )
    top.add_argument("--version", action="version", version=f"repo-ledger {__version__}")
    sub = top.add_subparsers(dest="command", required=True)

    inv = sub.add_parser("inventory", help="find work that exists only on this machine")
    inv.add_argument("paths", nargs="*", help="repository paths")
    inv.add_argument("--manifest", help="TOML file listing repositories (see docs)")
    inv.add_argument("--scan", action="append", metavar="DIR",
                     help="find repositories under DIR; DIR need not be a repository")
    inv.add_argument("--depth", type=int, default=1, help="levels below --scan DIR (default 1)")
    inv.add_argument("--json", action="store_true", help="print the JSON receipt")
    inv.add_argument("--check", action="store_true",
                     help="exit 1 if any repository or worktree is unreadable or missing, "
                          "or holds local-only work")
    inv.add_argument("--skip-worktree-status", action="store_true",
                     help="do not run status in linked worktrees (faster, undercounts dirty files)")
    inv.set_defaults(func=cmd_inventory)

    prov = sub.add_parser("provenance", help="which installed distribution an interpreter runs")
    prov.add_argument("--python", default=sys.executable,
                      help="absolute path to a trusted interpreter (default: this one)")
    prov.add_argument("--distribution", required=True)
    prov.add_argument("--module", required=True, help="top-level module name")
    prov.add_argument("--expected-commit", help="full 40-character commit the install should record")
    prov.add_argument("--repo", help="expect the commit at this repository's HEAD")
    prov.add_argument("--timeout", type=float, default=15, help="probe timeout, 0-60 seconds")
    prov.set_defaults(func=cmd_provenance)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
