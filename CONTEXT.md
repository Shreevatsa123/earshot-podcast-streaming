# Earshot — Project Context (Single Source of Truth)

> **This is a living document.** Anyone on the team (or their AI agent) updates it through a PR whenever a decision or contract changes. Rules: §12. History: §15 Changelog.
>
> **How to use it:**
> - **AI agent with repo access (Claude, Kiro, Copilot, …):** the agent reads `AGENTS.md`, which points here and to `TRACKER.md`. Start a session with: `I am M<#>. Work on task <ID> from TRACKER.md.`
> - **Chat-only AI:** paste this whole file, the relevant rows of `TRACKER.md`, and the same one-line instruction.
>
> If an AI suggestion contradicts this file, this file wins. If the file itself is wrong, fix it in a PR. Don't let the AI work around it.
>
> **Contract status:** `DRAFT` (becomes `FROZEN` when tracker task G0-1 is done; after that, only additive changes)

---

## 0. Rules for the AI assistant (read first)

1. **Don't change the contracts in §6–§9** (event schema, API, DynamoDB keys, names/SSM params). Code must conform to them. If a change seems needed, stop and tell the user to propose it to the team (§12).
2. **Don't add AWS services** beyond §3. In particular, never use NAT Gateway, ALB/NLB, RDS/Aurora, ElastiCache, OpenSearch, MSK, Managed Flink, EMR, Glue ETL/Spark jobs, Secrets Manager, KMS customer-managed keys, Route 53 hosted zones, VPC endpoints (interface), or Lambda inside a VPC.
3. **Stay free.** Every design choice must keep cost at about $0 when idle. Hourly-billed resources (Kinesis, Firehose, EC2) belong in the **pipeline** stack only (§5).
4. **Work only in the user's owned paths** (§4). If something outside them is needed, write it as a request to the owning member rather than editing their files.
5. **Lambda code uses only the Python standard library + boto3** (already in the Lambda runtime). No `pip` dependencies in Lambdas, so CDK never needs Docker bundling.
6. **IaC is AWS CDK v2 in Python.** Don't produce Terraform, SAM, Serverless Framework, or console click-ops instructions for anything that should be in code.
7. **Never hard-code** account IDs, regions, ARNs, URLs or secrets. Use the naming rules (§9), environment variables, or SSM parameters.
8. Write **small, readable code** with type hints and docstrings. Log JSON, once per batch or request, not once per event.
9. When unsure, prefer the **simpler** option and say what you assumed.
10. **Keep the docs in sync (agents with repo access):**
    - Before starting, read `TRACKER.md` and check the task's dependencies are `done`.
    - In the **same PR** as your code, update the task's status, PR link and notes in `TRACKER.md`.
    - If you made or changed a decision, add a line to §15 Changelog.
    - If you need something from someone else's area, don't edit their files. Tell your user what's needed and from which member, so they can message that person in the group chat.
11. **Never commit secrets, `.env` files, AWS credentials, or `cdk.out/`.** Never push directly to `main`.

---

## 1. Project summary

**Earshot** is a podcast streaming web app with a real-time data pipeline on AWS (MSML 650 term project, team of 6, Fall 2026).

- Users sign up, log in, browse real podcasts, and play episodes in the browser. **Audio streams directly from the publisher's public URL. We store only metadata and events, never audio.**
- The home page has **Continue Listening** (resume at exact position), **Trending Now** (live play counts), and **Recommended for You** (batch co-listening recommendations), with a **popular-content fallback** so the page is never empty.
- Every playback event (play, pause, seek, buffer, heartbeat, complete) flows through **API Gateway → Lambda → Kinesis**. It then splits into:
  - **Hot path:** Lambda stream processor → DynamoDB (seconds) + SNS quality alerts
  - **Cold path:** Amazon Data Firehose → Parquet in S3 → Athena (minutes)
- **Batch path:** Step Functions runs Athena queries on demand to build recommendations and writes them to DynamoDB.
- An **EC2 listener simulator** generates traffic from thousands of virtual users for testing and the demo.

**Problem we're showing a solution to:** process a continuous stream of small, possibly late, out-of-order or duplicated events so that the live app stays correct within seconds, while also keeping a complete, cheap, queryable history.

---

## 2. Architecture

```
 Browser (React app on S3 + CloudFront)
   │  Cognito managed login (OAuth code + PKCE) → access token (JWT)
   ▼
 API Gateway HTTP API  ── JWT authorizer (Cognito) ──────────────────────────────┐
   │ GET /home /shows /shows/{id} /genres /trending /progress/{id}               │ POST /events
   ▼                                                                             ▼
 Read Lambdas (M2) ──► DynamoDB single table ◄── Processor Lambda (M4)     Ingest Lambda (M3)
                         ▲                         ▲    │ SNS (QoE alert)        │ PutRecords
                         │ RECS/POPULAR items      │    ▼                        ▼
                         │                         └── Kinesis Data Stream (1 shard) ◄── EC2 Simulator (M3)
 Step Functions (M5) ── Athena ◄── Glue table ◄── S3 lake (Parquet) ◄── Data Firehose (M5) ◄─┘
   └─► Recs writer Lambda ─► DynamoDB                                          (via API)
 CloudWatch dashboard + alarms (M6) · AWS Budgets
```

