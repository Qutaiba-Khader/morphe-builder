# Real version formats (2026-08-01 to 2026-11-03)

Every case below is replayed by `tests/test_version_history.py` from `tests/fixtures/history.json`. Rebuild the fixture with
`tools/history_fixture.py`; answer new pairs from `tools/history_replay.py` with ObtainX's own `compareVersionStrings`, then `--save`.

| Format | Real example | Where it comes from | How it is handled |
|---|---|---|---|
| App, plain | `1.12.1`, `2.5.1`, `2026.42.0`, `21.30.216`, `46.2.3` | Stremio's feed, APKMirror | Numeric order |
| App, label in the name | `21.44.528-BETA` | APKMirror | A final beats its own beta. ObtainX offers beta to final |
| App, label inside only | file `21.41.525`, app says `21.41.525-EXTENDED` | YouTube from APKMirror | The site shows the file's version; `verify_apk` accepts a suffix |
| Feed pre-release | `2.2.0-beta.5`, `1.10.0-rc.18` | Stremio's feed, beta entries | We do not follow them. A patch-only rebuild of one would show as the same version in ObtainX |
| Patch, final | `v2.0.0`, `v0.6.0`, `v0.8.1` | Patch repos | `-2.0.0`; on a pre-release channel `.9999`, above its own dev.N |
| Patch, dev | `v2.1.0-dev.6` | Morphe, TikTok | `-2.1.0.6`; alpha, beta and rc rank above dev in that slot |
| Patch jump | `1.49.0-dev.5` to `2.1.0-dev.6` | An app stuck, then rebuilt | Still offered |
| Tag and file disagree | tag `v0.9.0-dev.2`, file `patches-0.9.0-dev.1.mpp` | TikTok's dev releases | The file's version is compared, because the notes record it |
| Same-day rebuild | `26.11.02-subs` held 2.5.0 and 2.5.1 | Our releases | Best version offered, the other removed |
| Same number again | `youtube-…-v21.30.216-all.apk` in many tags | Daily or manual rebuilds | Same text: not offered again |
| versionCode goes down | 21.41.525 to -EXTENDED; 21.44.528-BETA to 21.44.528 | Real builds, 26.10.14 and 26.11.01 | Android refuses it: `verify_apk` rejects it now, Health reports it |
| Version backwards | Not seen in the channels we follow | | Pin wins by design; otherwise Health reports it |
