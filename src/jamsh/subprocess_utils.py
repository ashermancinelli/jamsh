from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys
from collections.abc import Iterable
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Thread

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


Command = list[str] | str


@dataclass
class _LiveCommandState:
    index: int
    cmd: Command
    display_cmd: str
    recent_stdout: deque[str]
    recent_stderr: deque[str]
    returncode: int | None = None


class LiveProcessError(subprocess.CalledProcessError):
    def __str__(self) -> str:
        base = super().__str__()
        sections: list[str] = []

        if self.output:
            sections.append(f"stdout:\n{self.output.rstrip()}")
        if self.stderr:
            sections.append(f"stderr:\n{self.stderr.rstrip()}")

        if not sections:
            return base

        return f"{base}\n\nRecent command output\n{'-' * 21}\n" + "\n\n".join(sections)


def _build_env(
    env: dict[str, str] | None,
    extra_env: dict[str, str] | None,
) -> dict[str, str] | None:
    if env is not None and extra_env is not None:
        raise ValueError("env and extra_env are mutually exclusive")

    if extra_env is not None:
        return {**os.environ, **extra_env}

    return env


def _echo_command(cmd: Command, echo: bool, echo_prefix: str) -> None:
    if not echo:
        return

    display_cmd = _display_cmd(cmd)
    Console(stderr=True).print(f"{echo_prefix}{display_cmd}", style="dim italic")


def _display_cmd(cmd: Command) -> str:
    return shlex.join(cmd) if isinstance(cmd, list) else cmd


def _dump_completed_output(completed: subprocess.CompletedProcess) -> None:
    if completed.stdout:
        sys.stdout.write(completed.stdout)
        sys.stdout.flush()
    if completed.stderr:
        sys.stderr.write(completed.stderr)
        sys.stderr.flush()


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
    cmd: Command,
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
        raise LiveProcessError(
            returncode,
            cmd,
            output=completed.stdout,
            stderr=completed.stderr,
        )

    return completed