**Data paths:**
1. **Read:** browser → API → read Lambda → DynamoDB → JSON.
2. **Hot:** browser/simulator → `POST /events` → ingest Lambda → Kinesis → processor Lambda → DynamoDB (progress, trending, QoE windows) → SNS on buffering spikes.
3. **Cold:** Kinesis → Firehose (JSON→Parquet using the Glue table schema) → `s3://<lake>/events/dt=YYYY-MM-DD/hour=HH/` → Athena.
4. **Batch:** Step Functions → Athena (recs + popular queries) → results CSV in S3 → recs writer Lambda → DynamoDB `RECS` and `POPULAR` items.

---

## 3. Approved tech stack and services

| Area | Choice |
|---|---|
| Region | **us-east-1** (all accounts, all resources) |
| IaC | **AWS CDK v2, Python** (`aws-cdk-lib`), CDK CLI via Node 22+ (Node 20 is end-of-life) |
| Lambda runtime | **Python 3.12, arm64**, stdlib + boto3 only, 256 MB default (512 MB for read API) |
| Frontend | **React + Vite + TypeScript**, `react-oidc-context` / `oidc-client-ts` for Cognito managed login |
| Simulator / load tools | Python 3.11+ on EC2 (Amazon Linux 2023), `httpx` + `boto3` allowed here; **Locust** for load tests |
| Unit tests | `pytest` (+ `moto` allowed in tests only) |
| Repo | One GitHub monorepo, PRs into `main` |

**Approved AWS services (nothing else):** S3, CloudFront, Cognito, API Gateway (HTTP API), Lambda, DynamoDB (on-demand), Kinesis Data Streams (provisioned, 1 shard), Amazon Data Firehose, Glue **Data Catalog only**, Athena, Step Functions (Standard), SNS, SQS (DLQ only), EC2 (t3.micro, default VPC, public subnet), CloudWatch (logs, metrics, 1 dashboard, ≤ 10 alarms), SSM Parameter Store (Standard tier), IAM, AWS Budgets.

---

## 4. Team, ownership and repo layout

| ID | Role | Owns (paths) |
|---|---|---|
| **M1** | Frontend & Auth | `web/`, `infra/earshot_infra/constructs/auth.py`, `infra/earshot_infra/constructs/web.py` |
| **M2** | API & Catalog | `services/api/`, `scripts/catalog/`, `contracts/samples/catalog.json`, `infra/earshot_infra/constructs/api.py` |
| **M3** | Ingest & Simulator | `services/ingest/`, `simulator/`, `contracts/samples/events.jsonl`, `infra/earshot_infra/constructs/ingest.py` (base), `infra/earshot_infra/constructs/stream.py` (pipeline), `infra/earshot_infra/constructs/simulator.py` (pipeline) |
| **M4** | Real-time Processing | `services/processor/`, `infra/earshot_infra/constructs/processing.py` (processor function + DLQ in base, event source mapping in pipeline) |
| **M5** | Data Lake & Recommendations | `athena/`, `services/recs_writer/`, `infra/earshot_infra/constructs/lake.py`, `infra/earshot_infra/constructs/firehose.py`, `infra/earshot_infra/constructs/recs.py` |
| **M6** | Platform, Monitoring & Testing (integration lead) | `infra/app.py`, `infra/cdk.json`, `infra/requirements.txt`, `infra/earshot_infra/config.py`, `infra/earshot_infra/common.py`, `infra/earshot_infra/stacks/`, `infra/earshot_infra/constructs/core.py`, `infra/earshot_infra/constructs/monitoring.py`, `scripts/` (except `catalog/`), `tests/load/`, `tests/acceptance/`, `Makefile`, `pyproject.toml`, `requirements-dev.txt`, `.github/` |
| **All** | Shared | `contracts/` (change process §12), `services/shared/`, `CONTEXT.md`, `docs/` |

```
earshot/
├── AGENTS.md                   ← instructions for any AI agent (read first)
├── CLAUDE.md                   ← Claude Code entry point → imports AGENTS.md
├── .kiro/steering/earshot.md   ← Kiro entry point → includes CONTEXT.md + TRACKER.md
├── CONTEXT.md                  ← this file (living)
├── TRACKER.md                  ← tasks, status (living)
├── Makefile                    ← deploy/teardown/seed commands (M6); `make help`
├── pyproject.toml              ← pytest + ruff settings (M6)
├── requirements-dev.txt        ← local Python deps: CDK, pytest, boto3, moto (M6)
├── contracts/
│   └── samples/                ← fixtures everyone codes against (list: samples/README.md)
│       ├── catalog.json        ← canonical catalog snapshot (M2)
│       ├── events.jsonl        ← 1,000 sample events (M3)
│       ├── home.json  shows.json  show_detail.json  trending.json  progress.json  (M2)
├── infra/
│   ├── app.py                  ← reads -c stage=..., builds 2 stacks
│   ├── cdk.json  requirements.txt
│   └── earshot_infra/
│       ├── config.py           ← StageConfig: every name + ARN for a stage (wraps shared/names.py)
│       ├── common.py           ← python_function(), log_group(), removal policy, tags
│       ├── stacks/base_stack.py      ← persistent stack (composes constructs)
│       ├── stacks/pipeline_stack.py  ← ephemeral stack (composes constructs)
│       └── constructs/         ← one file per owner (see table)
├── services/                   ← ALL Lambda code; deployed as one asset dir
│   ├── shared/                 ← names.py (single source for §9 names), http.py, log.py (EMF metrics), validate.py, clock.py
│   ├── api/handler.py          ← routes: home, shows, show_detail, genres, trending, progress, health
│   ├── ingest/handler.py
│   ├── processor/handler.py
│   └── recs_writer/handler.py
├── athena/                     ← recs.sql, popular.sql, reconcile_trending.sql, count_events.sql
├── simulator/                  ← python -m simulator ...
├── web/                        ← React app
├── scripts/                    ← seed_catalog.py, set_flag.py, pipeline_up.sh, pipeline_down.sh, ...
├── tests/unit/  tests/acceptance/  tests/load/
└── docs/
    ├── BRD.md                  ← business requirements
    ├── results.md              ← measured S1–S10 results
    └── ai-usage.md             ← AI tool citations for the slides
```

