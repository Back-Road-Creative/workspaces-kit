"""Load a user manifest: an explicit list of repository paths.

    version = 1

    [[repo]]
    path = "products/my-app"     # relative to this file, or absolute, or ~/...
    name = "my-app"              # optional display name

Unknown keys are errors, so a typo cannot silently drop a repository.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_VERSION = 1
_TOP_KEYS = {"version", "repo"}
_REPO_KEYS = {"path", "name"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    path: Path
    name: str | None


def load(manifest: Path) -> list[Entry]:
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ManifestError(f"{manifest}: file not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ManifestError(f"{manifest}: cannot read ({exc.__class__.__name__})") from None
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{manifest}: invalid TOML ({exc})") from None
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise ManifestError(f"{manifest}: unknown key(s) {sorted(unknown)}")
    if data.get("version") != SUPPORTED_VERSION:
        raise ManifestError(f"{manifest}: version must be {SUPPORTED_VERSION}")
    repos = data.get("repo", [])
    if not isinstance(repos, list) or not repos:
        raise ManifestError(f"{manifest}: needs at least one [[repo]] table")
    base = manifest.resolve().parent
    entries = []
    for index, repo in enumerate(repos, 1):
        where = f"{manifest}: [[repo]] #{index}"
        if not isinstance(repo, dict):
            raise ManifestError(f"{where} must be a table")
        bad = set(repo) - _REPO_KEYS
        if bad:
            raise ManifestError(f"{where}: unknown key(s) {sorted(bad)}")
        raw = repo.get("path")
        if not isinstance(raw, str) or not raw.strip():
            raise ManifestError(f"{where}: path must be a non-empty string")
        name = repo.get("name")
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise ManifestError(f"{where}: name must be a non-empty string")
        path = Path(raw).expanduser()
        entries.append(Entry(path if path.is_absolute() else base / path, name))
    return entries
