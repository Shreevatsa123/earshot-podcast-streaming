# Listener simulator (M3, CONTEXT §11)

Run from the repo root (locally or on the simulator instance at `/opt/earshot`). Python 3.11+; `generate` needs nothing else, `replay` needs `boto3` and AWS credentials.

```bash
# Fixtures, no AWS (M4/M5): 10k lines, 10 % duplicates, shuffled
python -m simulator generate --out events.jsonl --users 200 --events 10000 --shuffle --dup-rate 0.10 --seed 7

# Publish a file straight to the SNS events topic (skips the API; needs sns:Publish)
python -m simulator replay --file events.jsonl --direct --stage <stage>
```

## Files

| File | What |
|---|---|
| `model.py` | Virtual users (2 favorite genres, home region), Zipf episode popularity, sessions (play → heartbeats/seek/buffer → pause/complete), 60 % continue an unfinished episode |
| `generate.py` | `generate`: JSON Lines fixtures, duplicates, shuffle |
| `replay.py` | `replay --direct`: 25 events per SNS message, `PublishBatch` |
