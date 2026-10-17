# Earshot — Business Requirements Document (BRD)

| | |
|---|---|
| **Project** | Earshot: A Real-Time Podcast Streaming & Analytics Platform on AWS |
| **Course** | MSML 650 Cloud Computing, Fall 2026 Term Project |
| **Version / Status** | 1.0 / Draft, becomes approved when all 6 members sign §15 |
| **Related documents** | `CONTEXT.md` (technical contracts, the single source of truth) · `TRACKER.md` (tasks, status, gates) · `docs/topic-summary.md` (submitted topic) |
| **Maintenance** | Living document, updated by PR. Requirement IDs (FR/NFR/S) are never reused or renumbered; deprecated items are struck through |

---

## 1. Purpose

This document defines **what** Earshot must do, the **constraints** it must respect, and **how success is measured**. It's the agreement the six team members build against. Technical details (schemas, APIs, table keys, names) live in `CONTEXT.md`, so they're defined in only one place.

## 2. Background and problem

Streaming services must:
- remember where each user stopped,
- show what's popular right now,
- personalize content,
- keep a complete activity history for analytics.

The input is a continuous stream of small playback events that may arrive **late, out of order, or duplicated**. The business need is a system that:
1. updates what users see **within seconds** and **correctly**, despite messy input;
2. stores **every** event cheaply for SQL analysis;
3. keeps working when parts fail or traffic spikes;
4. costs nearly nothing when idle.

Earshot demonstrates this with a podcast app. Audio streams from public publisher URLs, so we never store media or copyrighted content.

## 3. Objectives

| ID | Objective | Measured by |
|---|---|---|
| O1 | Deliver a working, demo-able streaming app on AWS | S1 |
| O2 | Show correct real-time event processing | S2, S3 |
| O3 | Show a scalable, loss-free pipeline with consistent hot and cold data | S4, S5, S6 |
| O4 | Show personalization and resilience | S7, S8, S9 |
| O5 | Stay within free credits and be fully automated | S10 |
| O6 | Score full marks on every rubric item (§13) | Rubric |

## 4. Stakeholders

| Stakeholder | Interest |
|---|---|
| Instructor | Timely deliverables, correct operation, technical depth, clear presentation |
| Team (M1–M6) | Parallel, unblocked work; fair and visible individual contribution (peer evals) |
| End users (simulated + demo users) | Fast, reliable playback, resume, and relevant recommendations |
| Class audience | Understanding "how it works" in 15 minutes |

## 5. Scope

**In scope (committed)**
- Web app: sign up/login, browse by genre, show detail, audio player, home page rows, live trending page.
- Event ingestion API, real-time stream processing, S3 data lake with Athena.
- On-demand recommendation batch job, popular fallback, quality alerting.
- EC2 traffic simulator, load and correctness tests, CloudWatch monitoring, cost controls.
- Infrastructure as code (one-command deploy/teardown).

**Out of scope**
- Storing or transcoding audio; mobile apps; social features; payments.
- ML model training services (SageMaker etc.); multi-region; custom domains.
- Production-grade security hardening (WAF, pen testing).

**Stretch (only after Gate G4 passes)**
- Apache Iceberg table with time travel.
- A/B test of two ranking methods.
- GitHub Actions CI deploy.
- Auto Scaling the simulator fleet.

## 6. Constraints

