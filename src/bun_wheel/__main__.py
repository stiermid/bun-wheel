# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: Apache-2.0

"""Entry point for running bun via `python -m bun_wheel`."""

from typing import NoReturn

from bun_wheel import exec_bun


def main() -> NoReturn:
    """Invoke the bundled bun binary via :func:`exec_bun`."""
    exec_bun()


if __name__ == "__main__":
    main()
