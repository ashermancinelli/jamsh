from __future__ import annotations

import sys

from .subprocess_utils import run_live
from .subprocess_utils import run_many_live


def main() -> None:
    print("jamsh demo: live subprocess output\n")

    print("1. live window with command title")
    run_live(
        [
            sys.executable,
            "-c",
            "import sys, time\nfor i in range(15):\n print(f'out {i}', flush=True)\n if i % 4 == 0: print(f'warn {i}', file=sys.stderr, flush=True)\n time.sleep(0.2)",
        ],
        max_window_height=10,
        max_lines=20,
    )

    print("\n2. parallel live window with current command title")
    run_many_live(
        [
            [
                sys.executable,
                "-c",
                "import time\nfor i in range(8):\n print(f'alpha {i}', flush=True)\n time.sleep(0.4)",
            ],
            [
                sys.executable,
                "-c",
                "import sys, time\nfor i in range(8):\n print(f'beta {i}', file=sys.stderr, flush=True)\n time.sleep(0.5)",
            ],
            [
                sys.executable,
                "-c",
                "import time\nfor i in range(8):\n print(f'gamma {i}', flush=True)\n time.sleep(0.3)",
            ],
        ],
        max_parallel=3,
        max_window_height=10,
        max_lines=40,
    )


if __name__ == "__main__":
    main()
