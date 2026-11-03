#!/usr/bin/env python3
"""Builds the wiki data from the Hollowdeep .mcaddon.

Hollowdeep has no in-game guide book, so the page text lives in tools/pages.py. Every number on
those pages is read from the pack when this runs: the tier table, boss tuning and relic weights
from the scripts (through tools/jsdata.mjs), mob health and damage from the entity files, recipes,
loot tables and item names from the pack. Mob pictures are rendered from the resource pack's own
models and skins with tools/render/hdlib.py.

Writes:
  src/HollowdeepWiki/wwwroot/data/wiki.json     categories, entries, recipes
  src/HollowdeepWiki/wwwroot/data/release.json  latest download + Minecraft range
  src/HollowdeepWiki/wwwroot/img/icons/*.png    item icons
  src/HollowdeepWiki/wwwroot/img/mobs/*.png     mob renders
  src/HollowdeepWiki/wwwroot/img/vanilla/*.png  vanilla ingredient icons
  src/HollowdeepWiki/wwwroot/img/lineup.png     the bosses, for the home page

Usage: python3 tools/extract.py [--repo owner/name] [--vanilla-src DIR]

--vanilla-src points at an unpacked `minecraft-textures` npm package and refreshes tools/vanilla/
(icons for vanilla items). Without it the cached icons in tools/vanilla/ are used.
Needs node (for tools/jsdata.mjs), pillow and numpy.
"""
import argparse, io, json, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WWW = ROOT / "src" / "HollowdeepWiki" / "wwwroot"
VANILLA = ROOT / "tools" / "vanilla"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "render"))

import pages  # noqa: E402

BP, RP = "Hollowdeep_BP/", "Hollowdeep_RP/"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class Pack:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.names = self.z.namelist()

    def read(self, name):
        return self.z.read(name)

    def json(self, name):
        txt = self.read(name).decode("utf-8-sig")
        txt = re.sub(r"^\s*//.*$", "", txt, flags=re.M)
        return json.loads(txt)

    def files(self, prefix, ext=".json"):
        return sorted(n for n in self.names if n.startswith(prefix) and n.endswith(ext))

    def image(self, name):
        return Image.open(io.BytesIO(self.read(name))).convert("RGBA")