**Pattern:**
- Each member owns a **construct** (`constructs/<x>.py`) and its **service code**.
- M6 owns the two thin **stack** files that instantiate every construct. M6-01 committed a stub construct for everyone, so the whole app synthesizes and deploys from day one. Each member then fills in their own construct.
- **Each stub's docstring is its spec:** what it must create, its inputs, and the attributes it **exposes** (e.g. `auth.user_pool`, `ingest.function`). Keep those attribute names; other constructs read them.
- An exposed attribute is `None` until its owner implements it. Consumers check for `None` and skip that wiring until then.
- `core.py` (M6) holds the shared resources: the DynamoDB table, the lake bucket, both SNS topics and the flags parameter.
- Never build a resource name by hand: use `cfg.<name>` / `cfg.<name>_arn` (`config.py`).

Lambdas: create them with **`common.python_function(...)`**. It sets the name (`earshot-<stage>-<name>`), Python 3.12 arm64, the `services/` asset, `STAGE`, and a 7-day log group. Handlers look like `api.handler.main`, `ingest.handler.main`, etc. Every folder has an `__init__.py`.

---

## 5. Environments, stacks and cost rules

**Stages.** Every member deploys into **their own AWS account** with `stage=<firstname>` (e.g. `stage=priya`). The team integration and demo environment is **one shared account** with `stage=prod`. All accounts: us-east-1.

**Two stacks per stage:**

| Stack | Name | Lifecycle | Contains |
|---|---|---|---|
| Base | `earshot-<stage>-base` | **Persistent** (about $0 idle) | DynamoDB table, lake bucket, web bucket + CloudFront, Cognito, HTTP API + all API Lambdas incl. ingest, processor Lambda function (no trigger), recs writer + Step Functions, Glue database + `events` table, Athena workgroup, SNS topics, SQS DLQ, SSM params, dashboard + alarms |
| Pipeline | `earshot-<stage>-pipeline` | **Ephemeral**: deploy for test or demo, destroy after | Kinesis stream (1 shard, 24 h retention), Kinesis→Lambda event source mapping, Firehose delivery stream, EC2 simulator instance |