| ID | Constraint | Implication |
|---|---|---|
| C1 | **Cost:** must stay within free credits (~$100–200 per account); target **< $30** in the shared account for the semester | Serverless first. Hourly-billed resources (Kinesis, Firehose, EC2) only in an ephemeral stack deployed for tests and demos. Banned list of costly services. Budgets alerts on day 1 |
| C2 | **Parallel, independent work:** 6 members working separately | Frozen contracts, one owner per component, stub constructs, mock fixtures, a personal AWS account per member |
| C3 | **Balanced difficulty:** not trivial, not overengineered | 1 pipeline, 1 table, 1 stream, 1 batch job. No ML services. Similar workload per member (7–10 tracker tasks each) |
| C4 | **Fixed course deadlines:** status update Nov 8, slides Dec 6, demo Dec 7–8, peer evaluations Dec 13 | Work is ordered by dependency, not by date; gate G3 must be reached before the status update and G6 before slides |
| C5 | **Course rules:** live demo in a 15-minute presentation; cite all sources and AI | Demo plan + recorded backups; `docs/ai-usage.md` |
| C6 | **Data/legal:** no copyrighted media | Metadata only, from Podcast Index; synthetic users |
| C7 | **Tooling:** one IaC tool, one language for the backend | AWS CDK v2 (Python), Lambda Python 3.12 stdlib + boto3 |

## 7. Assumptions and dependencies

- Each member has (or creates) an AWS account in the **Free plan**. **Accounts must be created after Jun 8, 2026** so the 6-month plan covers the Dec 7–8 demo. One member's account is the **shared `prod` account**, with IAM users for teammates.
- Some services may be restricted on Free plan accounts ([AWS docs](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)). M6 verifies early (tracker M6-03, part of gate G0) that every approved service deploys. If one is blocked, the shared account is upgraded to the Paid plan; credits still apply and Budgets stay on.
- The Podcast Index API (free key) is reachable once to build the catalog snapshot. After that, no live dependency.
- New accounts may have a low Lambda concurrency quota; an increase is requested as part of setup (M6-02).
- Each member's AI agent has repo access and follows `AGENTS.md`, so AI-written code is held to the same contracts and review rules as human-written code.
- Publisher audio URLs are generally stable; 20 demo episodes are verified before the demo.

## 8. Functional requirements

Priority: **M** = Must (needed for gate G3, the MVP), **S** = Should (needed for gate G4), **C** = Could (stretch).

| ID | Requirement | Pri | Owner | Verified by |
|---|---|---|---|---|
| FR-01 | Users can sign up, log in and log out with email/password (Cognito managed login) | M | M1 | S1 |
| FR-02 | Users can browse shows by genre (8 fixed genres) and open a show's episode list | M | M1, M2 | S1 |
| FR-03 | Users can play, pause and seek an episode in the browser; audio streams from the publisher URL | M | M1 | S1 |
| FR-04 | The app sends playback events (play, pause, seek, buffer, heartbeat, complete) in batches | M | M1 | S2 |
| FR-05 | The API accepts batched events, validates them, ties them to the authenticated user, and reports rejected events | M | M3 | S3, S4 |
| FR-06 | The system keeps each user's latest position per episode, robust to out-of-order and duplicate events | M | M4 | S2, S3 |
| FR-07 | Opening an episode resumes at the saved position; home shows a **Continue Listening** row | M | M1, M2 | S1, S2 |
| FR-08 | The system counts plays per episode per day exactly once and shows **Trending Now** (home row + live page) | M | M4, M2, M1 | S3, S5 |
| FR-09 | Every accepted event is stored in the S3 data lake (Parquet, date/hour partitions) and is queryable with SQL | M | M5 | S4, S5 |
| FR-10 | A batch job computes "Because you listened to X" recommendations for users with ≥ 3 plays, plus a popular list | S | M5 | S7 |
| FR-11 | Home shows personalized rows when available, and otherwise a popular or featured fallback. The home page is never empty | S | M2 | S7, S8 |
| FR-12 | If recommendations are disabled or failing, home still loads and is marked degraded | S | M2 | S8 |
| FR-13 | A buffering spike in a region sends one email alert per minute window | S | M4 | S9 |
| FR-14 | A simulator generates realistic traffic for N virtual users at a set rate, including a buffer-storm mode | M | M3 | S4, S9 |
| FR-15 | Operators can see system health on one dashboard and get alarm emails | S | M6 | Demo |
| FR-16 | The whole system deploys and tears down with documented one-line commands; idle cost ≈ $0 | M | M6 | S10 |
| FR-17 | Users can pick a demo "region" in settings (to show QoE alerts by region) | C | M1 | S9 demo |

