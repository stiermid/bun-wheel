# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for the PR-only Bun release updater."""

import subprocess
import sys
from copy import deepcopy
from unittest.mock import patch

import pytest

# The updater uses stdlib tomllib; runtime support still starts at Python 3.10.
if sys.version_info < (3, 11):
    pytest.skip("The updater requires Python 3.11+", allow_module_level=True)

from scripts import update_bun


@pytest.fixture
def release():
    return {
        "tag_name": "bun-v1.4.3",
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": name}
            for name in sorted(update_bun.REQUIRED_ASSETS | {"SHASUMS256.txt"})
        ],
    }


@pytest.mark.parametrize(
    ("current", "new", "expected"),
    [
        ("1.4.2", "1.4.3", "1.4.3"),
        ("1.4.9", "1.4.10", "1.4.10"),
        ("1.9.9", "1.10.0", "1.10.0"),
        ("1.4.3", "1.4.3", None),
        ("1.4.4", "1.4.3", None),
        ("1.4.3.post1", "1.4.3", None),
        ("1.4.2.post1", "1.4.3", "1.4.3"),
    ],
)
def test_select_update_compares_versions(release, current, new, expected):
    release["tag_name"] = f"bun-v{new}"
    assert update_bun.select_update(release, current) == expected


@pytest.mark.parametrize("flag", ["draft", "prerelease"])
def test_select_update_ignores_unstable_releases(release, flag):
    release[flag] = True
    assert update_bun.select_update(release, "1.4.2") is None


@pytest.mark.parametrize(
    "tag", ["canary", "bun-v1.4.3-canary.1", "bun-v1.4.3-rc.1", "v1.4.3", "bun-v01.4.3"]
)
def test_select_update_rejects_nonstable_tags(release, tag):
    release["tag_name"] = tag
    assert update_bun.select_update(release, "1.4.2") is None


@pytest.mark.parametrize(
    "missing", sorted(update_bun.REQUIRED_ASSETS | {"SHASUMS256.txt"})
)
def test_select_update_waits_for_every_asset(release, missing):
    incomplete = deepcopy(release)
    incomplete["assets"] = [a for a in release["assets"] if a["name"] != missing]
    assert update_bun.select_update(incomplete, "1.4.2") is None


@pytest.fixture
def manifest():
    return "\n".join(
        f"{'a' * 64}  {name}" for name in sorted(update_bun.REQUIRED_ASSETS)
    )


def test_verify_manifest_accepts_complete_checksums(manifest):
    update_bun.verify_manifest(manifest + "\nextra upstream asset\n")


def test_verify_manifest_rejects_missing_checksum(manifest):
    with pytest.raises(ValueError, match="Missing checksums"):
        update_bun.verify_manifest("\n".join(manifest.splitlines()[1:]))


def test_verify_manifest_rejects_malformed_checksum(manifest):
    with pytest.raises(ValueError, match="Invalid or duplicate checksum"):
        update_bun.verify_manifest(manifest.replace("a" * 64, "bad", 1))


def test_verify_manifest_rejects_duplicate_checksum(manifest):
    with pytest.raises(ValueError, match="Invalid or duplicate checksum"):
        update_bun.verify_manifest(manifest + "\n" + manifest.splitlines()[0])


def test_replace_project_version_preserves_other_sections():
    text = (
        '[tool.example]\nversion = "1.4.2"\n\n'
        "[project]\nname = 'bun-wheel'\nversion = '1.4.2' # Bun version\n\n"
        '[other]\nversion = "1.4.2"\n'
    )
    assert update_bun.replace_project_version(text, "1.4.3") == text.replace(
        "version = '1.4.2'", "version = '1.4.3'"
    )


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.4.2"\n')
    (tmp_path / "uv.lock").write_text("version = 1\n# original lock\n")
    return tmp_path


def test_update_project_relocks_without_dependency_upgrades(project):
    with patch.object(update_bun.subprocess, "run") as run:
        update_bun.update_project(project, "1.4.3")
    run.assert_called_once_with(["uv", "lock"], cwd=project, check=True)
    assert 'version = "1.4.3"' in (project / "pyproject.toml").read_text()


@pytest.mark.parametrize(
    "error", [subprocess.CalledProcessError(1, ["uv", "lock"]), FileNotFoundError("uv")]
)
def test_update_project_restores_files_on_failure(project, error):
    originals = {
        name: (project / name).read_bytes() for name in ["pyproject.toml", "uv.lock"]
    }

    def fail(*args, **kwargs):
        (project / "uv.lock").write_text("partially modified lock")
        raise error

    with patch.object(update_bun.subprocess, "run", side_effect=fail):
        with pytest.raises(type(error)):
            update_bun.update_project(project, "1.4.3")
    for name, original in originals.items():
        assert (project / name).read_bytes() == original


def test_main_noop_does_not_edit_or_fetch_checksums(release, project, monkeypatch):
    release["tag_name"] = "bun-v1.4.2"
    monkeypatch.setattr(sys, "argv", ["update_bun.py"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(update_bun, "update_project") as update,
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        update_bun.main()
    update.assert_not_called()
    fetch.assert_not_called()


def test_main_dry_run_does_not_edit_or_emit_outputs(
    release, manifest, project, monkeypatch, tmp_path
):
    monkeypatch.setattr(sys, "argv", ["update_bun.py", "--dry-run"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(update_bun, "update_project") as update,
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        fetch.return_value.__enter__.return_value.read.return_value = manifest.encode()
        update_bun.main()
    update.assert_not_called()
    assert not output.exists()


def test_main_emits_outputs_after_success(
    release, manifest, project, monkeypatch, tmp_path
):
    monkeypatch.setattr(sys, "argv", ["update_bun.py"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(update_bun, "update_project") as update,
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        fetch.return_value.__enter__.return_value.read.return_value = manifest.encode()
        update_bun.main()
    update.assert_called_once()
    assert output.read_text() == (
        "version=1.4.3\n"
        "release_url=https://github.com/oven-sh/bun/releases/tag/bun-v1.4.3\n"
        "changed=true\n"
    )


def test_main_invalid_manifest_does_not_edit(release, project, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["update_bun.py"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(update_bun, "update_project") as update,
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        fetch.return_value.__enter__.return_value.read.return_value = b""
        with pytest.raises(ValueError, match="Missing checksums"):
            update_bun.main()
    update.assert_not_called()


def test_main_failed_update_does_not_emit_outputs(
    release, manifest, project, monkeypatch, tmp_path
):
    monkeypatch.setattr(sys, "argv", ["update_bun.py"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(update_bun, "update_project", side_effect=OSError("lock failed")),
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        fetch.return_value.__enter__.return_value.read.return_value = manifest.encode()
        with pytest.raises(OSError, match="lock failed"):
            update_bun.main()
    assert not output.exists()
