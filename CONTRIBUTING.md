# Contributing

Thanks for looking. Small, focused pull requests are easiest to review.

## Set up and test

```sh
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -e './tools/repo-ledger[test]'
python3 -m pytest tools/repo-ledger/tests tests
bash examples/demo.sh
```

Tests must not touch the network, your real Git config or your real home
directory. The fixtures in `tools/repo-ledger/tests/conftest.py` give every test
an empty `HOME` and no user or system Git config; use them.

## Rules for changes

- **Read-only stays read-only.** `repo-ledger` must never write inside a
  repository it inspects or run code a repository supplies. A change that runs a
  new Git command needs a test showing the repository is byte-for-byte unchanged
  afterwards (see `test_inventory_writes_nothing_inside_the_repository`).
- **Receipts are a contract.** If you add or rename a field, update the schema in
  `schemas/` in the same change; `tests/test_schemas.py` will fail otherwise.
- **Bug fixes start with a failing test.**
- **No new runtime dependencies** without discussion in an issue first.
- **Catalog entries** come from the project's own repository: copy its
  description, license and default branch, then run `python3 tests/catalog_check.py`.

## A good first contribution

Run `repo-ledger inventory --scan` on a folder of your own repositories. If
anything is miscounted, open an issue with the redacted `--json` receipt for that
one repository and the `git` commands that reproduce its state.
