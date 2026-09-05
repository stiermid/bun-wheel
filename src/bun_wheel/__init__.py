# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Unofficial Bun wheel that provides the ``bun`` command via pip."""

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

__all__ = ["bun", "exec_bun", "run_bun"]


def _get_bun_path() -> str:
    bin_dir = Path(__file__).parent / "bin"

    if sys.platform == "win32":
        binary_path = bin_dir / "bun.exe"
    else:
        binary_path = bin_dir / "bun"

    if not binary_path.exists():
        raise FileNotFoundError(f"bun binary not found at {binary_path}")

    return str(binary_path)


def run_bun(
    args: Sequence[str] = (),
    return_completed_process: bool = False,
    **kwargs: Any,
) -> int | subprocess.CompletedProcess:
    """Run the bundled bun binary with the given arguments.

    Returns the exit code, or the completed process if requested.
    """
    binary = _get_bun_path()
    completed = subprocess.run([binary, *args], **kwargs)
    if return_completed_process:
        return completed
    return completed.returncode


def bun(
    args: Sequence[str] = (),
    return_completed_process: bool = False,
    **kwargs: Any,
) -> int | subprocess.CompletedProcess:
    """Run the bundled bun binary with the given arguments.

    Alias of :func:`run_bun` mirroring ``nodejs-wheel`` naming.
    """
    return run_bun(args, return_completed_process, **kwargs)


def exec_bun() -> None:
    """Run the bundled bun binary, forwarding command-line arguments."""
    try:
        binary = _get_bun_path()
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    args = [binary, *sys.argv[1:]]

    try:
        os.execv(binary, args)
    except OSError as e:
        print(f"error: failed to exec bun binary at {binary}: {e}", file=sys.stderr)
        sys.exit(1)
