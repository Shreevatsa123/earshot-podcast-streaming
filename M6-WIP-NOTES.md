# M6 work in progress (storage branch, not for merge)

This branch stores M6 code that's written but not merged yet: M6-05 monitoring, M6-07 acceptance harness and M6-08 cost check.

- **Don't merge or rebase this branch.** It's based on `main` from Nov 4 (`34c0166`), before PRs #5–#14. Its docs and stack files are out of date.
- **Bring it over one task per PR:** branch from the current `main`, copy that task's files (e.g. `git checkout origin/m6/wip-platform-tasks -- scripts/cost_check.py`), apply the changes below, then write the docs against the current `main`.

## Files per task

| Task | Copy from here | Notes |
|---|---|---|
| **M6-08 cost check** (do first; S10 imports it) | `scripts/cost_check.py`, `tests/unit/test_cost_check.py`; the two retain-guard tests in `tests/unit/test_infra.py` (`test_pipeline_never_leaves_resources_behind`, `test_dev_base_leaves_nothing_behind`); Makefile `cost-check` target, and `pipeline-down` running the check | Remove the Kinesis and Firehose checks: those APIs fail on the Free plan account (`SubscriptionRequiredException`), so every run would report "couldn't check" |
| **M6-05 monitoring** | `infra/earshot_infra/constructs/monitoring.py`, `tests/unit/test_monitoring.py`; in `base_stack.py`, pass `http_api=api.http_api` | Switch to CONTEXT §10: SQS metrics for both queues (`NumberOfMessagesSent`, `ApproximateNumberOfMessagesVisible`, `ApproximateAgeOfOldestMessage`), 5 functions, both DLQs, archiver errors, and the hot-queue age alarm in the **pipeline** stack. Create alarms only for prod (`cfg.is_prod`) so extra stages in the shared account stay within the 10 free alarm metrics |
| **M6-07 acceptance harness** | `tests/acceptance/`, `tests/unit/test_acceptance.py`, `docs/results.md`; `SIM_BOT_USERNAME` in `services/shared/names.py`; in `pyproject.toml`, `tests` on the pytest path and `acceptance` / `cost_check` as first-party; Makefile `acceptance` target | `test_acceptance.py`'s fake server returns `PIPELINE_OFFLINE`, which no longer exists. Use another code |

## Don't copy (main has newer versions)

- `infra/earshot_infra/stacks/service_check_stack.py`, `scripts/account_check.py`, `tests/unit/test_account_check.py`: M6-03, merged in #7 and #12. The copies here still include Kinesis/Firehose and the old Lambda threshold.
- `infra/app.py`, `config.py`, `names.py` (except `SIM_BOT_USERNAME`), `CONTEXT.md`, `TRACKER.md`, `README.md`, `docs/ai-usage.md`: out of date. Edit the current `main` versions instead.
