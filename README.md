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

## Bun update pull requests

The **Check for Bun updates** GitHub Actions workflow checks every six hours for
a newer stable Bun release. Once all eight platform archives and their checksum
entries are available, it opens or updates one PR from `automation/update-bun`
with changes to `pyproject.toml` and `uv.lock`. Draft, prerelease, and canary
releases are ignored. Dependency upgrades are not requested.

### One-time setup

After merging the workflow into `master`, enable **Settings → Actions → General
→ Workflow permissions → Allow GitHub Actions to create and approve pull requests**.
Despite the setting's name, this workflow only creates or updates PRs; it never
approves or merges them. It uses `GITHUB_TOKEN`, so no additional secret is needed.

You can also run it manually under **Actions → Check for Bun updates → Run workflow**.
If GitHub asks you to **Approve workflows to run** on the generated PR, approve
the CI run, then review and merge once all checks pass. Tagging and publishing
remain manual: push `vX.Y.Z` for the merged version to trigger the existing
**Build & Publish** workflow. The updater itself never creates tags or publishes.

### Local preview

Check the current upstream release without changing files (Python 3.11+):

```sh
python scripts/update_bun.py --dry-run
```

Omit `--dry-run` to update metadata and run `uv lock` locally; this requires `uv`
on your PATH. Use uv 0.11.19, as pinned in CI and pre-commit, to avoid changing the
lockfile format. If relocking fails, the updater restores both original files.

## Inspiration

This project was inspired by [nodejs-wheel](https://github.com/njzjz/nodejs-wheel) package.

## Disclaimer

This project is not affiliated with or endorsed by Oven Inc. Bun is developed and maintained by [Oven](https://oven.sh).

## License

This project is licensed under the LGPL-2.1 License - see the [LICENSE](LICENSE) file for details.
