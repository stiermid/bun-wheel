# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Unofficial Bun wheel that provides the ``bun`` command via pip."""

import functools
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, NoReturn, overload

__all__ = ["bun", "exec_bun", "run_bun"]

StrPath = str | os.PathLike[str]


def _get_bun_path() -> str:
    """Return the path to the bundled bun binary.

    Raises:
        FileNotFoundError: If the binary is missing for this platform.

    """
    bin_dir = Path(__file__).parent / "bin"

    if sys.platform == "win32":
        binary_path = bin_dir / "bun.exe"
    else:
        binary_path = bin_dir / "bun"

    if not binary_path.is_file():
        raise FileNotFoundError(f"bun binary not found at {binary_path}")

    return str(binary_path)


@overload
def run_bun(
    args: Sequence[StrPath] = (),
    return_completed_process: Literal[False] = False,
    **kwargs: Any,
) -> int: ...


@overload
def run_bun(
    args: Sequence[StrPath] = (),
    *,
    return_completed_process: Literal[True],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]: ...


def run_bun(
    args: Sequence[StrPath] = (),
    return_completed_process: bool = False,
    **kwargs: Any,
) -> int | subprocess.CompletedProcess[str]:
    """Run the bundled bun binary with the given arguments.

    Args:
        args: Arguments forwarded to the bun binary.
        return_completed_process: Return the completed process
            instead of the exit code.
        **kwargs: Forwarded to :func:`subprocess.run` (e.g. ``cwd``,
            ``env``, ``capture_output``).

    Returns:
        The exit code, or the completed process if requested.

    Raises:
        FileNotFoundError: If the bundled binary is missing.

    """
    binary = _get_bun_path()
    completed = subprocess.run([binary, *args], **kwargs)
    if return_completed_process:
        return completed
    return completed.returncode


@overload
def bun(
    args: Sequence[StrPath] = (),
    return_completed_process: Literal[False] = False,
    **kwargs: Any,
) -> int: ...


@overload
def bun(
    args: Sequence[StrPath] = (),
    *,
    return_completed_process: Literal[True],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]: ...


@functools.wraps(run_bun)
def bun(
    args: Sequence[StrPath] = (),
    return_completed_process: bool = False,
    **kwargs: Any,
) -> int | subprocess.CompletedProcess[str]:
    """Run the bundled bun binary with the given arguments.

    Alias of :func:`run_bun` mirroring ``nodejs-wheel`` naming.
    """
    return run_bun(args, return_completed_process=return_completed_process, **kwargs)


def exec_bun() -> NoReturn:
    """Replace the current process with the bundled bun binary.

    On POSIX uses :func:`os.execv` so exit codes and signals are preserved.
    On Windows (``sys.platform == "win32"``, which has no true exec)
    falls back to :func:`subprocess.run` plus ``sys.exit`` with the
    child's exit code.

    Forwards ``sys.argv[1:]`` to the binary. Exits with status 1 if the
    binary is missing or cannot be executed.
    """
    try:
        binary = _get_bun_path()
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    argv = [binary, *sys.argv[1:]]

    if sys.platform == "win32":
        completed = subprocess.run(argv)
        sys.exit(completed.returncode)

    try:
        os.execv(binary, argv)
    except OSError as e:
        print(f"error: failed to exec bun binary at {binary}: {e}", file=sys.stderr)
        sys.exit(1)
