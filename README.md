# workspaces-kit

Small, offline tools for people who keep many Git repositories and Python
environments on one machine, plus a catalog of the public projects they come from.

**Status:** early. One tool so far. Interfaces may change before 1.0.

## The problem

When you work across many repositories, work hides in places `git status` in
one directory does not show: a branch you never pushed, a stash from last month,
a linked worktree whose folder you deleted, a repository nested under a folder
that is not itself a repository. And when several environments install the same
package, it is easy to be wrong about which copy a scheduled job actually runs.

## What is here

| Path | What it is |
| --- | --- |
| `tools/repo-ledger/` | `repo-ledger inventory`: find work that exists only on this machine. `repo-ledger provenance`: which installed copy of a package an interpreter runs. |
| `catalog/projects.toml` | The public projects this kit belongs with, with each one's own description and license. |
| `catalog/prior-art.md` | Existing multi-repository tools, and when to use them instead. |
| `schemas/` | JSON Schemas for every receipt and file format here. |
| `examples/` | A demo that builds throwaway repositories and runs the tools. |
| `docs/concepts.md` | The ideas behind the checks. |

## Ten-minute quickstart

```sh
git clone <this repository> workspaces-kit
cd workspaces-kit
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install ./tools/repo-ledger
bash examples/demo.sh
```

The demo creates repositories in a new temporary directory, deletes them when
it exits, and prints something like:

```text
| repo | state | branch | dirty | stashes | unique commits | worktrees | at risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| my app | ok | experiment | 0 | 1 | 1 | 2 | yes |
| notes | ok | main | 0 | 0 | 1 | 1 | yes |

- my app: branches with commits on no remote: experiment
- notes: branches with commits on no remote: main
Remote refs are as of each repo's last fetch; nothing was fetched.
```

Then point it at your own folder:

```sh
repo-ledger inventory --scan ~/code
```

## Support

| | Supported |
| --- | --- |
| Operating systems | Linux, and Windows through WSL. macOS is untested. Native Windows is not supported. |
| Python | 3.11, 3.12, 3.13 (tested in CI) |
| Git | 2.36 or newer (`git worktree list -z` first shipped in 2.36); CI uses the runner's Git |

## When to use something else

For everyday "what branch is each repo on, is it ahead or behind" across a
registered list of repositories, use [gita](https://github.com/nosarthur/gita).
repo-ledger is for the recovery question ("what would I lose if this disk died
right now?") and for package provenance. See `catalog/prior-art.md`.

## License

Not yet chosen. Until a license file is added, no license is granted.

## Contributing and security

See `CONTRIBUTING.md` and `SECURITY.md`.
