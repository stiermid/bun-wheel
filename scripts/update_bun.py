# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: Apache-2.0

"""Propose stable Bun updates without merging, tagging, or publishing.

Requires Python 3.11+ and uv on PATH. Use --dry-run to check without editing.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tomllib
import urllib.request
from dataclasses import dataclass
from glob import glob
from pathlib import Path

REPOSITORY_URL = "https://github.com/oven-sh/bun"
API_URL = "https://api.github.com/repos/oven-sh/bun"
RAW_URL = "https://raw.githubusercontent.com/oven-sh/bun"
RELEASE_API = f"{API_URL}/releases/latest"
RELEASE_URL = f"{REPOSITORY_URL}/releases"
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


@dataclass(frozen=True)
class BunLicensing:
    """Release-pinned upstream facts, not a redistribution compliance approval."""

    version: str
    source_commit: str
    webkit_commit: str
    tinycc_commit: str
    document: bytes


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


def fetch_github_json(url: str) -> dict:
    """Fetch an upstream GitHub API object with optional authentication."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bun-wheel-update-check",
    }
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a GitHub API object: {url}")
    return data


def fetch_latest_release() -> dict:
    """Fetch GitHub's latest non-prerelease Bun release."""
    return fetch_github_json(RELEASE_API)


def fetch_source_file(commit: str, path: str) -> bytes:
    """Read an immutable upstream source file without forwarding API credentials."""
    with urllib.request.urlopen(f"{RAW_URL}/{commit}/{path}", timeout=30) as response:
        return response.read()


def _mask_typescript_non_code(text: str) -> str:
    """Hide comments and strings without exposing declarations inside them.

    Only SHA literals remain visible. Complex template interpolations are rejected
    rather than interpreted; this is a narrow extractor, not a TypeScript parser.
    """
    tokens = re.compile(
        r'(?P<double>"(?:\\(?:.|\Z)|[^"\\])*)(?P<double_end>"|\Z)'
        r"|(?P<single>'(?:\\(?:.|\Z)|[^'\\])*)(?P<single_end>'|\Z)"
        r"|(?P<template>`(?:\\(?:.|\Z)|[^`\\])*)(?P<template_end>`|\Z)"
        r"|(?P<block>/\*.*?)(?P<block_end>\*/|\Z)"
        r"|(?P<line>//[^\r\n]*)",
        re.DOTALL,
    )
    quoted = r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
    interpolation = rf"\$\{{(?:{quoted}|[^{{}}'\"`/\\])*\}}"

    def mask(match: re.Match[str]) -> str:
        if any(
            match.group(end) == ""
            for end in ("double_end", "single_end", "template_end", "block_end")
        ):
            raise ValueError("Unterminated TypeScript token; manual review needed")
        value = match[0]
        if match.group("template") is not None:
            contents = re.sub(r"\\.", "  ", value[1:-1], flags=re.DOTALL)
            contents = re.sub(interpolation, "", contents, flags=re.DOTALL)
            if "${" in contents:
                raise ValueError(
                    "Unsupported template interpolation; manual review needed"
                )
        elif (
            match.group("double") is not None or match.group("single") is not None
        ) and (re.fullmatch(r"([\"'])([0-9a-f]{40})\1", value) is not None):
            return value
        return re.sub(r"[^\r\n]", " ", value)

    return tokens.sub(mask, text)


def extract_commit(text: str, name: str) -> str:
    """Resolve one active const SHA literal, rejecting unsupported declarations."""
    code = _mask_typescript_non_code(text)
    declarations = re.findall(
        rf"(?m)^([ \t]*(?:export[ \t]+)?(?:declare[ \t]+)?"
        rf"(?:const|let|var)[ \t]+{re.escape(name)}\b[^\r\n]*)\r?$",
        code,
    )
    if len(declarations) != 1:
        raise ValueError(f"Cannot resolve exactly one {name}; review upstream layout")
    match = re.fullmatch(
        rf"[ \t]*(?:export[ \t]+)?const[ \t]+{re.escape(name)}"
        r"[ \t]*(?::[ \t]*string[ \t]*)?=[ \t]*"
        r"([\"'])([0-9a-f]{40})\1[ \t]*;?[ \t]*",
        declarations[0],
    )
    if match is None:
        raise ValueError(
            f"Expected an immutable commit for {name}; manual review needed"
        )
    return match[2]


