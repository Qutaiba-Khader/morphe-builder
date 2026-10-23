# Adding an app or a patch source

Everything lives in one file: [`config.toml`](config.toml). Edit it on github.com from any
device, commit, and the next build picks it up. Nothing else needs changing.

## Turn on an app that is already listed

Find its block and flip one line:

```toml
[YT-Music]
enabled = true
```

`config.toml` already carries ready-made blocks for about 25 apps (YouTube Music, X,
Instagram, Telegram, Twitch, TikTok, Duolingo, Prime Video …); everything not building today is
switched off.

## Add a new app

Paste this at the end of the file:

```toml
[My-App]
enabled = true
apkmirror-dlurl = "https://www.apkmirror.com/apk/<vendor>/<app>"

[My-App.patches]
"github:<owner>/<patches-repo>" = []
```

* The APKMirror URL is the app's page there — open apkmirror.com, search the app, copy the
  address of its main page (the one whose path is `/apk/<vendor>/<app>`).
* There is no package name to fill in. Patches can rename an app (Morphe's YouTube installs as
  `app.morphe.android.youtube`), so the package is read out of each built APK, and that is what
  the site, the API and Obtainium use.
* `[]` means *apply the bundle's own default patches* — the ones its author marked
  `Enabled: true`, i.e. the recommended set. It does **not** mean every patch. The site's
  **Our sources** tab shows `<recommended> of <total>` per app, and `data/catalog.json` marks
  `"default": true/false` on every patch.
* To pick an exact set instead, list the names:
  `"github:MorpheApp/morphe-patches" = ["Hide ads", "SponsorBlock"]`.
* To keep the defaults but drop a few: `= { exclude = ["Clone app"] }` — that is how the
  universal patches (`Change installer source`, `Clone app`, `Disable Play Store updates`,
  `Override certificate pinning`) are kept off here.

## Add a pre-release twin of an app

Copy the app's block under a new table name and make it look like this:

```toml
[My-App-Experimental]
enabled = true
brand = "morphe-dev"                       # own brand = own release tag and own update check
apkmirror-dlurl = "https://www.apkmirror.com/apk/<vendor>/<app>"
version = "exp"                            # allow versions only the dev patches support
patcher-args = "-e 'Clone app' -OpackageName=com.example.app.dev -e 'Custom branding' -OcustomName='My App Dev'"

[My-App-Experimental.patches]
"github:<owner>/<patches-repo>" = { version = "dev" }
```

`version = "dev"` takes the **highest-versioned release of any kind** from the source — the way
the builder picks it (`src/core/prebuilts.py`): usually the newest dev build, but a stable
release wins when it is as new (`v1.44.0` beats `v1.44.0-dev.11`). `Clone app` is what lets the
twin sit next to the stable build instead of replacing it — drop it if you would rather the
pre-release replace the stable app.

⚠ If the block you copied has `"Clone app"` in its `exclude` list (the stable blocks here do),
**remove it from the copy**. An exclude wins over an enable, so the twin would silently keep the
stable package and install over it.

🔴 Keep each `-O` option **directly after** the `-e` of the patch it belongs to. The CLI binds
an option to the `-e` it follows, so `-OpackageName=…` placed anywhere else is handed to a
different patch and silently ignored. Name the package explicitly rather than relying on the
`.morphe` default: for apps with `GmsCore support` (YouTube, YouTube Music, Google Photos) the
default is overridden, and only an explicit name gives the clone its own package.

Nothing else is needed. The site card, the API entries, the Obtainium endpoint, its one-tap
badge and the README row all appear by themselves after the first build (which, for a new app
under the existing `morphe-dev` brand, you start by hand — see *After editing*).

## Add a patch source

A source is the key inside the app's `.patches` table — `github:owner/repo` or
`gitlab:owner/repo`. One app can draw from several:

```toml
[YouTube.patches]
"github:MorpheApp/morphe-patches" = []
"github:someone/extra-patches" = ["One specific patch"]
```

Pin a version with the full form: `= { version = "v1.43.0", include = ["..."] }`.
`version = "dev"` takes the source's highest-versioned release, dev or stable.

## Google Play as a second APK source

APKMirror is tried first. Add `gplay-dlurl` and Google Play is tried when APKMirror fails
(down, blocked, or no matching file):

```toml
gplay-dlurl = "https://play.google.com/store/apps/details?id=com.google.android.youtube"
```

It runs [goopdl](https://github.com/Villoh/goopdl) (MIT) and packs Play's split APKs into one
bundle for the Morphe CLI. Google Play only hands out an **old** version by its exact version
code; the builder takes that code from APKMirror's page (or the patches) when it has one. A
universal APK needs Play's 64-bit **and** 32-bit files; when one of them is not offered, Play
fails rather than publish an APK that leaves 32-bit devices out.

🔴 **On GitHub it needs a Google account.** Play's anonymous sign-in (Aurora's token service)
answers HTTP 403 to GitHub's runners, so without one the Play step is skipped. Use a
**throwaway** account, not your own:

1. Create a new Google account.
2. On a computer with Chrome or Edge, run `uvx --from goopdl==1.2.1 goopdl aastoken --browser`,
   sign in to that account and tap **I agree**. It prints an AAS token (`aas_et/…`).
3. In the repository: **Settings → Secrets and variables → Actions → New repository secret**:
   `GOOPDL_ACCOUNT_EMAIL` = the account's address, `GOOPDL_AAS_TOKEN` = the token.

Changing that account's password invalidates the token; repeat step 2 then.

## Which apps and patches does a source have?

Don't guess, and don't go reading the patch source's code. The catalog is generated for you:

* Browsable: <https://qutaiba-khader.github.io/morphe-builder/>
* Raw: [`data/catalog.json`](data/catalog.json) — every configured source mapped to the apps it
  patches, the exact patch names, and the versions each supports.

It refreshes daily, and you can refresh it on demand from the **Catalog** workflow in the
Actions tab. Add a new source to `config.toml`, run that workflow, and the catalog will then
include it.

For sources **not** in `config.toml` yet, the site's **Patchable apps** tab lists every app the
Morphe community can patch (from [awesome-morphe](https://github.com/nvbangg/awesome-morphe),
refreshed daily into `data/community.json`): each app's patch sources, their patches and
supported versions, and a **Copy for config.toml** button with the block to paste here.

## Useful extras

| Key | Does what |
|---|---|
| `arch = "arm64-v8a"` | Build one architecture instead of a universal APK (smaller file) |
| `arch = "both"` | Build arm64-v8a and armeabi-v7a separately |
| `version = "1.2.3"` | Pin a stock app version instead of letting the patches choose |
| `brand = "mybuild"` | Appears in the output filename |
| `patcher-args = "-e 'Theme' -Oamoled=true"` | Pass patch options straight to the Morphe CLI |
| `enabled = false` | Keep the block but skip it |

Full reference: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## After editing

The daily CI run (10:00 UTC) rebuilds a brand when its **patch source** has published a newer
release than our newest release for that brand — not when the stock app alone moves, and not
when you enable an app. So after enabling an app, build it once by hand: Actions → **CI** →
**Run workflow**, tick *Build all apps* (or run **Build APKs** for just its brand). An app under
a brand that has never been released here builds on the next daily run by itself.
