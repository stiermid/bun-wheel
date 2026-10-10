# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for the PR-only Bun release updater."""

import hashlib
import io
import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from urllib.error import URLError
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


@pytest.fixture
def licensing():
    return update_bun.BunLicensing(
        version="1.4.3",
        source_commit="b" * 40,
        webkit_commit="c" * 40,
        tinycc_commit="d" * 40,
        document=b"Bun itself is MIT-licensed.\n\nFixture upstream licensing information",
    )


@pytest.fixture
def upstream_files(licensing):
    return {
        "package.json": b'{"version": "1.4.3"}',
        "LICENSE.md": licensing.document,
        "scripts/build/deps/webkit.ts": (
            f'export const WEBKIT_VERSION = "{licensing.webkit_commit}";\n'.encode()
        ),
        "scripts/build/deps/tinycc.ts": (
            f'const TINYCC_COMMIT = "{licensing.tinycc_commit}";\n'.encode()
        ),
    }


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
    (tmp_path / "THIRD_PARTY_NOTICES.md").write_bytes(b"Stable explanatory notices\n")
    license_dir = tmp_path / "LICENSES"
    license_dir.mkdir()
    files = {}
    for name in (
        "Bun-LICENSE.md",
        "MIT.txt",
        "LGPL-2.1-or-later.txt",
        "LicenseRef-Bun.txt",
    ):
        data = f"Retained fixture for {name}\n".encode()
        (license_dir / name).write_bytes(data)
        files[name] = hashlib.sha256(data).hexdigest()
    (license_dir / "bun.json").write_text(
        json.dumps({"version": "1.4.2", "files": files}), encoding="utf-8"
    )
    return tmp_path


