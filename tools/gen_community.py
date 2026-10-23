#!/usr/bin/env python3
"""Build data/community.json: every Morphe patch source the community knows, by app.

Source: nvbangg/awesome-morphe (MIT), which aggregates the Morphe community's patch bundles
every day into one file, web/public/bundles.json (the data behind awesome-morphe.vercel.app).
It is read ONCE per run, from GitHub's raw file host (not the project's website, so it costs
them no hosting), and only metadata is kept: which apps a bundle patches, its patch names and
descriptions, the app versions it supports, stars and dates. No patch file is downloaded or
redistributed, and nothing found here is ever built automatically - an app is built only when
someone adds it to config.toml.

Output (compact, sorted, stable between runs so a commit means a real change):
  {"generated", "source": {...}, "bundles": {"owner/repo": {...}},
   "apps": {"<package>": {"name", "icon", "category", "sources": [{"repo", "patches": [[name, description]],
            "versions", "experimental"}]}}}
The pseudo-package "__universal__" holds patches that work on any app.

Stdlib only. Keeps the previous file when the download fails.
"""

from __future__ import annotations

import gzip
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "community.json"
REPO = "nvbangg/awesome-morphe"
URL = f"https://raw.githubusercontent.com/{REPO}/main/web/public/bundles.json"
MAX_DESC = 240


def fetch() -> dict[str, Any]:
    req = urllib.request.Request(URL, headers={"User-Agent": "morphe-builder-catalog (+https://github.com/Qutaiba-Khader/morphe-builder)",
                                               "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw)


def _date(ms: Any) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def _desc(text: Any) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= MAX_DESC else s[: MAX_DESC - 1].rstrip() + "…"


def build(data: dict[str, Any]) -> dict[str, Any]:
    bundles_in: list[dict[str, Any]] = data.get("bundles") or []
    compat: list[Any] = data.get("compatibilities") or []
    store: dict[str, Any] = data.get("store") or {}

    bundles: dict[str, Any] = {}
    apps: dict[str, dict[str, Any]] = {}
    for b in bundles_in:
        repo, src = str(b.get("repo") or ""), str(b.get("source") or "github")
        if not repo or b.get("isArchived"):
            continue
        key = repo if src == "github" else f"{src}:{repo}"
        bundles[key] = {
            "source": src,
            "url": f"https://{'gitlab.com' if src == 'gitlab' else 'github.com'}/{repo}",
            "label": str(b.get("repoDescription") or b.get("name") or repo)[:80],
            "author": str(b.get("name") or repo.split("/")[0]),
            "stars": int(b.get("stars") or 0),
            "updated": _date(b.get("updatedAt")),
            "listed": bool(b.get("isOfficial")),          # listed on morphe-patches.software
            "prerelease": bool(b.get("isPreRelease")),
            "add": f"https://morphe.software/add-source?{src}={repo}",
            "patches": len(b.get("patches") or []),
        }
        per_app: dict[str, dict[str, Any]] = {}
        for p in b.get("patches") or []:
            k = p.get("compatiblePackagesKey")
            targets = compat[k] if isinstance(k, int) and 0 <= k < len(compat) else None
            pkgs = [(t.get("packageName"), t.get("targets") or []) for t in (targets or []) if isinstance(t, dict)]
            if not pkgs:
                pkgs = [("__universal__", [])]
            for pkg, tgts in pkgs:
                if not pkg:
                    continue
                entry = per_app.setdefault(pkg, {"repo": key, "patches": [], "versions": set(), "experimental": set()})
                entry["patches"].append([str(p.get("name") or ""), _desc(p.get("description"))])
                for t in tgts:
                    v = str(t.get("version") or "")
                    if v:
                        (entry["experimental"] if t.get("isExperimental") else entry["versions"]).add(v)
        for pkg, entry in per_app.items():
            app = apps.setdefault(pkg, {"sources": []})
            entry["patches"].sort(key=lambda x: x[0].lower())
            entry["versions"] = sorted(entry["versions"], key=_vkey, reverse=True)[:8]
            entry["experimental"] = sorted(entry["experimental"], key=_vkey, reverse=True)[:4]
            app["sources"].append(entry)

    for pkg, app in apps.items():
        meta = store.get(pkg) or {}
        app["name"] = "Any app" if pkg == "__universal__" else str(meta.get("name") or pkg)
        app["icon"] = str(meta.get("iconUrl") or "")
        app["category"] = str(meta.get("category") or "")
        # the official Morphe source first, then by stars: the likeliest-useful source on top
        app["sources"].sort(key=lambda s: (s["repo"] != "MorpheApp/morphe-patches", -bundles[s["repo"]]["stars"], -len(s["patches"]), s["repo"].lower()))

    return {
        "source": {"repo": REPO, "url": f"https://github.com/{REPO}", "file": URL, "license": "MIT",
                   "site": "https://awesome-morphe.vercel.app"},
        "bundles": dict(sorted(bundles.items(), key=lambda kv: kv[0].lower())),
        "apps": dict(sorted(apps.items(), key=lambda kv: (kv[0] != "__universal__", kv[1]["name"].lower(), kv[0]))),
    }


def _vkey(v: str) -> tuple:
    parts = []
    for x in v.replace("-", ".").split("."):
        parts.append((0, int(x), "") if x.isdigit() else (1, 0, x))
    return tuple(parts)


def main() -> int:
    try:
        data = fetch()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"community: could not read {URL}: {exc}; keeping the previous file", file=sys.stderr)
        return 0
    out = build(data)
    if not out["apps"]:
        print("community: the file had no apps; keeping the previous file", file=sys.stderr)
        return 0
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    n_src = len(out["bundles"])
    print(f"community: {len(out['apps'])} apps from {n_src} patch sources -> {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
