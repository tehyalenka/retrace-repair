# v2.7 Multi-file benchmark (two new tasks)

`pricing` requires coordinated changes to `catalog.py` and `orders.py` while retaining the `DiscountRules` API.
`session` requires coordinated changes to `tokens.py` and `gateway.py` while retaining the `Permissions` API.
Both use independent hidden verifiers. These are **small, synthetic Python repositories**, not real-world production repositories.

Offline smoke test (scripted fixture, no model calls):

```bash
PYTHONPATH=src:. python3 -m benchmarks.v27.challenging_recovery --mode offline --cases pricing session --repeats 1 --cooldown 0 --output v27-offline.json
```

Live run (only when ready, and using a new output path):

```bash
PYTHONPATH=src:. python3 -m benchmarks.v27.challenging_recovery --mode live --cases pricing session --repeats 1 --cooldown 90 --output v27-live.json
```

Resume with the same options and `--resume`. Do not share raw traces without reviewing them. Live success on two cases is insufficient to establish generalization or a feedback advantage.
