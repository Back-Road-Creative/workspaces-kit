# Concepts

## Unique commits

A commit is **unique** when a local branch reaches it and no remote-tracking ref
does: `git rev-list --count --branches --not --remotes`. This is the work a lost
disk takes with it. It is a count of commits, not of branches, so two branches
sharing one unpushed commit count it once in the repository summary.

"No remote-tracking ref" means as of your last fetch. repo-ledger never fetches,
because fetching writes to the repository and needs the network.

Squash and rebase merges inflate this count. When a branch is squash-merged on
the host, its original commits stay unreachable from any remote ref, so a local
copy of that branch still counts as unique even though its changes shipped.
Check such a branch with `git cherry -v <upstream> <branch>`: lines starting
with `-` are already upstream by patch content. Delete the branch once you have
confirmed that; repo-ledger does not do patch-id matching yet.

## Privacy of a receipt

A receipt names local paths, branch names, remote URLs with credentials
removed, and commit hashes. It never contains file contents. Treat it like a
directory listing: fine for your own records, worth a read before you post it.

## At risk

A repository is at risk when it has unique commits, stashes, or dirty paths in
any worktree. A missing worktree folder is reported separately: it holds no
files, but its branch may still carry unique commits.

## Read-only, enforced

Every Git command runs with optional locks off (so `git status` does not rewrite
the index), the fsmonitor hook off (so a repository's config cannot make Git run
a program), no terminal prompts, and the C locale (so messages parse the same
everywhere). The tests compare every file under `.git` before and after an
inventory.

## Refused repositories

Git refuses to open a repository owned by another user unless you trust it with
`safe.directory`. repo-ledger reports such a repository as `refused` with reason
`dubious-ownership` rather than changing your Git config. Decide yourself
whether to trust it.

## Provenance

pip records how a package was installed in `direct_url.json`: whether it was
editable, and for a Git install the commit. `repo-ledger provenance` reads that
record and finds the module's file without importing it, then checks the file
is one the distribution installed. An editable install, or a module file that
some other path provides, fails a pin check even when the recorded commit
matches.
