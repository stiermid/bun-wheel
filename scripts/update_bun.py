# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Propose stable Bun updates without merging, tagging, or publishing.

Requires Python 3.11+ and uv on PATH. Use --dry-run to check without editing.
"""

import argparse
import json
import os
import re
import subprocess
import tomllib
import urllib.request
from pathlib import Path

RELEASE_API = "https://api.github.com/repos/oven-sh/bun/releases/latest"
RELEASE_URL = "https://github.com/oven-sh/bun/releases"
REQUIRED_ASSETS = {
    "bun-linux-x64.zip",
    "bun-linux-aarch64.zip",
    "bun-linux-x64-musl.zip",
    "bun-linux-aarch64-musl.zip",
    "bun-darwin-x64.zip",
    "bun-darwin-aarch64.zip",
    "bun-windows-x64.zip",
    "bun-windows-aarch64.zip",
}
VERSION_PATTERN = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"


def version_tuple(version: str) -> tuple[int, int, int]:
    """Compare upstream versions, allowing packaging-only .postN revisions."""
    match = re.fullmatch(VERSION_PATTERN + r"(?:\.post\d+)?", version)
    if match is None:
        raise ValueError(f"Unsupported package version: {version}")
    return tuple(int(part) for part in match.groups())


def select_update(release: dict, current: str) -> str | None:
    """Return a newer stable version only when all required assets exist."""
    if release.get("draft") or release.get("prerelease"):
        return None
    match = re.fullmatch(r"bun-v(" + VERSION_PATTERN + r")", release["tag_name"])
    if match is None:
        return None
    version = match.group(1)
    if version_tuple(version) <= version_tuple(current):
        return None
    assets = {asset["name"] for asset in release["assets"]}
    if not REQUIRED_ASSETS.union({"SHASUMS256.txt"}).issubset(assets):
        return None
    return version


def verify_manifest(manifest: str) -> None:
    """Ensure each required archive has exactly one valid SHA-256 entry."""
    checksums = {}
    for line in manifest.splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[1] not in REQUIRED_ASSETS:
            continue
        checksum, name = parts
        if name in checksums or re.fullmatch(r"[a-fA-F0-9]{64}", checksum) is None:
            raise ValueError(f"Invalid or duplicate checksum for {name}")
        checksums[name] = checksum
    missing = REQUIRED_ASSETS.difference(checksums)
    if missing:
        raise ValueError(f"Missing checksums: {', '.join(sorted(missing))}")


def replace_project_version(text: str, version: str) -> str:
    """Change only [project].version, preserving formatting and other sections."""
    current = tomllib.loads(text)["project"]["version"]
    section = re.search(r"(?ms)^\[project\][ \t]*\n(.*?)(?=^\[|\Z)", text)
    if section is None:
        raise ValueError("Cannot locate [project] section")
    body, count = re.subn(
        r"(?m)^([ \t]*version[ \t]*=[ \t]*)([\"'])" + re.escape(current) + r"\2",
        lambda match: f"{match[1]}{match[2]}{version}{match[2]}",
        section[1],
        count=1,
    )
    if count != 1:
        raise ValueError("Cannot locate [project].version")
    return text[: section.start(1)] + body + text[section.end(1) :]


def update_project(root: Path, version: str) -> None:
    """Update metadata and relock, restoring files if relocking fails."""
    project = root / "pyproject.toml"
    lock = root / "uv.lock"
    original_project = project.read_bytes()
    original_lock = lock.read_bytes()
    updated = replace_project_version(original_project.decode(), version)
    try:
        project.write_text(updated)
        # No --upgrade: retain existing dependency pins during the metadata refresh.
        subprocess.run(["uv", "lock"], cwd=root, check=True)
    except (OSError, subprocess.CalledProcessError):
        project.write_bytes(original_project)
        lock.write_bytes(original_lock)
        raise


def fetch_latest_release() -> dict:
    """Fetch GitHub's latest non-prerelease Bun release with optional API auth."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bun-wheel-update-check",
    }
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(RELEASE_API, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    """Check upstream, optionally update files, and expose safe workflow outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    current = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    version = select_update(fetch_latest_release(), current)
    if version is None:
        print("No newer stable Bun release with all required assets available.")
        return

    tag = f"bun-v{version}"
    checksum_url = f"{RELEASE_URL}/download/{tag}/SHASUMS256.txt"
    with urllib.request.urlopen(checksum_url, timeout=30) as response:
        verify_manifest(response.read().decode())
    print(f"Bun update available: {current} -> {version}\n{RELEASE_URL}/tag/{tag}")
    if args.dry_run:
        return

    update_project(root, version)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a") as stream:
            stream.write(f"version={version}\nrelease_url={RELEASE_URL}/tag/{tag}\n")
            stream.write("changed=true\n")


if __name__ == "__main__":
    main()
