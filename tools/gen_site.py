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
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apk_package import package_of  # noqa: E402

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


def app_config() -> dict[str, dict[str, str]]:
    """app id -> {name, package} as written in config.toml.

    The name keeps its capitalisation ('YouTube', not 'Youtube'); the optional
    `package` is the Android package name, needed for an Obtainium deep link.
    """
    config = ROOT / "config.toml"
    if not config.exists():
        return {}
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for table, body in data.items():
        if isinstance(body, dict):
            name = str(body.get("app-name", table.replace("-", " ")))
            out[slug(name)] = {"name": name, "package": str(body.get("package", ""))}
    return out


def collect(releases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """app id -> {name, brand, builds[]}, newest build first."""
    apps: dict[str, dict[str, Any]] = {}
    names = app_config()
    for rel in releases:
        published = rel.get("published_at") or rel.get("created_at") or ""
        for asset in rel.get("assets", []):
            m = ASSET_RE.match(asset["name"])
            if not m:
                continue
            app_id = slug(m["app"])
            app = apps.setdefault(
                app_id,
                {
                    "id": app_id,
                    "name": names.get(app_id, {}).get("name") or m["app"].replace("-", " ").title(),
                    "package": names.get(app_id, {}).get("package", ""),
                    "brand": m["brand"],
                    "builds": {},
                },
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
            "package": app["package"],
            "brand": app["brand"],
            "builds": list(unique.values()),
        }
    return result


# ----------------------------------------------------------------- obtainium
#
# Obtainium's GitHub source takes its version from the release TAG, which here
# is a date (26.09.20-morphe) - so every release would look like an update even
# when the APK is unchanged. Its HTML source instead runs
# `versionExtractionRegEx` over the APK link, which carries the real app
# version. So each app gets a tiny HTML page holding exactly one .apk link
# (the HTML source takes the LAST matching link on the page) and a config that
# extracts the version from that link's filename.

OBTAINIUM_REDIRECT = "https://apps.obtainium.imranr.dev/redirect?r="

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{name} {version}</title>
<meta name="app-version" content="{version}">
<meta name="robots" content="noindex"></head>
<body>
<h1>{name}</h1>
<p>Latest version: <b>{version}</b> ({arch}) &mdash; built {published}</p>
<p><a href="{url}">{filename}</a></p>
<p>Obtainium endpoint for <a href="../">morphe-builder</a>. One APK link only,
so Obtainium always picks this build.</p>
</body></html>
"""


def _escape(text: str) -> str:
    # Dart's RegExp is ECMAScript: `\-` is only legal outside unicode mode, and
    # Python escapes hyphens. Leave them alone; they are not special here.
    return re.escape(text).replace("\\-", "-")


def version_regex(filename: str, version: str, arch: str) -> str:
    """Matched against the whole APK URL, not the filename.

    Obtainium runs this over the full decoded link
    (`https://github.com/.../youtube-morphe-v21.13.164-all.apk`), so it must NOT
    be anchored with `^` - `allMatches` returning nothing is what raises
    "Could not determine release version". The app prefix still keeps it from
    matching another app's link.
    """
    suffix = f"-v{version}-{arch}.apk"
    prefix = filename[: -len(suffix)] if filename.endswith(suffix) else filename.split("-v")[0]
    return f"{_escape(prefix)}-v(.+)-{_escape(arch)}\\.apk$"


def obtainium_entry(app: dict[str, Any], build: dict[str, Any], file: dict[str, Any],
                    site_url: str, repo: str, suffix: str = "") -> dict[str, Any]:
    page = f"obtainium/{app['id']}{suffix}.html"
    settings = {
        "versionExtractionRegEx": version_regex(file["name"], build["version"], file["arch"]),
        "matchGroupToUse": "1",
        "apkFilterRegEx": "\\.apk$",
    }
    label = app["name"] if not suffix else f"{app['name']} ({file['arch']})"
    config: dict[str, Any] = {
        "id": app.get("package") or "",
        "url": site_url + page,
        "author": repo.split("/")[0],
        "name": f"{label} ({app['brand'].title()})",
        "additionalSettings": json.dumps(settings, separators=(",", ":")),
    }
    if not config["id"]:
        config.pop("id")
    encoded = urllib.parse.quote(json.dumps(config, separators=(",", ":")), safe="")
    deep = f"obtainium://app/{encoded}"
    return {
        "app": app["id"],
        "name": label,
        "arch": file["arch"],
        "version": build["version"],
        "package": app.get("package") or None,
        "source_url": site_url + page,
        "apk": file["url"],
        "config": config,
        "deep_link": deep,
        "add_url": OBTAINIUM_REDIRECT + urllib.parse.quote(deep, safe=""),
        "page": page,
    }


def resolve_packages(apps: dict[str, dict[str, Any]]) -> None:
    """Replace each app's package with the one its built APK actually declares.

    Patches rename apps - Morphe's non-root YouTube installs as
    `app.morphe.android.youtube`, not `com.google.android.youtube` - and
    Obtainium refuses to install when the downloaded package does not match the
    configured id ("Downloaded package ID does not match existing app ID"). So
    the id is read from the artefact, with config.toml's `package` only as a
    fallback when the read fails.
    """
    for app in apps.values():
        if not app["builds"]:
            continue
        url = app["builds"][0]["files"][0]["url"]
        try:
            found = package_of(url)
            if found != app["package"]:
                print(f"  package {app['id']}: {app['package'] or '(unset)'} -> {found}")
            app["package"] = found
        except Exception as exc:  # noqa: BLE001 - never fail the site over this
            print(f"  warn: could not read {app['id']} package ({exc}); "
                  f"keeping {app['package'] or '(unset)'}", file=sys.stderr)


def write_obtainium(apps: dict[str, dict[str, Any]], site_url: str, repo: str, now: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for app in sorted(apps.values(), key=lambda a: a["name"]):
        if not app["builds"]:
            continue
        build = app["builds"][0]
        files = build["files"]
        # main page = the preferred file; one extra page per architecture when
        # the app ships more than one
        variants = [(files[0], "")] + ([(f, f"-{f['arch']}") for f in files] if len(files) > 1 else [])
        for file, suffix in variants:
            entry = obtainium_entry(app, build, file, site_url, repo, suffix)
            (OUT_DIR / entry["page"]).parent.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / entry["page"]).write_text(
                PAGE.format(
                    name=entry["name"], version=build["version"], arch=file["arch"],
                    published=build["published"][:10], url=file["url"], filename=file["name"],
                ),
                encoding="utf-8",
            )
            if not suffix:
                entries.append(entry)
            print(f"  wrote _site/{entry['page']}")

    bulk = [e["config"] for e in entries]
    encoded_all = urllib.parse.quote(json.dumps(bulk, separators=(",", ":")), safe="")
    payload = {
        "generated": now,
        "repo": repo,
        "how": (
            "Add the source_url as an Obtainium app of type 'HTML', or open add_url on the "
            "phone. The version is read from the APK filename, so Obtainium only prompts when "
            "the app version really changes."
        ),
        "add_all_url": OBTAINIUM_REDIRECT + urllib.parse.quote(f"obtainium://apps/{encoded_all}", safe=""),
        "apps": entries,
    }
    write_json(OUT_DIR / "api" / "obtainium.json", payload)
    return payload


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
    resolve_packages(apps)

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
            "package": app["package"] or None,
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

    # --- obtainium ----------------------------------------------------------
    obtainium = write_obtainium(apps, site_url, repo, now)

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
                "obtainium": "api/obtainium.json",
            },
            "obtainium": {
                "add_all_url": obtainium["add_all_url"],
                "source_url": "obtainium/{app_id}.html",
            },
            "apps": [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "package": a["package"] or None,
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
