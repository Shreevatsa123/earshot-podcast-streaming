# AI tool usage log (cited in the final slides, per course policy)

| Date | Member | Tool | Used for |
|---|---|---|---|
| 2026-09-27 | Team | Kiro (Claude) | Brainstorming the topic; drafting the BRD, CONTEXT.md, TRACKER.md and agent instructions |
| 2026-10-19 | M6 | Kiro (Claude) | M6-01 repo skeleton: CDK app and stacks, stub constructs, Makefile, shared Lambda helpers, unit tests |
| 2026-10-19 | M6 | Kiro (Claude) | M6-04 CI workflow (lint, tests, synth) and tracker cleanup |
| 2026-11-03 | M4 | Copilot SDK in VS Code | M4-01 processor progress handling and unit tests |
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
| 2026-11-08 | M6 | Kiro (Claude) | Shared-account rule for members whose own AWS account can't run Earshot |
| 2026-11-08 | M4 | Copilot SDK in VS Code | M4-01 SQS processor decoding, conditional progress tests, and message-level transient failure reporting |
| 2026-11-08 | M4 | Copilot SDK in VS Code | M4-02 atomic trending play deduplication and unit tests |
| 2026-11-09 | M4 | Copilot SDK in VS Code | M4-03 QoE minute-window deduplication, threshold SNS alert and unit tests |
| 2026-11-20 | M5 | Claude Code (Claude Opus 5.5) | M5-08 Glue table switch to gzipped JSON Lines, JSON test lake for the SQL tests, unit tests |
| 2026-11-16 | M3 | Claude (Claude Opus 5.5) | M3-01: event validation (`shared/validate.py`) and its unit tests |
| 2026-11-16 | M3 | Claude (Claude Opus 5.5) | M3-04: generating `contracts/samples/events.jsonl` and its fixture test |
| 2026-11-16 | M3 | Claude (Claude Opus 5.5) | M3-03: SNS events topic construct |
| 2026-11-16 | M3 | Claude (Claude Opus 5.5) | M3-02: ingest Lambda, ingest construct and unit tests |
| 2026-11-16 | M3 | Claude (Claude Opus 5.5) | M3-05: simulator `generate` + `replay --direct` and unit tests |
| 2026-11-16 | M3 | Claude (Claude Opus 5.5) | M3-06: simulator `run` (Cognito auth, rate control, retries, run report) and unit tests |
| 2026-11-16 | M3 | Claude (Claude Opus 5.5) | M3-08: simulator `buffer-storm` mode and unit test |
| 2026-11-16 | M3 | Claude (Claude Opus 5.5) | M3-07: simulator EC2 construct |
| 2026-11-24 | M1 | Kiro (Claude) | M1-02 Cognito auth construct (user pool, groups, web and sim clients, managed login domain and style, SSM params) and unit tests |
| 2026-11-24 | M2 | Claude Code (Claude Opus 5.5) | M2-03 `seed_catalog.py` (catalog → DynamoDB items) and moto tests |
| 2026-11-24 | M2 | Claude Code (Claude Opus 5.5) | M2-04 API construct (HTTP API, JWT authorizer, routes, CORS, throttling), unit tests, stage checks |
| 2026-11-24 | M2 | Claude Code (Claude Opus 5.5) | M2-05 API read routes (router, hydration, identity rules), moto tests, stage checks |
| 2026-11-24 | M2 | Claude Code (Claude Opus 5.5) | M2-06 `/home` (rows, fallback chain, short-timeout recs client, flags cache, HomeFallback metric), tests, S8 check in `sankha` |
| 2026-11-07 | M1 | Kiro (Claude) | M1-01 web scaffold: Vite + React + TS app, runtime `config.json` loader, `VITE_USE_MOCKS` mode against `contracts/samples`, purple theme adapted from the team's Nocturne design, Home page, show dialog, search and player dock |
| 2026-11-24 | M6 | Kiro (Claude) | M6-04 CI upkeep: alert email test counts only email subscriptions, `duckdb` in dev requirements, `archiver` in ruff first-party |
| 2026-11-25 | M6 | Kiro (Claude) | M6-03 re-run in `prod` (fixing the Codespace venv) and the tracker update |
| 2026-11-25 | M1 | Kiro (Claude) | M1-03 `create_sim_bot.py` (sim-bot Cognito user, optional generated SSM password) and unit tests |
| 2026-11-25 | M6 | Kiro (Claude) | M6-07 acceptance harness (`tests/acceptance/`, runner, results writer, API client), its unit tests and the `docs/results.md` template |
| 2026-11-25 | M6 | Kiro (Claude) | M6-08 cost check script, its unit tests, the S10 acceptance check and the two retain-guard synth tests |
| 2026-11-25 | M6 | Kiro (Claude) | M6-05 monitoring constructs (dashboard, prod alarms in base and pipeline) and their synth tests |
| 2026-11-26 | M2 | Claude Code (Claude Opus 5.5) | M2-09 S8 acceptance check (`s8_degradation.py`) and its unit tests |
| 2026-11-26 | M2 | Claude Code (Claude Opus 5.5) | Full recheck of the M2 work (tests, live routes in `sankha` and `prod`); §7.1 note on API Gateway's own error bodies |
| 2026-11-25 | M6 | Kiro (Claude) | Contract status approval check (`.github/workflows/contract-status.yml`) and undoing the early G0-1 freeze |
| 2026-11-25 | M1 | Kiro (Claude) | Own-stage setup for `tanishqa` (budget, admin user, CLI, bootstrap, deploy) and the M1-02/M1-03 stage checks |
| 2026-11-25 | M1 | Kiro (Claude) | M1-04 web construct (bucket, CloudFront with OAC, SPA routing, config.json deployment) and unit tests |
| 2026-11-26 | M6 | Kiro (Claude) | M6-06 Locust `/home` load test, its helpers and runbook, the S6 acceptance check and their unit tests |
