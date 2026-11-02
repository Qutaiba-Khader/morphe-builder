#!/usr/bin/env python3
"""Remove APKs a same-day rebuild superseded.

A rebuild on the same day uploads into that day's release, and an APK with a new
version has a new name, so the older one stays beside it. Within one release only
the highest version of an app and architecture is kept.

An asset is deleted only when the live site no longer offers it (Pages deploys
after the push, so this waits for it; if it never does, the next Site run retries),
and only when the build that replaces it is fully uploaded.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import gen_site  # noqa: E402


def merged_notes(old_body: str, new_notes: str, assets: list[str]) -> str:
    """Today's notes after a rebuild: what this run built, plus the lines of APKs from an earlier run of the
    day that are still in the release. Each APK's line says which bundles it has, so it stays described right."""
    new_lines = new_notes.splitlines()
    kept = [line for line in (old_body or "").splitlines()
            if line.startswith("- 🟢") and any(f"/{name})" in line and f"/{name})" not in new_notes for name in assets)]
    bundles = [line for line in (old_body or "").splitlines() if "» Patches:" in line and line.strip() not in new_notes]
    if not kept and not bundles:
        return new_notes
    last_green = max((i for i, line in enumerate(new_lines) if line.startswith("- 🟢")), default=-1)
    out = new_lines[:last_green + 1] + kept + new_lines[last_green + 1:]
    return "\n".join(out + bundles) + "\n"


def live_urls(site_url: str) -> set[str]:
    """Every APK URL the live site offers as an app's current build."""
    data = gen_site._get(site_url + "api/latest.json")
    return {f["url"] for app in (data.get("apps") or {}).values() for f in app.get("files", [])}


def delete_asset(repo: str, asset_id: int) -> None:
    req = urllib.request.Request(f"{gen_site.API}/repos/{repo}/releases/assets/{asset_id}", method="DELETE")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
    with urllib.request.urlopen(req, timeout=30):
        pass


def merge_notes_file(repo: str, tag: str, notes_file: str) -> int:
    # The list, not /releases/tags/: that answers 404 for a draft, which is every first build of a
    # day. And this is a safety net: failing here must not keep a good release from publishing.
    try:
        releases = gen_site._get(f"{gen_site.API}/repos/{repo}/releases?per_page=30")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::could not read the releases to keep earlier notes: {exc}")
        return 0
    release = next((r for r in releases if r.get("tag_name") == tag), {})
    path = Path(notes_file)
    path.write_text(merged_notes(release.get("body") or "", path.read_text(encoding="utf-8"),
                                 [a["name"] for a in release.get("assets", []) if a["name"].endswith(".apk")]), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None, wait_seconds: int = 300, poll_seconds: int = 20) -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "Qutaiba-Khader/morphe-builder")
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--merge-notes"]:
        return merge_notes_file(repo, args[1], args[2])
    owner, name = repo.split("/", 1)
    site_url = os.getenv("SITE_URL", f"https://{owner.lower()}.github.io/{name}/")
    config = gen_site.app_config()
    doomed = [(r["tag_name"], a) for r in gen_site.fetch_releases(repo) for a in gen_site.superseded(r, config)]
    if not doomed:
        print("nothing superseded")
        return 0
    deadline = time.monotonic() + wait_seconds
    while True:
        offered = live_urls(site_url)
        still = [a["name"] for _, a in doomed if a["browser_download_url"] in offered]
        if not still:
            break
        if time.monotonic() >= deadline:
            print(f"the live site still offers {still}: keeping everything until the next Site run")
            return 0
        time.sleep(poll_seconds)
    for tag, asset in doomed:
        delete_asset(repo, asset["id"])
        print(f"removed {tag}/{asset['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
