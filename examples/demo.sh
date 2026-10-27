#!/usr/bin/env bash
# Build throwaway repositories and run repo-ledger against them.
# Needs only git and an installed repo-ledger. Touches nothing outside a new temp dir.
set -euo pipefail

work="$(mktemp -d "${TMPDIR:-/tmp}/repo-ledger-demo.XXXXXX")"
trap 'rm -rf -- "$work"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=Demo GIT_AUTHOR_EMAIL=demo@example.invalid
export GIT_COMMITTER_NAME=Demo GIT_COMMITTER_EMAIL=demo@example.invalid

git init -q --bare -b main "$work/origin.git"
app="$work/demo/my app"
mkdir -p "$app" "$work/demo/not a repo"
git -C "$app" init -q -b main
echo hello > "$app/README"
git -C "$app" add README
git -C "$app" commit -q -m "first"
git -C "$app" remote add origin "$work/origin.git"
git -C "$app" push -q origin main
git -C "$app" switch -q -c experiment
echo idea > "$app/idea.txt"
git -C "$app" add idea.txt
git -C "$app" commit -q -m "unpushed idea"
echo wip > "$app/wip.txt"
git -C "$app" stash push -q -u -m "half done"
git -C "$app" worktree add -q "$work/demo/my app review" -b review main

notes="$work/demo/notes"
mkdir -p "$notes"
git -C "$notes" init -q -b main
echo note > "$notes/n.md"
git -C "$notes" add n.md
git -C "$notes" commit -q -m "notes"

echo "== scan a folder that is not itself a repository"
repo-ledger inventory --scan "$work/demo"

echo
echo "== the same repositories from a manifest file"
cp "$(dirname "$0")/manifest.example.toml" "$work/manifest.toml"
repo-ledger inventory --manifest "$work/manifest.toml"

echo
echo "== the same check as a gate (exit 1 means local-only work exists)"
set +e
repo-ledger inventory --check --scan "$work/demo" > /dev/null
echo "exit code: $?"
set -e

echo
echo "== which installed repo-ledger is this interpreter running?"
python3 - <<'PY'
import json, subprocess
out = subprocess.run(["repo-ledger", "provenance", "--distribution", "repo-ledger",
                      "--module", "repo_ledger"], capture_output=True, text=True)
report = json.loads(out.stdout)
print("installed:", report["distribution"]["installed"], "| editable:", report["distribution"]["editable"],
      "| module owned by distribution:", report["module"]["owned_by_distribution"])
PY
