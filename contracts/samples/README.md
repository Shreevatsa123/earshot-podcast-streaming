# Sample fixtures

Everyone builds against these before the real upstream exists (CONTEXT §12 "Mocks first"). Shapes follow CONTEXT §6–§8 exactly.

| File | Owner | Tracker | Shape |
|---|---|---|---|
| `catalog.json` | M2 | M2-01 | Shows + episodes snapshot (§8.1 Show/Episode attributes) |
| `events.jsonl` | M3 | M3-04 | 1,000 events, one JSON object per line (§6) |
| `home.json` | M2 | M2-07 | `GET /home` response (§7.4) |
| `shows.json` | M2 | M2-07 | `GET /shows` response (§7.3) |
| `show_detail.json` | M2 | M2-07 | `GET /shows/{id}` response (§7.3) |
| `trending.json` | M2 | M2-07 | `GET /trending` response (§7.3) |
| `progress.json` | M2 | M2-07 | `GET /progress/{id}` response (§7.3) |

Use real IDs from `catalog.json` in every other fixture, so they all line up.
