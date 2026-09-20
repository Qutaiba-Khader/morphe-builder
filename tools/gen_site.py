#!/usr/bin/env python3
"""Generate the Pages site and its JSON API from this repo's own GitHub releases.

Reads  : GitHub Releases API, site/static/*, data/catalog.json (optional)
Writes : _site/index.html, _site/assets/*, _site/api/*.json

Release assets are named  <app>-<brand>-v<version>-<arch>.apk  under a  YY.MM.DD-<source>
tag, which is all the structure the site needs.

Stdlib only, so the workflow needs no dependency install.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "site" / "static"
CATALOG_FILE = ROOT / "data" / "catalog.json"
OUT_DIR = ROOT / "_site"

ARCHES = ("all", "arm64-v8a", "armeabi-v7a", "x86_64", "x86", "universal")
ASSET_RE = re.compile(
    r"^(?P<app>.+?)-(?P<brand>[^-]+)-v(?P<version>.+)-(?P<arch>" + "|".join(ARCHES) + r")\.apk$",
    re.IGNORECASE,
)

API = "https://api.github.com"


def _get(url: str) -> Any:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "morphe-builder-site")
    if token := os.getenv("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_releases(repo: str, max_pages: int = 4) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        try:
            batch = _get(f"{API}/repos/{repo}/releases?per_page=100&page={page}")
        except urllib.error.HTTPError as exc:
            print(f"warn: releases page {page} failed: {exc}", file=sys.stderr)
            break
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
    return [r for r in out if not r.get("draft")]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def collect(releases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """app id -> {name, brand, builds[]}, newest build first."""
    apps: dict[str, dict[str, Any]] = {}
    for rel in releases:
        published = rel.get("published_at") or rel.get("created_at") or ""
        for asset in rel.get("assets", []):
            m = ASSET_RE.match(asset["name"])
            if not m:
                continue
            app_id = slug(m["app"])
            app = apps.setdefault(
                app_id,
                {"id": app_id, "name": m["app"].replace("-", " ").title(), "brand": m["brand"], "builds": {}},
            )
            key = (m["version"], rel["tag_name"])
            build = app["builds"].setdefault(
                key,
                {
                    "version": m["version"],
                    "tag": rel["tag_name"],
                    "published": published,
                    "prerelease": bool(rel.get("prerelease")),
                    "release_url": rel.get("html_url", ""),
                    "files": [],
                },
            )
            build["files"].append(
                {
                    "arch": m["arch"],
                    "size": asset.get("size", 0),
                    "sha256": (asset.get("digest") or "").removeprefix("sha256:"),
                    "downloads": asset.get("download_count", 0),
                    "url": asset["browser_download_url"],
                    "name": asset["name"],
                }
            )

    result: dict[str, dict[str, Any]] = {}
    for app_id, app in apps.items():
        builds = sorted(app["builds"].values(), key=lambda b: b["published"], reverse=True)
        for b in builds:
            b["files"].sort(key=lambda f: ARCHES.index(f["arch"].lower()) if f["arch"].lower() in ARCHES else 99)

        # The same app version is re-published under every release tag it survives.
        # Keep the newest build of each version and count the repeats.
        unique: dict[str, dict[str, Any]] = {}
        for b in builds:
            if (first := unique.get(b["version"])) is None:
                unique[b["version"]] = {**b, "rebuilds": 1}
            else:
                first["rebuilds"] += 1

        result[app_id] = {
            "id": app_id,
            "name": app["name"],
            "brand": app["brand"],
            "builds": list(unique.values()),
        }
    return result


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(OUT_DIR.parent)}")


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "Qutaiba-Khader/morphe-builder")
    owner, name = repo.split("/", 1)
    site_url = os.getenv("SITE_URL", f"https://{owner.lower()}.github.io/{name}/")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    releases = fetch_releases(repo)
    apps = collect(releases)
    print(f"{len(releases)} releases -> {len(apps)} apps")

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    api_dir = OUT_DIR / "api"

    # --- per-app history -----------------------------------------------------
    for app_id, app in apps.items():
        write_json(
            api_dir / "apps" / f"{app_id}.json",
            {"generated": now, "repo": repo, **app},
        )

    # --- latest per app ------------------------------------------------------
    latest = {
        app_id: {
            "id": app_id,
            "name": app["name"],
            "brand": app["brand"],
            **{k: v for k, v in app["builds"][0].items()},
        }
        for app_id, app in apps.items()
        if app["builds"]
    }
    write_json(api_dir / "latest.json", {"generated": now, "repo": repo, "apps": latest})

    # --- catalog (generated separately by tools/gen_catalog.py) --------------
    catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8")) if CATALOG_FILE.exists() else {
        "generated": None,
        "sources": {},
        "note": "run the Catalog workflow to populate this",
    }
    write_json(api_dir / "catalog.json", catalog)

    # --- index ---------------------------------------------------------------
    write_json(
        api_dir / "index.json",
        {
            "generated": now,
            "repo": repo,
            "site": site_url,
            "releases": f"https://github.com/{repo}/releases",
            "endpoints": {
                "index": "api/index.json",
                "latest": "api/latest.json",
                "app": "api/apps/{app_id}.json",
                "catalog": "api/catalog.json",
            },
            "apps": [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "brand": a["brand"],
                    "latest_version": a["builds"][0]["version"] if a["builds"] else None,
                    "updated": a["builds"][0]["published"] if a["builds"] else None,
                    "versions": len(a["builds"]),
                    "api": f"api/apps/{a['id']}.json",
                }
                for a in sorted(apps.values(), key=lambda x: x["name"])
            ],
        },
    )

    # --- static files --------------------------------------------------------
    for src in sorted(STATIC_DIR.iterdir()) if STATIC_DIR.is_dir() else []:
        if src.is_file():
            shutil.copy2(src, OUT_DIR / src.name)
            print(f"  copied {src.name}")
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
