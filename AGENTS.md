# Instructions for AI agents working in this repo

You are helping one member of a 6-person team build **Earshot** (MSML 650 term project). Six people, each with their own AI agent, work in this repo **in parallel**. These rules keep everyone from colliding.

## Before you write any code

1. Read **`CONTEXT.md`** fully. It's the source of truth for architecture, contracts, names and rules. **§0 is binding.**
2. Read **`TRACKER.md`**.
3. Find out which member you're working for (`M1`–`M6`) and which task ID. If the user didn't say, **ask**.
4. Check that every dependency of the task is `done` (or *(soft)*, in which case use `contracts/samples/` fixtures).
   - If a dependency isn't ready, say so. Offer to work against fixtures or pick another unblocked task.

## While working

- **Edit only paths owned by your member** (`CONTEXT.md` §4), plus your own rows in `TRACKER.md` and §15 of `CONTEXT.md`.
  - Need a change elsewhere? Don't edit their files. Tell the user exactly what's needed and from which member (M#), so they can message that person in the group chat.
- **Contracts (`CONTEXT.md` §6–§9, `contracts/`) are not yours to change silently.** Propose the change in a separate PR labelled `contract-change` (rules in §12). Code must match the current contracts.
- Use only the approved services and stack (§3). Lambda code: Python 3.12, stdlib + boto3 only. IaC: CDK v2 Python.
- Write unit tests for core logic (`tests/unit/`). Run `make lint`, `make test` and `make synth STAGE=<stage>` before opening a PR. CI runs the same checks on every PR, and a red ❌ must be fixed before merging.
- Keep diffs small and focused on the one task.

## AWS safety (cost and shared environments)

- Deploy **only** to the user's own stage (`STAGE=<their name>`) and only when the user asks.
- **Never deploy to, modify, or destroy `STAGE=prod`** unless the user explicitly asks and is M6 (or M6 has approved it).
- If you run `make pipeline-up`, run `make pipeline-down` when the work session ends, and tell the user.
- Never create resources outside CDK (no console steps, no ad-hoc `aws ... create-*` commands).
- Never commit secrets, credentials, `.env` files, or `cdk.out/`. Secrets live in SSM SecureString (§9).

## Git

- Branch: `m<#>/<short-desc>`, e.g. `m4/trending-transactions`. Never commit directly to `main`.
- Commit messages: `<area>: <imperative summary>`.
- Pull first (`git pull --rebase origin main`) and rebase before opening a PR.
- Open the PR into `main` using `.github/pull_request_template.md`.

## Finish every task by updating the docs (same PR)

- [ ] `TRACKER.md`: your task row → status `review`, PR link, a one-line note (the owner marks it `done` after merge + verification)
- [ ] Interface / success-criteria rows in `TRACKER.md` if you proved one (evidence → `docs/results.md`)
- [ ] `CONTEXT.md` §15 Changelog line if you made or changed any decision
- [ ] `contracts/samples/` fixtures if your output shape is a fixture someone else uses
- [ ] `docs/ai-usage.md`: one line (tool, member, what it helped with). This is required for course citations

## When to stop and ask the user

- A contract seems wrong or incomplete.
- A task needs a new AWS service, a paid feature, or anything hourly-billed outside the pipeline stack.
- You'd have to edit another member's files.
- Tests or `cdk synth` fail for reasons outside your task.
