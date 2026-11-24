"""Deterministic out-of-order state reconciliation experiments."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from out_of_order_state_reconciler.config import load_policy  # noqa: E402
from out_of_order_state_reconciler.reconciler import (  # noqa: E402
    load_partitions,
    reconcile_partitions,
)


def run_all_experiments(repo_root: Path | None = None) -> dict[str, object]:
    """Execute deterministic zero-lag corruption experiments."""
    root = repo_root or ROOT_DIR
    out_dir = root / "docs" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    pol = load_policy(root / "policy" / "reconcile_policy.json")
    recs = load_partitions(root / "fixtures" / "state_partitions.jsonl")
    full = reconcile_partitions(recs, pol)
    exp1 = {
        "total_partitions": full.total_partitions,
        "zero_lag_partitions_count": full.zero_lag_partitions_count,
        "count_mismatches_count": full.count_mismatches_count,
        "silent_corrupted_partitions_count": full.silent_corrupted_partitions_count,
        "clean_partitions_count": full.clean_partitions_count,
        "resolution_floor_pct": full.resolution_floor_pct,
    }
    (out_dir / "exp1_zero_lag_corruption.json").write_text(
        json.dumps(exp1, indent=2) + "\n", encoding="utf-8"
    )
    return {"exp1": exp1}


def main() -> None:
    e1 = run_all_experiments()["exp1"]
    print(
        f"Exp1 | partitions={e1['total_partitions']} | zero_lag={e1['zero_lag_partitions_count']} "
        f"| silent_corrupted={e1['silent_corrupted_partitions_count']}"
    )


if __name__ == "__main__":
    main()
