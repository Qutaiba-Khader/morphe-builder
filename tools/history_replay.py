#!/usr/bin/env python3
"""Replay the real version history (tests/fixtures/history.json) through the code that picks and names versions.

`transitions` says what a phone would be offered at each real moment. It backs tests/test_version_history.py.
Run directly it lists the (installed, offered) pairs to answer with ObtainX's own compareVersionStrings; `--save FILE`
stores the answers in the fixture, because the tests cannot run Dart.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import gen_site  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "history.json"

# Real formats and moments that the published history no longer shows, or that a phone reports by itself.
EXTRA_PAIRS = [
    ("2.5.0-2.0.0", "2.5.1-0.6.0"),               # the site's text before the fix, then the fix
    ("1.12.0-2.0.0", "1.12.1-0.6.0"),
    ("21.44.528-BETA-2.1.0.5", "21.44.528-2.1.0.5"),  # a beta app version, then its final
    ("21.44.528-BETA-2.1.0.5", "21.44.528-BETA-2.1.0.6"),
    ("21.43.523-2.1.0.4", "21.44.528-BETA-2.1.0.5"),
    ("21.41.525-1.48.0.3", "21.41.525-1.48.0.6"),
    ("2026.42.0-1.49.0.5", "2026.42.0-2.1.0.6"),   # major jump of the bundle
    ("21.44.528-2.1.0.16", "21.44.528-2.1.0.2001"),  # dev -> alpha -> beta -> rc -> final -> next dev
    ("21.44.528-2.1.0.2001", "21.44.528-2.1.0.3001"),
    ("21.44.528-2.1.0.3001", "21.44.528-2.1.0.4001"),
    ("21.44.528-2.1.0.4001", "21.44.528-2.1.0.9999"),
    ("21.44.528-2.1.0.9999", "21.44.528-2.2.0.1"),
    ("21.30.216-2.0.0", "21.30.216-2.0.0"),        # a rebuild with nothing new
]


def load() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def offers(releases: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """app id -> what the site would offer after each real release, one row per change of file or text."""
    out: dict[str, list[dict[str, Any]]] = {}
    for count in range(1, len(releases) + 1):
        for app_id, app in gen_site.collect(releases[:count]).items():
            build = app["builds"][0]
            row = {"version": build["version"], "tag": build["tag"], "text": gen_site.build_version(build),
                   "file": build["files"][0]["name"], "arch": build["files"][0]["arch"]}
            rows = out.setdefault(app_id, [])
            if not rows or (rows[-1]["text"], rows[-1]["file"]) != (row["text"], row["file"]):
                rows.append(row)
    return out


def transitions(releases: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [(a["text"], b["text"], app_id) for app_id, rows in offers(releases).items() for a, b in zip(rows, rows[1:]) if a["text"] != b["text"]]


def pairs(history: dict[str, Any]) -> list[list[str]]:
    wanted = {(a, b) for a, b, _ in transitions(history["ours"])} | set(EXTRA_PAIRS)
    return [list(p) for p in sorted(wanted)]


def main() -> int:
    history = load()
    if sys.argv[1:2] == ["--save"]:
        answers = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        all_pairs = pairs(history)
        history["obtainx"] = {f"{a}|{b}": answer[0] for (a, b), answer in zip(all_pairs, answers, strict=True)}
        FIXTURE.write_text(json.dumps(history, indent=0, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    json.dump(pairs(history), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
