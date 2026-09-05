"""Smoke tests against the real bundled bun binary.

Skipped when ``src/bun_wheel/bin/`` is absent (plain checkouts without a
build). Runs locally after ``hatch build`` and in cibuildwheel test envs.
"""

import shutil
import subprocess
import sys

import pytest

from bun_wheel import _get_bun_path, bun, run_bun

pytestmark = pytest.mark.integration


def _binary_available() -> bool:
    try:
        _get_bun_path()
    except FileNotFoundError:
        return False
    return True


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _binary_available(), reason="bundled bun binary not built"),
]


def test_run_bun_version_exit_code():
    assert run_bun(["--version"]) == 0


def test_bun_completed_process_captures_version():
    completed = bun(
        ["--version"],
        return_completed_process=True,
        capture_output=True,
        text=True,
    )
    assert isinstance(completed, subprocess.CompletedProcess)
    assert completed.returncode == 0
    assert completed.stdout.strip() != ""


def test_run_bun_nonzero_exit_code():
    assert run_bun(["-e", "process.exit(3)"]) == 3


def test_python_m_module_version():
    completed = subprocess.run(
        [sys.executable, "-m", "bun_wheel", "--version"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


@pytest.mark.skipif(
    shutil.which("bun") is None, reason="bun console script not installed"
)
def test_console_script_version():
    completed = subprocess.run(["bun", "--version"], capture_output=True, text=True)
    assert completed.returncode == 0
