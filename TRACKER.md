# Earshot — Tracker (living)

**Specs for every task are in `CONTEXT.md` (§ numbers below).** This file says *what* is being built, *who* owns it, *what it depends on*, and *where it stands*.

## How to update

- **Status values:** `todo` · `doing` · `review` (PR open) · `done` (merged + verified in your stage) · `blocked` (say who you're waiting on in Notes, and message them in the group chat).
- Update your row **in the same PR** as the work: Status, PR link, Notes. AI agents do this automatically (see `AGENTS.md`).
- **Start a task only when everything in "Depends on" is `done`.**
  - A *(soft)* dependency means you can start using fixtures and mocks; finish the connection when the real thing lands.
- Anyone may **add** tasks (next free ID in your section). Only the owner or M6 marks a task `done`.
- **CI** (GitHub Actions) runs lint, tests and synth on every PR. Merge only when it shows ✅.
- A **gate** is reached when all its items are `done`. M6 then ticks it and runs the integration check in `prod`.

## Team

| ID | Role | Name | GitHub | Stage name | Budgets set | Tools installed | Base deployed in own account |
|---|---|---|---|---|---|---|---|
| M1 | Frontend & Auth | | | | ☐ | ☐ | ☐ |
| M2 | API & Catalog | Sankha | SankhaS | `sankha` | ☑ | ☑ | ☐ |
| M3 | Ingest & Simulator | | | | ☐ | ☐ | ☐ |
| M4 | Real-time Processing | | | | ☐ | ☐ | ☐ |
| M5 | Data Lake & Recommendations | | | | ☐ | ☐ | ☐ |
| M6 | Platform, Monitoring & Testing | | | | ☐ | ☐ | ☐ |
| — | **Shared `prod` account** (owned by M6) | | | `prod` | ☑ | — | ☑ |

This repo is **public**: don't put AWS account IDs, emails or keys in it.

**Personal setup (everyone):**
- AWS account in us-east-1, created after Jun 8, 2026. If your account can't run Earshot (e.g. it can't use us-east-1), deploy your own stage in the shared account instead (CONTEXT §5, prod rule 4).
- **Budgets alerts at $5 and $20 before deploying anything.**
- MFA on root, plus an admin IAM user.
- Install Python 3.12, Node 22+, AWS CLI v2, CDK v2, Git, or just use GitHub Codespaces (README).
- Read `CONTEXT.md`.
- **Shared `prod` account:** sign in with the login M6 sent you, create an access key, and run `aws configure --profile earshot-prod`. Follow the prod rules in CONTEXT §5.

## Fixed course deadlines (from the syllabus, not a plan)

| Deliverable | Due | Should be reached before |
|---|---|---|
| Status update | Nov 8, 2026 | Gate **G3** |
| Presentation slides | Dec 6, 2026 | Gate **G6** |
| 15-min presentation + live demo | Dec 7–8, 2026 | Demo runbook |
| Peer evaluations (each teammate) | Dec 13, 2026 | — |

---

## Gates (checkpoints by dependency, not by date)

| Gate | Reached when | Status |
|---|---|---|
| **G0 Foundations** | G0-1, M6-01, M6-02, M6-03, M2-01, M2-07, M3-04 done; every Team row fully ticked | todo |
| **G1 Thin slice** | In `prod`, an event sent with `curl` to `POST /events` reaches a DynamoDB progress item **and** an Athena row; web login works. Interfaces I1, I5, I6, I12 proven | todo |
| **G2 Core features** | FR-01–FR-09 (BRD) work on the real backend in `prod`. Interfaces I2, I3, I4, I7 proven | todo |
| **G3 MVP** | S1 and S2 pass in `prod` and are recorded in `docs/results.md` | todo |
| **G4 Complete** | Interfaces I8–I11 proven; S3, S5, S7, S8, S9 pass | todo |
| **G5 Scale & backups** | S4 and S6 pass; backup video of every demo segment recorded | todo |
| **G6 Final** | S10 measured; `docs/results.md` complete; slides done; 2 full rehearsals | todo |

| ID | Task | Owner | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|---|
| G0-1 | Review `CONTEXT.md` §6–§9; all 6 approve; set contract status to `FROZEN` | All | — | todo | | |

---

## Tasks

