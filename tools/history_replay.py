#!/usr/bin/env python3
"""Replay the real version history (tests/fixtures/history.json) through the code that picks and names versions.

`transitions` says what a phone would be offered at each real moment, with today's naming: each build's versionName
is what src/core/apk_version.py gives it. It backs tests/test_version_history.py.
Run directly it lists the (installed, offered) pairs to answer with ObtainX's own compareVersionStrings; `--save FILE`
stores the answers in the fixture, because the tests cannot run Dart.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path[:0] = [str(Path(__file__).parent), str(Path(__file__).parent.parent)]
import gen_site  # noqa: E402

from src.core.apk_version import update_version  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "history.json"

# Installed (what the phone reports) against offered. Each must be an update, and none may be "unknown".
EXTRA_PAIRS = [
    ("46.2.3", "46.2.3.0.8.2"),                    # an app installed before versions carried the patch number
    ("1.12.1", "1.12.1.0.6.1"),
    ("2.5.1", "2.5.1.0.6.1"),
    ("21.44.528", "21.44.528.2.1.0.7"),
    ("2026.42.0", "2026.42.0.2.1.0.7"),
    ("21.30.216", "21.30.216.2.0.1"),
    ("2026.40.0", "2026.40.0.2.0.1"),
    ("21.20.405", "21.30.216"),                    # an older app, offered a build from before the change
    ("21.41.525-EXTENDED", "21.41.525.1.48.0.3"),   # a store's label inside
    ("21.44.528-BETA", "21.44.528-BETA.2.1.0.7"),   # a beta app version
    ("21.44.528-BETA.2.1.0.7", "21.44.528-BETA.2.1.0.8"),
    ("21.44.528-BETA.2.1.0.8", "21.44.528.2.1.0.8"),
    ("21.44.528-BETA", "21.44.528.2.1.0.8"),
    ("2.2.0-beta.5.0.6.0", "2.2.0-beta.5.0.7.0"),    # the form of Stremio's beta feed
    ("21.43.523.2.1.0.4", "21.44.528-BETA.2.1.0.5"),
    ("46.2.3.0.8.1", "46.2.3.0.8.2"),              # a patch-only update
    ("46.2.3.0.9.0", "46.2.4.0.8.1"),              # a new app version with a lower patch number
    ("2026.42.0.1.49.0.5", "2026.42.0.2.1.0.6"),   # major jump of the bundle
    ("21.44.528.2.1.0.16", "21.44.528.2.1.0.2001"),  # dev -> alpha -> beta -> rc -> final -> next dev
    ("21.44.528.2.1.0.2001", "21.44.528.2.1.0.3001"),
    ("21.44.528.2.1.0.3001", "21.44.528.2.1.0.4001"),
    ("21.44.528.2.1.0.4001", "21.44.528.2.1.0.9999"),
    ("21.44.528.2.1.0.9999", "21.44.528.2.2.0.1"),
]
# The same build: no update and no warning.
SAME_PAIRS = [
    ("46.2.3", "46.2.3"), ("1.12.1", "1.12.1"), ("2.5.1", "2.5.1"), ("21.44.528", "21.44.528"), ("2026.42.0", "2026.42.0"),
    ("21.30.216", "21.30.216"), ("2026.40.0", "2026.40.0"), ("46.2.3.0.8.1", "46.2.3.0.8.1"), ("1.12.1.0.6.0", "1.12.1.0.6.0"),
    ("21.44.528.2.1.0.6", "21.44.528.2.1.0.6"), ("21.41.525-EXTENDED", "21.41.525"),
]
# Not an update, and known: a patch-number downgrade; a beta after its final.
NOT_UPDATES = [
    ("46.2.3.0.8.2", "46.2.3.0.8.1"),
    ("21.44.528.2.1.0.6", "21.44.528-BETA.2.1.0.7"),
]
# The bug that was live until 2026-11-03: never offer this form again.
THE_BUG = ("46.2.3", "46.2.3-0.8.1")


def load() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def text_of(build: dict[str, Any]) -> str:
    """The versionName this build gets today, and so what its page offers."""
    bundles = [p["version"] for p in build.get("patches") or [] if p.get("version")]
    return update_version(build["version"], bundles[0] if bundles else "", bool(build.get("prerelease")))


def offers(releases: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """app id -> what the site would offer after each real release, one row per change of file or text."""
    out: dict[str, list[dict[str, Any]]] = {}
    for count in range(1, len(releases) + 1):
        for app_id, app in gen_site.collect(releases[:count]).items():
            build = app["builds"][0]
            row = {"version": build["version"], "tag": build["tag"], "text": text_of(build),
                   "file": build["files"][0]["name"], "arch": build["files"][0]["arch"]}
            rows = out.setdefault(app_id, [])
            if not rows or (rows[-1]["text"], rows[-1]["file"]) != (row["text"], row["file"]):
                rows.append(row)
    return out


def transitions(releases: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [(a["text"], b["text"], app_id) for app_id, rows in offers(releases).items() for a, b in zip(rows, rows[1:]) if a["text"] != b["text"]]


def pairs(history: dict[str, Any]) -> list[list[str]]:
    wanted = {(a, b) for a, b, _ in transitions(history["ours"])} | set(EXTRA_PAIRS) | set(SAME_PAIRS) | set(NOT_UPDATES) | {THE_BUG}
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
