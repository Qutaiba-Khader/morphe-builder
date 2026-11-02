# Entry points

Every way work enters the code. Found by `flowmap.py update`; rows whose owner starts with `manual` are added by hand (timers, queues, UI events no pattern finds) and stay.
Owner = the area or test family that exercises it. A row with `TODO` fails the gate.

| Kind | Entry | File | Owner |
|---|---|---|---|
| main | `main` | `src/scripts/matrix.py` | manual |
| main | `main` | `tools/apk_package.py` | manual |
| main | `main` | `tools/gen_site.py` | manual |
| main | `main` | `tools/prune_release.py` | manual |
| main | `main` | `tools/release_check.py` | manual |
| main | `main` | `tools/verify_apk.py` | manual |