def lang(pack):
    out = {}
    for line in pack.read(RP + "texts/en_US.lang").decode("utf-8-sig").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def script_data(pack, tmp):
    """Unpack the scripts and let node read the numbers out of them."""
    sdir = Path(tmp) / "scripts"
    sdir.mkdir()
    for n in pack.files(BP + "scripts/", ".js"):
        (sdir / Path(n).name).write_bytes(pack.read(n))
    res = subprocess.run(["node", str(ROOT / "tools" / "jsdata.mjs"), str(sdir)], capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit("tools/jsdata.mjs failed:\n" + res.stderr)
    return json.loads(res.stdout)


def entities(pack):
    out = {}
    for f in pack.files(BP + "entities/"):
        e = pack.json(f)["minecraft:entity"]
        key = e["description"]["identifier"].split(":")[1]
        c = e.get("components", {})
        out[key] = {
            "hp": (c.get("minecraft:health") or {}).get("value", 0),
            "attack": (c.get("minecraft:attack") or {}).get("damage"),
            "speed": (c.get("minecraft:movement") or {}).get("value", 0),
            "knockback": (c.get("minecraft:knockback_resistance") or {}).get("value", 0),
            "flies": any(k in c for k in ("minecraft:navigation.fly", "minecraft:navigation.hover", "minecraft:can_fly")),
            "fireImmune": "minecraft:fire_immune" in c,
        }
    return out


def items(pack, names):
    out = {}
    for f in pack.files(BP + "items/"):
        it = pack.json(f)["minecraft:item"]
        ident = it["description"]["identifier"]
        c = it["components"]
        out[ident] = {
            "name": names.get(f"item.{ident}") or (c.get("minecraft:display_name") or {}).get("value") or ident,
            "stack": c.get("minecraft:max_stack_size", 64),
            "durability": (c.get("minecraft:durability") or {}).get("max_durability"),
        }
    return out


def recipes(pack):
    out = []
    for f in pack.files(BP + "recipes/"):
        d = pack.json(f)
        for kind, r in d.items():
            if kind not in ("minecraft:recipe_shaped", "minecraft:recipe_shapeless"):
                continue
            res = r["result"][0] if isinstance(r["result"], list) else r["result"]
            res = {"item": res} if isinstance(res, str) else res
            if kind.endswith("shaped"):
                key = r["key"]
                rows = [[(key[ch]["item"] if ch in key else "") for ch in line] for line in r["pattern"]]
            else:
                flat = []
                for ing in r["ingredients"]:
                    flat += [ing["item"]] * int(ing.get("count", 1))
                rows = [flat[k:k + 3] for k in range(0, len(flat), 3)]
            out.append({"result": res["item"], "makes": int(res.get("count", 1)), "rows": rows,
                        "shapeless": kind.endswith("shapeless")})
    return out


def loot(pack):
    out = {}
    for f in pack.files(BP + "loot_tables/hollowdeep/"):
        d = pack.json(f)
        pools = []
        for p in d["pools"]:
            rolls = p.get("rolls", 1)
            rolls = (rolls["min"], rolls["max"]) if isinstance(rolls, dict) else (rolls, rolls)
            entries = []
            total = sum(e.get("weight", 1) for e in p["entries"])
            for e in p["entries"]:
                cnt = (1, 1)
                for fn in e.get("functions", []):
                    if fn.get("function") == "set_count":
                        c = fn["count"]
                        cnt = (c["min"], c["max"]) if isinstance(c, dict) else (c, c)
                entries.append({"item": e.get("name", ""), "weight": e.get("weight", 1), "total": total, "count": cnt})
            pools.append({"rolls": rolls, "entries": entries})
        out[Path(f).stem] = pools
    return out


def item_icons(pack, itemlist, dest):
    """16x16 item textures, scaled up 4x with nearest neighbour so they stay crisp."""
    tex = pack.json(RP + "textures/item_texture.json")["texture_data"]
    icons = {}
    for f in pack.files(BP + "items/"):
        it = pack.json(f)["minecraft:item"]
        ident = it["description"]["identifier"]
        icon = it["components"].get("minecraft:icon")
        key = None
        if isinstance(icon, dict):
            key = (icon.get("textures") or {}).get("default") or icon.get("texture")
        elif isinstance(icon, str):
            key = icon
        entry = tex.get(key)
        if not entry:
            print("No texture for", ident)
            continue
        path = entry["textures"]
        path = path[0] if isinstance(path, list) else path
        img = pack.image(RP + path + ".png")
        name = ident.split(":")[1]
        img.resize((64, 64), Image.NEAREST).save(dest / f"{name}.png")
        icons[ident] = f"img/icons/{name}.png"
    return icons


def mob_renders(pack, tmp, dest):
    """Renders each mob from the resource pack's own geometry and skin."""
    from hdlib import model_from_geo, render  # numpy + pillow
    rp = Path(tmp) / "rp"
    for n in pack.names:
        if n.startswith(RP) and not n.endswith("/"):
            p = rp / n[len(RP):]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(pack.read(n))
    geos = {}
    for g in (rp / "models" / "entity").glob("*.json"):
        d = json.loads(g.read_text())
        geos[d["minecraft:geometry"][0]["description"]["identifier"]] = d
    poses = {"mimic": {"lid": (-30, 0, 0)}}  # open the lid so it reads as a mimic
    out = {}
    for f in sorted((rp / "entity").glob("*.entity.json")):
        d = json.loads(f.read_text())["minecraft:client_entity"]["description"]
        key = d["identifier"].split(":")[1]
        m = model_from_geo(geos[d["geometry"]["default"]], str(rp / (d["textures"]["default"] + ".png")))
        em = "emissive" in d["materials"]["default"]
        im = render(m, 320, yaw=-30, pitch=14, emissive=em, pose=poses.get(key))
        im = im.crop(im.getbbox())
        w, h = im.size
        s = max(w, h) + 16
        sq = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        sq.alpha_composite(im, ((s - w) // 2, (s - h) // 2))
        sq.save(dest / f"{key}.png", optimize=True)
        sq.resize((96, 96), Image.LANCZOS).save(dest / f"{key}_icon.png", optimize=True)
        out[key] = {"big": f"img/mobs/{key}.png", "icon": f"img/mobs/{key}_icon.png"}
    return out


def lineup(src_dir, keys, dest):
    tiles = [Image.open(src_dir / f"{k}.png").resize((200, 200), Image.LANCZOS) for k in keys if (src_dir / f"{k}.png").exists()]
    if not tiles:
        return
    step = 170
    out = Image.new("RGBA", (step * (len(tiles) - 1) + 200, 200), (0, 0, 0, 0))
    for i, t in enumerate(tiles):
        out.alpha_composite(t, (step * i, 0))
    out.save(dest, optimize=True)


def vanilla_icons(ids, vanilla_src, dest):
    """Icons for vanilla items, cached in tools/vanilla/<id>.png."""
    VANILLA.mkdir(parents=True, exist_ok=True)
    found = {}
    if vanilla_src:
        base = Path(vanilla_src) / "dist" / "textures"
        idx = json.loads((base / "manifest" / "index.json").read_text())
        man = json.loads((base / "manifest" / f"{idx['latestVersion']}.json").read_text())
        by_id = {it["id"]: base / "assets" / it["texture"] for it in man["items"]}
        alias = {"minecraft:magma": "minecraft:magma_block", "minecraft:appleEnchanted": "minecraft:enchanted_golden_apple"}
        for i in ids:
            src = by_id.get(alias.get(i, i))
            if src:
                Image.open(src).convert("RGBA").resize((64, 64), Image.NEAREST).save(VANILLA / f"{i.split(':')[1]}.png")
    for i in ids:
        f = VANILLA / f"{i.split(':')[1]}.png"
        if f.exists():
            shutil.copy(f, dest / f.name)
            found[i] = f"img/vanilla/{f.name}"
    return found


def vanilla_name(ident):
    special = {"minecraft:experience_bottle": "Bottle o' Enchanting", "minecraft:totem_of_undying": "Totem of Undying",
               "minecraft:enchanted_golden_apple": "Enchanted Golden Apple", "minecraft:nether_star": "Nether Star"}
    return special.get(ident) or ident.split(":")[1].replace("_", " ").title()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="baseballr/Hollowdeep")
    ap.add_argument("--vanilla-src")
    args = ap.parse_args()

    rel = json.loads((ROOT / "addon" / "release.json").read_text())
    pack = Pack(ROOT / "addon" / rel["file"])
    manifest = pack.json(BP + "manifest.json")
    ver = ".".join(map(str, manifest["header"]["version"]))
    if ver != rel["version"]:
        raise SystemExit(f"addon/release.json says {rel['version']} but the pack is {ver}")

    for sub in ("icons", "mobs", "vanilla"):
        d = WWW / "img" / sub
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    names = lang(pack)
    with tempfile.TemporaryDirectory() as tmp:
        js = script_data(pack, tmp)
        if js["version"] != ver:
            raise SystemExit(f"scripts/version.js says {js['version']!r} but the pack is {ver}. "
                             "An empty or stale version.js stops the add-on's scripts from loading.")
        mobs = mob_renders(pack, tmp, WWW / "img" / "mobs")

    its = items(pack, names)
    recs = recipes(pack)
    tables = loot(pack)
    icons = item_icons(pack, its, WWW / "img" / "icons")

    vanilla_ids = set()
    for r in recs:
        vanilla_ids |= {c for row in r["rows"] for c in row if c.startswith("minecraft:")}
    for pools in tables.values():
        vanilla_ids |= {e["item"] for p in pools for e in p["entries"] if e["item"].startswith("minecraft:")}
    vanilla_ids |= {"minecraft:lodestone", "minecraft:crying_obsidian", "minecraft:chest", "minecraft:command_block",
                    "minecraft:book", "minecraft:clock", "minecraft:totem_of_undying", "minecraft:obsidian"}
    vicons = vanilla_icons(sorted(vanilla_ids), args.vanilla_src, WWW / "img" / "vanilla")
    missing = sorted(vanilla_ids - set(vicons))
    if missing:
        print("No icon for:", ", ".join(missing), "(run with --vanilla-src to fetch them)")

    def name_of(ident):
        if ident in its:
            return its[ident]["name"]
        return vanilla_name(ident)

    def icon_of(ident):
        return icons.get(ident) or vicons.get(ident)

    data = {
        "version": ver, "js": js, "entities": entities(pack), "items": its, "recipes": recs, "loot": tables,
        "mobs": mobs, "icon": icon_of, "name": name_of, "minEngine": ".".join(map(str, manifest["header"]["min_engine_version"])),
    }
    cats = pages.build(data)

    # [[Page name]] links, resolved now that every page has a slug.
    links = {}
    for c in cats:
        c["slug"] = slug(c["title"])
        for e in c["entries"]:
            e["slug"] = slug(e["name"])
            links.setdefault(e["name"].lower(), f"wiki/{c['slug']}/{e['slug']}")
            for alias in e.pop("aliases", []):
                links.setdefault(alias.lower(), f"wiki/{c['slug']}/{e['slug']}")
    bad = set()

    def link(m):
        target, label = m.group(1), m.group(2) or m.group(1)
        href = links.get(target.lower())
        if not href:
            bad.add(target)
            return label
        return f'<a href="{href}">{label}</a>'

    LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
    all_recipes = []
    for c in cats:
        c["icon"] = c.get("icon") or (c["entries"][0]["icon"] if c["entries"] else None)
        for e in c["entries"]:
            for b in e["blocks"]:
                for k in ("html", "text"):
                    if b.get(k) and k == "html":
                        b[k] = LINK.sub(link, b[k])
                if b["t"] == "grid" and b["title"] not in {r["name"] for r in all_recipes}:
                    all_recipes.append({"name": b["title"], "entry": e["name"], "cat": c["slug"], "slug": e["slug"],
                                        "icon": b.get("icon"), "makes": b.get("makes", 1), "rows": b["rows"]})
            e["summary"] = re.sub(r"<[^>]+>", "", LINK.sub(lambda m: m.group(2) or m.group(1), e.get("summary", "")))
    if bad:
        raise SystemExit("Links to no page: " + ", ".join(sorted(bad)))

    wiki = {
        "version": ver,
        "stats": {"topics": sum(len(c["entries"]) for c in cats), "mobs": len(data["entities"]),
                  "items": len(its), "recipes": len(all_recipes)},
        "categories": cats,
        "recipes": all_recipes,
    }
    (WWW / "data").mkdir(parents=True, exist_ok=True)
    (WWW / "data" / "wiki.json").write_text(json.dumps(wiki, ensure_ascii=False, separators=(",", ":")))

    repo, tag = args.repo, "v" + ver
    release = dict(rel)
    release["tag"] = tag
    release["download"] = f"https://github.com/{repo}/releases/download/{tag}/{rel['file']}"
    release["releasePage"] = f"https://github.com/{repo}/releases/tag/{tag}"
    release["allReleases"] = f"https://github.com/{repo}/releases"
    release["sizeBytes"] = (ROOT / "addon" / rel["file"]).stat().st_size
    try:
        release["date"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%cs", "--", "addon/release.json"], cwd=ROOT, text=True).strip() or None
    except Exception:
        release["date"] = None
    (WWW / "data" / "release.json").write_text(json.dumps(release, indent=2))

    pack.image(RP + "pack_icon.png").save(WWW / "img" / "pack_icon.png")
    lineup(WWW / "img" / "mobs", ["tomb_regent", "forge_tyrant", "winter_matriarch", "briar_colossus"], WWW / "img" / "lineup.png")

    print(f"v{ver}: {len(cats)} categories, {wiki['stats']['topics']} topics, {len(all_recipes)} recipes, "
          f"{len(mobs)} mob renders, {len(icons)} item icons")


if __name__ == "__main__":
    main()
