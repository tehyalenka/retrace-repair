# v1.9 Seeded-failure evaluation

Run from the project root with Python module imports:

```bash
PYTHONPATH=src:. python3 -m benchmarks.v19.seeded_repair --mode offline --output v19-offline.json
PYTHONPATH=src:. python3 -m benchmarks.v19.seeded_repair --mode live --cases feature --output v19-live-feature.json
```

The benchmark injects deliberately defective first edits for three v11 cases. Both arms replay the **same seed**, and then request either a new completion without feedback or a new completion with **sanitized failed-test identifiers**. The independent verifier runs locally; its source and assertions are not included in feedback messages. Offline continuations are scripted. Live continuations are fresh model requests. The report distinguishes these origins.

The three seeded cases cover repeated booking cancellation, non-atomic batch transfer, and Unicode casefold matching. The first response is seeded, not LLM-generated; results must not be described as natural-failure repair. API rate limits may still interrupt live trials. Reports can include model-generated source; review before sharing.
