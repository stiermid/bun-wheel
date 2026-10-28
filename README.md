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

Development and the Hatch build command require Python **3.11+** and
[uv](https://docs.astral.sh/uv/). The repository's `.python-version` selects
Python 3.14 by default. Installing and running the wheel supports Python **3.10+**.

```sh
uv run --locked --only-dev hatch build -t wheel
```

To build for a specific Bun version, update the `version` field in `pyproject.toml` to match the desired Bun release, then rebuild.

## Development and testing

Install the locked development tools and run the unit tests:

```sh
uv sync --locked --only-dev
PYTHONPATH=src uv run --no-sync --only-dev python -m pytest tests/test_runtime.py tests/test_build_hook.py tests/test_update_bun.py -q
```

These unit tests use mocks and do not need a downloaded Bun binary or network
access. `--only-dev` installs the tools without building the project itself.

The `dev` dependency group requires Python 3.11+ so Hatch can use patched
`filelock` releases. The lightweight `test` group contains pytest and supports
Python 3.10. CI runs the unit tests with locked dependencies on Python 3.11–3.14,
builds all supported platform wheels, and installs the Linux x86-64 wheel on
Python 3.10 to test the runtime, CLI, and bundled binary before publishing.

## Inspiration

This project was inspired by [nodejs-wheel](https://github.com/njzjz/nodejs-wheel) package.

## Disclaimer

This project is not affiliated with or endorsed by Oven Inc. Bun is developed and maintained by [Oven](https://oven.sh).

## License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.

The bundled Bun binary is distributed under its own MIT license - see [LICENSES/MIT.txt](LICENSES/MIT.txt).
