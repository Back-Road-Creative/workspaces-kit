import json

import pytest

from repo_ledger import cli


def run(capsys, *argv):
    code = cli.main(["inventory", "--json", *argv])
    captured = capsys.readouterr()
    return code, captured


def test_manifest_paths_resolve_relative_to_the_manifest(make_repo, tmp_path, capsys,
                                                         monkeypatch):
    repo = make_repo("app")
    manifest = tmp_path / "config dir" / "repos.toml"
    manifest.parent.mkdir()
    manifest.write_text('version = 1\n[[repo]]\npath = "../parent dir/app"\nname = "My App"\n'
                        '[[repo]]\npath = "~/not-there"\n')
    monkeypatch.chdir(tmp_path / "empty home")
    code, out = run(capsys, "--manifest", str(manifest))
    assert code == 0, out.err
    repos = json.loads(out.out)["repos"]
    assert repos[0]["name"] == "My App" and repos[0]["state"] == "ok"
    assert repos[0]["path"].endswith("parent dir/app")
    assert repos[1]["state"] == "missing"
    assert repos[1]["path"].startswith(str(tmp_path / "empty home"))


@pytest.mark.parametrize("text,message", [
    ("version = 2\n[[repo]]\npath='x'\n", "version must be 1"),
    ("version = 1\n", "at least one"),
    ("version = 1\n[[repo]]\npaht = 'x'\n", "unknown key"),
    ("version = 1\nrepos = []\n", "unknown key"),
    ("version = 1\n[[repo]]\npath = ''\n", "non-empty"),
    ("version = 1\n[[repo]]\npath = 'x'\nname = 3\n", "name must be"),
    ("not toml = = =", "invalid TOML"),
])
def test_bad_manifests_fail_before_any_inspection(tmp_path, capsys, text, message):
    manifest = tmp_path / "m.toml"
    manifest.write_text(text)
    code, out = run(capsys, "--manifest", str(manifest))
    assert code == 2
    assert message in out.err
    assert out.out == ""


def test_missing_manifest_is_a_usage_error(tmp_path, capsys):
    code, out = run(capsys, "--manifest", str(tmp_path / "absent.toml"))
    assert code == 2 and "not found" in out.err
