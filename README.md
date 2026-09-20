# morphe-builder

Patched APKs built automatically on GitHub Actions with [Morphe](https://morphe.software)
patches. Nothing runs on private hardware — GitHub's runners do the whole build.

**Building now:** YouTube · Reddit. Every other app is one line in [`config.toml`](config.toml).

| | |
|---|---|
| 📥 **Downloads** | [Releases](https://github.com/Qutaiba-Khader/morphe-builder/releases) |
| 🌐 **Site** | <https://qutaiba-khader.github.io/morphe-builder/> |
| 🔌 **JSON API** | [see below](#json-api) |
| ➕ **Add an app** | [ADD.md](ADD.md) — four lines in `config.toml` |
| 🗂 **What can be patched** | [`data/catalog.json`](data/catalog.json) — 8 sources, 359 apps |
| 🧭 **Plan and verification** | [WORKPLAN.md](WORKPLAN.md) |

The APKs are signed with this repository's own key, held in Actions secrets. An update installs
cleanly over a previous build from here, but not over one from another builder.

## What runs on its own

| Workflow | When | Does |
|---|---|---|
| **CI** | daily **10:00 UTC**, or on demand | For each brand in `config.toml`, compares that patch source's newest release against our newest release. If the patches moved, it fetches the stock APK, patches, signs and publishes a release tagged `YY.MM.DD-<brand>`. If nothing moved it exits without a release. |
| **Site** | after every CI run, every 6 h, on push | Regenerates the site and the JSON API from the releases and deploys to Pages. |
| **Catalog** | weekly, **Mon 04:00 UTC**, or on demand | Rebuilds [`data/catalog.json`](data/catalog.json) from every patch source. |
| **Sync upstream** | daily **08:00 UTC** | Pulls fixes from [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe); `config.toml` and everything in this fork's `IGNORE_SYNC_FILES` are preserved. |

So yes — it checks for updates by itself once a day, and only cuts a release when the patches
have actually moved. Two things worth knowing about that check:

* It watches the **patch source**, not APKMirror. That is normally the same thing, because
  Morphe patches declare which app versions they support and the patcher builds the newest
  supported one — a new app version becomes usable only when the patches bless it.
* The comparison is per **brand**, not per app. Enabling an app under a brand that already has
  releases here (everything using `MorpheApp/morphe-patches` shares the brand `morphe`) does not
  look new, so build it once by hand: Actions → **CI** → *Run workflow* → tick **Build all
  apps**. An app added under a brand new to this repo builds on the next daily run by itself.

<a id="json-api"></a>
## JSON API

Static files on the Pages origin. No key, no rate limit, and `access-control-allow-origin: *`,
so a browser or a script can read them directly.

Base: `https://qutaiba-khader.github.io/morphe-builder/`

| Endpoint | Returns |
|---|---|
| [`api/index.json`](https://qutaiba-khader.github.io/morphe-builder/api/index.json) | Every app, its newest version, when it was built, and where its history lives |
| [`api/latest.json`](https://qutaiba-khader.github.io/morphe-builder/api/latest.json) | The newest build of each app in full: version, tag, size, sha256, download URL |
| [`api/apps/<id>.json`](https://qutaiba-khader.github.io/morphe-builder/api/apps/youtube.json) | One app's complete build history |
| [`api/catalog.json`](https://qutaiba-khader.github.io/morphe-builder/api/catalog.json) | Every patch source → the apps it patches → patch names and supported versions |
| [`api/obtainium.json`](https://qutaiba-khader.github.io/morphe-builder/api/obtainium.json) | A ready-made Obtainium config and one-tap add link per app |
| `obtainium/<id>.html` | The per-app endpoint Obtainium polls ([youtube](https://qutaiba-khader.github.io/morphe-builder/obtainium/youtube.html), [reddit](https://qutaiba-khader.github.io/morphe-builder/obtainium/reddit.html)) |

```bash
# newest YouTube APK
curl -s https://qutaiba-khader.github.io/morphe-builder/api/latest.json \
  | jq -r '.apps.youtube.files[0].url'

# is there a newer build than the one I have?
curl -s https://qutaiba-khader.github.io/morphe-builder/api/index.json \
  | jq -r '.apps[] | "\(.name) \(.latest_version) \(.updated)"'
```

```jsonc
// api/latest.json  (trimmed)
{
  "generated": "2026-09-20T08:10:45Z",
  "apps": {
    "youtube": {
      "id": "youtube", "name": "YouTube", "brand": "morphe",
      "version": "21.13.164", "tag": "26.09.20-morphe",
      "published": "2026-09-20T02:58:34Z", "prerelease": false,
      "files": [{
        "arch": "all", "size": 128400453,
        "sha256": "a55b7e06…3d39",
        "url": "https://github.com/Qutaiba-Khader/morphe-builder/releases/download/26.09.20-morphe/youtube-morphe-v21.13.164-all.apk"
      }]
    }
  }
}
```

## Obtainium

[Obtainium](https://github.com/ImranR98/Obtainium) is an Android app that installs and updates
apps straight from where they are published, instead of from a store. Point it at this builder
once and it checks for new builds on its own and offers you the update.

**Tap one of these on the phone** (each opens Obtainium with the app pre-filled — it shows you
the config and waits for you to confirm; if Obtainium is not installed the page explains what to
do):

[![Add YouTube to Obtainium](https://img.shields.io/badge/Add%20to%20Obtainium-YouTube-2f6fed?style=for-the-badge&logo=android&logoColor=white)][obt-youtube]
[![Add Reddit to Obtainium](https://img.shields.io/badge/Add%20to%20Obtainium-Reddit-2f6fed?style=for-the-badge&logo=android&logoColor=white)][obt-reddit]
[![Add every app to Obtainium](https://img.shields.io/badge/Add%20to%20Obtainium-every%20app-16a34a?style=for-the-badge&logo=android&logoColor=white)][obt-all]

The same buttons are on the [site](https://qutaiba-khader.github.io/morphe-builder/), and
[`api/obtainium.json`](https://qutaiba-khader.github.io/morphe-builder/api/obtainium.json) always
holds the current set — it is regenerated after every build, so it covers any app added later
even if the badges above have not been updated.

To add one by hand: **Add App** → URL `https://qutaiba-khader.github.io/morphe-builder/obtainium/youtube.html`
→ source **HTML**. The ready-made settings for each app (including the version regex) are in
[`api/obtainium.json`](https://qutaiba-khader.github.io/morphe-builder/api/obtainium.json).

These endpoints exist because Obtainium's **GitHub** source takes the version from the release
**tag** — here a date like `26.09.20-morphe` — so it would announce an update on every release
even when that app's APK had not changed. The HTML endpoint holds exactly one APK link and the
version is read from the filename (`youtube-morphe-v21.13.164-all.apk` → `21.13.164`), so the
update prompt means the app really moved. Multi-architecture apps also get
`obtainium/<id>-<arch>.html`.

Everything here is regenerated from the releases after every build, so it always points at the
newest APK with no manual step.

---

<details>
<summary><b>Upstream README (nvbangg/builder-for-morphe)</b></summary>

## [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe)

<div align="center">

[![Typing SVG](https://readme-typing-svg.demolab.com/?font=Google+Sans&size=25&duration=3000&pause=2000&color=&center=true&vCenter=true&random=false&width=550&lines=%F0%9F%93%A6+Build+APKs+from+Morphe+patch+sources)](#-build-your-own-apks)<br>
You can use [this repository](https://github.com/nvbangg/builder-for-morphe) to automatically build patched APKs from [Morphe](https://morphe.software) patch sources on every new update.

</div>

<details>
<summary id="features"><b>🔥 Features</b></summary>

- 🚀 **Easy to use:** easily [build your own APKs](#-build-your-own-apks) just by customizing [`config.toml`](config.toml) (no extra setup required).
- 🧩 **Many pre-configured apps:** just set `enabled = true` for the apps you want.
- 🏗️ **Template support:** use this repository as a [template](https://github.com/new?template_name=builder-for-morphe&template_owner=nvbangg) for private builds or personal development.
- 🔁 **[Automatic upstream sync](CONTRIBUTING.md#-sync-upstream):** pull in bug fixes and new features while still preserving your own configuration.
- 🔄 **Auto-updates:** supports automatic updates through [Obtainium](https://github.com/ImranR98/Obtainium) using releases from your own fork.
- ✨ **And much more!**
</details>

## 🤖 Build Your Own APKs

1. 🍴 `Fork` [this repo](https://github.com/nvbangg/builder-for-morphe) (don't forget to ⭐ `Star` and 👀 `Watch` it)
   - ⚙️ **[Optional]** Customize the apps you want in [`config.toml`](config.toml)
2. 🚀 Run the [CI workflow](../../actions/workflows/ci.yml) (make sure workflows are enabled first)
3. ⬇️ Download your APKs from [Releases](../../releases)

<details>
<summary><b>⬇️ Step-by-step Visual Guide</b></summary>
<br>

<div align="center">

<img src="images/guide-1.png" width="450" />
<img src="images/guide-2.png" width="450" />
<img src="images/guide-3.png" width="450" />
<img src="images/guide-4.png" width="450" />
<img src="images/guide-5.png" width="450" />
<img src="images/guide-6.png" width="450" />
<img src="images/guide-7.png" width="450" />
<img src="images/guide-8.png" width="450" />
<img src="images/guide-9.png" width="450" />

</div>
</details>

## 📚 Documentation & Contributing

<details>
<summary><b>🔄 Obtainium Setup Visual Guide</b></summary>
<br>

In step 3, enter the APK prefix (e.g. `youtube`, `yt-music`, `x-twitter`, etc.) to filter the app you want.

<div align="center">

<img src="images/obtainium-guide.png" width="450" />

</div>
</details>

For full configuration reference, setup and contributing guide, see [CONTRIBUTING.md](CONTRIBUTING.md).

For all Morphe resources, patch bundles and community projects, visit [nvbangg/awesome-morphe](https://github.com/nvbangg/awesome-morphe).

---

## ℹ️ About

<div align="center"><i>

Maintained with ❤️ by **[@nvbangg](https://github.com/nvbangg)** (syncing upstream from [krvstek/uni-apks](https://github.com/krvstek/uni-apks) with the changes mentioned in the [Features](#features) section)  
⭐ Star [this repository](https://github.com/nvbangg/builder-for-morphe) if you find it useful!

</i></div>

<details>
<summary><h3>⚖️ License & Copyright</h3></summary>

This project is open-source and distributed under the **[GNU GPLv3](LICENSE)** license. You are free to use, modify, and redistribute this software, but you **must** keep all original and new copyright notices intact.

> **Copyright (C) 2026 [nvbangg](https://github.com/nvbangg)** (for all [modifications](https://github.com/nvbangg/builder-for-morphe/commits/main/?author=nvbangg) by nvbangg in [builder-for-morphe](https://github.com/nvbangg/builder-for-morphe), and those in [contributions](https://github.com/krvstek/uni-apks/commits/main/?author=nvbangg) and [co-authored commits](https://github.com/search?q=repo%3Akrvstek%2Funi-apks+Co-authored-by%3A+nvbangg&type=commits))  
> **Copyright (C) 2026 [krvstek](https://github.com/krvstek)** (for the original [uni-apks](https://github.com/krvstek/uni-apks) codebase)  
> **Authors:** See the list of [Contributors](https://github.com/nvbangg/builder-for-morphe/graphs/contributors) for their source code contributions, and see [icons/README.md](icons/README.md) for asset sources.

</details>

<details>
<summary><h3>⚠️ Disclaimer</h3></summary>

- [This project](https://github.com/nvbangg/builder-for-morphe) is not affiliated with [Morphe](https://morphe.software/) or any authors mentioned here.
- This project is intended for educational and research purposes only, and is not responsible for any issues arising from its use.
- This repository does not provide pre-patched APKs; it is only a tool to conveniently use publicly available patch bundles via GitHub Actions to ensure security and transparency.
</details>

</details>

<!-- Obtainium deep links (generated by tools/gen_site.py -> api/obtainium.json;
     tools/flow-test.mjs fails if they drift from the generated ones) -->
[obt-reddit]: https://apps.obtainium.imranr.dev/redirect?r=obtainium%3A%2F%2Fapp%2F%257B%2522id%2522%253A%2522com.reddit.frontpage%2522%252C%2522url%2522%253A%2522https%253A%252F%252Fqutaiba-khader.github.io%252Fmorphe-builder%252Fobtainium%252Freddit.html%2522%252C%2522author%2522%253A%2522Qutaiba-Khader%2522%252C%2522name%2522%253A%2522Reddit%2520%2528Morphe%2529%2522%252C%2522additionalSettings%2522%253A%2522%257B%255C%2522versionExtractionRegEx%255C%2522%253A%255C%2522reddit-morphe-v%2528.%252B%2529-all%255C%255C%255C%255C.apk%2524%255C%2522%252C%255C%2522matchGroupToUse%255C%2522%253A%255C%25221%255C%2522%252C%255C%2522apkFilterRegEx%255C%2522%253A%255C%2522%255C%255C%255C%255C.apk%2524%255C%2522%257D%2522%257D
[obt-youtube]: https://apps.obtainium.imranr.dev/redirect?r=obtainium%3A%2F%2Fapp%2F%257B%2522id%2522%253A%2522com.google.android.youtube%2522%252C%2522url%2522%253A%2522https%253A%252F%252Fqutaiba-khader.github.io%252Fmorphe-builder%252Fobtainium%252Fyoutube.html%2522%252C%2522author%2522%253A%2522Qutaiba-Khader%2522%252C%2522name%2522%253A%2522YouTube%2520%2528Morphe%2529%2522%252C%2522additionalSettings%2522%253A%2522%257B%255C%2522versionExtractionRegEx%255C%2522%253A%255C%2522youtube-morphe-v%2528.%252B%2529-all%255C%255C%255C%255C.apk%2524%255C%2522%252C%255C%2522matchGroupToUse%255C%2522%253A%255C%25221%255C%2522%252C%255C%2522apkFilterRegEx%255C%2522%253A%255C%2522%255C%255C%255C%255C.apk%2524%255C%2522%257D%2522%257D
[obt-all]: https://apps.obtainium.imranr.dev/redirect?r=obtainium%3A%2F%2Fapps%2F%255B%257B%2522id%2522%253A%2522com.reddit.frontpage%2522%252C%2522url%2522%253A%2522https%253A%252F%252Fqutaiba-khader.github.io%252Fmorphe-builder%252Fobtainium%252Freddit.html%2522%252C%2522author%2522%253A%2522Qutaiba-Khader%2522%252C%2522name%2522%253A%2522Reddit%2520%2528Morphe%2529%2522%252C%2522additionalSettings%2522%253A%2522%257B%255C%2522versionExtractionRegEx%255C%2522%253A%255C%2522reddit-morphe-v%2528.%252B%2529-all%255C%255C%255C%255C.apk%2524%255C%2522%252C%255C%2522matchGroupToUse%255C%2522%253A%255C%25221%255C%2522%252C%255C%2522apkFilterRegEx%255C%2522%253A%255C%2522%255C%255C%255C%255C.apk%2524%255C%2522%257D%2522%257D%252C%257B%2522id%2522%253A%2522com.google.android.youtube%2522%252C%2522url%2522%253A%2522https%253A%252F%252Fqutaiba-khader.github.io%252Fmorphe-builder%252Fobtainium%252Fyoutube.html%2522%252C%2522author%2522%253A%2522Qutaiba-Khader%2522%252C%2522name%2522%253A%2522YouTube%2520%2528Morphe%2529%2522%252C%2522additionalSettings%2522%253A%2522%257B%255C%2522versionExtractionRegEx%255C%2522%253A%255C%2522youtube-morphe-v%2528.%252B%2529-all%255C%255C%255C%255C.apk%2524%255C%2522%252C%255C%2522matchGroupToUse%255C%2522%253A%255C%25221%255C%2522%252C%255C%2522apkFilterRegEx%255C%2522%253A%255C%2522%255C%255C%255C%255C.apk%2524%255C%2522%257D%2522%257D%255D
