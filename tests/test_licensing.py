# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: Apache-2.0

"""Offline licensing regressions using real builds and a mocked Bun download."""

import base64
import csv
import hashlib
import io
import json
import shutil
import tarfile
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

import pytest

pytest.importorskip("hatchling")

from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder
from packaging.licenses import canonicalize_license_expression
from packaging.version import Version

REPOSITORY = Path(__file__).resolve().parents[1]
LICENSE_EXPRESSION = "Apache-2.0 AND LicenseRef-Bun"
APACHE_LICENSE_SHA256 = (
    "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
)
BINARY_CONTENT = b"fixture Bun executable; never run this file\n"


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    for name in (
        "pyproject.toml",
        "hatch_build.py",
        "LICENSE",
        "NOTICE",
        "THIRD_PARTY_NOTICES.md",
        "README.md",
        "CONTRIBUTING.md",
    ):
        shutil.copyfile(REPOSITORY / name, root / name)
    for name in ("LICENSES", "src", "scripts", "tests"):
        shutil.copytree(
            REPOSITORY / name,
            root / name,
            ignore=shutil.ignore_patterns("__pycache__", "bin"),
        )
    return root


@pytest.fixture
def downloads(monkeypatch):
    payload = io.BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("upstream/bun", BINARY_CONTENT)
        archive.writestr("upstream/bun.exe", BINARY_CONTENT)
    zip_data = payload.getvalue()
    digest = hashlib.sha256(zip_data).hexdigest()
    urls = []

    def urlopen(url, timeout):
        urls.append(url)
        if url.endswith(".zip"):
            return io.BytesIO(zip_data)
        if url.endswith("/SHASUMS256.txt"):
            asset = Path(urls[-2]).name
            return io.BytesIO(f"{digest}  {asset}\n".encode())
        pytest.fail(f"Unexpected network request: {url}")

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.delenv("_PYTHON_HOST_PLATFORM", raising=False)
    return urls


def _build(builder, root, directory):
    directory.mkdir()
    return Path(next(builder(str(root)).build(directory=str(directory))))


def _sdist_files(path):
    with tarfile.open(path) as archive:
        return {
            member.name.split("/", 1)[1]: archive.extractfile(member).read()
            for member in archive.getmembers()
            if member.isfile()
        }


def _assert_license_files(files, metadata_name, license_prefix, root):
    metadata = BytesParser().parsebytes(files[metadata_name])
    assert metadata["License-Expression"] == LICENSE_EXPRESSION
    assert canonicalize_license_expression(metadata["License-Expression"]) == (
        LICENSE_EXPRESSION
    )
    assert metadata["License"] is None
    assert not any(
        value.startswith("License ::") for value in metadata.get_all("Classifier", [])
    )
    expected = {"LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"} | {
        path.relative_to(root).as_posix() for path in (root / "LICENSES").iterdir()
    }
    license_files = metadata.get_all("License-File", [])
    assert len(license_files) == len(expected)
    assert set(license_files) == expected
    for name in license_files:
        assert files[f"{license_prefix}{name}"] == (root / name).read_bytes()
    assert hashlib.sha256(files[f"{license_prefix}LICENSE"]).hexdigest() == (
        APACHE_LICENSE_SHA256
    )


def _assert_wheel_licenses(path, root):
    with ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    metadata_name = next(name for name in files if name.endswith(".dist-info/METADATA"))
    dist_info = metadata_name.removesuffix("METADATA")
    _assert_license_files(files, metadata_name, f"{dist_info}licenses/", root)
    records = {
        name: (digest, size)
        for name, digest, size in csv.reader(
            io.StringIO(files[f"{dist_info}RECORD"].decode())
        )
    }
    for name, data in files.items():
        if name.startswith(f"{dist_info}licenses/"):
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            assert records[name] == (
                "sha256=" + digest.rstrip(b"=").decode(),
                str(len(data)),
            )
    binaries = [
        data for name, data in files.items() if name.startswith("bun_wheel/bin/")
    ]
    assert binaries == [BINARY_CONTENT]


def test_original_python_files_have_apache_spdx_headers():
    paths = [REPOSITORY / "hatch_build.py"]
    for directory in ("src", "scripts", "tests"):
        paths.extend((REPOSITORY / directory).rglob("*.py"))
    for path in paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("# SPDX-FileCopyrightText:"), path
        assert lines[1] == "# SPDX-License-Identifier: Apache-2.0", path


