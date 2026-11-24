"""Property, boundary, and CLI tests for out-of-order-state-reconciler."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from out_of_order_state_reconciler.cli import main as cli_main, render_table
from out_of_order_state_reconciler.config import ReconcilePolicy, load_policy
from out_of_order_state_reconciler.reconciler import (
    PartitionRecord,
    load_partitions,
    reconcile_partitions,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "state_partitions.jsonl"
POL = ROOT / "policy" / "reconcile_policy.json"


class TestReconcilerProperties(unittest.TestCase):
    def test_policies_validate_and_reject_invalid_values(self) -> None:
        ReconcilePolicy().validate()
        self.assertEqual(load_policy(POL).max_allowed_corrupted_partitions, 0)
        self.assertEqual(load_policy(None).max_allowed_corrupted_partitions, 0)
        with self.assertRaises(FileNotFoundError):
            load_policy(Path("/tmp/missing_rpol_999.json"))
        with self.assertRaises(ValueError):
            ReconcilePolicy(max_allowed_corrupted_partitions=-1).validate()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "p.json"
            p.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_policy(p)

    def test_loader_boundary_checks_and_null_digest_war_story(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_partitions(Path("/tmp/missing_sfix_999.jsonl"))
        with tempfile.TemporaryDirectory() as tmp:
            e = Path(tmp) / "e.jsonl"
            e.write_text("\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_partitions(e)
            b = Path(tmp) / "b.jsonl"
            b.write_text("[]\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_partitions(b)
            n = Path(tmp) / "n.jsonl"
            row = {
                "partition_id": "PN",
                "reported_lag_events": 0,
                "expected_row_count": 10,
                "actual_row_count": 10,
                "expected_digest": None,
                "actual_digest": "x",
            }
            n.write_text(json.dumps(row) + "\n", encoding="utf-8")
            s = reconcile_partitions(load_partitions(n), ReconcilePolicy())
            self.assertEqual(s.silent_corrupted_partitions_count, 1)

    def test_committed_fixture_exposes_eight_zero_lag_corruptions(self) -> None:
        s = reconcile_partitions(load_partitions(FIX), load_policy(POL))
        self.assertEqual(s.total_partitions, 24)
        self.assertEqual(s.zero_lag_partitions_count, 24)
        self.assertEqual(s.count_mismatches_count, 0)
        self.assertEqual(s.silent_corrupted_partitions_count, 8)
        self.assertEqual(s.clean_partitions_count, 16)
        self.assertAlmostEqual(s.resolution_floor_pct, 4.17)
        self.assertFalse(s.gate_passed)

    def test_lagged_mismatch_classified_separately(self) -> None:
        r = PartitionRecord("P_LAG", 50, 1000, 950, "d1", "d2")
        s = reconcile_partitions([r], ReconcilePolicy())
        self.assertEqual(s.silent_corrupted_partitions_count, 0)
        self.assertEqual(s.verdicts[0].status, "STATE_MISMATCH_LAGGED")
        self.assertTrue(s.gate_passed)

    def test_empty_records_rejected(self) -> None:
        with self.assertRaises(ValueError):
            reconcile_partitions([], ReconcilePolicy())

    def test_cli_exit_codes_and_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            oj = Path(tmp) / "o.json"
            rc = cli_main([
                "reconcile", "--fixture", str(FIX), "--policy", str(POL), "--out", str(oj)
            ])
            self.assertEqual(rc, 1)
            pf = Path(tmp) / "p.json"
            pf.write_text(json.dumps({"max_allowed_corrupted_partitions": 50}), encoding="utf-8")
            rc2 = cli_main([
                "reconcile", "--fixture", str(FIX), "--policy", str(pf),
                "--out", str(oj), "--json-only",
            ])
            self.assertEqual(rc2, 0)
        self.assertEqual(cli_main(["reconcile", "--fixture", "/tmp/missing_s_888.jsonl"]), 2)
        self.assertEqual(cli_main(["reconcile", "--max-rows", "abc"]), 2)
        self.assertEqual(cli_main(["--help"]), 0)
        s = reconcile_partitions(load_partitions(FIX), load_policy(POL))
        self.assertIn("SILENT_CORRUPT_ZERO_LAG", render_table(s))