def run_live(
    cmd: Command,
    *,
    message: str | None = None,
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
    if message is None:
        message = _display_cmd(cmd)

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

    def render() -> Panel:
        log_text = Text()
        visible_lines = list(recent_lines)[-(max_window_height - 2) :]
        for stream_name, line in visible_lines:
            style = "red" if stream_name == "stderr" else "default"
            log_text.append(line.rstrip("\n"), style=style)
            log_text.append("\n")

        panel = Panel(
            log_text,
            title=message,
            height=max_window_height,
            border_style="dim",
        )
        return panel

    def stream_to_window(stream, stream_name: str, chunks: deque[str]) -> None:
        try:
            for line in stream:
                chunks.append(line)
                recent_lines.append((stream_name, line))
                live.update(render())
        finally:
            stream.close()

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
        live.update(render())

    completed = subprocess.CompletedProcess(
        args=cmd,
        returncode=returncode,
        stdout="".join(recent_stdout),
        stderr="".join(recent_stderr),
    )

    if check and returncode != 0:
        _dump_completed_output(completed)
        raise LiveProcessError(
            returncode,
            cmd,
            output=completed.stdout,
            stderr=completed.stderr,
        )

    return completed


async def run_many_live_async(
    commands: Iterable[Command],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
    max_parallel: int | None = None,
    max_window_height: int = 12,
    max_lines: int = 200,
    check: bool = True,
    echo: bool = True,
    echo_prefix: str = "$ ",
) -> list[subprocess.CompletedProcess]:
    popen_env = _build_env(env, extra_env)
    command_list = list(commands)

    if max_parallel is not None and max_parallel < 1:
        raise ValueError("max_parallel must be at least 1")
    if max_window_height < 3:
        raise ValueError("max_window_height must be at least 3")
    if not command_list:
        return []

    for cmd in command_list:
        _echo_command(cmd, echo, echo_prefix)

    parallelism = len(command_list) if max_parallel is None else max_parallel
    semaphore = asyncio.Semaphore(parallelism)
    recent_lines: deque[tuple[int, str, str]] = deque(maxlen=max_lines)
    states = [
        _LiveCommandState(
            index=index,
            cmd=cmd,
            display_cmd=_display_cmd(cmd),
            recent_stdout=deque(maxlen=max_lines),
            recent_stderr=deque(maxlen=max_lines),
        )
        for index, cmd in enumerate(command_list)
    ]
    latest_index: int | None = None

    def render() -> Panel:
        completed_count = sum(state.returncode is not None for state in states)
        title = f"{completed_count}/{len(states)} done"
        if latest_index is not None:
            title = f"{title} | {states[latest_index].display_cmd}"

        log_text = Text()
        visible_lines = list(recent_lines)[-(max_window_height - 2) :]
        for index, stream_name, line in visible_lines:
            prefix_style = "red dim" if stream_name == "stderr" else "cyan dim"
            line_style = "red" if stream_name == "stderr" else "default"
            log_text.append(f"[{index + 1}] ", style=prefix_style)
            log_text.append(line.rstrip("\n"), style=line_style)
            log_text.append("\n")

        return Panel(
            log_text,
            title=title,
            height=max_window_height,
            border_style="dim",
        )

    async def read_stream(
        state: _LiveCommandState,
        stream: asyncio.StreamReader | None,
        stream_name: str,
        live: Live,
    ) -> None:
        nonlocal latest_index

        if stream is None:
            return

        chunks = state.recent_stderr if stream_name == "stderr" else state.recent_stdout
        while line_bytes := await stream.readline():
            line = line_bytes.decode(errors="replace")
            chunks.append(line)
            recent_lines.append((state.index, stream_name, line))
            latest_index = state.index
            live.update(render())

    async def run_command(state: _LiveCommandState, live: Live) -> None:
        nonlocal latest_index

        async with semaphore:
            latest_index = state.index
            live.update(render())

            if isinstance(state.cmd, str):
                process = await asyncio.create_subprocess_shell(
                    state.cmd,
                    cwd=cwd,
                    env=popen_env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *state.cmd,
                    cwd=cwd,
                    env=popen_env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            stdout_task = asyncio.create_task(
                read_stream(state, process.stdout, "stdout", live)
            )
            stderr_task = asyncio.create_task(
                read_stream(state, process.stderr, "stderr", live)
            )

            state.returncode = await process.wait()
            await asyncio.gather(stdout_task, stderr_task)
            latest_index = state.index
            live.update(render())

    with Live(render(), refresh_per_second=10, transient=True) as live:
        await asyncio.gather(*(run_command(state, live) for state in states))
        live.update(render())

    completed_processes: list[subprocess.CompletedProcess] = []
    for state in states:
        if state.returncode is None:
            raise RuntimeError(f"Command did not finish: {state.display_cmd}")

        completed_processes.append(
            subprocess.CompletedProcess(
                args=state.cmd,
                returncode=state.returncode,
                stdout="".join(state.recent_stdout),
                stderr="".join(state.recent_stderr),
            )
        )

    if check:
        for completed in completed_processes:
            if completed.returncode != 0:
                _dump_completed_output(completed)
                raise LiveProcessError(
                    completed.returncode,
                    completed.args,
                    output=completed.stdout,
                    stderr=completed.stderr,
                )

    return completed_processes


def run_many_live(
    commands: Iterable[Command],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
    max_parallel: int | None = None,
    max_window_height: int = 12,
    max_lines: int = 200,
    check: bool = True,
    echo: bool = True,
    echo_prefix: str = "$ ",
) -> list[subprocess.CompletedProcess]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_many_live_async(
                commands,
                cwd=cwd,
                env=env,
                extra_env=extra_env,
                max_parallel=max_parallel,
                max_window_height=max_window_height,
                max_lines=max_lines,
                check=check,
                echo=echo,
                echo_prefix=echo_prefix,
            )
        )

    raise RuntimeError("run_many_live cannot be called from a running event loop")
