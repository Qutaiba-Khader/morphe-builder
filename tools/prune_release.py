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


def mislabeled(release: dict[str, Any], new_notes: str, started: str) -> list[dict[str, Any]]:
    """APKs an earlier run left in today's release that the notes of this run would misdescribe.

    Which patches an APK has is read from its release's notes. If this run used other bundles
    and an app failed, its older APK would be labelled with bundles it does not have, and the
    app would then count as up to date. Removing it leaves the previous release's build on offer
    and makes the next check rebuild it.
    """
    bundles = lambda text: {p["file"] for p in gen_site.build_tools(text)["patches"]}  # noqa: E731
    old, new = bundles(release.get("body") or ""), bundles(new_notes)
    # Only a bundle the old APKs do not have makes them wrong. Fewer bundles just means the apps
    # that use the others failed this time, and those APKs are still what their notes said.
    if not old or not new - old:
        return []
    return [a for a in release.get("assets", [])
            if a["name"].endswith(".apk") and str(a.get("updated_at") or "") < started]


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


def drop_mislabeled(repo: str, tag: str, notes_file: str, started: str) -> int:
    # The list, not /releases/tags/: that answers 404 for a draft, which is every first build of a
    # day. And this is a safety net: failing here must not keep a good release from publishing.
    try:
        releases = gen_site._get(f"{gen_site.API}/repos/{repo}/releases?per_page=30")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::could not read the releases to compare patches: {exc}")
        return 0
    release = next((r for r in releases if r.get("tag_name") == tag), {})
    for asset in mislabeled(release, Path(notes_file).read_text(encoding="utf-8"), started):
        delete_asset(repo, asset["id"])
        print(f"::warning::removed {asset['name']} from {tag}: it was not rebuilt and has older patches than this release's notes")
    return 0


def main(argv: list[str] | None = None, wait_seconds: int = 300, poll_seconds: int = 20) -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "Qutaiba-Khader/morphe-builder")
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--mislabeled"]:
        return drop_mislabeled(repo, args[1], args[2], args[3])
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
