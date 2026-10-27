"""Validate catalog/projects.toml offline. Exit 0 when valid; print each problem otherwise."""

from __future__ import annotations

import datetime as dt
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "projects.toml"
FIELDS = {"id", "repository", "summary", "license", "default_branch", "checked"}
ID = re.compile(r"[a-z0-9][a-z0-9-]*")
REPO = re.compile(r"https://github\.com/[A-Za-z0-9-]+/([A-Za-z0-9._-]+)")
SPDX = re.compile(r"[A-Za-z0-9.+-]+")


def problems(path: Path = CATALOG) -> list[str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"version", "project"} or data["version"] != 1:
        return [f"{path.name}: top level must be exactly version = 1 and [[project]] tables"]
    found: list[str] = []
    seen: set[str] = set()
    for index, project in enumerate(data["project"], 1):
        where = f"project #{index} ({project.get('id', '?')})"
        if set(project) != FIELDS:
            found.append(f"{where}: fields must be exactly {sorted(FIELDS)}")
            continue
        if not ID.fullmatch(project["id"]):
            found.append(f"{where}: id must be lowercase letters, digits and dashes")
        if project["id"] in seen:
            found.append(f"{where}: duplicate id")
        seen.add(project["id"])
        match = REPO.fullmatch(project["repository"])
        if not match:
            found.append(f"{where}: repository must be https://github.com/<owner>/<repo>")
        elif match[1] != project["id"]:
            found.append(f"{where}: id must equal the repository name")
        if not isinstance(project["summary"], str):
            found.append(f"{where}: summary must be a string")
        if not SPDX.fullmatch(str(project["license"])):
            found.append(f"{where}: license must be an SPDX id or none-declared")
        if not isinstance(project["checked"], dt.date):
            found.append(f"{where}: checked must be a TOML date")
    return found


if __name__ == "__main__":
    issues = problems()
    for issue in issues:
        print(issue)
    sys.exit(1 if issues else 0)
