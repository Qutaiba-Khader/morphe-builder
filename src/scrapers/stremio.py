# ---------------------------------------------------------
# morphe-builder: an APK source for Stremio's own Android builds.
#
# Stremio publishes its Android and Android TV APKs on dl.strem.io and lists the current
# versions in the machine-readable feed behind www.stremio.com/downloads:
#   https://api.strem.io/downloads/config  ->  {"entries": [{"id": "android_tv", "value":
#       {"versionName": "1.11.3", "tag": "v1.11.3", "versionCode": {"arm64": "43145731", ...}}}, ...]}
# A config entry points at it with the feed URL and the entry id after '#':
#   stremio-dlurl = "https://api.strem.io/downloads/config#android_tv"
#
# Licensed under the GNU GPLv3, like the rest of this repository.
# ---------------------------------------------------------

import json
from pathlib import Path
from typing import Any

from src.scrapers.base import AppMetadata, BaseScraper, DownloadResult, ScraperError

PKG_NAME = "com.stremio.one"
DEFAULT_FEED = "https://api.strem.io/downloads/config"
# builder arch -> (feed key, file suffix)
_ARCHES = {
    "arm64-v8a": ("arm64", "arm64-v8a"),
    "armeabi-v7a": ("arm", "armeabi-v7a"),
    "x86_64": ("x86_64", "x86_64"),
    "x86": ("x86", "x86"),
}
# feed entry id -> the flavour in the download path (dl.strem.io/android/<tag>-<flavour>/...)
_FLAVOURS = {"android_tv": "androidTV", "android_tv_beta": "androidTV", "android": "android", "android_beta": "android"}


class StremioFeedError(ScraperError):
    pass


class StremioScraper(BaseScraper):
    def _entry(self, url: str) -> tuple[str, dict[str, Any]]:
        feed, _, entry_id = url.partition("#")
        entry_id = entry_id or "android_tv"
        if entry_id not in _FLAVOURS:
            raise StremioFeedError(f"Unknown Stremio feed entry '{entry_id}' (use one of {', '.join(_FLAVOURS)})")
        try:
            data = json.loads(self.net.get(feed or DEFAULT_FEED))
        except json.JSONDecodeError as exc:
            raise StremioFeedError(f"Stremio's download feed is not JSON: {exc}") from None
        for e in data.get("entries", []):
            if e.get("id") == entry_id and isinstance(e.get("value"), dict):
                value = e["value"]
                if not value.get("versionName") or not isinstance(value.get("versionCode"), dict):
                    raise StremioFeedError(f"Stremio's feed entry '{entry_id}' has no version")
                return entry_id, value
        raise StremioFeedError(f"Stremio's download feed has no entry '{entry_id}'")

    def fetch_metadata(self, url: str) -> AppMetadata:
        _, value = self._entry(url)
        return AppMetadata(pkg_name=PKG_NAME, versions=[str(value["versionName"])])

    def download(self, url: str, version: str, dest: Path, arch: str, dpi: str, version_code: str | None = None) -> DownloadResult:
        entry_id, value = self._entry(url)
        name = str(value["versionName"])
        if version.lstrip("v") != name:
            raise StremioFeedError(f"Stremio only offers its current version ({name}), not '{version}'")
        if arch in ("all", "both"):
            raise StremioFeedError("Stremio publishes one APK per CPU: set arch to arm64-v8a, armeabi-v7a, x86_64 or x86")
        if arch not in _ARCHES:
            raise StremioFeedError(f"No Stremio APK for arch '{arch}'")
        key, suffix = _ARCHES[arch]
        code = value["versionCode"].get(key)
        if not code:
            raise StremioFeedError(f"Stremio's feed has no '{key}' build of {name}")
        tag = str(value.get("tag") or f"v{name}")
        apk_url = f"https://dl.strem.io/android/{tag}-{_FLAVOURS[entry_id]}/{PKG_NAME}-{name}-{code}-{suffix}.apk"
        self.net.download(apk_url, dest)
        return DownloadResult(path=dest, is_bundle=False)
