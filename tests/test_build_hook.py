"""Unit tests for the hatch build hook helpers (mocked, no network)."""

import hashlib
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

pytest.importorskip("hatchling")

import hatch_build


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
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: machine)
    monkeypatch.setattr(hatch_build, "_is_musl", lambda: musl)
    assert hatch_build._wheel_platform_tag() == expected


def test_wheel_platform_tag_unsupported(monkeypatch):
    monkeypatch.setattr(sys, "platform", "freebsd")
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: "x86_64")
    with pytest.raises(RuntimeError, match="Unsupported platform"):
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
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: machine)
    monkeypatch.setattr(hatch_build, "_is_musl", lambda: musl)
    assert hatch_build._bun_platform() == expected


def test_bun_platform_unsupported(monkeypatch):
    monkeypatch.setattr(sys, "platform", "freebsd")
    monkeypatch.setattr(hatch_build, "_target_machine", lambda: "x86_64")
    with pytest.raises(RuntimeError, match="Unsupported platform"):
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
