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

## Already landed

So each branch also gets **unlanded commits**: its unique commits whose change
is not already on a remote's default branch (the remote's `HEAD`, else `main`,
else `master`). A commit has landed when `git cherry` finds a commit with the
same patch there, which covers rebase and cherry-pick merges. The whole branch
has landed when one commit there has the same patch as the branch's full diff
from its merge base, which covers a squash merge.

A branch with unique commits and no unlanded ones is listed under
**branches already landed**. Its commits are still counted as unique and the
repository is still at risk, because the match is by patch text, not identity:
confirm with `git cherry -v <default> <branch>` before you delete it. The
check misses a squash that also changed other files, and one whose context
lines changed because the default branch edited the same files first. A local
merge commit never counts as landed.

The check reads each remote's default branch once, back to the common ancestor
of the local branches, so a repository with hundreds of local-only branches and
a long history takes a few times longer to inventory than it did before.

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
