# Results: success criteria S1–S10

Measured results for the success criteria in `CONTEXT.md` §14 (owner: M6, tracker M6-07). This is the source for the Results slide.

**How it's updated:** `make acceptance STAGE=prod` runs every check in `tests/acceptance/` and rewrites the matching rows below (`ONLY=S1,S10` runs some of them).
- Only `prod` results are written here. Other stages print results without changing this file.
- PASS, FAIL and ERROR replace a row. NOT IMPLEMENTED never does, so a result you recorded by hand stays.
- Raw numbers for every run are saved in `tests/acceptance/output/` (not committed).

For anything checked by hand (the browser walkthrough, the alert email's arrival time, the semester cost), edit the row directly and add evidence below.

<!-- results:start -->
| # | Criterion | Target | Owner | Status | Measured | Last run (UTC) |
|---|---|---|---|---|---|---|
| S1 | End-to-end user flow | New user: sign up → log in → browse → play → pause → resume | M1 | NOT RUN |  |  |
| S2 | Resume freshness and accuracy | Visible in API < 5 s after pause (p95 of 20 trials); resume within ±2 s | M4 + M1 | NOT RUN |  |  |
| S3 | Bad-input correctness | 10k shuffled events with 10 % duplicates → 0 wrong positions, 0 double counts | M4 | NOT RUN |  |  |
| S4 | Throughput, no loss | 500 events/s for 10 min; accepted = processed = stored (Athena distinct count) | M3 + M6 | NOT RUN |  |  |
| S5 | Hot vs cold agreement | DynamoDB trending vs Athena distinct plays within 1 % | M5 | NOT RUN |  |  |
| S6 | API performance | /home p95 < 500 ms at 50 concurrent users, < 1 % errors (Locust from EC2) | M6 + M2 | NOT RUN |  |  |
| S7 | Personalization coverage | 100 % of sampled users with ≥ 3 plays get a personalized row; new users get the fallback; never empty | M5 | NOT RUN |  |  |
| S8 | Graceful degradation | recs_enabled=false and recs_fault_injection=true → /home 0 × 5xx, degraded:true | M2 | NOT RUN |  |  |
| S9 | Quality alerting | Buffer storm in one region → SNS email < 2 min | M4 + M3 | NOT RUN |  |  |
| S10 | Cost and automation | Semester < $30; pipeline-up < 10 min; full deploy from scratch < 25 min; after pipeline-down, 0 hourly-billed resources | M6 | NOT RUN |  |  |
<!-- results:end -->

## S10 notes (recorded by hand)

| Measurement | Target | Measured | Date | How |
|---|---|---|---|---|
| Semester cost of the shared `prod` account | < $30 | | | Billing console → Bills, month to date (add the months up) |
| `make pipeline-up STAGE=prod` | < 10 min | | | Time the command |
| Full deploy from scratch: `deploy-base`, `seed`, `pipeline-up` on a new stage | < 25 min | | | Time the three commands |

## Evidence

Screenshots, charts and links for the slides, e.g. the S4/S6 load and latency charts and the S9 alert email.
