# Hollowdeep

Hollowdeep is a Minecraft Bedrock add-on: rift dungeons in the sky with waves of custom mobs, elite affixes,
four themed bosses and rolled relics.

**Wiki:** https://baseballr.github.io/Hollowdeep/
**Download:** the [latest release](https://github.com/baseballr/Hollowdeep/releases/latest).

## How the wiki is built

The wiki is a Blazor WebAssembly site in `src/HollowdeepWiki`, built the same way as the Deepcore wiki.
`tools/extract.py` opens the `.mcaddon` in `addon/` and writes `wwwroot/data/wiki.json`,
`wwwroot/data/release.json`, the item icons and the mob pictures.

Hollowdeep has no in-game guide book, so the page text lives in `tools/pages.py`. The numbers on those pages
are not typed in: the tier table, boss tuning, relic odds, modifier and gate settings are read from the scripts
(`tools/jsdata.mjs`), mob health and damage from the entity files, and recipes and loot from the pack. When a
rebalance only changes numbers, the wiki updates by itself. When a script changes what something *does*, update
its text in `tools/pages.py`.

Mob pictures are rendered from the resource pack's own models and skins with `tools/render/hdlib.py`.

On every push to `main`, `.github/workflows/deploy.yml`:

1. creates the GitHub release `v<version>` with the `.mcaddon` attached, if it doesn't exist yet,
2. runs the extractor,
3. publishes the Blazor app and deploys it to GitHub Pages.

## Publishing a new version

1. Delete the old `.mcaddon` from `addon/` and copy the new one in.
2. Update `addon/release.json`: `version`, `file`, `notes`, and `minecraftMin` / `minecraftMax`
   (lowest and highest Minecraft Bedrock version it works on).
3. Commit and push to `main`.

The extractor stops the build if `release.json`, the pack's manifest and `scripts/version.js` disagree on the
version (an empty `version.js` stops the add-on's scripts from loading at all), or if a page links to a page
that doesn't exist.

## Running locally

```sh
pip install pillow numpy      # node is needed too
python3 tools/extract.py
cd src/HollowdeepWiki && dotnet run
```

Vanilla item icons are cached in `tools/vanilla/`. To add icons for new vanilla items, unpack the
`minecraft-textures` npm package and run `python3 tools/extract.py --vanilla-src path/to/package`.
