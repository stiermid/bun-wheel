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

To build for a specific Bun version, update the `version` field in `pyproject.toml` to match the desired Bun release, then rebuild.

## Inspiration

This project was inspired by [nodejs-wheel](https://github.com/njzjz/nodejs-wheel) package.

## Disclaimer

This project is not affiliated with or endorsed by Oven Inc. Bun is developed and maintained by [Oven](https://oven.sh).

## License

This project is licensed under the LGPL-2.1 License - see the [LICENSE](LICENSE) file for details.
