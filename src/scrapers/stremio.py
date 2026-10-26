# ---------------------------------------------------------
# morphe-builder: an APK source for Stremio's own Android builds.
#
# Stremio publishes its Android and Android TV APKs on dl.strem.io and lists the current
# versions in the machine-readable feed behind www.stremio.com/downloads:
#   https://api.strem.io/downloads/config  ->  {"entries": [{"id": "android_tv", "value":
#       {"versionName": "1.11.3", "tag": "v1.11.3", "versionCode": {"arm64": "43145731", ...}}}, ...]}
# A config entry points at it with the feed URL and the entry id after '#':
#   stremio-dlurl = "https://api.strem.io/downloads/config#android_tv"
# The feed lists only the current version. An older one stays on dl.strem.io; pin it with its base version code after
# '@' (the per-CPU codes are base + 1048576 arm, 2097152 x86, 3145728 arm64, 4194304 x86_64, as in every feed entry):
#   stremio-dlurl = "https://api.strem.io/downloads/config#android_tv@1.11.3:40000003"
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


# feed key -> what Stremio adds to a version's base code for that CPU
_CODE_OFFSETS = {"arm": 1048576, "x86": 2097152, "arm64": 3145728, "x86_64": 4194304}


class StremioFeedError(ScraperError):
    pass


def _pin(url: str) -> tuple[str, tuple[str, int] | None]:
    """'...#android_tv@1.11.3:40000003' -> ('...#android_tv', ('1.11.3', 40000003)); no '@' -> (url, None)."""
    base, sep, pin = url.partition("@")
    if not sep:
        return url, None
    name, _, code = pin.partition(":")
    if not name or not code.isdigit():
        raise StremioFeedError(f"A pinned Stremio version is written '<entry>@<version>:<base code>', not '@{pin}'")
    return base, (name.lstrip("v"), int(code))


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
        url, pin = _pin(url)
        if pin:
            return AppMetadata(pkg_name=PKG_NAME, versions=[pin[0]])
        _, value = self._entry(url)
        return AppMetadata(pkg_name=PKG_NAME, versions=[str(value["versionName"])])

    def download(self, url: str, version: str, dest: Path, arch: str, dpi: str, version_code: str | None = None) -> DownloadResult:
        url, pin = _pin(url)
        if pin:  # an older version, by its base code (the feed only knows the current one)
            entry_id = url.partition("#")[2] or "android_tv"
            if entry_id not in _FLAVOURS:
                raise StremioFeedError(f"Unknown Stremio feed entry '{entry_id}' (use one of {', '.join(_FLAVOURS)})")
            value = {"versionName": pin[0], "tag": f"v{pin[0]}", "versionCode": {k: str(pin[1] + o) for k, o in _CODE_OFFSETS.items()}}
        else:
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
