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
        ["bash", "-c", "for i in `seq 1 15`; do echo $i; sleep 0.2; done"],
        message="Running live demo",
        max_window_height=10,
        max_lines=20,
    )


if __name__ == "__main__":
    main()
