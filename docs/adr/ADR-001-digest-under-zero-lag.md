# ADR-001: Compare Canonical Digests Even When Lag Reads Zero

## Decision

Verify state digests independently of consumer offset lag so out-of-order drops cannot hide behind zero lag.
