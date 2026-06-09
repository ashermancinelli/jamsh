from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from threading import Thread


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
    if env is not None and extra_env is not None:
        raise ValueError("env and extra_env are mutually exclusive")

    if extra_env is not None:
        popen_env = {**os.environ, **extra_env}
    else:
        popen_env = env

    display_cmd = shlex.join(cmd) if isinstance(cmd, list) else cmd
    if echo:
        try:
            from rich.console import Console

            Console(stderr=True).print(f"{echo_prefix}{display_cmd}", style="dim italic")
        except ImportError:
            print(f"{echo_prefix}{display_cmd}", file=sys.stderr)

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
