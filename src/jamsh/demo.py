from __future__ import annotations

import sys

from .subprocess_utils import run_live
from .subprocess_utils import run


def main() -> None:
    print("jamsh demo: streaming subprocess output\n")

    print("1. stdout streaming")
    run(
        [
            sys.executable,
            "-c",
            "import time; print('hello from child'); time.sleep(1); print('done')",
        ]
    )

    print("\n2. stdout and stderr streaming")
    run(
        [
            sys.executable,
            "-c",
            "import sys, time; print('stdout: start'); time.sleep(1); print('stderr: warning', file=sys.stderr); time.sleep(1); print('stdout: end')",
        ]
    )

    print("\n3. extra_env support")
    run(
        [sys.executable, "-c", "import os; print(f\"DEMO_FLAG={os.environ['DEMO_FLAG']}\")"],
        extra_env={"DEMO_FLAG": "enabled"},
    )

    print("\n4. rich live window")
    run_live(
        [
            sys.executable,
            "-c",
            "import sys, time; "
            "print('step 1'); "
            "time.sleep(1); "
            "print('step 2'); "
            "time.sleep(1); "
            "print('note: still working', file=sys.stderr); "
            "time.sleep(1); "
            "print('step 3')",
        ],
        message="Running live demo",
        max_window_height=10,
        max_lines=20,
    )


if __name__ == "__main__":
    main()
