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

MIN_APK_BYTES = 1_000_000


def superseded(release: dict[str, Any], config: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """The assets of one release that a higher version of the same app and arch replaces."""
    groups: dict[tuple[str, str], list[tuple[tuple[int, ...], dict[str, Any]]]] = {}
    for asset in release.get("assets", []):
        parts = gen_site.split_asset(asset["name"], config)
        if parts:
            stem, version, arch = parts
            groups.setdefault((stem, arch), []).append((gen_site.version_key(version), asset))
    out: list[dict[str, Any]] = []
    for items in groups.values():
        items.sort(key=lambda i: i[0], reverse=True)
        best_key, best = items[0]
        if best.get("state", "uploaded") != "uploaded" or best.get("size", 0) < MIN_APK_BYTES:
            continue  # the replacement is not safely there
        out.extend(asset for key, asset in items[1:] if key < best_key)
    return out


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


def main(wait_seconds: int = 300, poll_seconds: int = 20) -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "Qutaiba-Khader/morphe-builder")
    owner, name = repo.split("/", 1)
    site_url = os.getenv("SITE_URL", f"https://{owner.lower()}.github.io/{name}/")
    config = gen_site.app_config()
    doomed = [(r["tag_name"], a) for r in gen_site.fetch_releases(repo) for a in superseded(r, config)]
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
