# bun-wheel

Unofficial Python wheel for [Bun](https://bun.sh)

Provides the `bun` command via pip/uv without requiring a separate installer.

## Installation

```sh
pip install bun-wheel
```

```sh
uv add bun-wheel
```

After installation, the `bun` command is available in your environment:

```sh
bun --version
bun run index.ts
```

## Versioning

The wheel version mirrors the bundled Bun release — `bun-wheel==1.3.14` always contains Bun `1.3.14`.

## Supported platforms

| Platform | x86-64 | ARM64 |
|---|---|---|
| Linux (glibc) | ✓ | ✓ |
| Linux (musl) | ✓ | ✓ |
| macOS | ✓ | ✓ |
| Windows | ✓ | ✓ |

## How it works

The custom Hatchling build hook (`hatch_build.py`) runs at wheel build time:

1. Reads the target Bun version from the package version in `pyproject.toml`.
2. Downloads the platform-specific zip from the [official Bun releases](https://github.com/oven-sh/bun/releases).
3. Verifies the SHA-256 checksum against Bun's published `SHASUMS256.txt`.
4. Extracts the binary into the wheel and sets the platform tag (e.g. `manylinux_2_17_x86_64`) so pip selects the correct wheel at install time.

No binary is committed to the repository.

## Building from source

```sh
uv run hatch build -t wheel
```

To build for a specific Bun version, update the `version` field in `pyproject.toml` to match the desired Bun release, then rebuild.

## Disclaimer

This project is not affiliated with or endorsed by Oven Inc. Bun is developed and maintained by [Oven](https://oven.sh). Please report issues with Bun itself to the [official Bun repository](https://github.com/oven-sh/bun).