def _project_bytes(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_update_project_relocks_without_dependency_upgrades(project, licensing):
    originals = _project_bytes(project)
    with patch.object(update_bun.subprocess, "run") as run:
        update_bun.update_project(project, "1.4.3", licensing)
    run.assert_called_once_with(["uv", "lock"], cwd=project, check=True)
    assert 'version = "1.4.3"' in (project / "pyproject.toml").read_text()
    updates = update_bun.licensing_updates(project, licensing)
    for name, data in updates.items():
        assert (project / name).read_bytes() == data
    for name in (
        "THIRD_PARTY_NOTICES.md",
        "LICENSES/LicenseRef-Bun.txt",
        "LICENSES/MIT.txt",
        "LICENSES/LGPL-2.1-or-later.txt",
    ):
        assert (project / name).read_bytes() == originals[name]


@pytest.mark.parametrize(
    "error", [subprocess.CalledProcessError(1, ["uv", "lock"]), FileNotFoundError("uv")]
)
def test_update_project_restores_files_on_failure(project, licensing, error):
    originals = _project_bytes(project)

    def fail(*args, **kwargs):
        (project / "uv.lock").write_text("partially modified lock")
        raise error

    with patch.object(update_bun.subprocess, "run", side_effect=fail):
        with pytest.raises(type(error)):
            update_bun.update_project(project, "1.4.3", licensing)
    assert _project_bytes(project) == originals


def test_main_noop_does_not_edit_or_fetch_checksums(release, project, monkeypatch):
    release["tag_name"] = "bun-v1.4.2"
    monkeypatch.setattr(sys, "argv", ["update_bun.py"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(update_bun, "update_project") as update,
        patch.object(update_bun, "fetch_licensing") as fetch_licenses,
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        update_bun.main()
    update.assert_not_called()
    fetch_licenses.assert_not_called()
    fetch.assert_not_called()


def test_main_dry_run_does_not_edit_or_emit_outputs(
    release, manifest, project, licensing, monkeypatch, tmp_path
):
    monkeypatch.setattr(sys, "argv", ["update_bun.py", "--dry-run"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    originals = _project_bytes(project)
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(update_bun, "update_project") as update,
        patch.object(update_bun, "fetch_licensing", return_value=licensing) as licenses,
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        fetch.return_value.__enter__.return_value.read.return_value = manifest.encode()
        update_bun.main()
    update.assert_not_called()
    licenses.assert_called_once_with("1.4.3")
    assert not output.exists()
    assert _project_bytes(project) == originals


def test_main_emits_outputs_after_success(
    release, manifest, project, licensing, monkeypatch, tmp_path
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
        patch.object(update_bun, "fetch_licensing", return_value=licensing),
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        fetch.return_value.__enter__.return_value.read.return_value = manifest.encode()
        update_bun.main()
    update.assert_called_once_with(project, "1.4.3", licensing)
    assert output.read_text() == (
        "version=1.4.3\n"
        "release_url=https://github.com/oven-sh/bun/releases/tag/bun-v1.4.3\n"
        f"source_commit={licensing.source_commit}\n"
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
        patch.object(update_bun, "fetch_licensing") as licenses,
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        fetch.return_value.__enter__.return_value.read.return_value = b""
        with pytest.raises(ValueError, match="Missing checksums"):
            update_bun.main()
    update.assert_not_called()
    licenses.assert_not_called()


def test_main_failed_update_does_not_emit_outputs(
    release, manifest, project, licensing, monkeypatch, tmp_path
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
        patch.object(update_bun, "fetch_licensing", return_value=licensing),
        patch.object(update_bun.urllib.request, "urlopen") as fetch,
    ):
        fetch.return_value.__enter__.return_value.read.return_value = manifest.encode()
        with pytest.raises(OSError, match="lock failed"):
            update_bun.main()
    assert not output.exists()


def _source_responses(licensing, upstream_files):
    responses = {
        f"{update_bun.API_URL}/commits/bun-v{licensing.version}": json.dumps(
            {"sha": licensing.source_commit}
        ).encode()
    }
    responses.update(
        {
            f"{update_bun.RAW_URL}/{licensing.source_commit}/{name}": data
            for name, data in upstream_files.items()
        }
    )
    return responses


def _urlopen(responses, requests):
    def fetch(request, timeout):
        requests.append(request)
        url = request.full_url if hasattr(request, "full_url") else request
        assert timeout == 30
        assert url in responses, f"Unexpected network request: {url}"
        data = responses[url]
        if isinstance(data, Exception):
            raise data
        return io.BytesIO(data)

    return fetch


@pytest.mark.parametrize("authenticated", [False, True])
def test_fetch_licensing_pins_every_source_request(
    licensing, upstream_files, monkeypatch, authenticated
):
    if authenticated:
        monkeypatch.setenv("GH_TOKEN", "fixture-token")
    else:
        monkeypatch.delenv("GH_TOKEN", raising=False)
    requests = []
    with patch.object(
        update_bun.urllib.request,
        "urlopen",
        side_effect=_urlopen(_source_responses(licensing, upstream_files), requests),
    ):
        assert update_bun.fetch_licensing("1.4.3") == licensing
    assert len(requests) == 5
    assert requests[0].full_url == f"{update_bun.API_URL}/commits/bun-v1.4.3"
    assert requests[0].get_header("Authorization") == (
        "Bearer fixture-token" if authenticated else None
    )
    # API credentials are never passed to raw-content requests.
    assert all(isinstance(request, str) for request in requests[1:])
    assert all(
        url.startswith(f"{update_bun.RAW_URL}/{licensing.source_commit}/")
        for url in requests[1:]
    )


def test_fetch_licensing_ignores_commented_dependency_revisions(
    licensing, upstream_files
):
    upstream_files["scripts/build/deps/webkit.ts"] = (
        f'/* Old revision:\nexport const WEBKIT_VERSION = "{"a" * 40}";\n*/\n'
        f'export const WEBKIT_VERSION: string = "{licensing.webkit_commit}";\n'
    ).encode()
    upstream_files["scripts/build/deps/tinycc.ts"] = (
        f'/* Old revision:\nconst TINYCC_COMMIT = "{"a" * 40}";\n*/\n'
        f'const TINYCC_COMMIT = "{licensing.tinycc_commit}";\n'
    ).encode()
    with patch.object(
        update_bun.urllib.request,
        "urlopen",
        side_effect=_urlopen(_source_responses(licensing, upstream_files), []),
    ):
        assert update_bun.fetch_licensing("1.4.3") == licensing


@pytest.mark.parametrize("sha", [None, "main", "a" * 39, "z" * 40, "a" * 40 + "/x"])
def test_fetch_licensing_rejects_unresolved_release_sha(sha):
    with (
        patch.object(update_bun, "fetch_github_json", return_value={"sha": sha}),
        patch.object(update_bun, "fetch_source_file") as source,
    ):
        with pytest.raises(ValueError, match="immutable commit"):
            update_bun.fetch_licensing("1.4.3")
        source.assert_not_called()


@pytest.mark.parametrize("version", ["canary", "1.4.3.post1", "01.4.3", "1.4.3/other"])
def test_fetch_licensing_rejects_nonstable_version(version):
    with patch.object(update_bun, "fetch_github_json") as fetch:
        with pytest.raises(ValueError, match="stable Bun version"):
            update_bun.fetch_licensing(version)
        fetch.assert_not_called()


@pytest.mark.parametrize("package", [b"{}", b"[]", b'{"version": "1.4.2"}'])
def test_fetch_licensing_rejects_source_version_mismatch(licensing, package):
    with (
        patch.object(
            update_bun,
            "fetch_github_json",
            return_value={"sha": licensing.source_commit},
        ),
        patch.object(update_bun, "fetch_source_file", return_value=package) as fetch,
    ):
        with pytest.raises(ValueError, match="does not match the release version"):
            update_bun.fetch_licensing("1.4.3")
        fetch.assert_called_once_with(licensing.source_commit, "package.json")


@pytest.mark.parametrize(
    "document", [b"", b"Bun is now licensed under different terms.", b"\xff"]
)
def test_fetch_licensing_rejects_unknown_license_declaration(
    licensing, upstream_files, document
):
    upstream_files["LICENSE.md"] = document
    with patch.object(
        update_bun.urllib.request,
        "urlopen",
        side_effect=_urlopen(_source_responses(licensing, upstream_files), []),
    ):
        with pytest.raises(ValueError):
            update_bun.fetch_licensing("1.4.3")


@pytest.mark.parametrize(
    "declaration",
    [
        'export const WEBKIT_VERSION = "{sha}";',
        "  const WEBKIT_VERSION = '{sha}' // source revision",
        'export const WEBKIT_VERSION = "{sha}";\r\n',
        'export const WEBKIT_VERSION: string = "{sha}";',
        'const WEBKIT_VERSION /* inline comment */ = "{sha}"; /* tail comment */',
    ],
)
def test_extract_commit_accepts_literal_revision(declaration):
    assert (
        update_bun.extract_commit(declaration.format(sha="a" * 40), "WEBKIT_VERSION")
        == "a" * 40
    )


@pytest.mark.parametrize(
    "text",
    [
        "// WEBKIT_VERSION was removed",
        'const WEBKIT_VERSION = "canary";',
        'const WEBKIT_VERSION = "abcd";',
        "const WEBKIT_VERSION = computeVersion();",
        f'let WEBKIT_VERSION = "{"a" * 40}";',
        f'var WEBKIT_VERSION = "{"a" * 40}";',
        f'export declare const WEBKIT_VERSION = "{"a" * 40}";',
        f'const WEBKIT_VERSION: CustomType = "{"a" * 40}";',
        f'const WEBKIT_VERSION = "{"a" * 40}" + suffix;',
        f'const WEBKIT_VERSION = "{"a" * 40}";\nconst WEBKIT_VERSION = "{"b" * 40}";',
    ],
)
def test_extract_commit_rejects_unknown_or_ambiguous_layout(text):
    with pytest.raises(ValueError, match="review"):
        update_bun.extract_commit(text, "WEBKIT_VERSION")


def test_extract_commit_ignores_commented_out_declarations():
    old = "a" * 40
    active = "b" * 40
    text = (
        f'/* Old configuration:\nconst WEBKIT_VERSION = "{old}";\n*/\n'
        f'// const WEBKIT_VERSION = "{old}";\n'
        f'export const WEBKIT_VERSION: string = "{active}";\n'
    )
    assert update_bun.extract_commit(text, "WEBKIT_VERSION") == active


@pytest.mark.parametrize("quote", ["'", '"', "`"])
def test_extract_commit_ignores_declarations_inside_strings(quote):
    old = "a" * 40
    active = "b" * 40
    escaped_quote = '\\"' if quote == '"' else '"'
    # A line continuation makes the quoted strings valid multiline JS strings.
    continuation = "" if quote == "`" else "\\"
    text = (
        f"const example = {quote}{continuation}\n"
        f"const WEBKIT_VERSION = {escaped_quote}{old}{escaped_quote};{continuation}\n"
        f"{quote};\n"
        f'export const WEBKIT_VERSION = "{active}";\n'
    )
    assert update_bun.extract_commit(text, "WEBKIT_VERSION") == active


def test_extract_commit_preserves_comment_markers_inside_strings():
    active = "b" * 40
    text = (
        'const url = "https://example.test/*not-a-comment*/";\n'
        'const description = "/*";\n'
        f'const WEBKIT_VERSION = "{active}";\n'
    )
    assert update_bun.extract_commit(text, "WEBKIT_VERSION") == active


def test_extract_commit_ignores_comments_and_strings_without_active_declaration():
    text = (
        f'/*\nconst WEBKIT_VERSION = "{"a" * 40}";\n*/\n'
        f'const example = `\nconst WEBKIT_VERSION = "{"b" * 40}";\n`;\n'
    )
    with pytest.raises(ValueError, match="exactly one"):
        update_bun.extract_commit(text, "WEBKIT_VERSION")


def test_extract_commit_rejects_unsupported_active_declaration_after_comment():
    text = (
        f'/*\nconst WEBKIT_VERSION = "{"a" * 40}";\n*/\n'
        f'export const WEBKIT_VERSION: CustomType = "{"b" * 40}";\n'
    )
    with pytest.raises(ValueError, match="immutable commit"):
        update_bun.extract_commit(text, "WEBKIT_VERSION")


@pytest.mark.parametrize(
    "tail",
    [
        "/* unterminated comment",
        'const broken = "unterminated',
        "const broken = 'unterminated",
        "const broken = `unterminated",
        'const broken = "trailing escape\\',
    ],
)
def test_extract_commit_rejects_unterminated_non_code_tokens(tail):
    text = f'const WEBKIT_VERSION = "{"a" * 40}";\n{tail}'
    with pytest.raises(ValueError, match="Unterminated TypeScript token"):
        update_bun.extract_commit(text, "WEBKIT_VERSION")


def test_extract_commit_masks_simple_template_interpolations():
    active = "b" * 40
    text = (
        'const url = `https://${host}/${select("path")}`;\n'
        'const triple = `${config.x64 ? "x86_64" : "arm64"}-linux`;\n'
        "const example = `escaped \\${notAnExpression}`;\n"
        f'const WEBKIT_VERSION = "{active}";\n'
    )
    assert update_bun.extract_commit(text, "WEBKIT_VERSION") == active


def test_extract_commit_rejects_nested_template_interpolations():
    text = (
        "const example = `outer ${`inner\n"
        f'const WEBKIT_VERSION = "{"a" * 40}";\n'
        "`}`;\n"
        f'const WEBKIT_VERSION = "{"b" * 40}";\n'
    )
    with pytest.raises(ValueError, match="Unsupported template interpolation"):
        update_bun.extract_commit(text, "WEBKIT_VERSION")


def test_fetch_github_json_rejects_nonobject_response():
    with patch.object(
        update_bun.urllib.request,
        "urlopen",
        return_value=io.BytesIO(b"[]"),
    ):
        with pytest.raises(ValueError, match="Expected a GitHub API object"):
            update_bun.fetch_github_json(update_bun.RELEASE_API)


def test_fetch_latest_release_uses_shared_api_client(release):
    with patch.object(update_bun, "fetch_github_json", return_value=release) as fetch:
        assert update_bun.fetch_latest_release() == release
    fetch.assert_called_once_with(update_bun.RELEASE_API)


@pytest.mark.parametrize("ending", [b"", b"\n", b"\r\n", b"\n\n"])
def test_licensing_updates_preserves_upstream_bytes(project, licensing, ending):
    document = b"Bun itself is MIT-licensed.\r\nCopyright fixture  " + ending
    licensing = replace(licensing, document=document)
    originals = _project_bytes(project)
    updates = update_bun.licensing_updates(project, licensing)
    snapshot = updates["LICENSES/Bun-LICENSE.md"]
    assert snapshot == (document if ending else document + b"\n")
    manifest = json.loads(updates["LICENSES/bun.json"])
    assert manifest["upstream_license_sha256"] == hashlib.sha256(document).hexdigest()
    assert manifest["files"]["Bun-LICENSE.md"] == hashlib.sha256(snapshot).hexdigest()
    assert manifest["version"] == licensing.version
    assert manifest["source_commit"] == licensing.source_commit
    assert manifest["webkit_commit"] == licensing.webkit_commit
    assert manifest["tinycc_commit"] == licensing.tinycc_commit
    assert manifest["source_url"] == (
        f"https://github.com/oven-sh/bun/tree/{licensing.source_commit}"
    )
    assert manifest["upstream_license_url"] == (
        f"https://github.com/oven-sh/bun/blob/{licensing.source_commit}/LICENSE.md"
    )
    assert _project_bytes(project) == originals


def test_licensing_updates_preserves_additional_component_notices(project, licensing):
    additional = project / "LICENSES" / "component-BSD.txt"
    additional.write_bytes(b"Additional retained component notice\n")
    original = additional.read_bytes()
    with patch.object(update_bun.subprocess, "run"):
        update_bun.update_project(project, "1.4.3", licensing)
    manifest = json.loads((project / "LICENSES" / "bun.json").read_bytes())
    assert manifest["files"][additional.name] == hashlib.sha256(original).hexdigest()
    assert additional.read_bytes() == original


@pytest.mark.parametrize("name", [".DS_Store", ".hidden-notice.txt", ".gitkeep"])
def test_licensing_updates_ignores_hidden_local_files(project, licensing, name):
    hidden = project / "LICENSES" / name
    hidden.write_bytes(b"\xffLocal metadata, not a packaged licensing file")
    originals = _project_bytes(project)
    updates = update_bun.licensing_updates(project, licensing)
    manifest = json.loads(updates["LICENSES/bun.json"])
    assert name not in manifest["files"]
    assert _project_bytes(project) == originals


def test_generated_license_entries_match_packaging_glob(project, licensing):
    pytest.importorskip("hatchling")
    from hatchling.builders.wheel import WheelBuilder

    # Use the project's actual packaging configuration to detect selection drift.
    config = Path(__file__).resolve().parents[1] / "pyproject.toml"
    (project / "pyproject.toml").write_bytes(config.read_bytes())
    directory = project / "LICENSES"
    (directory / ".DS_Store").write_bytes(b"\xffFinder metadata")
    (directory / "component-BSD.txt").write_bytes(b"Additional component notice\n")
    (directory / "unpackaged-directory").mkdir()
    (directory / "unpackaged-directory" / "notice.txt").write_bytes(b"Nested fixture")
    updates = update_bun.licensing_updates(project, licensing)
    manifest = json.loads(updates["LICENSES/bun.json"])
    packaged = {
        name.removeprefix("LICENSES/")
        for name in WheelBuilder(str(project)).metadata.core.license_files
        if name.startswith("LICENSES/") and name != "LICENSES/bun.json"
    }
    assert set(manifest["files"]) == packaged
    assert "component-BSD.txt" in packaged
    assert ".DS_Store" not in packaged
    assert "unpackaged-directory" not in packaged


def test_update_project_rejects_mismatched_licensing_version(project, licensing):
    originals = _project_bytes(project)
    with patch.object(update_bun.subprocess, "run") as run:
        with pytest.raises(ValueError, match="does not match the proposed Bun version"):
            update_bun.update_project(project, "1.4.4", licensing)
        run.assert_not_called()
    assert _project_bytes(project) == originals


def test_update_project_restores_earlier_writes_when_a_write_fails(project, licensing):
    originals = _project_bytes(project)
    write_bytes = Path.write_bytes

    def fail_manifest(path, data):
        if path == project / "LICENSES" / "bun.json":
            raise PermissionError("manifest is read-only")
        return write_bytes(path, data)

    with (
        patch.object(Path, "write_bytes", fail_manifest),
        patch.object(update_bun.subprocess, "run") as run,
    ):
        with pytest.raises(PermissionError, match="manifest is read-only"):
            update_bun.update_project(project, "1.4.3", licensing)
        run.assert_not_called()
    assert _project_bytes(project) == originals


def test_update_project_restores_a_deleted_lock_on_failure(project, licensing):
    originals = _project_bytes(project)

    def fail(*args, **kwargs):
        (project / "uv.lock").unlink()
        raise OSError("lock failed")

    with patch.object(update_bun.subprocess, "run", side_effect=fail):
        with pytest.raises(OSError, match="lock failed"):
            update_bun.update_project(project, "1.4.3", licensing)
    assert _project_bytes(project) == originals


@pytest.mark.parametrize(
    "error", [ValueError("unknown upstream layout"), URLError("offline")]
)
def test_main_licensing_failure_does_not_edit_or_emit_outputs(
    release, manifest, project, monkeypatch, tmp_path, error
):
    monkeypatch.setattr(sys, "argv", ["update_bun.py"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    originals = _project_bytes(project)
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(update_bun, "fetch_licensing", side_effect=error),
        patch.object(update_bun, "update_project") as update,
        patch.object(
            update_bun.urllib.request,
            "urlopen",
            return_value=io.BytesIO(manifest.encode()),
        ),
    ):
        with pytest.raises(type(error)):
            update_bun.main()
        update.assert_not_called()
    assert not output.exists()
    assert _project_bytes(project) == originals


def test_main_refreshes_version_and_licensing_together(
    release, manifest, project, licensing, upstream_files, monkeypatch, tmp_path
):
    monkeypatch.setattr(sys, "argv", ["update_bun.py"])
    monkeypatch.setattr(
        update_bun, "__file__", str(project / "scripts" / "update_bun.py")
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    originals = _project_bytes(project)
    responses = _source_responses(licensing, upstream_files)
    responses[f"{update_bun.RELEASE_URL}/download/bun-v1.4.3/SHASUMS256.txt"] = (
        manifest.encode()
    )
    with (
        patch.object(update_bun, "fetch_latest_release", return_value=release),
        patch.object(
            update_bun.urllib.request, "urlopen", side_effect=_urlopen(responses, [])
        ),
        patch.object(update_bun.subprocess, "run") as run,
    ):
        update_bun.main()
    run.assert_called_once_with(["uv", "lock"], cwd=project, check=True)
    assert 'version = "1.4.3"' in (project / "pyproject.toml").read_text()
    for name, data in update_bun.licensing_updates(project, licensing).items():
        assert (project / name).read_bytes() == data
    assert (project / "THIRD_PARTY_NOTICES.md").read_bytes() == originals[
        "THIRD_PARTY_NOTICES.md"
    ]
    assert (project / "LICENSES" / "LicenseRef-Bun.txt").read_bytes() == originals[
        "LICENSES/LicenseRef-Bun.txt"
    ]
    assert output.read_text() == (
        "version=1.4.3\n"
        "release_url=https://github.com/oven-sh/bun/releases/tag/bun-v1.4.3\n"
        f"source_commit={licensing.source_commit}\n"
        "changed=true\n"
    )
