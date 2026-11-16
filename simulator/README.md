# Listener simulator (M3, CONTEXT §11)

Run from the repo root (locally or on the simulator instance at `/opt/earshot`). Python 3.11+; `generate` needs nothing else, `replay` and `run` need `boto3` and AWS credentials.

```bash
# Fixtures, no AWS (M4/M5): 10k lines, 10 % duplicates, shuffled
python -m simulator generate --out events.jsonl --users 200 --events 10000 --shuffle --dup-rate 0.10 --seed 7

# Publish a file straight to the SNS events topic (skips the API; needs sns:Publish)
python -m simulator replay --file events.jsonl --direct --stage <stage>

# Live traffic through POST /events as sim-bot (needs the API, Cognito sim client and sim-bot user)
python -m simulator run --stage <stage> --users 2000 --rate 500 --duration 600 --seed 42
```

`run` reads the API URL, sim client id and sim-bot password from SSM (`/earshot/<stage>/...`). Override with `--api-url`, `--client-id`, or the `EARSHOT_SIM_PASSWORD` environment variable. It prints progress every 10 s and writes the run report to `runs/<run_id>.run-report.json`.

## Files

| File | What |
|---|---|
| `model.py` | Virtual users (2 favorite genres, home region), Zipf episode popularity, sessions (play → heartbeats/seek/buffer → pause/complete), 60 % continue an unfinished episode |
| `generate.py` | `generate`: JSON Lines fixtures, duplicates, shuffle |
| `replay.py` | `replay --direct`: 25 events per SNS message, `PublishBatch` |
| `run.py` | `run`: Cognito login/refresh, rate control, retries, run report |
