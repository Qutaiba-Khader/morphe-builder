"""morphe-builder (owner, 2026-11-18): proves the Google Play source works on GitHub's runners with the account secrets,
without building or publishing anything. Downloads one app's current version from Google Play into ./gplay-check and
names the files it got (sizes only). The leak guard then checks that folder. Never prints a secret.

  uv run python tools/gplay_check.py [play-url] [arch]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.core.network import NetworkManager  # noqa: E402
from src.scrapers.gplay import GPlayError, GPlayScraper, take_secrets  # noqa: E402

URL = "https://play.google.com/store/apps/details?id=com.reddit.frontpage"


def main(argv: list[str]) -> int:
    take_secrets()
    url = argv[0] if argv else URL
    arch = argv[1] if len(argv) > 1 else "all"
    out = Path("gplay-check")
    out.mkdir(exist_ok=True)
    with NetworkManager() as net:
        scr = GPlayScraper(net)
        try:
            version = scr.fetch_metadata(url).versions[0]
            print(f"Google Play offers version {version}")
            res = scr.download(url, version, out / f"check-{version}.apkm", arch, "")
        except GPlayError as exc:
            print(f"::error title=Google Play check failed::{exc}")
            return 1
    files = sorted(p for p in out.iterdir() if p.is_file())
    for f in files:
        print(f"got {f.name} ({f.stat().st_size // 1024} KB)")
    print(f"Google Play check passed: {res.path.name}")
    return 0 if files else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
