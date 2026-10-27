"""Report which installed distribution a Python environment actually runs.

The probe runs in the target interpreter with -I -B from a neutral cwd, so the
current directory, PYTHONPATH and user site-packages cannot shadow the module.
It reads metadata and module discovery only; the inspected module is never
imported. Provenance URLs are never printed.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import gitcmd

SCHEMA = "repo-ledger.provenance/1"

PROBE = r'''
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
import sys

distribution_name, module_name = sys.argv[1:]
try:
    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError:
        distribution = None
    spec = importlib.util.find_spec(module_name)
    origin = spec.origin if spec else None
    info = {"name": distribution_name, "installed": distribution is not None,
            "version": None, "editable": False, "commit": None}
    owned = False
    if distribution is not None:
        direct = json.loads(distribution.read_text("direct_url.json") or "{}")
        info.update(version=distribution.version,
                    editable=direct.get("dir_info", {}).get("editable", False),
                    commit=direct.get("vcs_info", {}).get("commit_id"))
        if origin:
            resolved = Path(origin).resolve()
            owned = any(Path(distribution.locate_file(entry)).resolve() == resolved
                        for entry in (distribution.files or ()))
    print(json.dumps({"interpreter": sys.executable, "distribution": info,
                      "module": {"name": module_name, "origin": origin,
                                 "owned_by_distribution": owned}}))
except Exception:
    # Never echo provenance URLs, credential-bearing metadata or startup output.
    print(json.dumps({"error": "unable to inspect installed metadata"}))
'''

_MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DIST = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_COMMIT = re.compile(r"[0-9a-f]{40}")


class RequestError(ValueError):
    """The request is invalid; nothing was launched."""


class ProbeError(RuntimeError):
    """The interpreter could not be inspected."""


def validate(python: Path, distribution: str, module: str, expected: str | None,
             timeout: float) -> None:
    if not python.is_absolute() or not python.is_file() or not os.access(python, os.X_OK):
        raise RequestError("--python must name an absolute executable file")
    if not _MODULE.fullmatch(module):
        raise RequestError("--module must be a top-level Python identifier")
    if not _DIST.fullmatch(distribution):
        raise RequestError("--distribution must be a distribution name")
    if expected is not None and not _COMMIT.fullmatch(expected):
        raise RequestError("--expected-commit must be a full lowercase Git commit")
    if not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise RequestError("--timeout must be greater than zero and at most 60 seconds")


def repo_head(repo: Path) -> tuple[str, bool]:
    """(HEAD commit, working tree dirty) for ``repo``."""
    try:
        head = gitcmd.run(repo, "rev-parse", "--verify", "HEAD").strip()
        dirty = bool(gitcmd.run(repo, "status", "--porcelain", "--untracked-files=no").strip())
    except gitcmd.GitError as exc:
        raise RequestError(f"--repo: {gitcmd.classify_error(exc.stderr)}") from None
    return head, dirty


def observe(python: Path, distribution: str, module: str, expected: str | None = None,
            timeout: float = 15) -> dict:
    validate(python, distribution, module, expected, timeout)
    try:
        # Do not resolve the interpreter symlink: that would discard its venv.
        result = subprocess.run(
            [str(python), "-I", "-B", "-c", PROBE, distribution, module],
            cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ProbeError("interpreter probe timed out") from None
    except OSError:
        raise ProbeError("could not launch interpreter") from None
    if result.returncode:
        raise ProbeError("interpreter probe failed")
    try:
        report = json.loads(result.stdout)
        if "error" in report:
            raise ValueError
        dist = report["distribution"]
        mod = report["module"]
        available = bool(dist["installed"] and mod["origin"])
        verified = None if expected is None else bool(
            available and dist["commit"] == expected
            and not dist["editable"] and mod["owned_by_distribution"]
        )
    except (ValueError, KeyError, TypeError):
        raise ProbeError("invalid or unavailable provenance metadata") from None
    report.update(schema=SCHEMA, expected_commit=expected, verified_pin=verified,
                  available=available)
    return report
