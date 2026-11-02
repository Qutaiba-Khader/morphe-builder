---
name: morphe-builder-flowmap
description: The flow map of morphe-builder: its stored, complete set of code paths with the checks for each, as deterministic tests plus a coverage gate. Use after ANY code change to morphe-builder (update the map and tests with it), before a deploy or release, and when asked for a flow test or full trace of morphe-builder. One clean pass, then stop.
---

# morphe-builder flow map

Method: the base skill `flowmap`. This project's map: `docs/FLOW-MAP.md`, `docs/flow-map/*.md`; settings: `flowmap.json`.

```bash
python3 tools/flow/flowmap.py update   # mechanical: line numbers, skeleton rows, entries
python3 tools/flow/flowmap.py quick    # after a change: affected tests + map consistency
python3 tools/flow/flowmap.py check    # the full pass, before a deploy or release. CLEAN = stop
python3 tools/flow/flowmap.py mutate   # the gate tests can fail
```

Every code change updates the map in the same commit. Fill each `TODO` row the update adds. Fix what a pass finds, re-run the full
pass, stop at the first clean one. No random review rounds in place of it.

## Project notes

Tests need the project's dependencies plus coverage: `uv sync --frozen && uv pip install coverage`, then `FLOWMAP_PYTHON=.venv/bin/python`. No test touches a network: `Net`, `FakeUrl` and mock.patch fake every boundary.
Scope is the release flow, level `standard`: today's other gaps are in the ledger, which may only shrink.
The workflows' bash steps, GitHub's scheduler and Pages are not covered here: `tools/release_check.py` watches their results from outside, and a real `Build APKs` run proves them.
