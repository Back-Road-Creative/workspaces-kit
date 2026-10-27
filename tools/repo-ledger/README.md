# repo-ledger

Find the Git work that exists only on this machine, and check which installed
copy of a Python package an interpreter really runs. Offline and read-only.

## Install

```sh
python3 -m pip install ./tools/repo-ledger      # from a checkout of this repository
```

Python 3.11 or newer and Git are the only requirements. There are no runtime
dependencies.

## `repo-ledger inventory`

```sh
repo-ledger inventory ~/code/app ~/code/notes     # named repositories
repo-ledger inventory --scan ~/code               # every repository one level down
repo-ledger inventory --scan ~/code --depth 2     # two levels down
repo-ledger inventory --manifest repos.toml       # an explicit list (see below)
repo-ledger inventory --scan ~/code --json        # machine-readable receipt
repo-ledger inventory --scan ~/code --check       # exit 1 if anything is at risk
```

For each repository it reports:

- **unique commits**: commits reachable from a local branch but from no
  remote-tracking ref. These are lost if the disk is.
- **branches with unique commits**, by name, including branches with no upstream.
- **branches already landed**: of those, the ones whose changes are already on a
  remote's default branch by patch content, as after a squash or rebase merge.
  Each branch's **unlanded commits** counts what has not landed. See
  [Concepts](../../docs/concepts.md#already-landed).
- **stashes** and **dirty paths** (staged, unstaged, untracked, conflicted),
  counted in the main worktree and in every linked worktree.
- **worktrees**, including ones whose directory is gone.
- remotes, with any `user:password@` removed from the URL.

A repository is **at risk** when it has unique commits, stashes or dirty paths.
A linked worktree found next to its repository is reported once, under the main
worktree, so nothing is counted twice.

Remote refs are only as fresh as your last `git fetch`. repo-ledger never
fetches, so the receipt records `"fetched": false` and each repository's last
fetch time. Fetch first if you need "not on the server" rather than "not in my
last fetch".

### Manifest

```toml
version = 1

[[repo]]
path = "products/my-app"   # relative to this file, absolute, or ~/...
name = "my-app"            # optional display name
```

Unknown keys are rejected, so a typo cannot silently drop a repository.

### What it will not do

- It never writes to a repository: no index refresh, no lock files, no fetch.
  Git runs with optional locks off.
- It never runs code a repository supplies. A repository's config can name an
  fsmonitor hook that `git status` would execute; repo-ledger turns it off.
- It does not follow symlinked directories while scanning, and does not descend
  into a repository it has found.
- A repository Git refuses to open (for example "dubious ownership" when another
  user owns it) is listed as `refused` with that reason. repo-ledger does not
  add `safe.directory` exceptions for you.

Exit codes: 0 done, 1 `--check` found something, 2 usage error.

## `repo-ledger provenance`

```sh
repo-ledger provenance --python /path/to/venv/bin/python \
  --distribution my-package --module my_package \
  --expected-commit 0123456789abcdef0123456789abcdef01234567
repo-ledger provenance --python /path/to/venv/bin/python \
  --distribution my-package --module my_package --repo ~/code/my-package
```

It runs a short probe inside the named interpreter with `-I -B` from a neutral
directory, so the current directory, `PYTHONPATH` and user site-packages cannot
shadow the module, and no bytecode is written. The probe reads package metadata
and finds the module's file without importing it.

The receipt reports the installed version, whether the install is editable, the
commit pip recorded, the module's file, and whether that file belongs to the
installed distribution. With `--expected-commit` (or `--repo`, which uses that
repository's `HEAD`), exit 0 needs all of: the recorded commit matches, the
install is not editable, and the module file belongs to the distribution.

Limits, stated plainly:

- The interpreter's own `.pth` files and site hooks still run at startup. Point
  it only at an interpreter you trust.
- A recorded commit is an installation record, not a signature over the files.
- It does not tell you which interpreter a scheduler or service actually uses.
- Namespace packages with no concrete module file cannot pass the check.

Exit codes: 0 found (and verified, when asked), 1 missing, wrong commit,
editable or unowned module, 2 invalid request or unreadable metadata.

## Receipts

Both commands print JSON with a `schema` field (`repo-ledger.inventory/1`,
`repo-ledger.provenance/1`). The schemas are in `../../schemas/`, and the test
suite checks real output against them.

## Tests

```sh
python3 -m pip install -e './tools/repo-ledger[test]'
python3 -m pytest tools/repo-ledger/tests
```

Every test builds throwaway repositories under a temporary directory with an
empty `HOME` and no user or system Git config.
