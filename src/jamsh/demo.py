from __future__ import annotations

import sys

from .subprocess_utils import run


def main() -> None:
    print("jamsh demo: streaming subprocess output\n")

    print("1. stdout streaming")
    run(
        [
            sys.executable,
            "-c",
            "import time; print('hello from child'); time.sleep(0.1); print('done')",
        ]
    )

    print("\n2. stdout and stderr streaming")
    run(
        [
            sys.executable,
            "-c",
            "import sys, time; print('stdout: start'); time.sleep(0.1); print('stderr: warning', file=sys.stderr); time.sleep(0.1); print('stdout: end')",
        ]
    )

    print("\n3. extra_env support")
    run(
        [sys.executable, "-c", "import os; print(f\"DEMO_FLAG={os.environ['DEMO_FLAG']}\")"],
        extra_env={"DEMO_FLAG": "enabled"},
    )


if __name__ == "__main__":
    main()
