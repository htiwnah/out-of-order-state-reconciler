CREATE TABLE IF NOT EXISTS partition_verdicts (partition_id TEXT PRIMARY KEY, lag INTEGER, silent_corrupt INTEGER);
SELECT COUNT(*) FROM partition_verdicts WHERE silent_corrupt = 1;
