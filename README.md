# bun-wheel

Unofficial Python wheel for [Bun](https://bun.sh)

## Supported platforms

| OS      | x86-64 | ARM64 |
|---------|--------|-------|
| Linux (glibc) | ✓ | ✓ |
| Linux (musl)  | ✓ | ✓ |
| macOS   | ✓      | ✓     |
| Windows | ✓      | ✓     |
| FreeBSD | ✓      | ✓     |

## Building from source

The wheel is built with [Hatchling](https://hatch.pypa.io). The custom build hook downloads the appropriate Bun binary for the current platform at build time, so no binary is committed to the repository.

```sh
uv run hatch build -t wheel
```

### Bun version

The wheel version mirrors the bundled Bun version — `bun-wheel==1.3.14` always contains Bun `1.3.14`. To build a specific version, set the `version` field in `pyproject.toml` accordingly.

## How it works

`hatch_build.py` implements a Hatchling build hook that runs before each wheel is assembled:

1. Reads the Bun version from the package version in `pyproject.toml`.
2. Downloads the platform-specific zip from the [official Bun releases](https://github.com/oven-sh/bun/releases).
3. Verifies the SHA-256 checksum against Bun's published `SHASUMS256.txt`.
4. Extracts the binary to `src/bun_wheel/bin/` and sets it executable.
5. Sets the wheel platform tag (e.g. `manylinux_2_17_x86_64`) so pip selects the right wheel on install.

## Disclaimer

This project is not affiliated with or endorsed by Oven Inc. Bun is developed and maintained by [Oven](https://oven.sh). Please report issues with Bun itself to the [official repository](https://github.com/oven-sh/bun).
