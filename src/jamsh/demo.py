from __future__ import annotations

import sys
from pathlib import Path

from .subprocess_utils import run
from .subprocess_utils import run_live
from .subprocess_utils import run_many_live


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
        [
            sys.executable,
            "-c",
            "import os; print(f\"DEMO_FLAG={os.environ['DEMO_FLAG']}\")",
        ],
        extra_env={"DEMO_FLAG": "enabled"},
    )

    print("\n4. rich live window with transient command header")
    run_live(
        ["bash", "-c", "for i in `seq 1 15`; do echo $i; sleep 0.2; done"],
        cwd=Path.cwd(),
        extra_env={"DEMO_STAGE": "single-live"},
        max_window_height=10,
        max_lines=20,
    )

    print("\n5. rich parallel live window with transient command header")
    run_many_live(
        [
            [
                sys.executable,
                "-c",
                "import time\nfor i in range(8):\n print(f'alpha {i}', flush=True)\n time.sleep(0.15)",
            ],
            [
                sys.executable,
                "-c",
                "import sys, time\nfor i in range(8):\n print(f'beta {i}', file=sys.stderr, flush=True)\n time.sleep(0.2)",
            ],
            [
                sys.executable,
                "-c",
                "import time\nfor i in range(8):\n print(f'gamma {i}', flush=True)\n time.sleep(0.1)",
            ],
        ],
        cwd=Path.cwd(),
        extra_env={"DEMO_STAGE": "parallel-live"},
        max_parallel=3,
        max_window_height=10,
        max_lines=40,
    )


if __name__ == "__main__":
    main()
