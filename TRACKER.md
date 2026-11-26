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
| M1 | Frontend & Auth | Tanishqa | tanishqa14 | `tanishqa` | ☑ | ☑ | ☑ |
| M2 | API & Catalog | Sankha | SankhaS | `sankha` | ☑ | ☑ | ☑ |
| M3 | Ingest & Simulator | Bhargav | sbhargav0620-ui | `bhargav` | ☑ | ☑ | ☑ |
| M4 | Real-time Processing | | | | ☐ | ☐ | ☐ |
| M5 | Data Lake & Recommendations | | | | ☐ | ☐ | ☐ |
| M6 | Platform, Monitoring & Testing | Shreevatsa | Shreevatsa123 | | ☑ | ☑ | ☐ |
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
| G0-1 | Review `CONTEXT.md` §6–§9; all 6 approve; set contract status to `FROZEN` | All | — | todo | | #46 was merged before any approvals and is undone (status back to `DRAFT`). M2 OK'd in the group chat; the freeze is redone in a new PR once a CI check enforces all 6 approvals |

---

## Tasks

### M1: Frontend & Auth
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M1-01 | Vite + React + TS scaffold in `web/`, runtime `config.json` loader, `VITE_USE_MOCKS` mode (§9) | M2-07 *(soft)* | done | [#29](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/29) | `web/` Vite+React+TS app, purple gradient theme from the team's Nocturne design (Tailwind v4 + lucide icons). Runtime `/config.json` loader (§9). `VITE_USE_MOCKS=true` answers from `contracts/samples` (`/shows` and `/shows/{id}` built from `catalog.json`; fixtures excluded from normal builds). Home: hero spotlight, genre filter, Continue / ranked Top Podcasts Today / recs rows; show details dialog; show search; player dock with real `<audio>` (resume via `/progress` and events stay in M1-07/M1-08). Browse, Live Trending, Settings routes are placeholders for M1-06. `npm run build` green. Running in stage `tanishqa` since M1-04 (Nov 25) |
| M1-02 | Auth construct: user pool, groups, web + sim clients, managed login domain, SSM params (§9) | M6-01 | done | [#30](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/30) | User pool (email sign-in, self sign-up, Essentials plan), groups `listeners` + `simulator`; `web` client (code + PKCE, no secret, callbacks = CloudFront URL when M1-04 lands + localhost:5173); `sim` client (`USER_PASSWORD_AUTH` + refresh); managed login domain `cfg.cognito_domain_prefix` + default style; 3 SSM params. `tests/unit/test_auth.py`; synth passes. Verified in stage `tanishqa` (Nov 25): base deployed; pool, both clients, domain and 3 SSM params created |
| M1-03 | Script: create `sim-bot@earshot.test` in `simulator` group, password from SSM | M1-02 | done | [#35](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/35) | `python scripts/create_sim_bot.py --stage <s> [--generate-password]`: reads the pool id from SSM, creates the user if missing (email verified, no invite email), sets the SSM password as permanent, adds it to `simulator`; safe to re-run, never prints the password. `--generate-password` creates `/earshot/<s>/sim/password` (SecureString) only if it's missing. `tests/unit/test_create_sim_bot.py`. Verified in stage `tanishqa` (Nov 25): `--generate-password` created the SSM password, user created in `simulator`; a `USER_PASSWORD_AUTH` login through the `sim` client returned a 60-minute token |
| M1-04 | Web construct: private bucket, CloudFront + OAC, SPA routing, `config.json` deployment | M6-01 | done | [#53](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/53) | Private bucket `cfg.web_bucket` (TLS only, DESTROY + auto-delete); CloudFront with OAC, HTTPS only, 403/404 → `/index.html` 200, PRICE_CLASS_100, managed security headers. `publish()`: one BucketDeployment of `web/dist` (if built; its local `config.json` excluded) + the generated `config.json`, then invalidates `/*`. Exposes `url` = `https://<id>.cloudfront.net`, now in the web client callbacks and API CORS. `tests/unit/test_web.py`. Verified in stage `tanishqa` (Nov 25): site served from CloudFront; `/config.json` has all 6 values; `/browse` deep link returns the app; API CORS preflight allows the CloudFront origin; `/home` without a token is 401 as expected |
| M1-05 | Login via `react-oidc-context` (code + PKCE); access token on API calls | M1-02, M1-04 | done | [#54](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/54) | `src/auth/session.tsx`: code + PKCE on the managed login pages, redirect back to the site's origin, access token on every API call, tokens in `localStorage` with silent renew, a 401 drops the token and shows the login screen, Log out clears tokens then Cognito's `/logout`. Login screen + account menu. Mock mode skips login. Checked in a headless browser with stage `tanishqa`'s config: the button redirects to the managed login page with `response_type=code`, `code_challenge_method=S256` and the right `redirect_uri`. Verified in stage `tanishqa` (Nov 26): sign up with email code, log in, Home loads from the real `/home` (FEATURED fallback row for a new user), stays logged in after reload, Log out returns to the login screen |
| M1-06 | Pages: Home rows, Genre browse, Show detail, Live Trending (5 s poll), Settings region picker | M1-01 | done | [#56](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/56) | Home rows + show detail dialog came with M1-01. New: **Browse** (`GET /genres` + `GET /shows?genre=`, genre in the URL `/browse?genre=history`), **Live Trending** (`GET /trending?limit=20` every 5 s while the tab is visible; rank movement and plays gained since the last poll), **Settings** (region picker for §6 `region`, stored in `localStorage`, read by the M1-08 emitter via `getRegion()`; account and Log out). Checked in a headless browser with mock data. Verified in stage `tanishqa` (Nov 26): Browse lists each genre's shows from the real API, Live Trending polls every 5 s (empty state, no plays yet), Settings shows the logged-in account and keeps the region after reload |
| M1-07 | Persistent player bar (`<audio>`) + resume via `GET /progress/{id}` | M1-06 | done | [#57](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/57) | Plays at once (at the card's `position_sec`, so the click isn't delayed), then `GET /progress/{id}` (2.5 s timeout) and jumps to the saved second; `completed` or within 15 s of the end starts over; `updated_at: null` keeps the first guess; a late answer for an episode the user left, or after they seeked, is ignored. "Resumed at m:ss" in the player bar. Logic in `web/src/lib/resume.ts`. Checked in a headless browser against a fake API (saved 600 s → playing from 10:00; nothing saved → from 0). Verified in stage `tanishqa` (Nov 26): plays, asks `/progress`, starts at 0 (nothing saved yet). Cross-device resume end to end (S2) waits for M4-05 |
| M1-08 | Event emitter per §6 (types, 15 s heartbeat, 25/batch, 5 s flush, immediate flush, keepalive, retry `THROTTLED`) | M1-07 | todo | | |
| M1-09 | Switch from mocks to the real API and ingest in own stage and `prod` | M1-05, M1-08, M2-06, M3-02 | todo | | |

### M2: API & Catalog
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M2-01 | `fetch_catalog.py` → commit `contracts/samples/catalog.json` (~50 shows × 20 episodes, 8 genres, §8.3) | — | done | [#8](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/8) | `scripts/catalog/fetch_catalog.py` → `catalog.json`: 48 shows (6 per genre) × ≤ 20 newest playable episodes = 958 episodes, from Podcast Index trending on Nov 7 (shape in §15). Keys are in prod SSM `/earshot/prod/podcastindex/*` |
| M2-02 | Pick 20 verified-playable `FEATURED` episodes | M2-01 | done | [#11](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/11) | `featured` list in `catalog.json`: 20 episodes from 20 shows, every genre (2–3 each). All 20 play (`python scripts/catalog/check_featured.py`; run it again the day before the demo) |
| M2-03 | `seed_catalog.py`: snapshot → Show / Episode / Featured items (§8.1); `make seed` | M2-01, M6-01 | done | [#31](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/31) | 1,007 items (48 shows, 958 episodes, `FEATURED`), BatchWriteItem, re-runnable. Tested on moto, then **verified in stage `sankha`** (shared account, §5 rule 4): 1,007 items, GSI1 order = `shows.json`. **Seeded in `prod`** (Nov 25, from `main`): 1,007 items, GSI1 order = `shows.json` (I12) |
| M2-04 | API construct: HTTP API, JWT authorizer (both clients), CORS, throttling, routes, `POST /events` → M3 ingest function | M6-01, M1-02 | done | [#32](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/32) | Verified in stage `sankha`: no/fake token → 401; real sim-client token → `POST /events` 202 via M3's ingest and `GET /home` reaches the API Lambda; CORS preflight allows only localhost (+ CloudFront later); throttle 500/1000; URL in SSM |
| M2-05 | API Lambda: `/health`, `/genres`, `/shows`, `/shows/{id}`, `/progress/{id}`, `/trending` (§7.3) | M2-03, M2-04 | done | [#33](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/33) | Routes in `services/api/handler.py`. Verified in stage `sankha` with a real token: `/shows?genre=true-crime` and `/shows/7212041` equal the M2-07 samples; `/progress` (stored + default), `/trending` (hydrated card), `/health`, `/genres`, 400/404 errors |
| M2-06 | `/home` rules 1–6 (§7.4): fallback chain, short-timeout client, 10 s flags cache, sim header, `HomeFallback` metric | M2-05 | done | [#34](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/34) | Verified in stage `sankha` with a real token: new user → FEATURED fallback row; progress + trending + RECS → continue, trending, recs-1; **S8 passes in `sankha`** (`recs_enabled=false` + `recs_fault_injection=true` → 200, `degraded:true`, fallback row, `HomeFallback` in the logs); /home median 177 ms round trip. S8 still to be recorded in `prod` |
| M2-07 | Commit sample responses `home.json`, `shows.json`, `show_detail.json`, `trending.json`, `progress.json` | M2-01 | done | [#10](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/10) | `home.json` (user `sim-000042`: continue, trending, 2 personalized rows) · `shows.json` = `?genre=true-crime` · `show_detail.json` = show `7212041` · `trending.json` (10 items) · `progress.json`. All IDs from `catalog.json`; `tests/unit/test_api_samples.py` checks them against §7 |
| M2-08 | `scripts/set_flag.py` for `recs_enabled` / `recs_fault_injection` | M6-01 | done | [#9](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/9) | `python scripts/set_flag.py --stage <s> [FLAG=true\|false ...] [--reset]`; no arguments = show. Verified in prod: show, flip `recs_fault_injection` on, `--reset` |
| M2-09 | S8 acceptance check `tests/acceptance/s8_degradation.py` (§14 S8): fault flags, wait for the cache, 20 × `/home`, flags restored in a `finally` | M2-06, M2-08, M6-07 | done | [#43](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/43) | Unit tests without AWS (`tests/unit/test_s8_degradation.py`). **PASS in stage `sankha`** (Nov 26): 0 × 5xx, 20/20 `degraded:true`, median 182 ms, flags back to what they were. Prod run (M6) writes `docs/results.md` |

### M3: Ingest & Simulator
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M3-01 | `services/shared/validate.py`: event validation per §6 + unit tests | — | done | [#19](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/19) | `validate_event(raw, now_ms=, allowed_genres=)` → `(clean, None)` or `(None, reason)`; checks every client field in §6 order; drops unknown fields and never returns `user_id`/`server_ts` (ingest sets them). `order_fields()` gives §6 field order. `tests/unit/test_validate.py` |
| M3-02 | Ingest Lambda (§7.5): validate, then publish one SNS message per request (§10 format) + ingest construct (base, publish on the topic) | M3-01, M3-03 | done | [#22](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/22) | 202 with per-index rejects; 400 for non-JSON, not `{"events":[...]}`, 0 or > 25 events, > 64 KB; §7.2 identity rule (`FORBIDDEN_USER`); one SNS publish per request, 3 retries (50/100/200 ms) on throttling/transient errors, then every event `THROTTLED`; `EventsAccepted`/`EventsRejected`. Construct: function (10 s timeout) + publish grant. `tests/unit/test_ingest.py` (SNS faked). Verified in stage `bhargav` (Nov 23): direct invoke with 3 good + 1 bad event → 202, 3 accepted, 1 `INVALID_FIELD:position_sec`, published to SNS |
| M3-03 | Events topic construct (`constructs/topic.py`, base): SNS standard topic `earshot-<stage>-events` (§9, §10) | M6-01 | done | [#21](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/21) | `sns.Topic` `earshot-<stage>-events`, standard, no encryption. Verified in stage `bhargav` (Nov 23): deployed |
| M3-04 | Commit `contracts/samples/events.jsonl` (1,000 events using catalog IDs) | M2-01 | done | [#20](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/20) | `python -m simulator generate --out contracts/samples/events.jsonl --users 50 --events 1000 --shuffle --dup-rate 0.05 --seed 650 --start 2026-11-14T00:00:00Z --window-hours 1`: 950 unique + 50 duplicates, shuffled, already enriched (`user_id`, `server_ts`). `tests/unit/test_events_fixture.py` checks every line against §6 and the catalog. Made with `generate` (M3-05) |
| M3-05 | Simulator `generate` (shuffle, dup-rate) + `replay --direct` (publishes to the SNS topic, §11) | M3-04, M3-03 | done | [#23](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/23) | `generate`: `--events` = lines incl. duplicates (`round(N × dup-rate)` copies with a later `server_ts`), deterministic per `--seed`. `replay --direct`: 25 events per message, `PublishBatch` × 10, retries, `server_ts` = publish time unless `--keep-server-ts`. Unit-tested with a fake SNS; verified in stage `bhargav` (Nov 23): `events.jsonl` → 40 messages, 1,000 events, 0 failed |
| M3-06 | Simulator `run`: virtual users, affinity + Zipf, rate control, token refresh, run report | M1-03, M2-04, M3-02 | review | [#24](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/24) | Code + unit tests done (fake API): Cognito `USER_PASSWORD_AUTH` + refresh, 25-event batches on a thread pool, back-pressure, retries `THROTTLED`/429/5xx × 3, run report. End-to-end test needs M1-03 (sim-bot) and M2-04 (route) |
| M3-07 | Simulator EC2 construct (pipeline): t3.micro AL2023, no inbound, SSM, S3 asset | M6-01 | done | [#26](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/26) | t3.micro AL2023 via `CfnInstance` (default VPC, SG with no inbound), SSM core + `/earshot/<stage>/*` params + `sns:Publish` on the events topic; user data installs Python 3.11, boto3, locust and unpacks the code to `/opt/earshot`. Verified in stage `bhargav` (Nov 23): `pipeline-up`, Session Manager, `generate` + `replay --direct` from the instance, `pipeline-down` |
| M3-08 | `buffer-storm` mode | M3-06 | review | [#25](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/25) | `--mode buffer-storm --storm-region <r> [--storm-rate 3]`: extra distinct `buffer` events at 3/s (180/min) in one region on top of normal traffic. A unit test checks ≥ 100/min |

### M4: Real-time Processing
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M4-01 | Processor: decode SQS messages (`body` = `{"events":[...]}`, §10) + progress conditional update (§8.2) + unit tests for out-of-order input | M3-04 *(soft)* | doing | [#15](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/15) | Merged and tests pass; own-stage deployment verification remains |
| M4-02 | Trending via `TransactWriteItems` + dedupe marker; duplicate unit tests | M4-01 | doing | [#16](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/16) | Merged; own-stage verification remains |
| M4-03 | QoE minute windows + exactly one SNS publish at threshold | M4-01 | review | [#17](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/17) | QoE dedupe, per-region/minute counts and threshold SNS alert; local tests pass |
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
| M5-08 | Switch the Glue `events` table from Parquet to JSON (§9): JSON SerDe, text input/output formats, `classification=json`; projection unchanged. Update `lake.py`, its docstring and `test_lake.py` | M5-01 | review | [#27](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/27) | JSON SerDe + text formats + `classification=json`, exactly as §9; projection, columns, workgroup unchanged; no SerDe options (a malformed line fails the query). SQL test lake is now `.json.gz` per `server_ts` hour, like the archiver; queries unchanged (comments only). Tests + synth pass; not yet deployed to own stage |

### M6: Platform, Monitoring & Testing
| ID | Task | Depends on | Status | PR | Notes |
|---|---|---|---|---|---|
| M6-01 | Repo skeleton (§4), `config.py`, `app.py`, both stacks with **stub constructs for every member**, Makefile (§5); `cdk synth` green | — | done | [#2](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/2) | Verified in Codespaces: 59 tests + `cdk synth` pass |
| M6-02 | Shared `prod` account: IAM access for 5 teammates, Budgets, Lambda concurrency quota increase request | — | done | [#5](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/5) | Console work done Nov 7. Monthly budget with alerts at $5, $20 and forecast (credits excluded); root MFA; admin IAM user. Limits checked: Lambda concurrency 400, EC2 32 vCPUs, both enough, so no increase requested. Free plan lasts past the demo; default VPC exists. 5 teammates in `earshot-team` (deploy access); prod rules in CONTEXT §5 |
| M6-03 | Free plan service check in `prod` (deploy one tiny resource per approved service, §3); report blockers | M6-02 | done | [#7](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/7), [#12](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/12) | **Found: the Free plan blocks Kinesis and Firehose** (first run Nov 7, confirmed by a read-only CLI check Nov 8); everything else answered normally. Limits are fine (Lambda 400, EC2 32 vCPUs). #12 drops both from the check and adds SNS → SQS → Lambda, the path that replaces them (contract change follows). `AWS_PROFILE=earshot-prod make service-check STAGE=prod` deploys a throwaway stack (S3, CloudFront, Cognito, HTTP API, Lambda, Step Functions, SNS → SQS → Lambda, EC2 t3.micro), prints the limits, then destroys it. Re-run passed in `prod` from `main` on Nov 25: every resource deployed (about 4 min), limits OK, stack destroyed |
| M6-04 | GitHub Actions on every PR: `cdk synth` + `pytest` (no deploy) | M6-01 | done | [#3](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/3) | `.github/workflows/ci.yml`: lint + tests + synth (dev and prod) on every PR and push to `main`; green since Oct 19. Nov 24: CI now installs `duckdb`, so the Athena SQL tests run; the alert email test counts only email subscriptions (queue subscriptions no longer break it); `archiver` added to ruff first-party. Nov 25: `contract-status.yml` adds the required check **contract status approvals**: a PR that changes the "Contract status" line in `CONTEXT.md` can't merge until every member except its author has approved on GitHub (G0-1) |
| M6-05 | Monitoring construct: dashboard + ≤ 10 alarms + ops topic (§10) | M6-01 | done | [#41](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/41) | Dashboard `earshot-<stage>` in every stage (38 metrics: API, 5 Lambdas, both queues, both DLQs, DynamoDB, 8 custom). Alarms in `prod` only, to the ops topic: both DLQs not empty, API 5xx rate > 1 %, Lambda throttles, archiver errors (base) and hot queue oldest message > 60 s (pipeline). 7 alarm metrics of the free 10; synth fails if either free-tier limit is exceeded. Verified in `prod` (Nov 25, `deploy-base` from `main`): dashboard `earshot-prod` exists, the 5 base alarms are OK, ops and QoE email subscriptions confirmed, and a forced ALARM on `lambda-throttles` (`set-alarm-state`) arrived by email. The hot queue alarm appears with `pipeline-up` |
| M6-06 | Locust `/home` test (50 users, 5 min, run from EC2) | M2-06, M3-07 | review | [#52](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/52) | `tests/load/locustfile.py`: 50 users, each a random `sim-NNNNNN`, `GET /home` every 1–2 s (~30 req/s) with one shared sim-bot token (simulator's `TokenProvider`). On EC2 it's fetched with `curl` from `main` (no change to the M3 construct); runbook in its docstring. S6 (`s6_api_perf.py`) reads the copied `s6_stats.csv`: pass if p95 < 500 ms and errors < 1 %. Not run yet: needs `make seed` and the sim-bot user in prod |
| M6-07 | Acceptance harness `tests/acceptance/` (S1–S10 runner) + `docs/results.md` template | M6-01 | review | [#38](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/38) | `make acceptance STAGE=<s> [ONLY=S1,S10]` runs every `tests/acceptance/s<N>_*.py`, prints a summary, saves raw JSON in `tests/acceptance/output/`, and for `prod` only rewrites the matching `docs/results.md` rows. Each S module is a stub for its owner to fill in (CONTEXT §15); S10 waits on the cost check (M6-08). Unit tests use fake checks and a local HTTP server, no AWS |
| M6-08 | Cost check script: lists any hourly-billed resources left running; weekly cost note in Notes | M6-01 | done | [#39](https://github.com/Shreevatsa123/earshot-podcast-streaming/pull/39) | `make cost-check` (read-only, whole account, us-east-1): running EC2 instances, Elastic IPs, NAT gateways and load balancers count as hourly; leftover pipeline/servicecheck stacks, stopped instances and loose EBS volumes are listed too. Exit 0 = clean, 1 = hourly running, 2 = couldn't check. `make pipeline-down` runs it afterwards. No Kinesis/Firehose checks (blocked on the Free plan). S10 (`tests/acceptance/s10_cost.py`) uses the same checks. Two synth tests make sure the pipeline stack and dev base retain nothing. Cost notes: Nov 25, first prod run clean, nothing hourly-billed running |
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
| I12 | Catalog snapshot → every account | §8.1 IDs | Same IDs everywhere after `make seed` | G1 | done |

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
