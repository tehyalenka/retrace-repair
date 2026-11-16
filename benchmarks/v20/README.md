# v2.0 Repeated seeded-repair benchmark

Apply after v1.9. Uses the same three v1.9 task families with defect-revealing comments removed. Runs repeated trials, alternates condition ordering, and writes checkpointed reports after each task. Provider errors are counted separately from successful repairs. The output contains generated source code and local test traces: inspect before sharing.

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_v19_seeded_repair tests.test_v20_rigorous_repair -v
PYTHONPATH=src:. python3 -m benchmarks.v20.rigorous_repair --mode offline --repeats 2 --output v20-offline.json
PYTHONPATH=src:. python3 -m benchmarks.v20.rigorous_repair --mode live --cases feature --repeats 2 --output v20-live-feature.json
```

Do not interpret offline scripted corrections as LLM repairs, or one/two trials as statistical evidence of superiority. Order is balanced by case and repetition, but no paired model random-seed control is guaranteed. The benchmark does not add new task families or eliminate possible hints in task descriptions.
