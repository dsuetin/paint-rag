#!/usr/bin/env python
"""CLI: сравнение двух итераций Customer Golden Questions.

Позволяет либо:
  * автоматически сравнить ПОСЛЕДНИЙ run с предыдущим;
  * сравнить два конкретных номера итераций.

Запуск::

    ./.venv/bin/python evaluation/compare_customer_questions.py
    ./.venv/bin/python evaluation/compare_customer_questions.py 1 3
    ./.venv/bin/python evaluation/compare_customer_questions.py --save
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from evaluation.comparison import (  # noqa: E402
    compare_runs,
    format_comparison,
)
from evaluation.questions import DEFAULT_RUNS_DIR  # noqa: E402
from evaluation.runner import (  # noqa: E402
    list_iterations,
    load_run,
    load_latest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two Customer Golden Questions runs."
    )
    parser.add_argument(
        "iterations",
        nargs="*",
        type=int,
        help="Two iterations to compare (e.g. 1 3). If omitted — latest vs previous.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Also write a JSON report to evaluation/comparisons/",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
    )
    args = parser.parse_args(argv)

    iters = list_iterations(args.runs_dir)
    if not iters:
        print("No runs found yet. Run `run_customer_questions.py` first.")
        return 1

    if len(args.iterations) == 2:
        prev_it, current_it = int(args.iterations[0]), int(args.iterations[1])
        if prev_it not in iters or current_it not in iters:
            available = ", ".join(str(i) for i in iters)
            print(
                f"Requested iterations not both present. Available: {available}"
            )
            return 1
    elif len(args.iterations) == 0:
        if len(iters) < 2:
            print(
                "Only one run exists. Use `1 1` or produce a second run."
            )
            prev_it = current_it = iters[-1]
        else:
            prev_it = iters[-2]
            current_it = iters[-1]
    else:
        parser.error("pass either 0 or 2 iterations")

    try:
        prev = load_run(runs_dir=args.runs_dir, iteration=prev_it)
        current = load_run(runs_dir=args.runs_dir, iteration=current_it)
    except FileNotFoundError as exc:
        print(f"run not found: {exc}")
        return 1

    result = compare_runs(prev, current)
    print(format_comparison(result))

    if args.save:
        out_dir = Path(__file__).resolve().parent / "comparisons"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"compare_{prev_it:03d}_{current_it:03d}.json"
        out.write_text(
            json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nSaved comparison report: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
