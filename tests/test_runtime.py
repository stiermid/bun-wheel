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
        run_bun_mock.assert_called_once_with(["--version"], False, capture_output=True)


def test_bun_same_signature_as_run_bun():
    assert str(inspect.signature(bun)) == str(inspect.signature(run_bun))


def test_get_bun_path_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with patch("pathlib.Path.exists", return_value=True):
        assert bun_wheel._get_bun_path().endswith("bin/bun")


def test_get_bun_path_win32(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with patch("pathlib.Path.exists", return_value=True):
        assert bun_wheel._get_bun_path().endswith("bin/bun.exe")


def test_get_bun_path_missing_raises():
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            bun_wheel._get_bun_path()


def test_exec_bun_missing_binary_exits_1(capsys):
    with patch("bun_wheel._get_bun_path", side_effect=FileNotFoundError("nope")):
        with pytest.raises(SystemExit) as exc_info:
            exec_bun()
        assert exc_info.value.code == 1
    assert "error" in capsys.readouterr().err


def test_exec_bun_oserror_exits_1(capsys, monkeypatch):
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
    monkeypatch.setattr(sys, "argv", ["bun", "run", "app.ts", "--watch"])
    with (
        patch("bun_wheel._get_bun_path", return_value="/fake/bun"),
        patch("bun_wheel.os.execv") as execv,
    ):
        exec_bun()
        execv.assert_called_once_with(
            "/fake/bun", ["/fake/bun", "run", "app.ts", "--watch"]
        )


def test_main_module_calls_exec_bun():
    with patch("bun_wheel.exec_bun") as exec_bun_mock:
        runpy.run_module("bun_wheel.__main__", run_name="__main__")
        exec_bun_mock.assert_called_once_with()
