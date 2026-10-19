# Earshot: Podcast Streaming & Analytics on AWS

A real-time podcast streaming & analytics platform on AWS (MSML 650 Cloud Computing, Fall 2026 term project).

Earshot is a podcast streaming web app built on AWS serverless services. Users log in, browse podcasts, play episodes, and get a **Continue Listening** row, a **Trending Now** row and a **Recommended for You** row. Behind the app, a streaming pipeline processes every playback event and also lands it in an S3 data lake that can be queried with SQL. Audio streams directly from publishers' public URLs, so we store only metadata and events, never audio.

| File | Purpose |
|---|---|
| `CONTEXT.md` | Architecture, contracts, names and rules. **The source of truth** |
| `TRACKER.md` | Tasks, owners, dependencies, status, blockers, success criteria |
| `AGENTS.md` | Rules for AI agents working in this repo (`CLAUDE.md` and `.kiro/steering/` point to it) |
| `docs/BRD.md` | Business requirements: scope, constraints, requirements, acceptance |
| `docs/topic-summary.md` | The topic summary submitted to the instructor (historical record) |
| `docs/ai-usage.md` | AI tool citations for the final slides |

**Getting started:**
1. Fill in your row in `TRACKER.md` → Team.
2. Read `CONTEXT.md`.
3. Pick an unblocked task in `TRACKER.md` and tell your AI agent: `I am M<#>. Work on task <ID> from TRACKER.md.`

## Developer setup

**Needs:** Python 3.12, Node 20+, AWS CLI v2 (`aws configure`, region `us-east-1`), the CDK CLI (`npm install -g aws-cdk`), and `make`. On Windows, use WSL.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
make install                    # Python dependencies
make test                       # unit tests (includes a CDK synth check)
make synth STAGE=<you>          # build the templates; changes nothing in AWS
```

**Deploying to your own AWS account** (stage = your first name, lowercase). Set Budgets alerts first.

```bash
make bootstrap     STAGE=<you>  # once per account
make deploy-base   STAGE=<you>  # persistent stack, about $0 while idle
make pipeline-up   STAGE=<you>  # Kinesis, Firehose, EC2: billed by the hour
make pipeline-down STAGE=<you>  # ALWAYS run this when you're done
```

Add `ALERT_EMAIL=you@example.com` to `deploy-base` to get alert emails (confirm the link AWS sends you). Run `make help` for every command.

**Where your code goes:**
- Your construct in `infra/earshot_infra/constructs/`. Its docstring lists what it must create and the attributes other constructs read.
- Your Lambda code in `services/<yours>/`. Shared helpers live in `services/shared/`.
- Don't edit `infra/earshot_infra/stacks/`. If you need something wired differently, ask M6.
