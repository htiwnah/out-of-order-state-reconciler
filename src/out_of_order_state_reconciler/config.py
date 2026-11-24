"""Explicit policy loader for silent partition corruption budgets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReconcilePolicy:
    """Immutable state reconciliation acceptance policy."""

    policy_version: str = "1.0"
    max_allowed_corrupted_partitions: int = 0
    fixture_path: str = "fixtures/state_partitions.jsonl"

    def validate(self) -> None:
        """Reject negative partition corruption budgets."""
        if self.max_allowed_corrupted_partitions < 0:
            raise ValueError("max_allowed_corrupted_partitions must be >= 0")


def load_policy(path: str | Path | None = None) -> ReconcilePolicy:
    """Load ReconcilePolicy from JSON or return validated defaults."""
    if path is None:
        cfg = ReconcilePolicy()
        cfg.validate()
        return cfg
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Policy not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Policy must be a JSON object")
    cfg = ReconcilePolicy(**raw)
    cfg.validate()
    return cfg