**Hard rules:**
- **Base never references Pipeline objects.** The ingest Lambda finds the stream by its **deterministic name** (§9) and IAM grants use the name-based ARN. If the stream doesn't exist, ingest returns `503 PIPELINE_OFFLINE`.
- **Pipeline references Base resources by name/ARN from `cfg`** (e.g. `cfg.function_arn("processor")`, `cfg.lake_bucket_arn`, `cfg.processor_dlq_arn`), never through CDK props. That means no CloudFormation exports, so base can be updated while pipeline is deployed, and pipeline can be destroyed anytime. IAM that base resources need for pipeline resources is granted in base on those ARNs (e.g. the processor role's Kinesis read on `cfg.stream_arn`).
- `make pipeline-down STAGE=x` after **every** working session. Nothing hourly-billed may be left running overnight.
- All log groups have **7-day retention**. Removal policy is `DESTROY` for all stages except the `prod` DynamoDB table and lake bucket (`RETAIN`).
- Tags on everything: `project=earshot`, `stage=<stage>`, `owner=<M#>`.
- Custom CloudWatch metrics: **only the 8 listed in §10**, namespace `Earshot`, dimension `Stage` only. No per-user, per-episode or per-region dimensions.
- No Lambda in a VPC. No Elastic IPs. The EC2 instance uses a default-VPC public subnet with **no inbound rules**, accessed through **SSM Session Manager** (no SSH keys).

Commands (owned by M6):
```
make bootstrap            # cdk bootstrap (once per account)
make deploy-base  STAGE=x # builds web/, deploys base stack
make seed         STAGE=x # loads contracts/samples/catalog.json into DynamoDB
make pipeline-up  STAGE=x # deploys pipeline stack
make pipeline-down STAGE=x# destroys pipeline stack
make destroy-all  STAGE=x # everything (dev stages only)
```

---

## 6. Contract: Event schema (v1)

One JSON object per playback event. The player and simulator produce it, ingest validates it, and the processor and lake consume it.

| Field | Type | Rules |
|---|---|---|
| `event_id` | string | UUID v4, unique per event (generated by the client) |
| `schema_version` | int | `1` (ingest sets it if missing) |
| `user_id` | string | Set by **ingest** from the token `sub`. Simulator users: must start with `sim-` (see §7.2) |
| `session_id` | string | UUID v4, new for each continuous listening session of one episode |
| `show_id` | string | From the catalog |
| `episode_id` | string | From the catalog |
| `genre` | string | One of §8.3 genres (the show's genre) |
| `event_type` | string | `play` \| `pause` \| `seek` \| `buffer` \| `heartbeat` \| `complete` |
| `position_sec` | int | 0 ≤ x ≤ 86400, playback position **after** the action |
| `duration_sec` | int | > 0, episode length |
| `client_ts` | int | Epoch **milliseconds** when it happened on the client. Must be ≥ 1767225600000 (2026-01-01) and ≤ now + 300000 |
| `server_ts` | int | Epoch ms, **set by ingest** (clients don't send it; ignored if they do) |
| `region` | string | `us-east` \| `us-west` \| `eu-west` \| `ap-south` |
| `device` | string | `web` \| `sim` |

Example:
```json
{"event_id":"8f0c1f9e-6c43-4b5e-9a37-0a6f8a1c2d11","schema_version":1,"user_id":"sim-000042",
 "session_id":"b1d2...","show_id":"920666","episode_id":"16795090","genre":"true-crime",
 "event_type":"pause","position_sec":734,"duration_sec":2810,"client_ts":1793548801000,
 "server_ts":1793548801312,"region":"us-east","device":"web"}
```

**Client emission rules (web player and simulator):**
- `play` when playback starts or resumes; `pause`; `seek` (after the seek completes); `buffer` on the HTML5 `waiting` event; `heartbeat` every **15 s** while playing; `complete` on `ended`.
- Batch up to **25** events per request. Flush every **5 s**, and **immediately** on `pause`, `complete`, and page hide (`fetch(..., {keepalive:true})`).
- Retry only events rejected with reason `THROTTLED` (max 3 times, exponential backoff).

**Semantics the backend guarantees:**
- **Progress:** the event with the greatest `client_ts` wins (out-of-order safe). `completed = (event_type == "complete") or position_sec >= 0.95 * duration_sec`.
- **Trending:** counts **distinct `play` events** (by `event_id`) per UTC date of `server_ts`.
- Duplicates (same `event_id`) are never double-counted in trending or QoE.

---

## 7. Contract: HTTP API

Base URL: `https://<api-id>.execute-api.us-east-1.amazonaws.com` (the `$default` stage, no path prefix). Published to SSM `/earshot/<stage>/api/url` and to the web app's `config.json`.

### 7.1 General
- **Auth:** every route except `GET /health` needs `Authorization: Bearer <Cognito access token>` (HTTP API JWT authorizer; issuer = user pool; audience = both app client IDs).
- **Identity:** `user_id = token claim "sub"`. Read the claims from `event["requestContext"]["authorizer"]["jwt"]["claims"]`.
- **CORS:** origins = CloudFront URL + `http://localhost:5173`; methods GET, POST, OPTIONS; headers `authorization, content-type, x-earshot-sim-user`.
- **Throttling:** stage default rate 500 req/s, burst 1000.
- **Errors:** `{"error":{"code":"<UPPER_SNAKE>","message":"<human text>"}}` with codes `BAD_REQUEST` 400, `UNAUTHORIZED` 401, `FORBIDDEN` 403, `NOT_FOUND` 404, `PIPELINE_OFFLINE` 503, `INTERNAL` 500.
- **EpisodeCard** (used in many responses):
```json
{"show_id":"920666","episode_id":"16795090","title":"Ep 12: The Vanishing",
 "show_title":"Serial Stories","image_url":"https://...","audio_url":"https://...",
 "duration_sec":2810,"genre":"true-crime","position_sec":734}
```
`position_sec` appears only where noted.

### 7.2 Simulator impersonation rule
The Cognito group **`simulator`** (`cognito:groups` claim; in HTTP API claims it may arrive as the string `"[simulator]"`, so parse defensively) may act on behalf of virtual users:
- `POST /events`: `user_id` in each event is kept **only if** it starts with `sim-`; otherwise the event is rejected `FORBIDDEN_USER`.
- Read routes: header `X-Earshot-Sim-User: sim-000042` makes the request act as that user.
- **Non-simulator callers:** `user_id` is always the token `sub`. The body value and the header are ignored.

### 7.3 Routes

| Method & path | Owner | Response 200 |
|---|---|---|
| `GET /health` | M2 | `{"status":"ok","stage":"<stage>"}` (no auth) |
| `GET /genres` | M2 | `{"genres":[{"id":"true-crime","name":"True Crime"}, ...]}` |
| `GET /shows?genre=<id>&limit=<1..50, default 20>` | M2 | `{"shows":[{"show_id","title","author","image_url","genre","episode_count"}]}` sorted by title |
| `GET /shows/{showId}` | M2 | `{"show":{...show fields, "description"}, "episodes":[EpisodeCard (no position)...]}` newest first; 404 if unknown |
| `GET /progress/{episodeId}` | M2 | `{"episode_id","position_sec","completed","updated_at"}`; if none: `{"episode_id","position_sec":0,"completed":false,"updated_at":null}` |
| `GET /trending?limit=<1..20, default 10>` | M2 | `{"date":"2026-11-02","items":[{...EpisodeCard, "plays":123}]}` (today UTC, plays desc) |
| `GET /home` | M2 | see 7.4 |
| `POST /events` | M3 | see 7.5 |

### 7.4 `GET /home`
```json
{"user_id":"sim-000042","generated_at":1793548801312,"degraded":false,
 "rows":[
   {"id":"continue","title":"Continue Listening","source":"progress","items":[EpisodeCard + position_sec, ...]},
   {"id":"trending","title":"Trending Now","source":"trending","items":[EpisodeCard + "plays"]},
   {"id":"recs-1","title":"Because you listened to Ep 12: The Vanishing","source":"personalized","items":[...]},
   {"id":"recs-2","title":"Because you listened to ...","source":"personalized","items":[...]}
 ]}
```
Rules:
1. **continue:** up to 10 progress items with `completed=false`, newest `updated_at` first. Omit the row if empty.
2. **trending:** top 10 from today's trending. If fewer than 5, fill from `POPULAR`. Omit only if both are empty.
3. **recs:** if flag `recs_enabled` is true and the `RECS` item exists → up to 2 rows with `source:"personalized"`. Otherwise → one row `{"id":"popular","title":"Popular on Earshot","source":"popular_fallback"}` from `POPULAR`, or from `FEATURED` if `POPULAR` is missing.
4. **Fallback on failure:** the recs lookup uses a DynamoDB client with connect/read timeout 0.3 s and 1 retry. Any exception or timeout (or `recs_fault_injection=true`) → use rule 3's fallback, set `"degraded":true`, and emit the `HomeFallback` metric. **`/home` must never return 5xx because of recs.**
5. The response always contains **at least one row** (`FEATURED` guarantees this).
6. Cards are hydrated with `BatchGetItem` (episode items + show `META` for `show_title`).

### 7.5 `POST /events`
Request: `{"events":[Event, ...]}` with 1–25 events and body ≤ 64 KB.
Response **202**: `{"accepted":24,"rejected":[{"index":3,"reason":"INVALID_FIELD:position_sec"}]}`

Ingest behavior:
1. Validate each event (§6). Reject reasons: `INVALID_JSON`, `INVALID_FIELD:<name>`, `FORBIDDEN_USER`, `THROTTLED`.
2. Apply the identity rule (§7.2). Set `server_ts`, and set `schema_version=1` if missing.
3. `PutRecords` to stream `earshot-<stage>-events` with `PartitionKey=user_id`. Retry failed records up to 3 times (backoff 50/100/200 ms). Records still failing → rejected `THROTTLED`.
4. Stream not found → **503 `PIPELINE_OFFLINE`** for the whole request.
5. Whole body invalid / not JSON / >25 events → **400**.
6. Emit metrics `EventsAccepted`, `EventsRejected`.

**Definition of "lost event" (for S4):** accepted by the API (counted in `accepted`) but never stored in S3. Rejected events are reported back to the sender, so they aren't counted as lost.

---

## 8. Contract: DynamoDB single table

Table **`earshot-<stage>-main`** · on-demand · `PK` (S) + `SK` (S) · GSI **`GSI1`** on `GSI1PK` (S) + `GSI1SK` (S), projection ALL · TTL attribute **`ttl`** (epoch seconds).

### 8.1 Items

| Item | PK | SK | Attributes | Writer | Readers |
|---|---|---|---|---|---|
| Show | `SHOW#<show_id>` | `META` | `show_id, title, author, description, image_url, genre, episode_count`, `GSI1PK=GENRE#<genre>`, `GSI1SK=SHOW#<lowercase title>` | M2 seed | M2 |
| Episode | `SHOW#<show_id>` | `EP#<episode_id>` | `show_id, episode_id, title, audio_url, duration_sec, published_at (epoch s), image_url, genre` | M2 seed | M2, M3 sim |
| Featured | `FEATURED` | `GLOBAL` | `items: [{show_id, episode_id}]` (20 hand-picked, verified playable) | M2 seed | M2 |
| Progress | `USER#<user_id>` | `PROG#<episode_id>` | `show_id, episode_id, position_sec, duration_sec, completed (BOOL), client_ts (N ms), updated_at (N ms)` | **M4** | M2 |
| Recs | `USER#<user_id>` | `RECS` | `rows: [{seed_show_id, seed_episode_id, items:[{show_id, episode_id, score}]}]` (≤ 2 rows × 10 items), `generated_at, run_id` | **M5** | M2 |
| Popular | `POPULAR` | `GLOBAL` | `items: [{show_id, episode_id, plays}]` (top 20, last 7 days), `generated_at, run_id` | **M5** | M2 |
| Trending counter | `TREND#<yyyy-mm-dd>` | `EP#<episode_id>` | `plays (N), show_id`, `ttl = +8 days` | **M4** | M2 |
| Dedupe marker | `EVT#<event_id>` | `EVT` | `ttl = +24 h` | **M4** | M4 |
| QoE window | `QOE#<region>` | `MIN#<yyyymmddHHMM>` | `buffers (N)`, `ttl = +1 day` | **M4** | M4 |

### 8.2 Required write patterns (M4)
- **Progress (every event type):** `UpdateItem` SET fields, with `ConditionExpression: attribute_not_exists(client_ts) OR client_ts < :ts`. `ConditionalCheckFailedException` = stale event → ignore, count `StaleEvents`.
- **Trending (`play` only):** `TransactWriteItems` = [Put dedupe marker with `attribute_not_exists(PK)`, Update trending counter `ADD plays :1`]. Cancelled because of the marker condition = duplicate → skip, count `DuplicateEvents`. This makes trending **exact** even with retries.
- **QoE (`buffer` only):** Put dedupe marker (conditional). If that succeeds, `UpdateItem ADD buffers :1` with `ReturnValues=UPDATED_NEW`. If the new value **equals** `QOE_THRESHOLD` (env, default `30` per region per minute), publish **one** SNS message to the QoE topic. (A crash between the two writes may undercount by 1; acceptable for alerting.)
- Trending date and QoE minute come from **`server_ts`** (UTC).

### 8.3 Genres (fixed)
`true-crime` True Crime · `comedy` Comedy · `news` News · `technology` Technology · `business` Business · `science` Science · `sports` Sports · `history` History

Catalog target: **~50 shows (≈6 per genre) × ~20 newest episodes ≈ 1,000 episodes**.

---

## 9. Contract: names, SSM parameters, flags

`config.py` builds every name from `stage`. Use these exact patterns:

| Resource | Name |
|---|---|
| DynamoDB table | `earshot-<stage>-main` |
| Lake bucket | `earshot-<stage>-lake-<account_id>` |
| Web bucket | `earshot-<stage>-web-<account_id>` |
| Kinesis stream | `earshot-<stage>-events` |
| Firehose | `earshot-<stage>-events-to-s3` |
| Glue database | `earshot_<stage>` (hyphens → underscores) |
| Glue table | `events` |
| Athena workgroup | `earshot-<stage>` (results `s3://<lake>/athena-results/`, 1 GB per-query scan cutoff) |
| SNS topics | `earshot-<stage>-qoe-alerts`, `earshot-<stage>-ops-alerts` |
| SQS DLQ | `earshot-<stage>-processor-dlq` |
| State machine | `earshot-<stage>-recs` |
| Cognito domain prefix | `earshot-<stage>-<last 6 digits of account_id>` |
| Lambda functions | `earshot-<stage>-api`, `-ingest`, `-processor`, `-recs-writer` |

**S3 lake layout:**
```
events/dt=YYYY-MM-DD/hour=HH/*.parquet      ← Firehose (prefix uses !{timestamp:yyyy-MM-dd} / !{timestamp:HH})
errors/<error-type>/dt=YYYY-MM-DD/          ← Firehose error output
recs-runs/<run_id>/                         ← Athena outputs used by recs writer
athena-results/                             ← workgroup results (lifecycle: expire 7 days)
```
Glue table `events`: Parquet, columns exactly as in §6 (`int` for int fields, `bigint` for `client_ts`/`server_ts`), partition keys `dt` (string) and `hour` (string), **partition projection** enabled (`dt` date `yyyy-MM-dd` range `2026-09-01,NOW`; `hour` integer 0–23 with 2 digits). No crawlers, no `MSCK REPAIR`.

Firehose: source = Kinesis stream; format conversion to Parquet using the Glue table; buffer 64 MiB / **60 s**.

**SSM parameters (String, Standard tier):**

| Parameter | Value | Written by |
|---|---|---|
| `/earshot/<stage>/api/url` | API base URL | Base stack |
| `/earshot/<stage>/cognito/user-pool-id` | id | Base stack |
| `/earshot/<stage>/cognito/web-client-id` | id | Base stack |
| `/earshot/<stage>/cognito/sim-client-id` | id (USER_PASSWORD_AUTH enabled) | Base stack |
| `/earshot/<stage>/flags` | JSON `{"recs_enabled":true,"recs_fault_injection":false}` | Base stack (initial); `scripts/set_flag.py` |
| `/earshot/<stage>/sim/password` | SecureString (AWS-managed key), simulator user password | Manually, once |
| `/earshot/<stage>/podcastindex/key`, `.../secret` | SecureString, Podcast Index credentials | Manually (M2 only) |

API Lambdas cache `flags` for **10 s**.

**Lambda environment variables:** `STAGE`, `TABLE_NAME`, `STREAM_NAME`, `QOE_TOPIC_ARN`, `QOE_THRESHOLD`, `FLAGS_PARAM`, `LAKE_BUCKET`, `ALLOWED_GENRES` (comma list). Each function gets only what it uses.

**Cognito:** user pool with email sign-in, self sign-up on, Essentials/Lite tier (free ≤ 10k MAU). Groups: `listeners` (default) and `simulator`. Two app clients without secrets: **web** (auth code + PKCE, managed login, callbacks = CloudFront URL + `http://localhost:5173`) and **sim** (`USER_PASSWORD_AUTH`). One user `sim-bot@earshot.test` in `simulator`. The API uses **access tokens**.

**Web runtime config:** the base stack writes `config.json` to the web bucket:
`{"apiUrl","region","userPoolId","webClientId","cognitoDomain","stage"}`. The app fetches it at startup (no rebuild per stage). `VITE_USE_MOCKS=true` serves `contracts/samples/*.json` instead.

---

## 10. Processing, batch and monitoring specs

**Kinesis → processor event source mapping:** batch size 100, batching window 1 s, starting position `TRIM_HORIZON`, parallelization factor 1, `ReportBatchItemFailures` on, bisect on error on, max retries 5, max record age 3600 s, on-failure destination = SQS DLQ. The processor returns `batchItemFailures` only for transient AWS errors. A malformed record is logged and skipped (it isn't retried forever).

**Recommendations (M5), Step Functions `earshot-<stage>-recs`:**
1. Parallel: Athena `recs.sql` and `popular.sql` (`startQueryExecution.sync`, workgroup `earshot-<stage>`, output under `recs-runs/<run_id>/`).
2. Recs writer Lambda reads both result CSVs from S3 and writes `RECS` items (BatchWriteItem) + the `POPULAR` item.
3. Output `{run_id, users_written, popular_count}`.

Algorithm (`recs.sql`, last 30 days of `play` events):
- `(user_id, episode_id)` distinct pairs.
- Co-occurrence: count of users who played both A and B.
- For each user, take their **2 most recent distinct played episodes** as seeds. For each seed, take the top 10 co-played episodes the user hasn't played, by co-count.
- If fewer than 10, pad with the most-played episodes in the seed's genre that the user hasn't played.
- Only users with **≥ 3 distinct plays** get `RECS`.

`popular.sql`: top 20 episodes by distinct `play` events, last 7 days.

**Custom metrics (namespace `Earshot`, dimension `Stage`; emit with CloudWatch Embedded Metric Format in logs, about 8 metrics total):**
`EventsAccepted`, `EventsRejected` (M3) · `PlaysCounted`, `DuplicateEvents`, `StaleEvents`, `QoEAlertsSent` (M4) · `HomeFallback` (M2) · `RecsUsersWritten` (M5)

**Dashboard `earshot-<stage>` (M6):** API count/5xx/p95 latency; Lambda errors/throttles/duration (4 functions); Kinesis `IncomingRecords` + `GetRecords.IteratorAgeMilliseconds`; Firehose `DeliveryToS3.Records`; DynamoDB consumed WCU/RCU + throttles; all 8 custom metrics.

**Alarms (≤ 10, to `ops-alerts`):** processor iterator age > 60 s; DLQ visible messages > 0; API 5xx rate > 1 % (5 min); any Lambda throttles > 0; Firehose delivery failures > 0.

---

## 11. Simulator spec (M3)

CLI (runs on the EC2 instance through SSM Session Manager, or locally):
```
python -m simulator run      --stage prod --users 2000 --rate 500 --duration 600 --seed 42 [--mode normal|buffer-storm --storm-region us-west]
python -m simulator generate --out events.jsonl --users 200 --events 10000 --shuffle --dup-rate 0.10 --seed 7
python -m simulator replay   --file events.jsonl --direct-kinesis --stage <stage>   # sets server_ts itself
```
- Virtual users `sim-000000 … sim-NNNNNN`, each with 2 favorite genres. Episode choice is affinity-weighted plus Zipf popularity. Users continue unfinished episodes 60 % of the time.
- Uses the **committed catalog snapshot** (`contracts/samples/catalog.json`), so IDs match every account.
- Authenticates as `sim-bot` through the `sim` app client. Refreshes the token before expiry.
- Sends batches of 25 to `POST /events`. Retries only `THROTTLED`.
- At the end, writes a run report: `{"run_id","start_ms","end_ms","sent","accepted","rejected_by_reason":{...}}`.
- `buffer-storm` mode: ≥ 100 `buffer` events/min in one region (QoE threshold is 30).
- Files from `generate` are the fixtures M4 and M5 use to build and test **without AWS**.

---

## 12. Working agreements

- **Updating this file:**
  - **Non-contract sections** (§1–§5, §10–§14): any member may update through a normal PR with one review.
  - **Contract sections** (§6–§9) and `contracts/`: PR labelled `contract-change`, approved by **every affected owner + M6**. While status is `DRAFT`, anything can change. Once it's `FROZEN`, only **additive** changes (new optional field, new route, new item type). Never rename or remove a field.
  - Every change gets a §15 Changelog line.
- **Updating `TRACKER.md`:** each member keeps their own rows current. Agents update rows as part of their PR (rule 10). Anyone may add tasks; only the owner (or M6) marks a task `done`. Blockers go to the group chat, not a table.
- **Branches:** `m<#>/<short-desc>` (e.g. `m4/progress-conditional-write`). PR to `main`, one teammate review, squash merge. **CI must show ✅ before merging** (`.github/workflows/ci.yml` runs `make lint`, `make test`, `make synth`), so `main` always synthesizes cleanly.
- **Public repo:** never commit AWS account IDs, emails, keys or passwords.
- **Commits:** `<area>: <imperative summary>` (e.g. `processor: dedupe play events with transactions`).
- **Definition of done** for any task: code + unit tests for core logic + deployed and verified in your own stage + `TRACKER.md` row updated + any contract fixture updated.
- **Mocks first:** build against `contracts/samples/` before the real upstream exists.
- **Cite AI use:** keep a line in `docs/ai-usage.md` (tool, what for) for the final slides.

---

## 13. Role briefs (task list for each role: `TRACKER.md`)

**M1 (Frontend & Auth):** React/Vite/TS app with pages Home (rows from `/home`), Genre browse, Show detail, persistent Player bar (HTML5 `<audio>`), Live Trending (polls `/trending` every 5 s), and a Settings region selector (for demos). Cognito managed login via `react-oidc-context`. Resume: on play, `GET /progress/{id}` then set `currentTime`. Event emitter per §6 rules. Mock mode with `contracts/samples`. Construct: Cognito (pool, groups, 2 clients, domain, sim-bot user via script), web bucket, CloudFront with OAC, `config.json`.

**M2 (API & Catalog):** One API Lambda with a small router for all GET routes (§7.3, §7.4), including the fallback logic, flags cache and hydration. Catalog scripts: `fetch_catalog.py` (Podcast Index API → `catalog.json`, run once, committed), `seed_catalog.py` (snapshot → DynamoDB incl. `FEATURED`). Construct: HTTP API, JWT authorizer, routes, CORS, throttling, API Lambda. The API construct takes M3's ingest function as a prop and wires it to `POST /events`.

**M3 (Ingest & Simulator):** Ingest Lambda (§7.5) with the validation shared in `services/shared/validate.py`. `constructs/ingest.py` (base) creates the function and grants `kinesis:PutRecords` on the name-based stream ARN. `constructs/stream.py` (pipeline) creates the Kinesis stream. Simulator (§11), committed `contracts/samples/events.jsonl`. EC2 construct: t3.micro AL2023, default VPC public subnet, no inbound SG rules, instance role with SSM core + read of the simulator S3 asset + read of `/earshot/<stage>/*` params; user-data installs Python deps and unpacks the simulator.

**M4 (Real-time processing):** Processor Lambda (§8.2, §10) with partial batch failures, plus the event source mapping in the pipeline stack and the DLQ in base. Owns the **S3 correctness replay test** and the **S9 QoE test** logic.

**M5 (Lake & Recs):** Glue database and `events` table with partition projection (base), Firehose with Parquet conversion (pipeline), Athena workgroup, SQL in `athena/`, Step Functions + recs writer (base). Owns the **S5 reconciliation** and **S7 recs coverage** tests.

**M6 (Platform & Testing):** CDK app/stacks/config/stubs, Makefile + scripts, monitoring construct, Locust (`tests/load/`), acceptance harness for S1–S10 (`tests/acceptance/`), `docs/results.md`, the cost tracker, the shared `prod` account and team IAM users, and integration gates.

---

## 14. Success criteria (what "working" means)

| # | Criterion | Target |
|---|---|---|
| S1 | End-to-end | New user: sign up → log in → browse → play → pause → resume |
| S2 | Resume freshness/accuracy | Visible in API < 5 s after pause (p95 of 20 trials); resume within ±2 s |
| S3 | Bad-input correctness | 10k shuffled events with 10 % duplicates → 0 wrong positions, 0 double counts |
| S4 | Throughput, no loss | 500 events/s for 10 min; accepted = processed = stored (Athena distinct count) |
| S5 | Hot vs cold agreement | DynamoDB trending vs Athena distinct plays within 1 % |
| S6 | API performance | `/home` p95 < 500 ms at 50 concurrent users, < 1 % errors (Locust from EC2) |
| S7 | Personalization | 100 % of sampled users with ≥ 3 plays get a personalized row; new users get the fallback; never empty |
| S8 | Graceful degradation | `recs_enabled=false` **and** `recs_fault_injection=true` → `/home` 0 × 5xx, `degraded:true` |
| S9 | Alerting | Buffer storm in one region → SNS email < 2 min |
| S10 | Cost & automation | Semester < $30 (shared account); `pipeline-up` < 10 min; full deploy from scratch < 25 min; after `pipeline-down`, 0 hourly-billed resources |

---

## 15. Changelog

Add the newest entry at the top: `YYYY-MM-DD · M<#> · §<section> · what changed and why`.

| Date | Who | Section | Change |
|---|---|---|---|
| 2026-10-19 | M6 | §0, §3, §12 | Added CI (M6-04): lint, tests and synth on every PR; merge only on ✅. Removed the TRACKER Blockers table (blockers go to the group chat). Node 22+ (20 is EOL). No account IDs/emails in the public repo |
| 2026-10-19 | M6 | §4, §5 | M6-01 skeleton. **Pipeline now references base by name/ARN, not CDK props** (avoids CloudFormation export locks). `core.py` owns the table, lake bucket, SNS topics and flags param. `services/shared/names.py` is the single source of names. Lambdas use `common.python_function`. Dropped `contracts/event.schema.json` and `api.md` copies (§6/§7 are the contract; copies would drift) |
| 2026-09-27 | Team | All | v1 created: architecture, contracts §6–§9 (DRAFT), CDK Python, stdlib-only Lambdas, committed catalog snapshot, SQS DLQ, simulator group |
