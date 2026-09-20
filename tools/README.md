# tools

| File | What it does | Run by |
|---|---|---|
| `gen_site.py` | Builds `_site/` — the Pages site and the JSON API — from this repo's releases (plus `data/catalog.json`). Stdlib only. | `.github/workflows/site.yml` |
| `gen_catalog.py` | Builds `data/catalog.json`: every patch source in `config.toml`, the apps it can patch, patch names and supported versions. Needs `java`. | `.github/workflows/catalog.yml` |
| `flow-test.mjs` | Drives the published page like a visitor (renders `app.js` under jsdom against the live site) and asserts every feature is wired: cards, download links, All-versions history, catalog tab, search, API tab. | manually |

```bash
# site + API, locally
GITHUB_TOKEN=... GITHUB_REPOSITORY=Qutaiba-Khader/morphe-builder python3 tools/gen_site.py

# catalog, locally (downloads the Morphe CLI and each .mpp)
GITHUB_TOKEN=... python3 tools/gen_catalog.py

# flow test against the live site
npm install jsdom && node tools/flow-test.mjs
```
