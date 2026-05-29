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

### Pinning a Bun version

By default the hook fetches the latest Bun release. Override it with an environment variable:

```sh
BUN_VERSION=1.2.0 uv run hatch build -t wheel
```

Or set it permanently in `pyproject.toml`:

```toml
[tool.hatch.build.hooks.custom]
path = "hatch_build.py"
bun-version = "1.2.0"
```

## How it works

`hatch_build.py` implements a Hatchling build hook that runs before each wheel is assembled:

1. Resolves the target Bun version (env var → config → latest GitHub release).
2. Downloads the platform-specific zip from the [official Bun releases](https://github.com/oven-sh/bun/releases).
3. Verifies the SHA-256 checksum against Bun's published `SHASUMS256.txt`.
4. Extracts the binary to `src/bun_wheel/bin/` and sets it executable.
5. Sets the wheel platform tag (e.g. `manylinux_2_17_x86_64`) so pip selects the right wheel on install.

## Disclaimer

This project is not affiliated with or endorsed by Oven Inc. Bun is developed and maintained by [Oven](https://oven.sh). Please report issues with Bun itself to the [official repository](https://github.com/oven-sh/bun).
