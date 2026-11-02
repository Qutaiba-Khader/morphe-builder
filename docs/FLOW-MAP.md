# Flow map — morphe-builder

The stored, complete, deterministic set of this project's code paths and the checks each needs. **Update it with every code
change, run one full pass, fix, re-run until a pass is clean, stop.** Skill: `morphe-builder-flowmap`.

```bash
python3 tools/flow/flowmap.py check     # the full pass. CLEAN = stop
python3 tools/flow/flowmap.py quick     # after a change: affected tests + map consistency
python3 tools/flow/flowmap.py update    # mechanical update: line numbers, skeleton rows, entries
```

<!-- TOTALS:START -->
**Last clean pass 2026-11-03 00:12:12 +0300:** 89 paths, 0 gate tests · lines 1229/1581 (77.7%) · branches 401/608 (66.0%) · 0 justified, 0 unjustified.
<!-- TOTALS:END -->

## Areas

| Area | Prefix | Map | Tests | Owns |
|---|---|---|---|---|
| main | P-MAIN | [main.md](flow-map/main.md) | | |

## Entry points

[flow-map/entries.md](flow-map/entries.md) lists every way work enters the code. A path not reachable from one of them is dead
code: remove it or justify it.

## Main flows

One chain per main flow, from an entry to its visible result. Name files and symbols, not line numbers, and mark each boundary:
`[NET]` network, `[DB]` database, `[BIN]` external program, `[DEV]` device. Each boundary has a fake in the tests.

```
entry → file symbol → file symbol [DB] → what the user sees
```

## Critical gates

Branch coverage can pass while a sub-condition never decides anything. Each compound condition that decides what the user gets,
loses data or restarts work has a decision table: per atomic condition, a pair of inputs where only that condition changes and the
outcome changes. Tests are named `G-<GATE>-<condition>`; `flow-map/mutants.json` proves each one can fail.

| Gate | Where | Conditions | Outcome decided |
|---|---|---|---|

## The update rule

Every code change, with no exceptions:

1. Add or edit the rows in `flow-map/<area>.md` and their tests for each new or changed branch, mode or edge case. Removed code
   loses its rows. A changed compound condition updates its gate table.
2. `flowmap.py check`. New gaps get a test or a justified row.
3. Clean: commit map, tests and code together. A defect found: fix it, add its path, run the full pass again. Stop at the first
   clean pass. No random rounds in place of the pass.
