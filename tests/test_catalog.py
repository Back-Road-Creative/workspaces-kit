import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import catalog_check  # noqa: E402


def test_catalog_is_valid():
    assert catalog_check.problems() == []


def test_checker_rejects_bad_entries(tmp_path):
    bad = tmp_path / "p.toml"
    bad.write_text(
        'version = 1\n[[project]]\nid = "x"\nrepository = "http://example.invalid/x"\n'
        'summary = ""\nlicense = "MIT"\ndefault_branch = "main"\nchecked = 2026-01-01\n'
        '[[project]]\nid = "y"\n'
    )
    issues = catalog_check.problems(bad)
    assert any("repository must be" in i for i in issues)
    assert any("fields must be exactly" in i for i in issues)


def test_checker_rejects_id_repo_mismatch(tmp_path):
    bad = tmp_path / "p.toml"
    bad.write_text(
        'version = 1\n[[project]]\nid = "x"\nrepository = "https://github.com/o/y"\n'
        'summary = ""\nlicense = "MIT"\ndefault_branch = "main"\nchecked = 2026-01-01\n'
    )
    assert any("must equal the repository name" in i for i in catalog_check.problems(bad))
