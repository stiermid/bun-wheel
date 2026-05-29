from typing import Any

import glob
import hashlib
import os
import platform
import subprocess
import sys
import urllib.request
import zipfile
import tempfile
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _is_musl() -> bool:
    if glob.glob("/lib/ld-musl-*.so.1"):
        return True
    try:
        result = subprocess.run(["ldd", "--version"], capture_output=True, text=True)
        return "musl" in (result.stdout + result.stderr).lower()
    except Exception:
        return False


def _target_machine() -> str:
    # cibuildwheel sets _PYTHON_HOST_PLATFORM for cross-arch builds on macOS
    # e.g. "macosx-11.0-x86_64" when building x86_64 on an arm64 runner
    host_platform = os.environ.get("_PYTHON_HOST_PLATFORM", "")
    if host_platform:
        return host_platform.rsplit("-", 1)[-1]
    return platform.machine().lower()


def _bun_platform() -> str:
    system = sys.platform
    machine = _target_machine()

    if machine in ("x86_64", "amd64"):
        arch = "x64"
    elif machine in ("aarch64", "arm64"):
        arch = "aarch64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    if system == "linux":
        suffix = "-musl" if _is_musl() else ""
        return f"bun-linux-{arch}{suffix}"
    elif system == "darwin":
        return f"bun-darwin-{arch}"
    elif system == "win32":
        return f"bun-windows-{arch}"
    elif system.startswith("freebsd"):
        return f"bun-freebsd-{arch}"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def _wheel_platform_tag() -> str:
    system = sys.platform
    machine = _target_machine()

    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "aarch64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    if system == "linux":
        return f"manylinux_2_17_{arch}.manylinux2014_{arch}"
    elif system == "darwin":
        if arch == "aarch64":
            return "macosx_11_0_arm64"
        return "macosx_10_9_x86_64"
    elif system == "win32":
        return "win_amd64" if arch == "x86_64" else f"win_{arch}"
    elif system.startswith("freebsd"):
        return f"freebsd_13_0_{arch}"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        bun_version = self.metadata.version

        bun_plat = _bun_platform()
        binary_name = "bun.exe" if sys.platform == "win32" else "bun"
        asset_name = f"{bun_plat}.zip"
        base_url = f"https://github.com/oven-sh/bun/releases/download/bun-v{bun_version}"

        print(f"Downloading Bun v{bun_version} for {bun_plat}...")

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / asset_name
            urllib.request.urlretrieve(f"{base_url}/{asset_name}", zip_path)
            self._verify_checksum(zip_path, asset_name, f"{base_url}/SHASUMS256.txt")

            with zipfile.ZipFile(zip_path) as zf:
                member = next(m for m in zf.namelist() if Path(m).name == binary_name)
                data = zf.read(member)

        bin_dir = Path(self.root) / "src" / "bun_wheel" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        binary_path = bin_dir / binary_name
        binary_path.write_bytes(data)
        binary_path.chmod(0o755)

        build_data["tag"] = f"py3-none-{_wheel_platform_tag()}"

    def _verify_checksum(self, zip_path: Path, asset_name: str, shasums_url: str) -> None:
        with urllib.request.urlopen(shasums_url) as resp:
            shasums = resp.read().decode()

        expected = next(
            (line.split()[0] for line in shasums.splitlines()
             if len(line.split()) == 2 and line.split()[1] == asset_name),
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
