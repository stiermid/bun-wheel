# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the hatch build hook helpers (mocked, no network)."""

import hashlib
import json
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

pytest.importorskip("hatchling")

import hatch_build


@pytest.fixture
def license_snapshot(tmp_path):
    license_dir = tmp_path / "LICENSES"
    license_dir.mkdir()
    files = {}
    for name in (
        "Bun-LICENSE.md",
        "MIT.txt",
        "LGPL-2.1-or-later.txt",
        "LicenseRef-Bun.txt",
    ):
        data = f"fixture notice for {name}\n".encode()
        (license_dir / name).write_bytes(data)
        files[name] = hashlib.sha256(data).hexdigest()
    (license_dir / "bun.json").write_text(
        json.dumps({"version": "1.4.2", "files": files}), encoding="utf-8"
    )
    return tmp_path


def test_verify_bun_licenses_matches_snapshot(license_snapshot):
    hatch_build._verify_bun_licenses(license_snapshot, "1.4.2")


def test_verify_bun_licenses_rejects_stale_version(license_snapshot):
    with pytest.raises(RuntimeError, match="does not match licensing snapshot"):
        hatch_build._verify_bun_licenses(license_snapshot, "1.4.3")


@pytest.mark.parametrize(
    "manifest", ["{", "[]", "null", "{}", '{"version": "1.4.2", "files": []}']
)
def test_verify_bun_licenses_rejects_invalid_manifest(license_snapshot, manifest):
    (license_snapshot / "LICENSES" / "bun.json").write_text(manifest, encoding="utf-8")
    with pytest.raises(RuntimeError, match=r"Missing or invalid LICENSES/bun\.json"):
        hatch_build._verify_bun_licenses(license_snapshot, "1.4.2")


def test_verify_bun_licenses_rejects_missing_manifest(tmp_path):
    with pytest.raises(RuntimeError, match=r"Missing or invalid LICENSES/bun\.json"):
        hatch_build._verify_bun_licenses(tmp_path, "1.4.2")


@pytest.mark.parametrize(
    "name", ["Bun-LICENSE.md", "MIT.txt", "LGPL-2.1-or-later.txt", "LicenseRef-Bun.txt"]
)
def test_verify_bun_licenses_rejects_missing_file(license_snapshot, name):
    (license_snapshot / "LICENSES" / name).unlink()
    with pytest.raises(RuntimeError, match="Missing Bun licensing file or checksum"):
        hatch_build._verify_bun_licenses(license_snapshot, "1.4.2")


def test_verify_bun_licenses_rejects_missing_checksum(license_snapshot):
    path = license_snapshot / "LICENSES" / "bun.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    del manifest["files"]["MIT.txt"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Missing Bun licensing file or checksum"):
        hatch_build._verify_bun_licenses(license_snapshot, "1.4.2")


def test_verify_bun_licenses_rejects_changed_notice(license_snapshot):
    (license_snapshot / "LICENSES" / "Bun-LICENSE.md").write_bytes(b"altered notice")
    with pytest.raises(RuntimeError, match="Bun licensing checksum mismatch"):
        hatch_build._verify_bun_licenses(license_snapshot, "1.4.2")


@pytest.fixture
def additional_license_snapshot(license_snapshot):
    directory = license_snapshot / "LICENSES"
    data = b"Additional component copyright and license notice\n"
    (directory / "component-BSD.txt").write_bytes(data)
    path = directory / "bun.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"]["component-BSD.txt"] = hashlib.sha256(data).hexdigest()
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return license_snapshot


def test_verify_bun_licenses_checks_additional_notice(additional_license_snapshot):
    hatch_build._verify_bun_licenses(additional_license_snapshot, "1.4.2")


def test_verify_bun_licenses_rejects_missing_additional_notice(
    additional_license_snapshot,
):
    (additional_license_snapshot / "LICENSES" / "component-BSD.txt").unlink()
    with pytest.raises(RuntimeError, match="Missing Bun licensing file or checksum"):
        hatch_build._verify_bun_licenses(additional_license_snapshot, "1.4.2")


def test_verify_bun_licenses_rejects_changed_additional_notice(
    additional_license_snapshot,
):
    (additional_license_snapshot / "LICENSES" / "component-BSD.txt").write_bytes(
        b"altered"
    )
    with pytest.raises(RuntimeError, match="Bun licensing checksum mismatch"):
        hatch_build._verify_bun_licenses(additional_license_snapshot, "1.4.2")


