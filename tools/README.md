# tools

| File | What it does | Run by |
|---|---|---|
| `gen_site.py` | Builds `_site/` — the Pages site and the JSON API — from this repo's releases (plus `data/catalog.json`). Stdlib only. | `.github/workflows/site.yml` |
| `gen_catalog.py` | Builds `data/catalog.json`: every patch source in `config.toml`, the apps it can patch, patch names and supported versions. Needs `java`. | `.github/workflows/catalog.yml` |
| `gen_readme.py` | Rewrites the README's generated blocks from `_site/api/*.json`: the Download tables (one per channel, one row per app with its download and Obtainium buttons, then a folded table of packages, release tags and Obtainium endpoints) and the `[obt-*]` link targets. | the `readme` job in `site.yml` |
| `apk_package.py` | Reads the package name out of a built APK's binary manifest, locally or over HTTP range requests (~100 KB). Patches rename apps, so this is where Obtainium's app id comes from. | `gen_site.py` |
| `flow-test.mjs` | Drives the published page like a visitor (renders `app.js` under jsdom against the live site) and asserts every feature is wired: cards, download links, All-versions history, catalog tab, search, API tab; every Obtainium config replayed the way Obtainium reads it, each id checked against the package the APK really declares, the bulk-add page, and the README's generated rows against the live API and `config.toml`. | manually |

```bash
# site + API, locally
GITHUB_TOKEN=... GITHUB_REPOSITORY=Qutaiba-Khader/morphe-builder python3 tools/gen_site.py

# catalog, locally (downloads the Morphe CLI and each .mpp)
GITHUB_TOKEN=... python3 tools/gen_catalog.py

# flow test against the live site
npm install --no-save jsdom && node tools/flow-test.mjs   # node_modules is git-ignored
```
