from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

import jamsh.subprocess_utils as subprocess_utils
from jamsh import run
from jamsh import run_live
from jamsh import run_many_live
from jamsh import run_many_live_async


def test_run_list_command_captures_and_streams(
    capsys: pytest.CaptureFixture[str],
) -> None:
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
    assert "$ " not in captured.err
    assert sys.executable in captured.err


def test_run_string_command_uses_shlex_split(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run(f"{sys.executable} -c \"print('hello there')\"", capture=True)

    captured = capsys.readouterr()
    assert result.stdout == "hello there\n"
    assert captured.out == "hello there\n"


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


def test_run_extra_env_accepts_pathlike_values(tmp_path: Path) -> None:
    result = run(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ['JAMSH_PATH'])",
        ],
        capture=True,
        echo=False,
        extra_env={"JAMSH_PATH": tmp_path},
    )

    assert result.stdout == f"{tmp_path}\n"


def test_run_echo_includes_extra_env_exports_and_cwd(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    run(
        [sys.executable, "-c", "print('ok')"],
        capture=True,
        cwd=tmp_path,
        extra_env={"JAMSH_FLAG": "hello world", "JAMSH_PATH": tmp_path},
    )

    captured = capsys.readouterr()
    display_cwd = shlex.quote(str(tmp_path))
    assert "export JAMSH_FLAG='hello world'" in captured.err
    assert f"export JAMSH_PATH={display_cwd}" in captured.err
    assert f"cd {display_cwd} && " in captured.err
    assert "$ " not in captured.err
    assert captured.err.index("export JAMSH_FLAG") < captured.err.index("cd ")


def test_display_command_lines_splits_live_header_metadata(tmp_path: Path) -> None:
    lines = subprocess_utils._display_command_lines(
        [Path(sys.executable), "-c", "print('ok')"],
        cwd=tmp_path,
        extra_env={"JAMSH_FLAG": "hello world"},
    )

    assert lines == [
        "export JAMSH_FLAG='hello world'",
        f"cd {shlex.quote(str(tmp_path))}",
        shlex.join([sys.executable, "-c", "print('ok')"]),
    ]


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
        echo=False,
        max_lines=10,
    )

    assert result.stdout == "out\n"
    assert result.stderr == "err\n"


def test_run_live_command_title_is_transient_by_default(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    result = run_live(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        extra_env={"JAMSH_FLAG": "transient"},
    )

    captured = capsys.readouterr()
    assert result.stdout == "ok\n"
    assert "JAMSH_FLAG" not in captured.out
    assert "JAMSH_FLAG" not in captured.err
    assert str(tmp_path) not in captured.out
    assert str(tmp_path) not in captured.err


def test_run_live_accepts_pathlike_command_args() -> None:
    result = run_live(
        [Path(sys.executable), "-c", "print('path arg')"],
        echo=False,
    )

    assert result.stdout == "path arg\n"


def test_run_live_failure_returns_recent_lines_in_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_live(
            [
                sys.executable,
                "-c",
                "import sys; print('one'); print('two'); print('warn', file=sys.stderr); raise SystemExit(9)",
            ],
            echo=False,
            max_lines=2,
        )

    exc = exc_info.value
    assert exc.returncode == 9
    assert exc.output == "one\ntwo\n"
    assert exc.stderr == "warn\n"
    assert "Recent command output" in str(exc)
    assert "stdout:" in str(exc)
    assert "stderr:" in str(exc)
    captured = capsys.readouterr()
    assert "one\n" in captured.out
    assert "two\n" in captured.out
    assert "warn\n" in captured.err


def test_run_live_rejects_env_and_extra_env_together() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        run_live(
            [sys.executable, "-c", "print('x')"],
            env={},
            extra_env={},
        )


def test_run_many_live_returns_results_in_input_order() -> None:
    results = run_many_live(
        [
            [
                sys.executable,
                "-c",
                "import time; time.sleep(0.1); print('first')",
            ],
            [sys.executable, "-c", "print('second')"],
        ],
        max_parallel=2,
        echo=False,
        max_lines=10,
    )

    assert [result.returncode for result in results] == [0, 0]
    assert [result.stdout for result in results] == ["first\n", "second\n"]


def test_run_many_live_command_title_is_transient_by_default(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    results = run_many_live(
        [[sys.executable, "-c", "print('ok')"]],
        cwd=tmp_path,
        extra_env={"JAMSH_FLAG": "transient"},
    )

    captured = capsys.readouterr()
    assert results[0].stdout == "ok\n"
    assert "JAMSH_FLAG" not in captured.out
    assert "JAMSH_FLAG" not in captured.err
    assert str(tmp_path) not in captured.out
    assert str(tmp_path) not in captured.err


def test_run_many_live_accepts_pathlike_command_args() -> None:
    results = run_many_live(
        [[Path(sys.executable), "-c", "print('path arg')"]],
        echo=False,
    )

    assert results[0].stdout == "path arg\n"


def test_run_many_live_failure_raises_first_failed_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_many_live(
            [
                [sys.executable, "-c", "print('ok')"],
                [
                    sys.executable,
                    "-c",
                    "import sys; print('bad'); print('warn', file=sys.stderr); raise SystemExit(5)",
                ],
            ],
            max_parallel=2,
            echo=False,
            max_lines=10,
        )

    exc = exc_info.value
    assert exc.returncode == 5
    assert exc.cmd == [
        sys.executable,
        "-c",
        "import sys; print('bad'); print('warn', file=sys.stderr); raise SystemExit(5)",
    ]
    assert exc.output == "bad\n"
    assert exc.stderr == "warn\n"
    captured = capsys.readouterr()
    assert "bad\n" in captured.out
    assert "warn\n" in captured.err


def test_run_many_live_check_false_returns_failures() -> None:
    results = run_many_live(
        [[sys.executable, "-c", "raise SystemExit(3)"]],
        check=False,
        echo=False,
    )

    assert results[0].returncode == 3


def test_run_many_live_rejects_env_and_extra_env_together() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        run_many_live(
            [[sys.executable, "-c", "print('x')"]],
            env={},
            extra_env={},
        )


def test_run_many_live_rejects_invalid_parallelism() -> None:
    with pytest.raises(ValueError, match="max_parallel"):
        run_many_live([[sys.executable, "-c", "print('x')"]], max_parallel=0)


def test_run_many_live_async_returns_results() -> None:
    results = asyncio.run(
        run_many_live_async(
            [[sys.executable, "-c", "print('async')"]],
            echo=False,
        )
    )

    assert results[0].stdout == "async\n"