@pytest.mark.parametrize("checksum", [None, 0, {}, [], "bad", "z" * 64])
def test_verify_bun_licenses_rejects_invalid_checksum(
    additional_license_snapshot, checksum
):
    path = additional_license_snapshot / "LICENSES" / "bun.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"]["component-BSD.txt"] = checksum
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Invalid Bun licensing checksum"):
        hatch_build._verify_bun_licenses(additional_license_snapshot, "1.4.2")


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".hidden.txt",
        "../outside.txt",
        "/absolute.txt",
        "subdir/file.txt",
        r"subdir\file.txt",
        "C:notice.txt",
        "notice\n.txt",
        "bun.json",
    ],
)
def test_verify_bun_licenses_rejects_unsafe_manifest_filename(license_snapshot, name):
    path = license_snapshot / "LICENSES" / "bun.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"][name] = "a" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Invalid Bun licensing filename"):
        hatch_build._verify_bun_licenses(license_snapshot, "1.4.2")


@pytest.mark.parametrize(
    ("machine", "expected"),
    [
        ("x86_64", "x86_64"),
        ("amd64", "x86_64"),
        ("aarch64", "aarch64"),
        ("arm64", "aarch64"),
    ],
)
def test_normalize_arch_valid(machine, expected):
    assert hatch_build._normalize_arch(machine) == expected


@pytest.mark.parametrize("machine", ["i686", "riscv64", "win32", ""])
def test_normalize_arch_invalid(machine):
    with pytest.raises(RuntimeError, match="Unsupported architecture"):
        hatch_build._normalize_arch(machine)


def test_target_machine_last_segment(monkeypatch):
    monkeypatch.delenv("_PYTHON_HOST_PLATFORM", raising=False)
    with patch("sysconfig.get_platform", return_value="linux-x86_64"):
        assert hatch_build._target_machine() == "x86_64"


def test_target_machine_host_platform_env_precedence(monkeypatch):
    monkeypatch.setenv("_PYTHON_HOST_PLATFORM", "macosx-14.0-arm64")
    with patch("sysconfig.get_platform", return_value="macos-13.0-x86_64"):
        assert hatch_build._target_machine() == "arm64"


def test_target_machine_win32_raises(monkeypatch):
    monkeypatch.delenv("_PYTHON_HOST_PLATFORM", raising=False)
    with patch("sysconfig.get_platform", return_value="win32"):
        with pytest.raises(RuntimeError, match="Unsupported architecture"):
            hatch_build._target_machine()


@pytest.mark.parametrize(
    ("host_platform", "expected"),
    [
        ("linux-x86_64", "linux"),
        ("linux-aarch64", "linux"),
        ("manylinux_2_17_x86_64", "linux"),
        ("musllinux_1_2_aarch64", "linux"),
        ("macosx-14.0-arm64", "darwin"),
        ("macosx-10.9-x86_64", "darwin"),
        ("darwin-22.0-arm64", "darwin"),
        ("win-amd64", "win32"),
        ("win-arm64", "win32"),
        ("win32", "win32"),
        ("mingw_x86_64", "win32"),
    ],
)
def test_target_system_from_get_platform(monkeypatch, host_platform, expected):
    monkeypatch.delenv("_PYTHON_HOST_PLATFORM", raising=False)
    with patch("sysconfig.get_platform", return_value=host_platform):
        assert hatch_build._target_system() == expected


def test_target_system_host_platform_env_precedence(monkeypatch):
    monkeypatch.setenv("_PYTHON_HOST_PLATFORM", "macosx-14.0-arm64")
    with patch("sysconfig.get_platform", return_value="linux-x86_64"):
        assert hatch_build._target_system() == "darwin"


def test_target_system_unsupported(monkeypatch):
    monkeypatch.delenv("_PYTHON_HOST_PLATFORM", raising=False)
    with patch("sysconfig.get_platform", return_value="freebsd-14.0-amd64"):
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            hatch_build._target_system()


