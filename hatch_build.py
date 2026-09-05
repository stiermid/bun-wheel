# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Custom Hatchling build hook that downloads and bundles the Bun binary."""

from typing import Any

import hashlib
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import urllib.request
import zipfile
from glob import glob
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging.version import Version


def _is_musl() -> bool:
    if glob("/lib/ld-musl-*.so.1"):
        return True
    try:
        result = subprocess.run(["ldd", "--version"], capture_output=True, text=True)
        return "musl" in (result.stdout + result.stderr).lower()
    except (OSError, subprocess.SubprocessError):
        return False


def _target_machine() -> str:
    # _PYTHON_HOST_PLATFORM is set by cibuildwheel for cross-arch builds (e.g. macOS).
    # sysconfig.get_platform() reads VSCMD_ARG_TGT_ARCH on Windows, so it correctly
    # returns "win-arm64" during Windows ARM64 cross-compilation.
    plat = os.environ.get("_PYTHON_HOST_PLATFORM", "") or sysconfig.get_platform()
    machine = plat.rsplit("-", 1)[-1]
    if machine == "win32":
        raise RuntimeError("Unsupported architecture: win32 (32-bit)")
    return machine


def _normalize_arch(machine: str) -> str:
    """Normalize a host machine name to canonical ``x86_64`` / ``aarch64``."""
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    if machine in ("aarch64", "arm64"):
        return "aarch64"
    raise RuntimeError(f"Unsupported architecture: {machine}")


def _bun_platform() -> str:
    system = sys.platform
    arch = _normalize_arch(_target_machine())

    bun_arch = "x64" if arch == "x86_64" else "aarch64"

    if system == "linux":
        suffix = "-musl" if _is_musl() else ""
        return f"bun-linux-{bun_arch}{suffix}"
    elif system == "darwin":
        return f"bun-darwin-{bun_arch}"
    elif system == "win32":
        return f"bun-windows-{bun_arch}"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def _wheel_platform_tag() -> str:
    system = sys.platform
    arch = _normalize_arch(_target_machine())

    if system == "linux":
        if _is_musl():
            return f"musllinux_1_2_{arch}"
        return f"manylinux_2_17_{arch}.manylinux2014_{arch}"
    elif system == "darwin":
        if arch == "aarch64":
            return "macosx_11_0_arm64"
        return "macosx_10_9_x86_64"
    elif system == "win32":
        return "win_amd64" if arch == "x86_64" else "win_arm64"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


class CustomBuildHook(BuildHookInterface):
    """Download the Bun binary for the target platform into the wheel."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Fetch the Bun asset, verify its checksum, and add it to the wheel."""
        bun_version = Version(self.metadata.version).base_version

        bun_plat = _bun_platform()
        binary_name = "bun.exe" if sys.platform == "win32" else "bun"
        asset_name = f"{bun_plat}.zip"
        base_url = (
            f"https://github.com/oven-sh/bun/releases/download/bun-v{bun_version}"
        )

        print(f"Downloading Bun v{bun_version} for {bun_plat}...")

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / asset_name
            with (
                urllib.request.urlopen(f"{base_url}/{asset_name}", timeout=30) as resp,
                open(zip_path, "wb") as f,
            ):
                shutil.copyfileobj(resp, f)
            self._verify_checksum(zip_path, asset_name, f"{base_url}/SHASUMS256.txt")

            with zipfile.ZipFile(zip_path) as zf:
                try:
                    member = next(
                        m for m in zf.namelist() if Path(m).name == binary_name
                    )
                except StopIteration:
                    raise RuntimeError(
                        f"{binary_name} not found in {asset_name}"
                    ) from None
                data = zf.read(member)

        bin_dir = Path(self.root) / "src" / "bun_wheel" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        binary_path = bin_dir / binary_name
        binary_path.write_bytes(data)
        binary_path.chmod(0o755)

        build_data["force_include"][str(binary_path)] = f"bun_wheel/bin/{binary_name}"
        build_data["tag"] = f"py3-none-{_wheel_platform_tag()}"

    def clean(self, versions: list[str]) -> None:
        """Remove the downloaded binary staged under the source tree."""
        bin_dir = Path(self.root) / "src" / "bun_wheel" / "bin"
        if bin_dir.is_dir():
            shutil.rmtree(bin_dir)

    def _verify_checksum(
        self, zip_path: Path, asset_name: str, shasums_url: str
    ) -> None:
        with urllib.request.urlopen(shasums_url, timeout=30) as resp:
            shasums = resp.read().decode()

        expected = next(
            (
                line.split()[0]
                for line in shasums.splitlines()
                if len(line.split()) == 2 and line.split()[1] == asset_name
            ),
            None,
        )
        if expected is None:
            raise RuntimeError(f"No checksum found for {asset_name} in SHASUMS256.txt")

        actual = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(
                f"Checksum mismatch for {asset_name}\n"
                f"  expected: {expected}\n"
                f"  actual:   {actual}"
            )
