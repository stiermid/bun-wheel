# SPDX-FileCopyrightText: 2026 Agil Mammadov
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the bun_wheel runtime shims (mocked, no binary needed)."""

import inspect
import runpy
import sys
from unittest.mock import MagicMock, patch

import pytest

import bun_wheel
from bun_wheel import bun, exec_bun, run_bun


def test_all_exports_sorted_and_resolve():
    assert bun_wheel.__all__ == sorted(bun_wheel.__all__)
    assert set(bun_wheel.__all__) == {"bun", "exec_bun", "run_bun"}


def test_run_bun_returns_exit_code():
    completed = MagicMock(returncode=0)
    with (
        patch("bun_wheel._get_bun_path", return_value="/fake/bun"),
        patch("bun_wheel.subprocess.run", return_value=completed) as run,
    ):
        assert run_bun(["--version"]) == 0
        run.assert_called_once_with(["/fake/bun", "--version"])


def test_run_bun_empty_args_calls_binary_only():
    completed = MagicMock(returncode=0)
    with (
        patch("bun_wheel._get_bun_path", return_value="/fake/bun"),
        patch("bun_wheel.subprocess.run", return_value=completed) as run,
    ):
        assert run_bun() == 0
        run.assert_called_once_with(["/fake/bun"])


def test_run_bun_completed_process():
    completed = MagicMock(returncode=0)
    with (
        patch("bun_wheel._get_bun_path", return_value="/fake/bun"),
        patch("bun_wheel.subprocess.run", return_value=completed),
    ):
        assert run_bun(["--version"], return_completed_process=True) is completed


def test_run_bun_kwargs_passthrough():
    completed = MagicMock(returncode=0)
    with (
        patch("bun_wheel._get_bun_path", return_value="/fake/bun"),
        patch("bun_wheel.subprocess.run", return_value=completed) as run,
    ):
        run_bun(["run", "app.ts"], cwd="/tmp", check=False)
        run.assert_called_once_with(
            ["/fake/bun", "run", "app.ts"], cwd="/tmp", check=False
        )


def test_run_bun_default_args_immutable():
    assert inspect.signature(run_bun).parameters["args"].default == ()


def test_run_bun_missing_binary_propagates():
    with patch("bun_wheel._get_bun_path", side_effect=FileNotFoundError("nope")):
        with pytest.raises(FileNotFoundError):
            run_bun(["--version"])


def test_bun_alias_forwards_to_run_bun():
    with patch("bun_wheel.run_bun", return_value=3) as run_bun_mock:
        assert bun(["--version"], capture_output=True) == 3
        run_bun_mock.assert_called_once_with(
            ["--version"], return_completed_process=False, capture_output=True
        )


def test_bun_same_signature_as_run_bun():
    assert str(inspect.signature(bun)) == str(inspect.signature(run_bun))


def test_get_bun_path_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with patch("pathlib.Path.is_file", return_value=True):
        assert bun_wheel._get_bun_path().endswith("bin/bun")


def test_get_bun_path_win32(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with patch("pathlib.Path.is_file", return_value=True):
        assert bun_wheel._get_bun_path().endswith("bin/bun.exe")


def test_get_bun_path_missing_raises():
    with patch("pathlib.Path.is_file", return_value=False):
        with pytest.raises(FileNotFoundError):
            bun_wheel._get_bun_path()


def test_get_bun_path_rejects_directory(monkeypatch):
    # A directory named ``bun`` must not be treated as the binary:
    # exists() is True but is_file() is False.
    monkeypatch.setattr(sys, "platform", "linux")
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=False),
    ):
        with pytest.raises(FileNotFoundError):
            bun_wheel._get_bun_path()


def test_exec_bun_missing_binary_exits_1(capsys):
    with patch("bun_wheel._get_bun_path", side_effect=FileNotFoundError("nope")):
        with pytest.raises(SystemExit) as exc_info:
            exec_bun()
        assert exc_info.value.code == 1
    assert "error" in capsys.readouterr().err


def test_exec_bun_oserror_exits_1(capsys, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", ["bun", "--version"])
    with (
        patch("bun_wheel._get_bun_path", return_value="/fake/bun"),
        patch("bun_wheel.os.execv", side_effect=PermissionError("denied")),
    ):
        with pytest.raises(SystemExit) as exc_info:
            exec_bun()
        assert exc_info.value.code == 1
    assert "failed to exec" in capsys.readouterr().err


def test_exec_bun_forwards_argv(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", ["bun", "run", "app.ts", "--watch"])
    with (
        patch("bun_wheel._get_bun_path", return_value="/fake/bun"),
        patch("bun_wheel.os.execv") as execv,
        patch("bun_wheel.subprocess.run") as run,
    ):
        exec_bun()
        execv.assert_called_once_with(
            "/fake/bun", ["/fake/bun", "run", "app.ts", "--watch"]
        )
        run.assert_not_called()


def test_exec_bun_win32_fallback_exits_with_child_code(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", ["bun", "--version"])
    completed = MagicMock(returncode=3)
    with (
        patch("bun_wheel._get_bun_path", return_value=r"C:\fake\bun.exe"),
        patch("bun_wheel.subprocess.run", return_value=completed) as run,
        patch("bun_wheel.os.execv") as execv,
    ):
        with pytest.raises(SystemExit) as exc_info:
            exec_bun()
        assert exc_info.value.code == 3
        run.assert_called_once_with([r"C:\fake\bun.exe", "--version"])
        execv.assert_not_called()


def test_exec_bun_win32_fallback_zero_exit(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", ["bun", "run", "app.ts"])
    completed = MagicMock(returncode=0)
    with (
        patch("bun_wheel._get_bun_path", return_value=r"C:\fake\bun.exe"),
        patch("bun_wheel.subprocess.run", return_value=completed),
    ):
        with pytest.raises(SystemExit) as exc_info:
            exec_bun()
        assert exc_info.value.code == 0


def test_exec_bun_return_annotation_is_noreturn():
    from typing import NoReturn

    assert bun_wheel.exec_bun.__annotations__["return"] is NoReturn


def test_run_bun_accepts_pathlike_args():
    completed = MagicMock(returncode=0)
    with (
        patch("bun_wheel._get_bun_path", return_value="/fake/bun"),
        patch("bun_wheel.subprocess.run", return_value=completed) as run,
    ):
        from pathlib import Path

        assert run_bun([Path("app.ts")]) == 0
        run.assert_called_once_with(["/fake/bun", Path("app.ts")])


def test_main_module_calls_exec_bun():
    with patch("bun_wheel.exec_bun") as exec_bun_mock:
        runpy.run_module("bun_wheel.__main__", run_name="__main__")
        exec_bun_mock.assert_called_once_with()


def test_main_import_has_no_side_effect():
    with patch("bun_wheel.exec_bun") as exec_bun_mock:
        runpy.run_module("bun_wheel.__main__", run_name="bun_wheel.__main__")
        exec_bun_mock.assert_not_called()


def test_main_function_calls_exec_bun():
    import bun_wheel.__main__ as main_mod

    with patch.object(main_mod, "exec_bun") as exec_bun_mock:
        with pytest.raises(Exception, match="stop"):
            # exec_bun never returns; simulate with a sentinel exception
            exec_bun_mock.side_effect = RuntimeError("stop")
            main_mod.main()
        exec_bun_mock.assert_called_once_with()