def test_ensure_native_build_match(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    hatch_build._ensure_native_build("linux")


def test_ensure_native_build_mismatch(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="Cross-OS build not supported"):
        hatch_build._ensure_native_build("darwin")


@pytest.mark.parametrize(
    ("platform", "machine", "musl", "expected"),
    [
        ("linux", "x86_64", False, "manylinux_2_17_x86_64.manylinux2014_x86_64"),
        ("linux", "aarch64", False, "manylinux_2_17_aarch64.manylinux2014_aarch64"),
        ("linux", "x86_64", True, "musllinux_1_2_x86_64"),
        ("linux", "aarch64", True, "musllinux_1_2_aarch64"),
        ("darwin", "aarch64", False, "macosx_11_0_arm64"),
        ("darwin", "x86_64", False, "macosx_10_9_x86_64"),
        ("win32", "x86_64", False, "win_amd64"),
        ("win32", "aarch64", False, "win_arm64"),
    ],
)
def test_wheel_platform_tag_matrix(monkeypatch, platform, machine, musl, expected):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(hatch_build, "_target_system", lambda: platform)
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: machine)
    monkeypatch.setattr(hatch_build, "_is_musl", lambda: musl)
    assert hatch_build._wheel_platform_tag() == expected


def test_wheel_platform_tag_unsupported(monkeypatch):
    monkeypatch.setattr(sys, "platform", "freebsd")
    monkeypatch.setattr(hatch_build, "_target_system", lambda: "freebsd")
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: "x86_64")
    with pytest.raises(RuntimeError, match="Unsupported platform"):
        hatch_build._wheel_platform_tag()


def test_wheel_platform_tag_cross_os_fails(monkeypatch):
    # Target says darwin but the build host is linux: must fail fast
    # instead of bundling the wrong asset.
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(hatch_build, "_target_system", lambda: "darwin")
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: "aarch64")
    with pytest.raises(RuntimeError, match="Cross-OS build not supported"):
        hatch_build._wheel_platform_tag()


@pytest.mark.parametrize(
    ("platform", "machine", "musl", "expected"),
    [
        ("linux", "x86_64", False, "bun-linux-x64"),
        ("linux", "x86_64", True, "bun-linux-x64-musl"),
        ("linux", "aarch64", False, "bun-linux-aarch64"),
        ("linux", "aarch64", True, "bun-linux-aarch64-musl"),
        ("darwin", "aarch64", False, "bun-darwin-aarch64"),
        ("darwin", "x86_64", False, "bun-darwin-x64"),
        ("win32", "x86_64", False, "bun-windows-x64"),
        ("win32", "aarch64", False, "bun-windows-aarch64"),
    ],
)
def test_bun_platform_matrix(monkeypatch, platform, machine, musl, expected):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(hatch_build, "_target_system", lambda: platform)
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: machine)
    monkeypatch.setattr(hatch_build, "_is_musl", lambda: musl)
    assert hatch_build._bun_platform() == expected


def test_bun_platform_unsupported(monkeypatch):
    monkeypatch.setattr(sys, "platform", "freebsd")
    monkeypatch.setattr(hatch_build, "_target_system", lambda: "freebsd")
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: "x86_64")
    with pytest.raises(RuntimeError, match="Unsupported platform"):
        hatch_build._bun_platform()


def test_bun_platform_cross_os_fails(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(hatch_build, "_target_system", lambda: "win32")
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: "x86_64")
    with pytest.raises(RuntimeError, match="Cross-OS build not supported"):
        hatch_build._bun_platform()


def test_is_musl_via_ld_so_pattern():
    with patch("hatch_build.glob", return_value=["/lib/ld-musl-x86_64.so.1"]):
        assert hatch_build._is_musl() is True


def test_is_musl_via_ldd_output():
    completed = MagicMock(stdout="", stderr="musl libc (x86_64) version 1.2.3")
    with (
        patch("hatch_build.glob", return_value=[]),
        patch("hatch_build.subprocess.run", return_value=completed),
    ):
        assert hatch_build._is_musl() is True


def test_is_musl_ldd_missing():
    with (
        patch("hatch_build.glob", return_value=[]),
        patch("hatch_build.subprocess.run", side_effect=OSError("no ldd")),
    ):
        assert hatch_build._is_musl() is False


def _fake_urlopen(content: bytes):
    response = MagicMock()
    response.read.return_value = content
    opener = MagicMock()
    opener.__enter__.return_value = response
    return opener


