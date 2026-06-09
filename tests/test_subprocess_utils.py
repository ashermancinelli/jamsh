from __future__ import annotations

import os
import subprocess
import sys

import pytest

from jamsh import run
from jamsh import run_live


def test_run_list_command_captures_and_streams(capsys: pytest.CaptureFixture[str]) -> None:
    result = run(
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr)",
        ],
        capture=True,
    )

    captured = capsys.readouterr()
    assert result.returncode == 0
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"
    assert captured.out == "out\n"
    assert captured.err.endswith("err\n")
    assert "$ " in captured.err


def test_run_string_command_uses_shell(capsys: pytest.CaptureFixture[str]) -> None:
    result = run(f'{sys.executable} -c "print(123)"', capture=True)

    captured = capsys.readouterr()
    assert result.stdout == "123\n"
    assert captured.out == "123\n"


def test_run_extra_env_preserves_environment() -> None:
    result = run(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ['PATH']); print(os.environ['JAMSH_FLAG'])",
        ],
        capture=True,
        echo=False,
        extra_env={"JAMSH_FLAG": "1"},
    )

    lines = result.stdout.splitlines()
    assert lines[0] == os.environ["PATH"]
    assert lines[1] == "1"


def test_run_rejects_env_and_extra_env_together() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        run([sys.executable, "-c", "print('x')"], env={}, extra_env={})


def test_run_check_raises_called_process_error() -> None:
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run(
            [
                sys.executable,
                "-c",
                "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)",
            ],
            capture=True,
            echo=False,
        )

    exc = exc_info.value
    assert exc.returncode == 7
    assert exc.output == "out\n"
    assert exc.stderr == "err\n"


def test_run_without_capture_returns_none_streams() -> None:
    result = run([sys.executable, "-c", "print('out')"], capture=False, echo=False)

    assert result.stdout is None
    assert result.stderr is None


def test_run_live_returns_recent_output_on_success() -> None:
    result = run_live(
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr)",
        ],
        message="Running demo",
        echo=False,
        max_lines=10,
    )

    assert result.stdout == "out\n"
    assert result.stderr == "err\n"


def test_run_live_failure_returns_recent_lines_in_exception() -> None:
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_live(
            [
                sys.executable,
                "-c",
                "import sys; print('one'); print('two'); print('warn', file=sys.stderr); raise SystemExit(9)",
            ],
            message="Failing command",
            echo=False,
            max_lines=2,
        )

    exc = exc_info.value
    assert exc.returncode == 9
    assert exc.output == "one\ntwo\n"
    assert exc.stderr == "warn\n"


def test_run_live_rejects_env_and_extra_env_together() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        run_live(
            [sys.executable, "-c", "print('x')"],
            message="bad env",
            env={},
            extra_env={},
        )