## 9. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Performance | `GET /home` p95 < 500 ms at 50 concurrent users; position visible < 5 s after pause |
| NFR-02 | Throughput | Sustain 500 events/s for 10 min on one Kinesis shard |
| NFR-03 | Correctness | 0 lost accepted events; 0 double-counted plays; latest position always wins |
| NFR-04 | Consistency | Real-time trending matches lake counts within 1 % |
| NFR-05 | Availability / resilience | Recs failure never causes a home 5xx; failed stream batches go to a DLQ and raise an alarm |
| NFR-06 | Security | All API routes except `/health` require a Cognito JWT; users can only act as themselves (only the simulator group may act as `sim-*` users); least-privilege IAM per function; secrets in SSM SecureString; private S3 buckets (CloudFront OAC); EC2 with no inbound ports |
| NFR-07 | Cost | Idle ≈ $0/month; shared account < $30 for the semester; Budgets alerts at $5 and $20 in **every** account |
| NFR-08 | Maintainability | Infrastructure 100 % in CDK; contracts versioned; unit tests for core logic; PR review for every change |
| NFR-09 | Observability | JSON logs (7-day retention), 8 custom metrics, 1 dashboard, ≤ 10 alarms |
| NFR-10 | Portability | Any member can deploy the full system into their own account under their own stage name |

## 10. Solution overview

Four data paths on serverless AWS (full detail: `CONTEXT.md` §2):

- **Read:** CloudFront web app → API Gateway (JWT) → Lambda → DynamoDB.
- **Hot:** `POST /events` → ingest Lambda → Kinesis → processor Lambda → DynamoDB + SNS.
- **Cold:** Kinesis → Data Firehose → Parquet in S3 → Glue Catalog → Athena.
- **Batch:** Step Functions → Athena → recs writer Lambda → DynamoDB.

**Services:**
- **Core:** S3, CloudFront, Cognito, API Gateway, Lambda, DynamoDB, Kinesis Data Streams, Data Firehose, Glue Data Catalog, Athena, Step Functions, SNS, EC2, CloudWatch.
- **Supporting:** SQS (DLQ), SSM Parameter Store, IAM, AWS Budgets.

Two stacks per environment:
- **base** (persistent, ≈ $0 idle)
- **pipeline** (Kinesis, Firehose, EC2 simulator; deployed only for tests and demos)

**Parallel-work model:**
1. Each member owns one component (code + CDK construct) and deploys the whole system into their own account.
2. Unbuilt components are stubs, and upstream data comes from committed fixtures (catalog snapshot, sample events, sample API responses).
3. Integration happens in the shared `prod` account at dependency-based gates.
4. Each member's AI agent has repo access and follows `AGENTS.md`: owned paths only, contracts unchanged, and `TRACKER.md` updated in every PR.

## 11. Responsibilities and gates

| Member | Component | Primary success criteria owned |
|---|---|---|
| M1 | Frontend & Auth | S1, S2 (client side) |
| M2 | API & Catalog | S6 (with M6), S8 |
| M3 | Ingest & Simulator | S4 (with M6), S9 (with M4) |
| M4 | Real-time Processing | S2, S3, S9 |
| M5 | Data Lake & Recommendations | S5, S7 |
| M6 | Platform, Monitoring & Testing (integration lead) | S4, S6, S10, results report |

Gates are reached **when their items are done**, not on dates. Live status and the task list for each gate are in `TRACKER.md`.

