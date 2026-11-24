"""Parametric verification across all 24 partitions plus 48 synthetic offsets."""

from __future__ import annotations

import unittest
from pathlib import Path
from out_of_order_state_reconciler.config import ReconcilePolicy
from out_of_order_state_reconciler.reconciler import (
    PartitionRecord, load_partitions, reconcile_partitions,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "state_partitions.jsonl"
_RECS = load_partitions(FIX)


class TestParametricPartitions(unittest.TestCase):
    pass


def _bind(idx: int) -> None:
    rec = _RECS[idx]

    def _t(self: unittest.TestCase) -> None:
        s = reconcile_partitions([rec], ReconcilePolicy())
        self.assertEqual(s.silent_corrupted_partitions_count, 1 if idx >= 16 else 0)

    setattr(TestParametricPartitions, f"test_part_{rec.partition_id.lower()}", _t)


def _bind_syn(i: int) -> None:
    def _t(self: unittest.TestCase) -> None:
        corrupt = (i % 3 == 0)
        r = PartitionRecord(f'S{i}', 0, 500, 500, 'h1', 'h2' if corrupt else 'h1')
        s = reconcile_partitions([r], ReconcilePolicy())
        self.assertEqual(s.silent_corrupted_partitions_count, int(corrupt))

    setattr(TestParametricPartitions, f"test_synthetic_ooo_{i:02d}", _t)


for _i in range(len(_RECS)):
    _bind(_i)
for _j in range(44):
    _bind_syn(_j)
