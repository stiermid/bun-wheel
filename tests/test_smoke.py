# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: Apache-2.0

"""Smoke tests against the real bundled bun binary.

Skipped when ``src/bun_wheel/bin/`` is absent (plain checkouts without a
build). Runs locally after ``hatch build`` and in cibuildwheel test envs.
"""

import hashlib
import json
import shutil
import subprocess
import sys
from importlib.metadata import distribution

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


def test_installed_distribution_retains_licenses():
    dist = distribution("bun-wheel")
    assert dist.metadata["License-Expression"] == "Apache-2.0 AND LicenseRef-Bun"
    license_files = dist.metadata.get_all("License-File", [])
    assert {
        "LICENSE",
        "NOTICE",
        "THIRD_PARTY_NOTICES.md",
        "LICENSES/LicenseRef-Bun.txt",
        "LICENSES/Bun-LICENSE.md",
        "LICENSES/MIT.txt",
        "LICENSES/LGPL-2.1-or-later.txt",
        "LICENSES/bun.json",
    }.issubset(license_files)
    installed = {}
    for name in license_files:
        matches = [
            path
            for path in dist.files or []
            if path.as_posix().endswith(f".dist-info/licenses/{name}")
        ]
        assert len(matches) == 1, name
        installed[name] = dist.locate_file(matches[0]).read_bytes()
    assert hashlib.sha256(installed["LICENSE"]).hexdigest() == (
        "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
    )
    manifest = json.loads(installed["LICENSES/bun.json"])
    assert manifest["version"] == dist.version.split(".post", 1)[0]
    for name, expected in manifest["files"].items():
        assert hashlib.sha256(installed[f"LICENSES/{name}"]).hexdigest() == expected


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