def fetch_licensing(version: str) -> BunLicensing:
    """Resolve a release tag and collect licensing facts only from its commit."""
    if re.fullmatch(VERSION_PATTERN, version) is None:
        raise ValueError(f"Expected a stable Bun version: {version}")
    commit = fetch_github_json(f"{API_URL}/commits/bun-v{version}").get("sha")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("Cannot resolve Bun release tag to an immutable commit")

    package = json.loads(fetch_source_file(commit, "package.json"))
    if not isinstance(package, dict) or package.get("version") != version:
        raise ValueError("Resolved Bun source does not match the release version")
    document = fetch_source_file(commit, "LICENSE.md")
    if "Bun itself is MIT-licensed." not in document.decode("utf-8"):
        raise ValueError(
            "Bun's MIT licensing declaration changed; manual review needed"
        )
    webkit = extract_commit(
        fetch_source_file(commit, "scripts/build/deps/webkit.ts").decode("utf-8"),
        "WEBKIT_VERSION",
    )
    tinycc = extract_commit(
        fetch_source_file(commit, "scripts/build/deps/tinycc.ts").decode("utf-8"),
        "TINYCC_COMMIT",
    )
    return BunLicensing(version, commit, webkit, tinycc, document)


def licensing_updates(root: Path, licensing: BunLicensing) -> dict[str, bytes]:
    """Render the snapshot and manifest without rewriting explanatory notices."""
    document = licensing.document
    snapshot = document if document.endswith(b"\n") else document + b"\n"
    files = {"Bun-LICENSE.md": hashlib.sha256(snapshot).hexdigest()}
    for name in ("MIT.txt", "LGPL-2.1-or-later.txt", "LicenseRef-Bun.txt"):
        files[name] = hashlib.sha256(
            (root / "LICENSES" / name).read_bytes()
        ).hexdigest()
    # Match the flat LICENSES/* packaging glob, including its hidden-file rules.
    for name in sorted(glob("*", root_dir=root / "LICENSES")):
        path = root / "LICENSES" / name
        if path.is_file() and path.name not in files and path.name != "bun.json":
            files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "version": licensing.version,
        "source_commit": licensing.source_commit,
        "webkit_commit": licensing.webkit_commit,
        "tinycc_commit": licensing.tinycc_commit,
        "release_url": f"{RELEASE_URL}/tag/bun-v{licensing.version}",
        "source_url": f"{REPOSITORY_URL}/tree/{licensing.source_commit}",
        "upstream_license_url": (
            f"{REPOSITORY_URL}/blob/{licensing.source_commit}/LICENSE.md"
        ),
        "webkit_source_url": (
            f"https://github.com/oven-sh/WebKit/tree/{licensing.webkit_commit}"
        ),
        "tinycc_source_url": (
            f"https://github.com/oven-sh/tinycc/tree/{licensing.tinycc_commit}"
        ),
        "upstream_license_sha256": hashlib.sha256(document).hexdigest(),
        "files": files,
    }
    return {
        "LICENSES/Bun-LICENSE.md": snapshot,
        "LICENSES/bun.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }


def update_project(root: Path, version: str, licensing: BunLicensing) -> None:
    """Update release data together, restoring files on write or relock failure."""
    if licensing.version != version:
        raise ValueError("Licensing snapshot does not match the proposed Bun version")
    updates = licensing_updates(root, licensing)
    original_project = (root / "pyproject.toml").read_bytes()
    updates["pyproject.toml"] = replace_project_version(
        original_project.decode("utf-8"), version
    ).encode("utf-8")
    originals = {name: (root / name).read_bytes() for name in (*updates, "uv.lock")}
    try:
        for name, data in updates.items():
            (root / name).write_bytes(data)
        # No --upgrade: retain existing dependency pins during the metadata refresh.
        subprocess.run(["uv", "lock"], cwd=root, check=True)
    except (OSError, subprocess.CalledProcessError):
        for name, data in originals.items():
            path = root / name
            if not path.is_file() or path.read_bytes() != data:
                path.write_bytes(data)
        raise


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
    licensing = fetch_licensing(version)
    print(f"Bun update available: {current} -> {version}\n{RELEASE_URL}/tag/{tag}")
    print(f"Licensing source: {REPOSITORY_URL}/tree/{licensing.source_commit}")
    if args.dry_run:
        return

    update_project(root, version, licensing)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a") as stream:
            stream.write(f"version={version}\nrelease_url={RELEASE_URL}/tag/{tag}\n")
            stream.write(f"source_commit={licensing.source_commit}\n")
            stream.write("changed=true\n")


if __name__ == "__main__":
    main()