def test_verify_checksum_match(tmp_path):
    payload = b"fake-zip-payload"
    zip_path = tmp_path / "bun-linux-x64.zip"
    zip_path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    shasums = f"{digest}  bun-linux-x64.zip\n".encode()
    with patch(
        "hatch_build.urllib.request.urlopen", return_value=_fake_urlopen(shasums)
    ):
        hatch_build.CustomBuildHook._verify_checksum(
            None, zip_path, "bun-linux-x64.zip", "https://example/SHASUMS256.txt"
        )


def test_verify_checksum_mismatch(tmp_path):
    zip_path = tmp_path / "bun-linux-x64.zip"
    zip_path.write_bytes(b"tampered")
    shasums = ("0" * 64 + "  bun-linux-x64.zip\n").encode()
    with patch(
        "hatch_build.urllib.request.urlopen", return_value=_fake_urlopen(shasums)
    ):
        with pytest.raises(RuntimeError, match="Checksum mismatch"):
            hatch_build.CustomBuildHook._verify_checksum(
                None, zip_path, "bun-linux-x64.zip", "https://example/SHASUMS256.txt"
            )


def test_verify_checksum_missing_entry(tmp_path):
    zip_path = tmp_path / "bun-linux-x64.zip"
    zip_path.write_bytes(b"payload")
    shasums = ("ab" * 32 + "  other-file.zip\n").encode()
    with patch(
        "hatch_build.urllib.request.urlopen", return_value=_fake_urlopen(shasums)
    ):
        with pytest.raises(RuntimeError, match="No checksum found"):
            hatch_build.CustomBuildHook._verify_checksum(
                None, zip_path, "bun-linux-x64.zip", "https://example/SHASUMS256.txt"
            )


@contextmanager
def _hook_at(root):
    hook = hatch_build.CustomBuildHook.__new__(hatch_build.CustomBuildHook)
    with patch.object(
        hatch_build.CustomBuildHook, "root", new_callable=PropertyMock
    ) as mock_root:
        mock_root.return_value = str(root)
        yield hook


def test_initialize_rejects_stale_licenses_before_network(license_snapshot):
    with (
        _hook_at(license_snapshot) as hook,
        patch.object(
            hatch_build.CustomBuildHook, "metadata", new_callable=PropertyMock
        ) as metadata,
        patch("hatch_build.urllib.request.urlopen") as fetch,
    ):
        metadata.return_value.version = "1.4.3"
        with pytest.raises(RuntimeError, match="does not match licensing snapshot"):
            hook.initialize("standard", {"force_include": {}})
        fetch.assert_not_called()
    assert not (license_snapshot / "src").exists()


def test_initialize_rejects_changed_additional_notice_before_network(
    additional_license_snapshot,
):
    (additional_license_snapshot / "LICENSES" / "component-BSD.txt").write_bytes(
        b"altered"
    )
    with (
        _hook_at(additional_license_snapshot) as hook,
        patch.object(
            hatch_build.CustomBuildHook, "metadata", new_callable=PropertyMock
        ) as metadata,
        patch("hatch_build.urllib.request.urlopen") as fetch,
    ):
        metadata.return_value.version = "1.4.2"
        with pytest.raises(RuntimeError, match="Bun licensing checksum mismatch"):
            hook.initialize("standard", {"force_include": {}})
        fetch.assert_not_called()
    assert not (additional_license_snapshot / "src").exists()


@pytest.mark.parametrize("version", ["1.4.2", "1.4.2.post1"])
def test_initialize_checks_base_bun_version(license_snapshot, version):
    with (
        _hook_at(license_snapshot) as hook,
        patch.object(
            hatch_build.CustomBuildHook, "metadata", new_callable=PropertyMock
        ) as metadata,
        patch(
            "hatch_build._verify_bun_licenses", wraps=hatch_build._verify_bun_licenses
        ) as verify,
        patch(
            "hatch_build._bun_platform", side_effect=RuntimeError("stop after check")
        ),
    ):
        metadata.return_value.version = version
        with pytest.raises(RuntimeError, match="stop after check"):
            hook.initialize("standard", {"force_include": {}})
        verify.assert_called_once_with(license_snapshot, "1.4.2")


def test_clean_removes_staged_bin_dir(tmp_path):
    bin_dir = tmp_path / "src" / "bun_wheel" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "bun").write_bytes(b"fake")
    with _hook_at(tmp_path) as hook:
        hook.clean([])
    assert not bin_dir.exists()


def test_clean_missing_bin_dir_ok(tmp_path):
    with _hook_at(tmp_path) as hook:
        hook.clean([])
