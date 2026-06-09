from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections import deque
from pathlib import Path
from threading import Thread


def _build_env(
    env: dict[str, str] | None,
    extra_env: dict[str, str] | None,
) -> dict[str, str] | None:
    if env is not None and extra_env is not None:
        raise ValueError("env and extra_env are mutually exclusive")

    if extra_env is not None:
        return {**os.environ, **extra_env}

    return env


def _echo_command(cmd: list[str] | str, echo: bool, echo_prefix: str) -> None:
    if not echo:
        return

    display_cmd = shlex.join(cmd) if isinstance(cmd, list) else cmd
    try:
        from rich.console import Console

        Console(stderr=True).print(f"{echo_prefix}{display_cmd}", style="dim italic")
    except ImportError:
        print(f"{echo_prefix}{display_cmd}", file=sys.stderr)


def _stream_lines(stream, target, chunks: list[str] | None) -> None:
    try:
        for line in stream:
            target.write(line)
            target.flush()
            if chunks is not None:
                chunks.append(line)
    finally:
        stream.close()


def run(
    cmd: list[str] | str,
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
    capture: bool = False,
    check: bool = True,
    echo: bool = True,
    echo_prefix: str = "$ ",
) -> subprocess.CompletedProcess:
    popen_env = _build_env(env, extra_env)
    _echo_command(cmd, echo, echo_prefix)

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=popen_env,
        shell=isinstance(cmd, str),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stdout_chunks = [] if capture else None
    stderr_chunks = [] if capture else None

    stdout_thread = Thread(
        target=_stream_lines,
        args=(process.stdout, sys.stdout, stdout_chunks),
        daemon=True,
    )
    stderr_thread = Thread(
        target=_stream_lines,
        args=(process.stderr, sys.stderr, stderr_chunks),
        daemon=True,
    )

    stdout_thread.start()
    stderr_thread.start()

    returncode = process.wait()

    stdout_thread.join()
    stderr_thread.join()

    completed = subprocess.CompletedProcess(
        args=cmd,
        returncode=returncode,
        stdout=None if stdout_chunks is None else "".join(stdout_chunks),
        stderr=None if stderr_chunks is None else "".join(stderr_chunks),
    )

    if check and returncode != 0:
        raise subprocess.CalledProcessError(
            returncode,
            cmd,
            output=completed.stdout,
            stderr=completed.stderr,
        )

    return completed


def run_live(
    cmd: list[str] | str,
    *,
    message: str,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
    max_window_height: int = 12,
    max_lines: int = 200,
    check: bool = True,
    echo: bool = True,
    echo_prefix: str = "$ ",
) -> subprocess.CompletedProcess:
    popen_env = _build_env(env, extra_env)

    from rich.console import Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn
    from rich.progress import Progress
    from rich.progress import SpinnerColumn
    from rich.progress import TextColumn
    from rich.text import Text

    _echo_command(cmd, echo, echo_prefix)

    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=popen_env,
        shell=isinstance(cmd, str),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    recent_stdout: deque[str] = deque(maxlen=max_lines)
    recent_stderr: deque[str] = deque(maxlen=max_lines)
    recent_lines: deque[tuple[str, str]] = deque(maxlen=max_lines)

    def render() -> Group:
        log_text = Text()
        for stream_name, line in recent_lines:
            style = "red" if stream_name == "stderr" else "default"
            log_text.append(line.rstrip("\n"), style=style)
            log_text.append("\n")

        panel = Panel(
            log_text,
            title="Process Output",
            height=max_window_height,
            border_style="dim",
        )
        return Group(panel, progress)

    def stream_to_window(stream, stream_name: str, chunks: deque[str]) -> None:
        try:
            for line in stream:
                chunks.append(line)
                recent_lines.append((stream_name, line))
                live.update(render())
        finally:
            stream.close()

    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(bar_width=None),
        transient=True,
    )
    task_id = progress.add_task(message, total=None)

    with Live(render(), refresh_per_second=10, transient=True) as live:
        stdout_thread = Thread(
            target=stream_to_window,
            args=(process.stdout, "stdout", recent_stdout),
            daemon=True,
        )
        stderr_thread = Thread(
            target=stream_to_window,
            args=(process.stderr, "stderr", recent_stderr),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        returncode = process.wait()

        stdout_thread.join()
        stderr_thread.join()
        progress.update(task_id, completed=1)
        live.update(render())

    completed = subprocess.CompletedProcess(
        args=cmd,
        returncode=returncode,
        stdout="".join(recent_stdout),
        stderr="".join(recent_stderr),
    )

    if check and returncode != 0:
        raise subprocess.CalledProcessError(
            returncode,
            cmd,
            output=completed.stdout,
            stderr=completed.stderr,
        )

    return completed
