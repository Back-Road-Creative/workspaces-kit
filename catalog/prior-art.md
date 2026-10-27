# Prior art

Checked 2026-10-27 against each project's own README. Claims below are limited
to what those READMEs say; "not documented" means the README does not mention
it, not that the tool cannot do it.

| Tool | What its README documents | Registry | All branches, stashes, worktrees | Package provenance |
| --- | --- | --- | --- | --- |
| [gita](https://github.com/nosarthur/gita) | Per-repo current branch, ahead/behind colouring, staged, unstaged, untracked and stash markers, last commit message and time; runs git commands across repos | `gita add`, stored in `$XDG_CONFIG_HOME/gita/repos.csv` | Current branch and a stash marker; listing every branch and worktree not documented | Not documented |
| [myrepos](https://myrepos.branchable.com/) (`mr`) | Runs commit, push, status and other commands across many repositories of several VCS types; a `freeze` extension records revisions | `~/.mrconfig` | Not documented | Not documented |
| [mu-repo](https://github.com/fabioz/mu-repo) | "Tool to help working with multiple git repositories" | Config file | Not documented | Not documented |
| [meta](https://github.com/mateodelnorte/meta) | `.meta` JSON listing child repos; `meta git status`, `meta exec` across them | `.meta` file | Not documented | Not documented |
| [repo](https://gerrit.googlesource.com/git-repo/) (Google) | Manages many Git repositories from a manifest; a single Python script | Manifest XML | Not documented in its README | Not documented |

## When to use which

- **Daily status across a known list of repositories:** use gita. It is mature
  and does this well.
- **Running one command in every repository:** gita, myrepos or meta.
- **"What would I lose if this disk died now?"** That is `repo-ledger inventory`:
  commits on no remote across every local branch, stashes, dirty files in every
  linked worktree, missing worktree folders, and repositories under a folder
  that is not itself a repository, with no registry to keep up to date and a
  JSON receipt you can keep.
- **"Which copy of this package does that interpreter run?"** That is
  `repo-ledger provenance`. None of the tools above documents it.
