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
