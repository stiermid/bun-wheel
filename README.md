# bun-wheel

![PyPI - Version](https://img.shields.io/pypi/v/bun-wheel?logo=pypi&label=bun-wheel)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bun-wheel)
![PyPI - Downloads](https://img.shields.io/pypi/dm/bun-wheel)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/stiermid/bun-wheel/build.yml)

Unofficial Python wheel for [Bun](https://bun.sh). Provides the `bun` command via pip.

## Installation

```sh
pip install bun-wheel
```

After installation, the `bun` command is available in your environment:

```sh
bun --version
bun run index.ts
```

## Supported platforms

| Platform | x86-64 | ARM64 |
|---|---|---|
| Linux (glibc) | ✓ | ✓ |
| Linux (musl) | ✓ | ✓ |
| macOS | ✓ | ✓ |
| Windows | ✓ | ✓ |

## Building from source

```sh
uv run hatch build -t wheel
```

To build for a specific Bun version, update the `version` field in `pyproject.toml`
and refresh the release-pinned upstream licensing files before rebuilding. See
the [contribution and release checklist](CONTRIBUTING.md). Packaging-only `.postN`
versions use the same underlying Bun release.

## Inspiration

This project was inspired by [nodejs-wheel](https://github.com/njzjz/nodejs-wheel) package.

## Disclaimer

This project is not affiliated with or endorsed by Oven Inc. Bun is developed and maintained by [Oven](https://oven.sh).

## License

The original Python wrapper, build tooling, tests, documentation, and
configuration are licensed under the **Apache License, Version 2.0**. See
[LICENSE](LICENSE) and [NOTICE](NOTICE).

The bundled Bun executable and its embedded dependencies retain their own
upstream licenses; they are **not** relicensed under Apache-2.0. The distribution
metadata uses `Apache-2.0 AND LicenseRef-Bun` to record this distinction. See
[LicenseRef-Bun](LICENSES/LicenseRef-Bun.txt) and the retained
[Bun licensing document](LICENSES/Bun-LICENSE.md).

See [third-party licensing information](THIRD_PARTY_NOTICES.md) for the retained
upstream notices and outstanding redistribution review requirements. Retaining
these documents is not, by itself, a completed compliance audit.

Earlier releases were offered under LGPL-2.1-or-later. This change does not
revoke the license rights already granted for those releases.