| Gate | Exit criteria | Must precede |
|---|---|---|
| **G0** Foundations | Contracts frozen; repo + stubs deploy in all 6 accounts; Budgets set; catalog snapshot + fixtures committed; Free plan service check done | Everything else |
| **G1** Thin slice | In `prod`: one event from `POST /events` reaches DynamoDB progress **and** an Athena row; web app logs in | — |
| **G2** Core features | FR-01–FR-09 working on the real backend in `prod` | — |
| **G3** MVP | S1, S2 pass | **Status update (Nov 8)** |
| **G4** Complete features | FR-10–FR-15; S3, S5, S7, S8, S9 pass | Slides drafting |
| **G5** Scale & backups | S4, S6 pass; backup demo videos recorded | — |
| **G6** Final | S10 measured; `docs/results.md` final; 2 rehearsals | **Slides (Dec 6)**, demo (Dec 7–8) |

## 12. Success criteria and acceptance

The project is accepted when **S1–S10 pass in the `prod` stage** and the results are recorded in `docs/results.md`. Exact targets and test definitions: `CONTEXT.md` §14. They cover every criterion in the submitted topic summary and add S7 (personalization coverage).

| # | Criterion | Target | Test owner |
|---|---|---|---|
| S1 | End-to-end user flow | Sign up → resume works | M1 |
| S2 | Resume freshness / accuracy | < 5 s p95; ±2 s | M4 + M1 |
| S3 | Bad-input correctness | 0 wrong positions, 0 double counts | M4 |
| S4 | Throughput, no loss | 500 ev/s × 10 min, 0 lost | M3 + M6 |
| S5 | Hot vs cold agreement | ≤ 1 % difference | M5 |
| S6 | API performance | p95 < 500 ms @ 50 users, < 1 % errors | M6 + M2 |
| S7 | Personalization coverage | 100 % eligible users personalized; never empty | M5 |
| S8 | Graceful degradation | 0 × 5xx with recs off or faulted | M2 |
| S9 | Quality alerting | Email < 2 min | M4 + M3 |
| S10 | Cost & automation | < $30; pipeline up < 10 min; full deploy < 25 min; 0 idle hourly resources | M6 |

## 13. Rubric traceability

| Rubric item | Pts | How this BRD secures it |
|---|---|---|
| Timeliness (topic + status) | 3 | Topic submitted on time; gate G3 must be reached before the status update (Nov 8), which M6 owns (tracker M6-09) |
| Correct operation | 7 | 10 measurable criteria; Must/Should/Could scope; gates; recorded backups |
| Technical content of slides | 7 | Architecture, the 4 paths, design decisions (conditional writes, transactions, partition projection, ephemeral stack), measured results, cost |
| Presentation clarity | 5 | 4 live demo segments; each member explains their component; 2 full rehearsals are part of gate G6 |
| Peer evaluation | 8 | One clearly owned component per member, balanced workload, visible PR history |
| Late slides (−5/day) | — | Slides due Dec 6; gate G6 must be reached before then |

## 14. Risks

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| A service is blocked on the Free plan | Medium | High | Early service check (M6-03); upgrade shared account to Paid plan if needed | M6 |
| Hourly resources left running | Medium | Medium | `pipeline-down` after every session; Budgets alerts; weekly cost check | All / M6 |
| Contract drift between members | Medium | High | Single CONTEXT.md, PR approval rule, fixtures, G1 thin slice | M6 |
| A member falls behind | Medium | High | Stubs and fixtures keep others unblocked; Must/Should/Could priorities; pair at gates | M6 |
| Lambda concurrency quota too low for S6 | Medium | Medium | Request increase during setup (M6-02) | M6 |
| Broken audio URLs on demo day | Low | Medium | 20 verified demo episodes in `FEATURED`; check the day before | M2 |
| Live demo failure (Wi-Fi/API) | Low | High | Pipeline deployed 2 h early; recorded backups | All |
| Scope creep | Medium | Medium | Stretch work only after G4 | All |

## 15. Approvals

| Member | Role | Name | Approved (date) |
|---|---|---|---|
| M1 | Frontend & Auth | | |
| M2 | API & Catalog | | |
| M3 | Ingest & Simulator | | |
| M4 | Real-time Processing | | |
| M5 | Data Lake & Recommendations | | |
| M6 | Platform, Monitoring & Testing | | |
