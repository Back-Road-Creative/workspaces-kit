# Security

## Reporting a vulnerability

Please report security problems privately through GitHub: open the repository's
**Security** tab and choose **Report a vulnerability**. Do not open a public
issue for a security problem.

Include the tool version (`repo-ledger --version`), your Git and Python
versions, and the smallest set of steps that shows the problem. Remove any real
paths, remote URLs, usernames and tokens from what you send.

## What counts

The tools promise to be read-only and offline. These are in scope:

- `repo-ledger` writing anything inside an inspected repository.
- `repo-ledger` running code or hooks a repository's config or contents supply.
- A receipt leaking a credential, for example a token inside a remote URL.
- `repo-ledger provenance` importing the module it was asked only to locate.

Known limits are listed in `tools/repo-ledger/README.md`, for example that an
interpreter's own startup hooks run when it is probed.