### M1: Frontend & Auth
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M1-01 | Vite + React + TS scaffold in `web/`, runtime `config.json` loader, `VITE_USE_MOCKS` mode (§9) | M2-07 *(soft)* | todo | | |
| M1-02 | Auth construct: user pool, groups, web + sim clients, managed login domain, SSM params (§9) | M6-01 | todo | | |
| M1-03 | Script: create `sim-bot@earshot.test` in `simulator` group, password from SSM | M1-02 | todo | | |
| M1-04 | Web construct: private bucket, CloudFront + OAC, SPA routing, `config.json` deployment | M6-01 | todo | | |
| M1-05 | Login via `react-oidc-context` (code + PKCE); access token on API calls | M1-02, M1-04 | todo | | |
| M1-06 | Pages: Home rows, Genre browse, Show detail, Live Trending (5 s poll), Settings region picker | M1-01 | todo | | |
| M1-07 | Persistent player bar (`<audio>`) + resume via `GET /progress/{id}` | M1-06 | todo | | |
| M1-08 | Event emitter per §6 (types, 15 s heartbeat, 25/batch, 5 s flush, immediate flush, keepalive, retry `THROTTLED`) | M1-07 | todo | | |
| M1-09 | Switch from mocks to the real API and ingest in own stage and `prod` | M1-05, M1-08, M2-06, M3-02 | todo | | |

