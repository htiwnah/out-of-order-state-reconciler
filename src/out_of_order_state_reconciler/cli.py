"""CLI for out-of-order-state-reconciler with explicit 0/1/2 exit codes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from out_of_order_state_reconciler.config import load_policy
from out_of_order_state_reconciler.reconciler import (
    ReconcileSummary,
    load_partitions,
    reconcile_partitions,
)


def render_table(s: ReconcileSummary, max_rows: int = 12) -> str:
    """Render scannable table surfacing zero-lag digest mismatches."""
    hdr = f"{'PartID':<8} {'Lag':>5} {'CntOK':<5} {'DigOK':<5} {'Status'}"
    lines = [
        "Out-of-Order State Reconciler: Lag Watermarks vs Canonical Digests",
        (
            f"Partitions: {s.total_partitions} | Zero-Lag: {s.zero_lag_partitions_count} | "
            f"Count Mismatches: {s.count_mismatches_count} | "
            f"Silent Corrupted: {s.silent_corrupted_partitions_count}"
        ),
        hdr,
        "-" * len(hdr),
    ]
    ordered = sorted(s.verdicts, key=lambda v: (0 if v.silent_corruption else 1, v.partition_id))
    for v in ordered[:max_rows]:
        lines.append(
            f"{v.partition_id:<8} {v.reported_lag_events:>5} {str(v.count_matches):<5} "
            f"{str(v.digest_matches):<5} {v.status}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Execute CLI and return 0 (pass), 1 (answered no), or 2 (error)."""
    p = argparse.ArgumentParser(prog="state-reconcile")
    sub = p.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("reconcile")
    rp.add_argument("--fixture", default="fixtures/state_partitions.jsonl")
    rp.add_argument("--policy", default=None)
    rp.add_argument("--out", default="reports/reconcile_audit.json")
    rp.add_argument("--max-rows", type=int, default=12)
    rp.add_argument("--json-only", action="store_true")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        pol = load_policy(args.policy)
        s = reconcile_partitions(load_partitions(args.fixture), pol)
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(s.to_dict(), indent=2) + "\n", encoding="utf-8")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError, TypeError) as exc:
        sys.stderr.write(f"Reconcile input error: {exc}\n")
        return 2
    if args.json_only:
        sys.stdout.write(json.dumps(s.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(render_table(s, max_rows=args.max_rows) + "\n")
    return 0 if s.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
