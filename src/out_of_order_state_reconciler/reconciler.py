"""Deterministic partition watermark, row-count, and canonical digest reconciler."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from out_of_order_state_reconciler.config import ReconcilePolicy


@dataclass(frozen=True)
class PartitionRecord:
    """Single partition snapshot pairing lag watermark, row counts, and digests."""

    partition_id: str
    reported_lag_events: int
    expected_row_count: int
    actual_row_count: int
    expected_digest: str
    actual_digest: str


@dataclass(frozen=True)
class PartitionVerdict:
    """Per-partition verdict distinguishing zero-lag silent corruption."""

    partition_id: str
    reported_lag_events: int
    count_matches: bool
    digest_matches: bool
    silent_corruption: bool
    status: str


@dataclass(frozen=True)
class ReconcileSummary:
    """Aggregated reconciliation report across all partitions."""

    total_partitions: int
    zero_lag_partitions_count: int
    count_mismatches_count: int
    digest_mismatches_count: int
    silent_corrupted_partitions_count: int
    clean_partitions_count: int
    resolution_floor_pct: float
    gate_passed: bool
    verdicts: list[PartitionVerdict] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Serialize summary to plain JSON dictionary."""
        return {
            "total_partitions": self.total_partitions,
            "zero_lag_partitions_count": self.zero_lag_partitions_count,
            "count_mismatches_count": self.count_mismatches_count,
            "digest_mismatches_count": self.digest_mismatches_count,
            "silent_corrupted_partitions_count": self.silent_corrupted_partitions_count,
            "clean_partitions_count": self.clean_partitions_count,
            "resolution_floor_pct": self.resolution_floor_pct,
            "gate_passed": self.gate_passed,
            "verdicts": [
                {
                    "partition_id": v.partition_id,
                    "reported_lag_events": v.reported_lag_events,
                    "count_matches": v.count_matches,
                    "digest_matches": v.digest_matches,
                    "silent_corruption": v.silent_corruption,
                    "status": v.status,
                }
                for v in self.verdicts
            ],
        }


def load_partitions(path: str | Path) -> list[PartitionRecord]:
    """Load JSONL partition snapshots with explicit validation."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"State fixture not found: {p}")
    out: list[PartitionRecord] = []
    for ln_no, raw_ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        s = raw_ln.strip()
        if not s:
            continue
        r = json.loads(s)
        if not isinstance(r, dict):
            raise ValueError(f"Line {ln_no} must be a JSON object")
        exp_d = "" if r.get("expected_digest") is None else str(r["expected_digest"])
        act_d = "" if r.get("actual_digest") is None else str(r["actual_digest"])
        out.append(
            PartitionRecord(
                partition_id=str(r["partition_id"]),
                reported_lag_events=int(r["reported_lag_events"]),
                expected_row_count=int(r["expected_row_count"]),
                actual_row_count=int(r["actual_row_count"]),
                expected_digest=exp_d,
                actual_digest=act_d,
            )
        )
    if not out:
        raise ValueError(f"No partition records in {p}")
    return out


def reconcile_partitions(
    records: list[PartitionRecord], policy: ReconcilePolicy
) -> ReconcileSummary:
    """Compare digests and counts regardless of reported zero lag."""
    if not records:
        raise ValueError("Cannot reconcile empty partition list")
    policy.validate()
    zlag = c_mm = d_mm = corr = clean = 0
    verdicts: list[PartitionVerdict] = []
    for r in records:
        lag0 = r.reported_lag_events == 0
        c_ok = r.expected_row_count == r.actual_row_count
        d_ok = r.expected_digest == r.actual_digest
        zlag += int(lag0)
        c_mm += int(not c_ok)
        d_mm += int(not d_ok)
        silent = bool(lag0 and (not c_ok or not d_ok))
        if silent:
            corr += 1
            st = "SILENT_CORRUPT_ZERO_LAG"
        elif c_ok and d_ok:
            clean += 1
            st = "RECONCILED_OK"
        else:
            st = "STATE_MISMATCH_LAGGED"
        verdicts.append(
            PartitionVerdict(r.partition_id, r.reported_lag_events, c_ok, d_ok, silent, st)
        )
    n = len(verdicts)
    return ReconcileSummary(
        total_partitions=n,
        zero_lag_partitions_count=zlag,
        count_mismatches_count=c_mm,
        digest_mismatches_count=d_mm,
        silent_corrupted_partitions_count=corr,
        clean_partitions_count=clean,
        resolution_floor_pct=round((1.0 / n) * 100.0, 2),
        gate_passed=corr <= policy.max_allowed_corrupted_partitions,
        verdicts=verdicts,
    )