### M2: API & Catalog
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M2-01 | `fetch_catalog.py` → commit `contracts/samples/catalog.json` (~50 shows × 20 episodes, 8 genres, §8.3) | — | done | [#8](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/8) | `scripts/catalog/fetch_catalog.py` → `catalog.json`: 48 shows (6 per genre) × ≤ 20 newest playable episodes = 958 episodes, from Podcast Index trending on Nov 7 (shape in §15). Keys are in prod SSM `/earshot/prod/podcastindex/*` |
| M2-02 | Pick 20 verified-playable `FEATURED` episodes | M2-01 | review | [#11](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/11) | `featured` list in `catalog.json`: 20 episodes from 20 shows, every genre (2–3 each). All 20 play (`python scripts/catalog/check_featured.py`; run it again the day before the demo) |
| M2-03 | `seed_catalog.py`: snapshot → Show / Episode / Featured items (§8.1); `make seed` | M2-01, M6-01 | todo | | |
| M2-04 | API construct: HTTP API, JWT authorizer (both clients), CORS, throttling, routes, `POST /events` → M3 ingest function | M6-01, M1-02 | todo | | |
| M2-05 | API Lambda: `/health`, `/genres`, `/shows`, `/shows/{id}`, `/progress/{id}`, `/trending` (§7.3) | M2-03, M2-04 | todo | | |
| M2-06 | `/home` rules 1–6 (§7.4): fallback chain, short-timeout client, 10 s flags cache, sim header, `HomeFallback` metric | M2-05 | todo | | |
| M2-07 | Commit sample responses `home.json`, `shows.json`, `show_detail.json`, `trending.json`, `progress.json` | M2-01 | done | [#10](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/10) | `home.json` (user `sim-000042`: continue, trending, 2 personalized rows) · `shows.json` = `?genre=true-crime` · `show_detail.json` = show `7212041` · `trending.json` (10 items) · `progress.json`. All IDs from `catalog.json`; `tests/unit/test_api_samples.py` checks them against §7 |
| M2-08 | `scripts/set_flag.py` for `recs_enabled` / `recs_fault_injection` | M6-01 | done | [#9](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/9) | `python scripts/set_flag.py --stage <s> [FLAG=true\|false ...] [--reset]`; no arguments = show. Verified in prod: show, flip `recs_fault_injection` on, `--reset` |

### M3: Ingest & Simulator
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M3-01 | `services/shared/validate.py`: event validation per §6 + unit tests | — | todo | | Shared with M4 |
| M3-02 | Ingest Lambda (§7.5): validate, then publish one SNS message per request (§10 format) + ingest construct (base, publish on the topic) | M3-01, M3-03 | todo | | Changed Nov 8: SNS instead of Kinesis |
| M3-03 | Events topic construct (`constructs/topic.py`, base): SNS standard topic `earshot-<stage>-events` (§9, §10) | M6-01 | todo | | Changed Nov 8: replaces the Kinesis stream |
| M3-04 | Commit `contracts/samples/events.jsonl` (1,000 events using catalog IDs) | M2-01 | todo | | Unblocks M4, M5 |
| M3-05 | Simulator `generate` (shuffle, dup-rate) + `replay --direct` (publishes to the SNS topic, §11) | M3-04, M3-03 | todo | | Changed Nov 8: `--direct` replaces `--direct-kinesis` |
| M3-06 | Simulator `run`: virtual users, affinity + Zipf, rate control, token refresh, run report | M1-03, M2-04, M3-02 | todo | | |
| M3-07 | Simulator EC2 construct (pipeline): t3.micro AL2023, no inbound, SSM, S3 asset | M6-01 | todo | | |
| M3-08 | `buffer-storm` mode | M3-06 | todo | | |

### M4: Real-time Processing
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M4-01 | Processor: decode SQS messages (`body` = `{"events":[...]}`, §10) + progress conditional update (§8.2) + unit tests for out-of-order input | M3-04 *(soft)* | doing | [#15](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/15) | Merged and tests pass; own-stage deployment verification remains |
| M4-02 | Trending via `TransactWriteItems` + dedupe marker; duplicate unit tests | M4-01 | doing | [#16](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/16) | Merged; own-stage verification remains |
| M4-03 | QoE minute windows + exactly one SNS publish at threshold | M4-01 | doing | | Implementing QoE dedupe, minute counts and threshold alert locally while stage verification is pending |
| M4-04 | Partial batch failures, skip malformed records, metrics (§10) | M4-01 | todo | | |
| M4-05 | Processing construct: hot queue + DLQ + subscription + function (base); SQS trigger with §10 settings (pipeline) | M6-01, M3-03 | todo | | Changed Nov 8: SQS trigger instead of Kinesis |
| M4-06 | S3 replay test `tests/acceptance/s3_replay.py` (expected results computed offline) | M3-05, M4-02 | todo | | |

### M5: Data Lake & Recommendations
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M5-01 | Lake construct (base): Glue DB, `events` table with partition projection, Athena workgroup + scan cutoff, lifecycle (§9) | M6-01 | review | [#4](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/4) | Glue DB + `events` table (projection on `dt`/`hour`), workgroup (1 GB cutoff, not enforced: see §15), 7-day `athena-results/` expiry. Tests + synth pass; not yet deployed to own stage |
| M5-02 | Archiver (§9, §10): `services/archiver/` Lambda writing gzipped JSON Lines to `events/dt=/hour=` by `server_ts`; `constructs/archiver.py`: cold queue + DLQ + subscription + function (base), SQS trigger (pipeline) | M5-01, M3-03 | todo | | Changed Nov 8: replaces the Firehose construct |
| M5-03 | SQL in `athena/`: `count_events`, `reconcile_trending`, `popular`, `recs` (§10); develop locally against fixtures first | M3-04 *(soft)* | review | [#6](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/6) | All 4 queries take `dt_from, dt_to, start_ms, end_ms` (see §15). Tested in DuckDB on a Firehose-shaped lake (`tests/unit/test_athena_sql.py`, skipped in CI until `duckdb` is in `requirements-dev.txt`). On 2,000 fake users: every eligible user got 2 full recs rows. Not yet run in real Athena |
| M5-04 | Recs writer Lambda: result CSVs → RECS + POPULAR items, `RecsUsersWritten` metric | M5-03 | todo | | |
| M5-05 | Recs construct (base): Step Functions, parallel Athena `.sync` → writer | M5-01, M5-04 | todo | | |
| M5-06 | S5 reconciliation script (Athena vs DynamoDB trending) | M4-02, M5-02 | todo | | |
| M5-07 | S7 coverage script (100 eligible + 20 new sim users via `/home`) | M5-05, M2-06 | todo | | |
| M5-08 | Switch the Glue `events` table from Parquet to JSON (§9): JSON SerDe, text input/output formats, `classification=json`; projection unchanged. Update `lake.py`, its docstring and `test_lake.py` | M5-01 | todo | | Added Nov 8 (contract change). The SQL in `athena/` doesn't change |

### M6: Platform, Monitoring & Testing
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M6-01 | Repo skeleton (§4), `config.py`, `app.py`, both stacks with **stub constructs for every member**, Makefile (§5); `cdk synth` green | — | done | [#2](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/2) | Verified in Codespaces: 59 tests + `cdk synth` pass |
| M6-02 | Shared `prod` account: IAM access for 5 teammates, Budgets, Lambda concurrency quota increase request | — | done | [#5](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/5) | Console work done Nov 7. Monthly budget with alerts at $5, $20 and forecast (credits excluded); root MFA; admin IAM user. Limits checked: Lambda concurrency 400, EC2 32 vCPUs, both enough, so no increase requested. Free plan lasts past the demo; default VPC exists. 5 teammates in `earshot-team` (deploy access); prod rules in CONTEXT §5 |
| M6-03 | Free plan service check in `prod` (deploy one tiny resource per approved service, §3); report blockers | M6-02 | review | [#7](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/7), [#12](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/12) | **Found: the Free plan blocks Kinesis and Firehose** (first run Nov 7, confirmed by a read-only CLI check Nov 8); everything else answered normally. Limits are fine (Lambda 400, EC2 32 vCPUs). #12 drops both from the check and adds SNS → SQS → Lambda, the path that replaces them (contract change follows). `AWS_PROFILE=earshot-prod make service-check STAGE=prod` deploys a throwaway stack (S3, CloudFront, Cognito, HTTP API, Lambda, Step Functions, SNS → SQS → Lambda, EC2 t3.micro), prints the limits, then destroys it. Done once the re-run passes in `prod` from `main` |
| M6-04 | GitHub Actions on every PR: `cdk synth` + `pytest` (no deploy) | M6-01 | done | [#3](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/3) | `.github/workflows/ci.yml`: lint + tests + synth (dev and prod) on every PR and push to `main`; green since Oct 19 |
| M6-05 | Monitoring construct: dashboard + ≤ 10 alarms + ops topic (§10) | M6-01 | todo | | |
| M6-06 | Locust `/home` test (50 users, 5 min, run from EC2) | M2-06, M3-07 | todo | | |
| M6-07 | Acceptance harness `tests/acceptance/` (S1–S10 runner) + `docs/results.md` template | M6-01 | todo | | |
| M6-08 | Cost check script: lists any hourly-billed resources left running; weekly cost note in Notes | M6-01 | todo | | |
| M6-09 | Status update document (done / hurdles / remaining, from this tracker) | G2 | todo | | Course deliverable |
| M6-10 | Slides skeleton; each member fills in their component; sources + `docs/ai-usage.md` cited | G4 | todo | | Course deliverable |

### Stretch (only after G4)
| ID | Task | Owner | Status | Notes |
|---|---|---|---|---|
| X-01 | Iceberg table with time travel | M5 | todo | |
| X-02 | A/B test of two ranking methods | M2 + M5 | todo | |
| X-03 | GitHub Actions deploy to `prod` | M6 | todo | |

---

## Interfaces (each one must be proven end to end)

| ID | From → To | Contract (§) | Proven by | Gate | Status |
|---|---|---|---|---|---|
| I1 | Web → Cognito | Code + PKCE, access token | Login in browser | G1 | todo |
| I2 | Web → API reads | §7, EpisodeCard | Home renders real data | G2 | todo |
| I3 | Web → `POST /events` | §6, §7.5 | 202 + message in the hot queue | G2 | todo |
| I4 | Simulator → ingest | §7.2 sim client | Run report `accepted` > 0 | G2 | todo |
| I5 | Ingest → SNS topic → hot queue → processor | §10 | Progress item appears | G1 | todo |
| I6 | SNS topic → cold queue → archiver → S3 → Athena | §9 Glue table, §10 | `count_events.sql` > 0 | G1 | todo |
| I7 | Processor → DynamoDB → `/home` | §8.1 Progress, Trending | Continue + trending rows | G2 | todo |
| I8 | Processor → SNS → email | §8.2 QoE | Alert email received | G4 | todo |
| I9 | Step Functions → DynamoDB → `/home` | §8.1 RECS, POPULAR | Personalized row | G4 | todo |
| I10 | SSM flags → API | §9 flags | S8 | G4 | todo |
| I11 | All functions → CloudWatch | §10 metrics | Dashboard populated during sim run | G4 | todo |
| I12 | Catalog snapshot → every account | §8.1 IDs | Same IDs everywhere after `make seed` | G1 | todo |

## Success criteria (record evidence in `docs/results.md`)

| # | Criterion | Target (CONTEXT §14) | Owner | Measured | Status |
|---|---|---|---|---|---|
| S1 | End-to-end flow | Sign up → resume | M1 | | todo |
| S2 | Resume freshness / accuracy | < 5 s p95, ±2 s | M4 + M1 | | todo |
| S3 | Bad-input correctness | 0 wrong / 0 double | M4 | | todo |
| S4 | Throughput, no loss | 500 ev/s × 10 min, 0 lost | M3 + M6 | | todo |
| S5 | Hot vs cold agreement | ≤ 1 % | M5 | | todo |
| S6 | API performance | p95 < 500 ms @ 50 users, < 1 % errors | M6 + M2 | | todo |
| S7 | Personalization coverage | 100 % eligible; never empty | M5 | | todo |
| S8 | Graceful degradation | 0 × 5xx, `degraded:true` | M2 | | todo |
| S9 | Quality alert | Email < 2 min | M4 + M3 | | todo |
| S10 | Cost & automation | < $30; pipeline-up < 10 min; full deploy < 25 min; 0 idle hourly | M6 | | todo |

## Demo runbook (use on demo day)

- [ ] **Day before:** full rehearsal on a fresh `make pipeline-up STAGE=prod`; all 20 `FEATURED` episodes play; check the credit balance
- [ ] **T−2 h:** `make pipeline-up STAGE=prod`; dashboard green
- [ ] **T−1 h:** `simulator run --users 2000 --rate 100 --duration 1800`; run the recs state machine once
- [ ] **T−15 min:** log in on the demo laptop; dashboard, Athena and email inbox open in tabs; flags reset
- [ ] **Live:** (1) play → refresh → resume, (2) simulator burst → live trending + dashboard, (3) Athena query, (4) recs off/fault → home still loads, degraded
- [ ] **After:** `make pipeline-down STAGE=prod`; cost check script shows 0 hourly resources