def test_license_snapshot_provenance_matches_project(project):
    manifest = json.loads(
        (project / "LICENSES" / "bun.json").read_text(encoding="utf-8")
    )
    version = Version(WheelBuilder(str(project)).metadata.version).base_version
    assert manifest["version"] == version
    for key in ("source_commit", "webkit_commit", "tinycc_commit"):
        assert len(manifest[key]) == 40
        assert all(character in "0123456789abcdef" for character in manifest[key])
    assert manifest["release_url"] == (
        f"https://github.com/oven-sh/bun/releases/tag/bun-v{version}"
    )
    assert manifest["source_url"] == (
        f"https://github.com/oven-sh/bun/tree/{manifest['source_commit']}"
    )
    assert manifest["upstream_license_url"] == (
        f"https://github.com/oven-sh/bun/blob/{manifest['source_commit']}/LICENSE.md"
    )
    for component, repository in (("webkit", "WebKit"), ("tinycc", "tinycc")):
        assert manifest[f"{component}_source_url"] == (
            f"https://github.com/oven-sh/{repository}/tree/{manifest[f'{component}_commit']}"
        )
    snapshot = (project / "LICENSES" / "Bun-LICENSE.md").read_bytes()
    # Preserve upstream bytes, allowing only an added final newline.
    assert manifest["upstream_license_sha256"] in {
        hashlib.sha256(snapshot).hexdigest(),
        hashlib.sha256(snapshot.removesuffix(b"\n")).hexdigest(),
    }


def test_explanatory_notices_do_not_duplicate_release_facts(project):
    manifest = json.loads(
        (project / "LICENSES" / "bun.json").read_text(encoding="utf-8")
    )
    for name in ("THIRD_PARTY_NOTICES.md", "LICENSES/LicenseRef-Bun.txt"):
        text = (project / name).read_text(encoding="utf-8")
        assert "bun.json" in text
        assert manifest["version"] not in text
        for key in ("source_commit", "webkit_commit", "tinycc_commit"):
            assert manifest[key] not in text


def test_sdist_retains_licenses_without_binary_or_download(
    project, tmp_path, downloads
):
    bin_dir = project / "src" / "bun_wheel" / "bin"
    bin_dir.mkdir()
    staged_binary = bin_dir / "bun"
    staged_binary.write_bytes(b"pre-existing staged executable")
    path = _build(SdistBuilder, project, tmp_path / "sdist")
    files = _sdist_files(path)
    _assert_license_files(files, "PKG-INFO", "", project)
    assert not any(
        name.startswith(("src/bun_wheel/bin/", "bun_wheel/bin/")) for name in files
    )
    assert "hatch_build.py" in files
    assert "CONTRIBUTING.md" in files
    assert downloads == []
    assert staged_binary.read_bytes() == b"pre-existing staged executable"


@pytest.mark.parametrize("post_release", [False, True])
def test_wheel_retains_licenses_and_record_hashes(
    project, tmp_path, downloads, post_release
):
    version = WheelBuilder(str(project)).metadata.version
    if post_release:
        config = project / "pyproject.toml"
        text = config.read_text(encoding="utf-8")
        text = text.replace(
            f'version = "{version}"',
            f'version = "{Version(version).base_version}.post1"',
            1,
        )
        config.write_text(text, encoding="utf-8")
    path = _build(WheelBuilder, project, tmp_path / "wheel")
    _assert_wheel_licenses(path, project)
    assert len(downloads) == 2
    assert f"/bun-v{Version(version).base_version}/" in downloads[0]
    assert downloads[0].endswith(".zip")
    assert downloads[1].endswith("/SHASUMS256.txt")


def test_wheel_from_sdist_retains_licenses(project, tmp_path, downloads):
    sdist = _build(SdistBuilder, project, tmp_path / "sdist")
    rebuilt_root = tmp_path / "unpacked"
    for name, data in _sdist_files(sdist).items():
        destination = rebuilt_root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    wheel = _build(WheelBuilder, rebuilt_root, tmp_path / "wheel")
    _assert_wheel_licenses(wheel, project)
    assert len(downloads) == 2
