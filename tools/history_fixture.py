#!/usr/bin/env python3
"""Rebuild tests/fixtures/history.json: real version history from the original sources.

Network, so never run by a test. Reads every release of this repo and of the patch and CLI
repositories, and the package, version and signer inside every published APK. The ObtainX answers are
added by tools/history_replay.py --save, from a run of ObtainX's own compareVersionStrings.
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_site  # noqa: E402
from apk_package import manifest_attrs, manifest_from_url, names_from_url, signer_of  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "history.json"
SINCE = "2026-08-01"
UPSTREAM = {"morphe-patches": "MorpheApp/morphe-patches", "morphe-cli": "MorpheApp/morphe-desktop",
            "subs-patches": "Qutaiba-Khader/stremio-subs-patches", "tiktok-patches": "icysymmetra/tiktok-patches-for-morphe"}


def releases(repo: str) -> list[dict]:
    return gen_site.all_releases(repo, max_pages=30)


def facts(asset: dict) -> tuple[str, dict]:
    url = asset["browser_download_url"]
    try:
        attrs = manifest_attrs(manifest_from_url(url))
        abis = sorted({n.split("/")[1] for n in names_from_url(url) if n.startswith("lib/") and n.count("/") >= 2})
        return asset["browser_download_url"].rsplit("/", 2)[1] + "/" + asset["name"], {"package": attrs.get("package"), "versionName": attrs.get("versionName"),
                               "versionCode": attrs.get("versionCode"), "abis": abis, "signer": signer_of(url)}
    except Exception as exc:  # noqa: BLE001 - recorded: a file that cannot be read is a finding
        return asset["browser_download_url"].rsplit("/", 2)[1] + "/" + asset["name"], {"error": str(exc)[:120]}


def main() -> int:
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    repo = "Qutaiba-Khader/morphe-builder"
    ours = [r for r in releases(repo) if not r.get("draft")]
    data = {"note": "Real data. Rebuild with tools/history_fixture.py and tools/history_replay.py.", "ours": [], "upstream": {}, "apks": {},
            "feed": old.get("feed", []), "play": old.get("play", {}), "obtainx": old.get("obtainx", {})}
    for rel in sorted(ours, key=lambda r: r["published_at"]):
        lines = [ln.strip() for ln in (rel.get("body") or "").splitlines()
                 if ln.startswith("- 🟢") or re.search(r"⚙️ » (CLI|Patches):", ln)]
        data["ours"].append({"tag_name": rel["tag_name"], "published_at": rel["published_at"], "prerelease": rel["prerelease"],
                             "html_url": "", "body": "\n".join(lines),
                             "assets": [{"name": a["name"], "size": a["size"], "state": a["state"], "browser_download_url": a["browser_download_url"]}
                                        for a in rel["assets"] if a["name"].endswith(".apk")]})
    for key, source in UPSTREAM.items():
        data["upstream"][key] = sorted(({"tag": r["tag_name"], "published": r["published_at"], "prerelease": r["prerelease"],
                                         "files": [a["name"] for a in r["assets"] if a["name"].endswith((".mpp", ".jar"))]}
                                        for r in releases(source) if not r.get("draft") and (r["published_at"] or "") >= SINCE),
                                       key=lambda r: r["published"])
    assets = [a for r in ours for a in r["assets"] if a["name"].endswith(".apk")]
    with ThreadPoolExecutor(8) as pool:
        data["apks"] = dict(pool.map(facts, assets))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=0, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(data['ours'])} releases, {len(data['apks'])} APKs, " + ", ".join(f"{k} {len(v)}" for k, v in data["upstream"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
