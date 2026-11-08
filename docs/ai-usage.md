# AI tool usage log (cited in the final slides, per course policy)

| Date | Member | Tool | Used for |
|---|---|---|---|
| 2026-09-27 | Team | Kiro (Claude) | Brainstorming the topic; drafting the BRD, CONTEXT.md, TRACKER.md and agent instructions |
| 2026-10-19 | M6 | Kiro (Claude) | M6-01 repo skeleton: CDK app and stacks, stub constructs, Makefile, shared Lambda helpers, unit tests |
| 2026-10-19 | M6 | Kiro (Claude) | M6-04 CI workflow (lint, tests, synth) and tracker cleanup |
| 2026-11-04 | M5 | Claude Code (Claude Opus 5.5) | M5-01 lake construct: Glue database and `events` table with partition projection, Athena workgroup, unit tests |
| 2026-11-07 | M6 | Kiro (Claude) | M6-02: shared account setup steps (budget, IAM group and access-key policy), prod deploy rules |
| 2026-11-07 | M5 | Claude Code (Claude Opus 5.5) | M5-03 Athena SQL (`count_events`, `popular`, `reconcile_trending`, `recs`), DuckDB test harness and tests |
| 2026-11-07 | M6 | Kiro (Claude) | M6-03: service-check stack, account limit check, tests |
| 2026-11-07 | M2 | Claude Code (Claude Opus 5.5) | M2-01 catalog script (Podcast Index → `catalog.json`), catalog checks, unit tests |
| 2026-11-07 | M2 | Claude Code (Claude Opus 5.5) | M2-08 `set_flag.py` (show, change and reset the feature flags), unit tests |
| 2026-11-07 | M2 | Claude Code (Claude Opus 5.5) | M2-07 sample API responses generated from the catalog, and a test that checks them against CONTEXT §7 |
| 2026-11-07 | M2 | Claude Code (Claude Opus 5.5) | M2-02 picking the 20 FEATURED episodes, `check_featured.py` playability check |
| 2026-11-08 | M6 | Kiro (Claude) | M6-03 follow-up: diagnosing the Free plan block on Kinesis and Firehose, updated service check (SNS → SQS → Lambda) |
| 2026-11-08 | M6 | Kiro (Claude) | Contract change replacing Kinesis and Firehose with an SNS topic and two SQS queues: CONTEXT, tracker, stubs, stacks, names |
