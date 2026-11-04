"""The wiki's pages. Hollowdeep has no in-game guide book, so the words live here.

Every number comes from `d`, which tools/extract.py reads out of the .mcaddon, so the pages follow
the add-on when it is rebalanced. Only the descriptions of how things behave are written by hand:
when a script changes what a mob, boss or relic *does*, update its text here.

Text is HTML. [[Page name]] or [[Page name|label]] links to another page (extract.py fails the
build on a link to a page that doesn't exist).
"""
import math

ROMAN = ["I", "II", "III", "IV", "V"]
EFFECT_LEVEL = ["I", "II", "III", "IV", "V", "VI", "VII"]

# ---------------------------------------------------------------- block helpers


def P(html):
    return {"t": "p", "html": html}


def H2(text):
    return {"t": "h2", "text": text}


def H3(text):
    return {"t": "h3", "text": text}


def TABLE(rows):
    head = "".join(f"<th>{c}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows[1:])
    return {"t": "table", "html": f'<div class="table-wrap"><table class="wiki-table"><thead><tr>{head}</tr></thead>'
                                  f"<tbody>{body}</tbody></table></div>"}


def FIG(src, caption):
    return {"t": "figure", "icon": src, "text": caption}


def LIST(items):
    return {"t": "html", "html": "<ul class=\"wiki-list\">" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"}


def ENTRY(name, icon, summary, blocks, aliases=()):
    return {"name": name, "icon": icon, "summary": summary, "blocks": [P(summary)] + blocks, "aliases": list(aliases)}


# ---------------------------------------------------------------- number helpers


def jsround(x):
    return math.floor(x + 0.5)


def n(x):
    """3.0 -> 3, 2.5 -> 2.5"""
    return int(x) if float(x).is_integer() else round(x, 2)


def hearts(hp):
    return f"{n(hp)} ({n(hp / 2)} ♥)"


def secs(s):
    s = n(s)
    if s >= 60 and s % 60 == 0:
        return f"{s // 60} min"
    if s >= 60:
        return f"{s // 60} min {s % 60} s"
    return f"{s} s"


def pct(x):
    return f"{n(round(x * 100, 1))}%"


def level(amp):
    """Effect amplifier 0 -> 'I'."""
    return EFFECT_LEVEL[amp] if 0 <= amp < len(EFFECT_LEVEL) else str(amp + 1)


class Numbers:
    def __init__(self, d):
        self.d = d
        js = d["js"]
        self.T = {int(k): v for k, v in js["tiers"].items()}
        self.tune = {int(k): v for k, v in js["bossTune"].items()}
        self.rw = {int(k): v for k, v in js["rarityWeights"].items()}
        self.ent = d["entities"]
        self.label = js["mobLabel"]
        self.label.setdefault("ward_crystal", "Ward Crystal")

    def boost(self, amp):
        """Health Boost adds 4 health per level; amplifier -1 means no effect."""
        return 4 * (amp + 1) if amp >= 0 else 0

    def strength(self, amp):
        """Strength adds 3 melee damage per level in Bedrock."""
        return 3 * (amp + 1) if amp >= 0 else 0

    def mob_hp(self, key, t):
        amp = self.T[t]["bossBoost"] if key in BOSSES else self.T[t]["hpAmp"]
        return self.ent[key]["hp"] + (0 if key == "ward_crystal" else self.boost(amp))

    def elite_hp(self, key, t):
        return self.ent[key]["hp"] + self.boost(self.T[t]["hpAmp"] + 2)

    def melee(self, key, t):
        a = self.ent[key].get("attack")
        if not a:
            return None
        return a + (0 if key == "wisp" else self.strength(self.T[t]["strAmp"]))

    def ability(self, t, base, per):
        return max(1, jsround((base + per * t) * self.tune[t]["dmg"] * 2) / 2)


BOSSES = ["tomb_regent", "forge_tyrant", "winter_matriarch", "briar_colossus"]


# ---------------------------------------------------------------- pages


def build(d):
    N = Numbers(d)
    js = d["js"]
    icon, name = d["icon"], d["name"]
    mob_icon = lambda k: d["mobs"].get(k, {}).get("icon")
    mob_big = lambda k: d["mobs"].get(k, {}).get("big")
    T, tiers = N.T, sorted(N.T)
    L = js["limits"]
    G = js["gates"]

    def grid(result):
        r = next((r for r in d["recipes"] if r["result"] == result), None)
        if not r:
            return None
        rows = [[{"name": name(c) if c else "", "icon": icon(c) if c else None} for c in row] for row in r["rows"]]
        return {"t": "grid", "title": name(result), "icon": icon(result), "makes": r["makes"], "rows": rows,
                "note": "Crafting table, any order" if r["shapeless"] else "Crafting table"}

    def themes_with(mob):
        return [t["name"] for t in js["themes"].values() if any(k == mob for k, _ in t["extra"]) or t["boss"] == mob]

    cats = []

    # ============================================================ Getting started
    start = []
    key1 = grid("hollowdeep:rift_key")
    start.append(ENTRY("How to play", icon("hollowdeep:rift_key"),
        "Hollowdeep adds rifts: short, instanced dungeons in the sky with waves of custom mobs, elite affixes, "
        "four themed bosses and a vault of relics at the end.",
        [
            H2("Your first rift"),
            LIST([
                "Craft a <b>Rift Key</b> (recipe below), or find a [[Rift Gates|Rift Gate]] that tears open near you.",
                f"Gather your friends: everyone standing within <b>{L['joinRadius']} blocks</b> of you when you use the key comes along.",
                "Use the key. The rift builds in a few seconds, then everyone is pulled inside.",
                "Walk into the first chamber. The gate shuts behind you and the fight starts. Each chamber has a [[Chamber objectives|goal]]: "
                "clear the waves, hold a sigil, hunt a champion or crack a rune lock. Finish it to open the next gate.",
                "After the last chamber comes the boss arena. Break the boss's [[Boss fights|wards]], dodge its arena hazards and beat it, and the vault gate opens.",
                f"Loot the vault chests. You have <b>{secs(L['lootWindow'])}</b> before the rift collapses and sends you home.",
            ]),
            key1,
            H2("Good to know"),
            LIST([
                "Inside a rift you are in Adventure mode: you can't break or place blocks. Your old game mode comes back when you leave.",
                "Every rift has a time limit (see [[Rift tiers]]). If it runs out the rift collapses and you go home without the vault.",
                "If you die, you get a [[Soul Tether]] when you respawn. Use it to jump back in.",
                "The crying obsidian sigil in the entrance (and in the vault) is the way out. Stand still on it for 3 seconds to leave for good.",
                "When you leave or the rift ends you go back to the exact spot you left from.",
                "Chests in the chambers are loot caches, but some are [[Mimic|Mimics]].",
            ]),
            H2("Getting stronger"),
            P("Bosses drop <b>Rift Cores</b> and every kill can drop <b>Hollow Essence</b>. Use them to upgrade your key to "
              "[[Rift Keys|Rift Key II to V]]: higher tiers have more chambers, tougher mobs, more vault chests and better "
              "[[Relics|relic]] odds. Relics are the gear Hollowdeep is built around: carry them for their bonuses and use "
              "them for their powers."),
            P("Everything you earn feeds back in: spend Essence and Cores at the [[Hollow Forge]] to ascend, temper and reroll your "
              "relics, and earn Delver XP from every kill and clear to climb the ten [[Delver ranks]] and unlock permanent perks."),
        ], aliases=["Getting started"]))

    start.append(ENTRY("Rift Gates", icon("minecraft:lodestone"),
        "Rift Gates are free rifts that tear open in the Overworld near players. Tap the lodestone in the middle to open a rift, no key needed.",
        [
            H2("Where gates appear"),
            LIST([
                f"Once a minute, each player on the surface of the Overworld (between y {G['height'][0]} and {G['height'][1]}) has a "
                f"<b>{pct(G['chance'])}</b> chance to make a gate appear.",
                f"The gate lands {G['range'][0]} to {G['range'][1]} blocks away, and chat tells you how far and in which direction.",
                "Gates only appear on flat, natural ground (grass, dirt, sand, stone, snow and so on) with open sky, so they never land on your builds.",
                f"There are at most <b>{G['max']}</b> gates in the world at once.",
                f"A gate fades after <b>{G['lifetimeMin']} minutes</b> of real time, and the ground under it is put back.",
            ]),
            H2("Gate tier"),
            P("The further from world spawn, the higher the tier of the rift a gate opens:"),
            TABLE([["Distance from world spawn", "Rift tier"]] + [
                [f"{'under' if i == 0 else 'from ' + format(G['distances'][i - 1], ',') + ' to'} {G['distances'][i]:,} blocks"
                 if i < 4 else f"{G['distances'][3]:,} blocks or more", f"Tier {ROMAN[i]}"] for i in range(5)]),
            H2("What it looks like"),
            P("A 5 by 5 platform of polished blackstone bricks with a crying obsidian pillar topped by a soul lantern in each "
              "corner and a lodestone in the middle. Tap the lodestone to open the rift. Like a key, it takes everyone standing "
              f"within {L['joinRadius']} blocks of you. Breaking the lodestone removes the gate."),
        ], aliases=["Rift Gate", "Gates"]))

    tether = "hollowdeep:soul_tether"
    start.append(ENTRY("Dying and leaving", icon(tether),
        "How to get out of a rift, and what happens when you die in one.",
        [
            H2("Dying"),
            P("When you die inside a rift you respawn in the world as usual, with a [[Soul Tether]] in your inventory. Use it "
              "to return to the rift's entrance while the rift is still open. Your items stay where you died; vanilla rules "
              "apply, so they despawn after 5 minutes. Chat tells you the coordinates."),
            P("Your friends carry on without you. The rift stays open while at least one member is inside, and closes "
              f"by itself if it has been empty for <b>{secs(L['emptyGrace'])}</b>."),
            H2("Leaving early"),
            P("The crying obsidian sigil just inside the entrance is the exit. Stand still on it for 3 seconds. Leaving this way is "
              "permanent: you are no longer a member of the rift, and your Soul Tether stops working."),
            H2("How a rift ends"),
            TABLE([["Reason", "What happens"],
                   ["Boss beaten", f"The vault opens. {secs(L['lootWindow'])} later the rift collapses and everyone inside goes home."],
                   ["Time ran out", "The rift collapses. Nobody gets the vault."],
                   ["Empty", f"Nobody has been inside for {secs(L['emptyGrace'])}: the rift fades."],
                   ["Admin", "<code>/scriptevent hollowdeep:end</code> closes every rift (see [[Commands]])."]]),
            P("Players are always sent back to where they were standing when they entered. If the world crashes or restarts "
              "with a rift open, the rift is cleaned up on the next load and anyone stuck in it is sent home."),
        ], aliases=["Leaving a rift", "Dying"]))

    cats.append({"title": "Basics", "group": "Getting started",
                 "blurb": "Opening your first rift, gates in the world, dying and leaving.", "entries": start})

    # ============================================================ Rifts
    rift = []
    rift.append(ENTRY("Inside a rift", icon("minecraft:crying_obsidian"),
        "Every rift is a straight run of rooms built high in the sky: an entrance, a row of chambers, the boss arena and the vault.",
        [
            H2("The rooms"),
            TABLE([["Room", "Size", "What happens there"],
                   ["Entrance", "15 long, 15 wide", "Where you arrive. The exit sigil is here."],
                   ["Chambers", "25 long, 21 wide", "Each has an [[Chamber objectives|objective]]. A gate seals the way on until it's done. Loot caches line the walls, and some chambers have a barred Reliquary."],
                   ["Boss arena", "35 long, 33 wide", "The theme's boss rises when you walk in. It can't leave the arena."],
                   ["Vault", "13 long, 11 wide", "Opens when the boss dies: the relic chest and the vault chests, plus a second exit sigil."]]),
            P("Short corridors join the rooms, each with a gate. The number of chambers depends on the [[Rift tiers|tier]]."),
            H2("Chambers and waves"),
            P("A chamber wakes up when you step into it. The first chamber is always a Purge: several waves, the next coming when the "
              "last mob of the one before it is dead. Later chambers can roll other goals, see [[Chamber objectives]]. "
              "When you enter a rift, chat lists each chamber's objective."),
            P("The number of mobs in a wave is:"),
            P("<code>base + chamber number + 2 × wave number + (players − 1) × per extra player</code>, "
              "capped at the tier's maximum. Hollow Wisps come in threes but only count as two."),
            P("Chamber and wave numbers start at 0. A [[Rift modifiers|Bloodmoon]] rift multiplies the total by 1.35 "
              "before the cap. The numbers for each tier are on [[Rift tiers]]."),
            P("Which mobs show up depends on how deep you are: the first chamber has only "
              "[[Crypt Brute|Crypt Brutes]] and [[Hollow Wisp|Wisps]], later chambers add [[Hexcaster|Hexcasters]], "
              "[[Warded Husk|Warded Husks]] and [[Bone Chorus|Bone Choruses]], and from the second chamber on the "
              "[[Rift themes|theme]]'s own mobs join in."),
            H2("The HUD"),
            P("The action bar shows the tier, which chamber you're in, its objective's progress, how many foes are left, the time remaining and the rift's modifiers."),
            H2("Limits"),
            LIST([f"Up to <b>{L['maxRifts']}</b> rifts can be open at once in a world. Opening another tells you to wait.",
                  "Each open rift uses one ticking area. Bedrock allows 10 per world, so if yours are all taken the rift can't form "
                  "(your key is given back and chat tells you to remove one with <code>/tickingarea list</code>).",
                  "You can only be in one rift at a time, and rifts can only be opened in the Overworld.",
                  f"Rifts are built at x {L['origin']['x']:,}, y {L['origin']['y']}, far from anything you've built. "
                  "Vanilla monsters that wander in are removed."]),
        ], aliases=["Rift layout", "Chambers"]))

    obj = js["objectives"]
    ow = sum(o["weight"] for o in obj.values())
    hb = js["holdBase"]
    rift.append(ENTRY("Chamber objectives", icon("minecraft:sea_lantern"),
        "Every chamber after the first rolls a goal: clear the waves, hold a sigil, hunt a champion or crack a rune lock. "
        "Some also hide a barred Reliquary, and a rift can hold a Shrine that offers a bargain.",
        [
            H2("Objectives"),
            TABLE([["Objective", "Chance", "How to clear it"],
                   [obj["waves"]["name"], pct(obj["waves"]["weight"] / ow), "Kill every wave. The first chamber is always a Purge."],
                   [obj["hold"]["name"], pct(obj["hold"]["weight"] / ow),
                    f"A ring of sea lanterns glows in the middle of the floor. Stand in it until it charges: {hb[0]} + {hb[1]} × tier seconds "
                    "with one player, faster with more. Foes keep coming, and any foe inside the ring stalls the charge. When it's full the rest are banished."],
                   [obj["champion"]["name"], pct(obj["champion"]["weight"] / ow),
                    "A Champion waits on a gilded dais at the far end: an elite with extra health, Resistance and fire immunity that calls guards "
                    "every 15 seconds. Kill it and its guards scatter. Champions drop extra Essence and often a Rift Core."],
                   [obj["runes"]["name"], pct(obj["runes"]["weight"] / ow),
                    "Four coloured pedestals with buttons on top. Beat the guardians, then watch the runes light up and press them in the same "
                    "order. Two rounds; the sequence is 3 + half the tier long and one longer in round two. A wrong press hurts everyone and "
                    "summons more guardians, then the runes show a new sequence."]]),
            P("The same objective never comes twice in a row, except Purge."),
            H2("Reliquaries"),
            P("About one chamber in three (at most two per rift) has a barred alcove in its north wall with a relic inside. Once the "
              "chamber is clear, press the button on the gold block beside the bars to wake its guardians: a pack of elites, each with an "
              "[[Elites|affix]]. Kill them all and the bars lift, revealing a chest with a rolled relic (+10% quality) and some Essence. "
              "It's optional: skip it if your party is hurting."),
            H2("Shrines"),
            P("About half of all rifts hide a Shrine in one chamber. It rises from the floor when that chamber is cleared. Press its button "
              "to hear its bargain, and accept or walk away. A pact binds the whole party and can only be taken once."),
            TABLE([["Pact", "Price", "Reward"]] + [[v["name"], v["cost"], v["gain"]] for v in js["pacts"].values()]),
        ], aliases=["Objectives", "Hold the Sigil", "Hunt the Champion", "Rune Lock", "Reliquary", "Shrine", "Shrines", "Pacts", "Champion"]))

    # ---- tiers
    rows = [["", *[f"Tier {ROMAN[t - 1]}" for t in tiers]]]
    def row(label, f):
        rows.append([label, *[f(t) for t in tiers]])
    row("Key", lambda t: f"[[Rift Keys|{name(['hollowdeep:rift_key', 'hollowdeep:rift_key_2', 'hollowdeep:rift_key_3', 'hollowdeep:rift_key_4', 'hollowdeep:rift_key_5'][t - 1])}]]")
    row("Time limit", lambda t: f"{T[t]['minutes']} min")
    row("Chambers", lambda t: T[t]["chambers"])
    row("Waves per chamber", lambda t: T[t]["waves"])
    row("Mobs in first wave", lambda t: T[t]["mobBase"])
    row("Extra mobs per extra player", lambda t: f"+{T[t]['perExtraPlayer']}")
    row("Most mobs in a wave", lambda t: T[t]["cap"])
    row("Mob bonus health", lambda t: f"+{N.boost(T[t]['hpAmp'])}")
    row("Mob bonus damage", lambda t: f"+{N.strength(T[t]['strAmp'])}" if T[t]["strAmp"] >= 0 else "none")
    row("Elite chance (first chamber)", lambda t: pct(T[t]["elite"]))
    row("Elite chance (last chamber)", lambda t: pct(T[t]["elite"] + 0.03 * (T[t]["chambers"] - 1)))
    row("Boss bonus health", lambda t: f"+{N.boost(T[t]['bossBoost'])}")
    row("Boss ability damage", lambda t: f"× {n(N.tune[t]['dmg'])}")
    row("Boss enrages after", lambda t: secs(N.tune[t]["enrageAt"]))
    row("Vault chests", lambda t: T[t]["chests"])
    row("Themes", lambda t: "Sunken Crypt only" if t < min(th["minTier"] for th in js["themes"].values() if th["boss"] != "tomb_regent") else "all four")
    rarity_names = [r["n"] for r in js["rarities"]]
    for i, rn in enumerate(rarity_names):
        row(f"{rn} relic", lambda t, i=i: f"{N.rw[t][i]}%")

    mob_rows = [["Mob", *[f"T{ROMAN[t - 1]}" for t in tiers]]]
    for k in ["crypt_brute", "warded_husk", "hexcaster", "bone_chorus", "wisp", "mimic", "ember_imp", "frost_revenant", "thorn_stalker"]:
        mob_rows.append([f"[[{N.label[k]}]]", *[f"{n(N.mob_hp(k, t))} hp / {n(N.melee(k, t))} dmg" for t in tiers]])
    boss_rows = [["Boss", *[f"T{ROMAN[t - 1]}" for t in tiers]]]
    for k in BOSSES:
        boss_rows.append([f"[[{N.label[k]}]]", *[f"{n(N.mob_hp(k, t))} hp / {n(N.melee(k, t))} dmg" for t in tiers]])

    rift.append(ENTRY("Rift tiers", icon("hollowdeep:rift_key_3"),
        "Rifts come in five tiers. The tier is set by the key you use, or for a gate by how far it is from world spawn.",
        [
            H2("The balance table"),
            TABLE(rows),
            P("Mob bonus health comes from Health Boost (4 health per level) and bonus damage from Strength (3 damage per level). "
              "Elite chance goes up by 3% for each chamber, plus 15% in a [[Rift modifiers|Bloodmoon]] rift. Relic odds are "
              "shifted further toward the rare end by a rift's [[Rift modifiers|modifiers]]."),
            H2("Mob health and melee damage by tier"),
            TABLE(mob_rows),
            P("Elites have more health than this: see [[Elites]]. Hollow Wisps never get bonus damage."),
            H2("Boss health and melee damage by tier"),
            TABLE(boss_rows),
            P("Boss abilities hit harder than their melee: see [[Boss fights]] for every ability's damage at each tier."),
        ], aliases=["Tiers", "Balance", "Tier"]))

    # ---- themes
    theme_rows = [["Theme", "From tier", "Boss", "Extra mobs", "Boss relic"]]
    for t in js["themes"].values():
        extra = ", ".join(f"[[{N.label[k]}]]" for k, _ in t["extra"]) or "none"
        theme_rows.append([t["name"], ROMAN[t["minTier"] - 1], f"[[{N.label[t['boss']]}]]", extra,
                           f"[[{name(t['relic'])}]]" if t["relic"] else "none"])
    rift.append(ENTRY("Rift themes", mob_icon("forge_tyrant"),
        "Each rift picks a theme when it opens. The theme sets the look of the rooms, adds its own mobs from the second chamber on, and decides the boss.",
        [
            TABLE(theme_rows),
            P("Tier I rifts are always a Sunken Crypt. From Tier II up the theme is picked at random from all four."),
            P("Themed bosses also drop their theme's relic, already rolled, on top of the vault's own relic."),
            H2("Looks"),
            TABLE([["Theme", "Walls", "Floor", "Ceiling"]] + [
                [t["name"], t["wall"].split(":")[1].replace("_", " "), t["floor"].split(":")[1].replace("_", " "),
                 t["ceil"].split(":")[1].replace("_", " ")] for t in js["themes"].values()]),
        ], aliases=["Themes", "Theme", "Sunken Crypt", "Ember Forge", "Frostbound Vault", "Verdant Ruin"]))

    # ---- modifiers
    mod_effect = {
        "bloodmoon": f"35% more mobs in every wave, and +15% elite chance.",
        "swift": "Every mob has Speed I.",
        "armored": "Every mob has Resistance I (20% less damage taken).",
        "volatile": "30% of mobs explode when they die. The blast hurts but never breaks blocks.",
        "haunted": "Every chamber has two [[Mimic|Mimics]] among its chests instead of at most one.",
        "gloom": "Darkness washes over everyone for 7 seconds, every 20 seconds.",
    }
    mod_rows = [["Modifier", "Effect", "Relic bonus"]]
    for k, m in js["mods"].items():
        mod_rows.append([k.title(), mod_effect.get(k, m["desc"]), f"+{m['bump']}%"])
    rift.append(ENTRY("Rift modifiers", icon("minecraft:clock"),
        "Some rifts roll modifiers when they open. Each one makes the rift harder and pushes its relics toward higher rarities.",
        [
            TABLE(mod_rows),
            H2("How many"),
            TABLE([["Tier", "Modifiers"],
                   ["I", "25% chance of one"],
                   ["II", "55% chance of one"],
                   ["III", "55% chance of one, and a separate 20% chance of a second"],
                   ["IV and V", "Always one, and a 50% chance of a second"]]),
            P("A rift never rolls the same modifier twice. The modifiers are announced in chat when you arrive and shown on the HUD."),
            H2("The relic bonus"),
            P("The relic bonuses of every modifier on the rift are added up. That many percentage points are taken from the "
              "Common and Rare odds (Common first) and handed out 70% to Epic and 30% to Legendary. It applies to the vault relic and the boss relic."),
            P("Mimic chests, Wisps and Ward Crystals don't get Swift or Armored, and they never explode."),
        ], aliases=["Modifiers", "Bloodmoon", "Gloom", "Haunted"]))

    # ---- loot
    def loot_table(pools):
        out = [["Item", "Amount", "Chance per pick"]]
        for p in pools:
            for e in p["entries"]:
                if not e["item"]:
                    continue
                c = e["count"]
                amt = str(c[0]) if c[0] == c[1] else f"{c[0]} to {c[1]}"
                out.append([name(e["item"]), amt, pct(e["weight"] / e["total"])])
        return out

    def picks(pools):
        return " then ".join(f"{p['rolls'][0]}" if p["rolls"][0] == p["rolls"][1] else f"{p['rolls'][0]} to {p['rolls'][1]}" for p in pools)

    lt = d["loot"]
    loot_blocks = [
        H2("Where loot comes from"),
        LIST([
            "<b>Mob drops.</b> A normal mob has a 55% chance to drop 1 Hollow Essence; an [[Elites|elite]] drops 2 to 4 and a "
            "[[Mimic]] 3 to 6. Each kill also has a chance of one extra Essence equal to the best Fortune bonus in the party "
            "(see [[Relics]]). Mobs raised by a [[Bone Chorus]], summoned by an elite or called in by a boss drop nothing.",
            "<b>Caches.</b> Each chamber has one real chest of loot, and usually a decoy that is a [[Mimic]] (50% chance, or always two in a "
            "[[Rift modifiers|Haunted]] rift).",
            f"<b>The boss.</b> Drops 1 + tier [[Rift Core|Rift Cores]] and 10 + 4 × tier [[Hollow Essence]], and a themed boss "
            "also drops its theme's relic.",
            "<b>The vault.</b> One chest holds a [[Relics|relic]] plus Essence and Rift Cores; the rest hold valuables. "
            "Relics are rolled the moment the chest is filled.",
        ]),
        H2("Boss drops by tier"),
        TABLE([["Tier", "Rift Cores", "Hollow Essence"]] + [[ROMAN[t - 1], 1 + t, 10 + 4 * t] for t in tiers]),
    ]
    for t in tiers:
        loot_blocks += [H2(f"Tier {ROMAN[t - 1]}")]
        loot_blocks += [H3(f"Chamber cache ({picks(lt[f'cache_t{t}'])} picks)"), TABLE(loot_table(lt[f"cache_t{t}"]))]
        loot_blocks += [H3(f"Vault relic chest ({picks(lt[f'vault_relic_t{t}'])} picks)"),
                        P("The first pick is always one relic, equally likely to be any of the eight."),
                        TABLE(loot_table(lt[f"vault_relic_t{t}"][1:]))]
        loot_blocks += [H3(f"Vault chests ({T[t]['chests'] - 1} of them, {picks(lt[f'vault_goods_t{t}'])} picks each)"),
                        TABLE(loot_table(lt[f"vault_goods_t{t}"]))]
    loot_blocks += [P("Other add-ons can add their own items to vault chests: see [[Commands]].")]
    rift.append(ENTRY("Loot", icon("minecraft:chest"),
        "What drops from mobs and bosses, and what's in the chamber caches and the vault at each tier.", loot_blocks,
        aliases=["Vault", "Caches", "Loot tables"]))

    cats.append({"title": "Rift mechanics", "group": "Rifts",
                 "blurb": "How a rift is laid out, the five tiers and their numbers, themes, modifiers and loot.", "entries": rift})

    # ============================================================ Mobs
    def mob_entry(key, summary, behaviour, extra=(), aliases=()):
        e = N.ent[key]
        found = []
        if key in ("crypt_brute", "warded_husk", "hexcaster", "bone_chorus", "wisp"):
            first = next(i for i, p in enumerate(js["pools"]) if any(k == key for k, _ in p))
            found.append(f"Every theme, from chamber {first + 1}")
        th = themes_with(key)
        if th and key not in BOSSES:
            found.append(", ".join(th) + " rifts, from chamber 2")
        if key == "mimic":
            found.append("Decoy chests in every chamber")
        stats = [["", *[f"T{ROMAN[t - 1]}" for t in tiers]],
                 ["Health", *[n(N.mob_hp(key, t)) for t in tiers]]]
        if e.get("attack"):
            stats.append(["Melee damage", *[n(N.melee(key, t)) for t in tiers]])
        info = [["Base health", hearts(e["hp"])]]
        if e.get("attack"):
            info.append(["Base melee damage", n(e["attack"])])
        info.append(["Movement", "Flies" if e["flies"] else ("Stationary" if not e["speed"] else f"Walks ({n(e['speed'])})")])
        info.append(["Knockback resistance", pct(e["knockback"])])
        if found:
            info.append(["Found in", "; ".join(found)])
        info.append(["Can be elite", "No" if key in ("wisp", "mimic", "ward_crystal", "ember_imp") or key in BOSSES else "Yes"])
        info_html = "<table class=\"info-table\">" + "".join(f"<tr><th>{a}</th><td>{b}</td></tr>" for a, b in info) + "</table>"
        blocks = [FIG(mob_big(key), N.label[key]), {"t": "table", "html": info_html}, H2("Behaviour")]
        blocks += [P(b) for b in behaviour]
        blocks += list(extra)
        blocks += [H2("By tier"), TABLE(stats)]
        return ENTRY(N.label[key], mob_icon(key), summary, blocks, aliases)

    curses = ", ".join(f"{c[0].replace('_', ' ').title()} {level(c[2])} for {n(c[1] / 20)} s" for c in js["curses"])
    hex_dmg = ", ".join(f"T{ROMAN[t - 1]} {n(2 + t * 1.5)}" for t in tiers)
    mobs = [
        mob_entry("crypt_brute", "The rank and file of every rift: a slow, tough skeleton that hits hard up close.",
                  ["Walks up and hits you. No tricks, but it has the most health of the regular mobs and shrugs off half of all knockback.",
                   "Crypt Brutes are in every chamber of every rift, and the Ember Forge adds even more of them."]),
        mob_entry("warded_husk", "A husk that floats a Ward Crystal over its head. While the crystal lives, the husk can't be hurt.",
                  ["Each Warded Husk spawns with a [[Ward Crystal]] hovering above it. While the crystal is intact the husk has Resistance V, "
                   "which blocks all damage. Break the crystal first: chat shouts <i>The ward shatters</i> and the husk can be hurt normally.",
                   "The crystal follows the husk around, so aim up."]),
        mob_entry("ward_crystal", "The floating crystal that shields a Warded Husk. Break it to make the husk vulnerable.",
                  [f"Has only {n(N.ent['ward_crystal']['hp'])} health and never gets tier bonuses, but it floats above the husk's head and moves with it.",
                   "It doesn't attack, drops nothing, and doesn't count toward clearing the chamber."]),
        mob_entry("hexcaster", "A robed caster that hangs back and fires curse bolts.",
                  [f"Every 2.75 seconds, if a player is within 15 blocks, it fires a curse bolt (a purple line of particles) that always hits. "
                   f"The bolt deals magic damage that goes up with the tier ({hex_dmg}) and puts one random curse on you: {curses}.",
                   "It is fragile up close. Close the distance or break its line of sight."]),
        mob_entry("bone_chorus", "A skeletal singer that raises the dead. Kill it first.",
                  ["While a Bone Chorus is alive, any other mob that dies within 14 blocks of it rises again 3 seconds later "
                   "(a soul flame marks the spot). A raised mob can't come back a second time, can't be an elite and drops nothing.",
                   "The chamber can't clear while a mob is waiting to rise. Bone Choruses and Wisps are never raised."]),
        mob_entry("wisp", "Small, fast, flying spirits that come in threes.",
                  ["Wisps always spawn in groups of three (which only count as two toward the wave size). They fly, are quick, and have very "
                   "little health. They never get the tier's bonus damage.",
                   "Summoner [[Elites|elites]] also call in Wisps; those drop nothing."]),
        mob_entry("mimic", "A chest with teeth. Some of the chests in each chamber are Mimics.",
                  ["Each chamber has one real loot chest and, half of the time, a decoy. Opening the decoy turns it into a Mimic "
                   "(two decoys in a [[Rift modifiers|Haunted]] rift). You can't tell them apart before opening.",
                   "A Mimic drops 3 to 6 [[Hollow Essence]], more than any other regular mob. It doesn't count toward clearing the chamber, "
                   "so you can leave it for later."]),
        mob_entry("ember_imp", "A tiny flying devil from the Ember Forge whose hits set you on fire.",
                  ["Flies, is very fast and fragile. Every hit sets you on fire for 3 seconds.",
                   "The [[Forge Tyrant]] calls swarms of them in."]),
        mob_entry("frost_revenant", "An icy knight of the Frostbound Vault whose hits slow you down.",
                  ["Every hit gives you Slowness I for 3 seconds. Tough, like a [[Crypt Brute]].",
                   "The [[Winter Matriarch]] calls them in."]),
        mob_entry("thorn_stalker", "A quick, thorny hunter from the Verdant Ruin whose hits poison you.",
                  ["Faster than most walkers. Every hit poisons you (Poison I for 3 seconds).",
                   "The [[Briar Colossus]] calls them in."]),
    ]
    cats.append({"title": "Mobs", "group": "Foes",
                 "blurb": "The creatures that fill the chambers: what each one does and how tough it is at each tier.", "entries": mobs})

    # ---- elites
    aff_text = {
        "shielded": ("Shielded", "Absorption IV: 16 extra health as yellow hearts on top of its normal health."),
        "vampiric": ("Vampiric", "Speed I, and it heals 60% of the damage it deals to you."),
        "explosive": ("Explosive", "Explodes when it dies (a bigger blast than Volatile). It doesn't break blocks."),
        "summoner": ("Summoner", "Every 10 seconds, while a player is within 24 blocks, it summons 2 [[Hollow Wisp|Wisps]] (up to 14 in the rift). Summoned Wisps drop nothing."),
        "teleporter": ("Phasing", "When you are 6 to 22 blocks away it teleports right next to you, every 6 seconds."),
        "thorned": ("Thorned", "Every time you hit it you take 1.5 + tier damage back."),
    }
    elite_rows = [["", *[f"T{ROMAN[t - 1]}" for t in tiers]]]
    for k in ["crypt_brute", "warded_husk", "hexcaster", "bone_chorus", "frost_revenant", "thorn_stalker"]:
        elite_rows.append([f"[[{N.label[k]}]]", *[n(N.elite_hp(k, t)) for t in tiers]])
    elites = [ENTRY("Elites", mob_icon("crypt_brute"),
        "Any regular mob can spawn as an elite: it gets an affix, extra health, a coloured name and drops more Hollow Essence.",
        [
            H2("Affixes"),
            TABLE([["Affix", "What it does"]] + [[aff_text[a][0], aff_text[a][1]] for a in js["affixes"]]),
            H2("Elite chance"),
            P("The chance for each mob is the tier's base chance, plus 3% for each chamber after the first, plus 15% in a "
              "[[Rift modifiers|Bloodmoon]] rift. See [[Rift tiers]] for the numbers."),
            P("Wisps, Mimics, Ward Crystals, Ember Imps, bosses and anything raised or summoned are never elite."),
            H2("Elite health"),
            P("An elite has Health Boost two levels higher than the tier gives normal mobs: 8 more health than a normal mob of the same tier."),
            TABLE(elite_rows),
            H2("Rewards"),
            P("An elite drops 2 to 4 [[Hollow Essence]] instead of the usual 55% chance of one. Other add-ons can listen for elite kills "
              "(see [[Commands]])."),
        ], aliases=["Elite", "Affixes", "Elite affixes"])]
    cats.append({"title": "Elites", "group": "Foes",
                 "blurb": "Affixed mobs with more health, nastier tricks and better drops.", "entries": elites})

    # ============================================================ Bosses
    ab_text = {
        "slam": ("Slam", 6.5, "Raises a fist (a ring of smoke appears, fire for the Forge Tyrant) and slams 1 second later. Everyone inside "
                 "the 6.5 block ring takes damage and is thrown back. The Forge Tyrant's slam also sets you on fire."),
        "drain": ("Life Drain", None, "A soul beam to the nearest player within 30 blocks. Deals magic damage and heals the boss "
                  "2% of its maximum health. It can't be dodged."),
        "fire_wave": ("Fire Wave", None, "A line of flame toward the nearest player, 16 blocks long. 1 second later anyone within 2 blocks "
                      "of the line is burned and set on fire. Step sideways."),
        "fire_nova": ("Fire Nova", None, "Two rings of flame appear around the boss. 1.25 seconds later everyone between 5 and 10 blocks "
                      "away is burned. Hug the boss or run far."),
        "frost_nova": ("Frost Nova", None, "A ring of snow 9 blocks out. 1.25 seconds later everyone inside it takes damage, "
                       "gets Slowness III for 4 seconds and is pushed away."),
        "ice_spikes": ("Ice Spikes", None, "A small ring of snow appears under up to four players. 1.25 seconds later spikes burst out: anyone "
                       "still within 2.4 blocks is hurt and launched upward. Keep moving."),
        "root_snare": ("Root Snare", None, "Roots grab the two closest players: Slowness VI for 3 seconds, Poison I for 4 seconds and some "
                       "magic damage. It can't be dodged."),
        "thorn_burst": ("Thorn Burst", None, "Eight lines of thorns shoot out from the boss in a star, 11 blocks long. 1 second later anyone on a "
                        "line is hurt and gets Poison II for 4 seconds. Stand between the lines."),
    }
    boss_text = {
        "tomb_regent": ("The lord of the Sunken Crypt and the boss of every Tier I rift. A slow, heavy fighter who calls up the dead.",
                        "Sunken Crypt"),
        "forge_tyrant": ("Master of the Ember Forge. Fire everywhere: slams, waves and a nova, with swarms of Ember Imps.", "Ember Forge"),
        "winter_matriarch": ("Queen of the Frostbound Vault. Ice spikes under your feet, a freezing nova, and Frost Revenants.", "Frostbound Vault"),
        "briar_colossus": ("The giant at the heart of the Verdant Ruin. Roots, thorns and Thorn Stalkers, and the most health of any boss.",
                           "Verdant Ruin"),
    }
    bosses = []
    bosses.append(ENTRY("Boss fights", icon("hollowdeep:rift_core"),
        "Every rift ends with its theme's boss. All four fight in three phases, call in adds, and enrage if the fight takes too long.",
        [
            H2("Phases"),
            LIST([
                "<b>Phase 1</b> (full to 2/3 health): the boss uses its phase 1 abilities.",
                "<b>Phase 2</b> (below 2/3): it announces itself in chat, calls in a group of adds and unlocks more abilities. "
                "From now on it also calls more adds every so often (only while fewer than 12 are alive).",
                "<b>Phase 3</b> (below 1/3): another wave of adds, every ability, all cooldowns 30% shorter, Speed II, and from Tier III up Strength I.",
                f"<b>Last Stand</b> (Tier {ROMAN[js['ascendedTier'] - 1]} only, below 15%): the Ascended boss gets Speed III, raises one more ward and uses its abilities even faster.",
            ]),
            H2("Wards"),
            P("When a boss enters phase 2 (and phase 3, from Tier III up) it raises a ward: it becomes immune to damage and slowly heals, "
              "while 3 or 4 Ward Anchors float around the arena, linked to it by blue flames. Shatter every anchor to break the ward. "
              "The boss is then <b>staggered</b> for 8 seconds: nearly frozen, weakened, and unable to use abilities or call adds. Hit it hard."),
            H2("Arena hazards"),
            P("Each arena fights back with its theme's hazard, more often in later phases:"),
            TABLE([["Arena", "Hazard", "What to do"],
                   ["Sunken Crypt", "Graves split open under each player and one random spot, then burst with Wither.", "Step out of the soul circle."],
                   ["Ember Forge", "Floor vents glow, then erupt in columns of fire, one of them under a player.", "Move off the flaming rings."],
                   ["Frostbound Vault", "A blizzard sweeps the arena: everyone not within 4 blocks of one of the four campfire braziers is frozen and slowed.", "Run to a brazier when the blizzard warning shows."],
                   ["Verdant Ruin", "Spore pods burst where players stand and linger for 5 seconds, poisoning anyone inside.", "Leave the cloud and fight elsewhere."]]),
            H2("Ascended bosses"),
            P(f"Every Tier {ROMAN[js['ascendedTier'] - 1]} boss is <b>Ascended</b>: its name is shown in red, it has the Last Stand phase, and "
              f"beating it gives 100 extra Delver XP. It has a {pct(js['uniqueChance'])} chance to drop its own unique relic, always Epic or "
              "Legendary: " + ", ".join(f"[[{N.label[b]}]]: [[{name(r)}]]" for b, r in js["uniqueRelics"].items()) + "."),
            H2("Enrage"),
            P("If the fight lasts too long the boss enrages: chat says <i>ENRAGED!</i> and it gets Speed III and Strength."),
            H2("Boss tuning by tier"),
            TABLE([["", *[f"T{ROMAN[t - 1]}" for t in tiers]],
                   ["Ability damage", *[f"× {n(N.tune[t]['dmg'])}" for t in tiers]],
                   ["Adds", *[f"× {n(N.tune[t]['adds'])}" for t in tiers]],
                   ["Adds every (phase 2+)", *[secs(N.tune[t]['addEvery'] / 20) for t in tiers]],
                   ["Enrages after", *[secs(N.tune[t]['enrageAt']) for t in tiers]],
                   ["Enrage Strength", *[level(N.tune[t]['enrageAmp']) if N.tune[t]['enrageAmp'] >= 0 else "none" for t in tiers]],
                   ["Phase 3 Strength I", *["yes" if N.tune[t]['p3Strength'] else "no" for t in tiers]]]),
            H2("Ability damage by tier"),
            TABLE([["Ability", *[f"T{ROMAN[t - 1]}" for t in tiers]]] + [
                [ab_text[a][0], *[" / ".join(str(n(N.ability(t, b, p))) for b, p in js["abilities"][a]) for t in tiers]]
                for a in ab_text if a in js["abilities"]]),
            H2("The arena"),
            P("The boss can't leave its arena: if it follows you into the corridor it is pulled back to the middle in a puff of smoke. "
              "It rises when you first walk into the arena, so take a breath in the corridor first."),
            H2("Rewards"),
            P("See [[Loot]]: Rift Cores, Hollow Essence, the boss's own relic, and the vault. Ascended bosses can also drop a unique relic."),
        ], aliases=["Bosses", "Boss", "Enrage", "Wards", "Ward Anchors", "Ascended", "Arena hazards", "Last Stand"]))

    for k in BOSSES:
        spec = js["bosses"][k]
        summary, theme = boss_text[k]
        ab_rows = [["Ability", "From phase", "Every", *[f"T{ROMAN[t - 1]}" for t in tiers]]]
        for a in spec["abilities"]:
            dmg = js["abilities"].get(a["n"], [])
            ab_rows.append([ab_text[a["n"]][0], a["phase"], f"{n(a['cd'] / 20)} s",
                            *[" / ".join(str(n(N.ability(t, b, p))) for b, p in dmg) for t in tiers]])
        adds = ", ".join(f"[[{N.label[x]}]]" for x in spec["adds"])
        theme_relic = js["themes"][[tk for tk, tv in js["themes"].items() if tv["boss"] == k][0]]["relic"]
        blocks = [
            FIG(mob_big(k), N.label[k]),
            {"t": "table", "html": "<table class=\"info-table\">"
                f"<tr><th>Theme</th><td>[[Rift themes|{theme}]]</td></tr>"
                f"<tr><th>Base health</th><td>{hearts(N.ent[k]['hp'])}</td></tr>"
                f"<tr><th>Base melee damage</th><td>{n(N.ent[k]['attack'])}</td></tr>"
                f"<tr><th>Calls in</th><td>{adds}</td></tr>"
                f"<tr><th>Drops relic</th><td>{'[[' + name(theme_relic) + ']]' if theme_relic else 'none (vault relic only)'}</td></tr>"
                "<tr><th>Immune to</th><td>fire, full knockback resistance</td></tr></table>"},
            H2("Abilities"),
            TABLE(ab_rows),
            P("Damage shown at each tier. Cooldowns are 30% shorter in phase 3."),
        ]
        for a in spec["abilities"]:
            blocks += [H3(ab_text[a["n"]][0]), P(ab_text[a["n"]][2])]
        blocks += [H2("Phases"),
                   P(f"<b>Phase 2:</b> <i>{spec['p2']}</i> {spec['addCount'][1]} adds (times the tier's add multiplier)."),
                   P(f"<b>Phase 3:</b> <i>{spec['p3']}</i> {spec['addCount'][2]} more adds."),
                   H2("By tier"),
                   TABLE([["", *[f"T{ROMAN[t - 1]}" for t in tiers]],
                          ["Health", *[n(N.mob_hp(k, t)) for t in tiers]],
                          ["Melee damage", *[n(N.melee(k, t)) for t in tiers]],
                          ["Adds at phase 2 / 3", *[f"{jsround(spec['addCount'][1] * N.tune[t]['adds'])} / {jsround(spec['addCount'][2] * N.tune[t]['adds'])}" for t in tiers]],
                          ["Enrages after", *[secs(N.tune[t]['enrageAt']) for t in tiers]]])]
        if k == "tomb_regent":
            blocks.insert(4, P("The Tomb Regent has no ability in phase 1: it just fights. It is the only boss in Tier I rifts."))
        bosses.append(ENTRY(N.label[k], mob_icon(k), summary, blocks))
    cats.append({"title": "Bosses", "group": "Foes",
                 "blurb": "The four bosses, their abilities and phases, and how they scale.", "entries": bosses})

    # ============================================================ Relics
    rel = js["relicNames"]
    bon = js["bonuses"]
    rar = js["rarities"]
    unit = lambda b: bon[b]["unit"]
    bonus_rows = [["Bonus", "Does", *[r["n"] for r in rar]]]
    bon_desc = {
        "Power": "Extra damage to Hollowdeep mobs, as a % of each hit",
        "Haste": "Shorter relic cooldowns (capped at 60% in total)",
        "Leech": "Heals you for this % of the damage you deal",
        "Vigor": "Health Boost: 2 extra hearts per point (up to 7 points)",
        "Fortune": "Chance per kill of one extra Hollow Essence",
    }
    for b, v in bon.items():
        bonus_rows.append([b, bon_desc.get(b, v["desc"]),
                           *[f"{max(1, jsround(v['base'] * r['mult'] * 0.8))} to {max(1, jsround(v['base'] * r['mult'] * 1.25))}{unit(b)}" for r in rar]])
    relics = [ENTRY("Relics", icon("hollowdeep:blink_charm"),
        "Relics are Hollowdeep's gear. Each one rolls a rarity and random bonuses, and most also have a power you use.",
        [
            H2("Rarity"),
            TABLE([["Rarity", "Bonuses", "Bonus strength"]] + [[f"<span class=\"rar-{r['n'].lower()}\">{r['n']}</span>", r["count"], f"× {n(r['mult'])}"] for r in rar]),
            P("The rarity and bonuses are written on the relic's tooltip when it is rolled, and its name is coloured by rarity. "
              "Each bonus is different. The odds of each rarity depend on the [[Rift tiers|tier]] and the rift's [[Rift modifiers|modifiers]]."),
            H2("Bonuses"),
            TABLE(bonus_rows),
            H2("Carrying relics"),
            LIST([
                "Relics work from anywhere in your inventory; they don't need to be in your hand.",
                "If you carry two of the same relic, only the one with the higher total bonuses counts.",
                "Only your best <b>four</b> relics (by total bonuses) count at once: five from [[Delver ranks|Delver rank]] 3 and six from rank 7.",
                "Power only adds damage against Hollowdeep mobs; Leech works on anything you hit.",
                "Fortune uses the best Fortune in the party, not everyone's added together.",
            ]),
            H2("Getting relics"),
            P("Every vault has a relic chest with one random relic. The [[Forge Tyrant]], [[Winter Matriarch]] and [[Briar Colossus]] "
              "also drop their own theme's relic. Relics taken from the creative inventory or with <code>/give</code> keep their "
              "power but have no rarity and no bonuses: only relics from rifts are rolled. [[Chamber objectives|Reliquaries]] hold one "
              "more, and Ascended (Tier V) bosses can drop a unique relic."),
            H2("Improving relics"),
            P("Take relics to the [[Hollow Forge]] to ascend their rarity, temper them (up to five stars, +10% each) or reroll a bonus. "
              "Relics you don't want can be salvaged for Essence."),
            H2("All relics"),
            {"t": "icons", "rows": [[{"name": v, "icon": icon(k)} for k, v in rel.items()]]},
        ], aliases=["Relic", "Rarity", "Power", "Haste", "Leech", "Vigor", "Fortune", "Unique relics"])]

    cd = js["cooldowns"]
    relic_text = {
        "hollowdeep:blink_charm": ("Use it to teleport up to 9 blocks the way you're looking, through open air, water or cobwebs. "
                                   "You get 2 seconds of Slow Falling. If there's no room it doesn't use the cooldown.", "blink_charm"),
        "hollowdeep:vampiric_ring": ("Passive. While you carry it, every hit heals you for 20% of the damage you deal, "
                                     "on top of any Leech bonus. Each heal is at least ¼ heart and at most 3 hearts.", None),
        "hollowdeep:stormcaller_staff": ("Use it while looking at a monster within 22 blocks: lightning hits it for 8, then jumps to up "
                                         "to three more monsters within 7 blocks of each other for 6, 5 and 4 damage. Uses 1 durability per cast.",
                                         "stormcaller_staff"),
        "hollowdeep:aegis_pendant": ("Passive. When you don't already have Absorption, it gives you Absorption II (4 extra hearts) "
                                     "for 40 seconds, then recharges for 45 seconds. Haste shortens the recharge.", None),
        "hollowdeep:hollow_lantern": ("Use it to expose every monster within 14 blocks: Slowness II and Weakness I for 8 seconds. "
                                      "Bosses only get Slowness I for 3 seconds.", "hollow_lantern"),
        "hollowdeep:ember_brand": ("Use it to burst into flame: every monster within 5.5 blocks takes 6 fire damage and burns for 5 seconds. "
                                   "Uses 1 durability per use. Dropped by the [[Forge Tyrant]].", "ember_brand"),
        "hollowdeep:frost_charm": ("Use it to freeze everything within 6.5 blocks: 4 magic damage and Slowness IV for 3.5 seconds. "
                                   "Dropped by the [[Winter Matriarch]].", "frost_charm"),
        "hollowdeep:briar_totem": ("Use it to heal every player within 10 blocks (you too) by 3 hearts and give Regeneration II for "
                                   "5 seconds. Dropped by the [[Briar Colossus]].", "briar_totem"),
        "hollowdeep:regent_crown": ("Use it to rend the souls of every monster within 8 blocks: each takes 6 magic damage and you heal "
                                    "1 heart per soul (up to 5 hearts). Unique: dropped only by the Ascended [[Tomb Regent]].", "regent_crown"),
        "hollowdeep:tyrant_hammer": ("Use it to slam the ground: every monster within 6 blocks takes 10 damage, burns for 3 seconds and "
                                     "is thrown into the air (bosses aren't). Uses 1 durability. Unique: dropped only by the Ascended [[Forge Tyrant]].",
                                     "tyrant_hammer"),
        "hollowdeep:winter_heart": ("Use it to encase every monster within 8 blocks in ice: 4 damage, Slowness VII and Weakness II for 4 "
                                    "seconds (bosses get Slowness II for 2.5 seconds). Passive: anything that hits you is slowed. "
                                    "Unique: dropped only by the Ascended [[Winter Matriarch]].", "winter_heart"),
        "hollowdeep:colossus_seed": ("Use it to plant a grove where you stand for 8 seconds: every second, players within 6 blocks heal "
                                     "1 heart and monsters inside are slowed and take 1.5 damage. Unique: dropped only by the Ascended "
                                     "[[Briar Colossus]].", "colossus_seed"),
    }
    for k, v in rel.items():
        text, cdk = relic_text[k]
        it = d["items"][k]
        info = [["Type", "Passive" if not cdk else "Use (right-click / tap)"]]
        if cdk:
            info.append(["Cooldown", f"{n(cd[cdk])} s"])
        if it.get("durability"):
            info.append(["Durability", it["durability"]])
        info.append(["Stacks", "No"])
        info_html = "<table class=\"info-table\">" + "".join(f"<tr><th>{a}</th><td>{b}</td></tr>" for a, b in info) + "</table>"
        e = ENTRY(v, icon(k), text.split(". ")[0].rstrip(".") + ".",
                  [{"t": "table", "html": info_html}, H2("Power"), P(text),
                   P("Like every relic it also rolls a rarity and bonuses: see [[Relics]].")])
        e["blocks"][0] = P("A [[Relics|relic]] from Hollowdeep rifts.")  # the summary repeats the power text below
        relics.append(e)
    cats.append({"title": "Relics", "group": "Loot and gear",
                 "blurb": "Rolled gear with rarities, bonuses and powers.", "entries": relics})

    # ============================================================ Items
    its = []
    keys = ["hollowdeep:rift_key", "hollowdeep:rift_key_2", "hollowdeep:rift_key_3", "hollowdeep:rift_key_4", "hollowdeep:rift_key_5"]
    blocks = [H2("Recipes")]
    for k in keys:
        g = grid(k)
        if g:
            blocks.append(g)
    blocks += [H2("Using a key"),
               P(f"Use the key to open a rift of its tier. Everyone within {L['joinRadius']} blocks who isn't already in a rift comes with you. "
                 "If the rift can't form (all slots busy, no free ticking area, or its chunks don't load) you get the key back."),
               P("Keys stack to 16. Each upgrade uses up the key below it.")]
    its.append(ENTRY("Rift Keys", icon("hollowdeep:rift_key"),
        "Keys open rifts. Craft the first one from vanilla items, then upgrade it tier by tier with Hollow Essence and Rift Cores.",
        blocks, aliases=["Rift Key", "Keys", "Rift Key II", "Rift Key III", "Rift Key IV", "Rift Key V"]))
    its.append(ENTRY("Hollow Essence", icon("hollowdeep:hollow_essence"),
        "The common currency of the rifts. It drops from mobs and fills caches and vaults, and goes into keys and the Rift Ledger.",
        [H2("Getting it"),
         P("Most mobs have a 55% chance to drop one, elites drop 2 to 4, Mimics 3 to 6 and bosses 10 + 4 × tier. Caches and vault "
           "chests hold more (see [[Loot]]). The [[Relics|Fortune]] bonus gives a chance of one extra per kill."),
         H2("Uses"),
         LIST(["[[Rift Keys|Rift Key II]] (4) and [[Rift Keys|Rift Key III]] (4)", "[[Rift Ledger]] (2)", "[[Hollow Forge]] (4)",
               "Every [[Hollow Forge]] upgrade"])]))
    its.append(ENTRY("Rift Core", icon("hollowdeep:rift_core"),
        "The heart of a beaten boss. Rift Cores are what you need to upgrade keys past Tier II.",
        [H2("Getting it"),
         P("Every boss drops 1 + tier Rift Cores, and the vault relic chest often has more (see [[Loot]])."),
         H2("Uses"),
         LIST(["[[Rift Keys|Rift Key III]] (2)", "[[Rift Keys|Rift Key IV]] (3)", "[[Rift Keys|Rift Key V]] (4)", "[[Hollow Forge]] (1)",
               "Ascending relics, and tempering past three stars, at the [[Hollow Forge]]"])]))
    its.append(ENTRY("Soul Tether", icon(tether),
        "You get one when you respawn after dying in a rift. Use it to return to the rift's entrance.",
        [P("It only works while the rift you died in is still open and you are still one of its members. If the rift has ended it "
           "frays into nothing when you use it. Using it while you're already inside does nothing."),
         P("You land at the rift's entrance, not where you died. Your dropped items are where you fell."),
         P("See [[Dying and leaving]].")]))
    led = grid("hollowdeep:rift_ledger")
    its.append(ENTRY("Rift Ledger", icon("hollowdeep:rift_ledger"),
        "A book that keeps your rift record. Use it to see your stats and the server's top delvers.",
        [led,
         H2("Your stats"),
         P("Your [[Delver ranks|Delver rank]], XP and perks, then rifts opened, rifts cleared, kills, deaths, and your fastest clear time at each tier."),
         H2("Top Delvers"),
         P("The five players with the most clears (kills break ties), and the fastest clear at each tier. Offline players are included."),
         P("Clears are also kept on the <code>hd_clears</code> scoreboard. <code>/scriptevent hollowdeep:board</code> shows it on the sidebar.")]))
    fg = js["forge"]
    rar_n = [r["n"] for r in js["rarities"]]
    cost = lambda c: f"{c['ess']} Essence" + (f" + {c['core']} Core{'s' if c['core'] > 1 else ''}" if c["core"] else "")
    its.append(ENTRY("Hollow Forge", icon("hollowdeep:hollow_forge"),
        "A portable forge. Use it to spend Essence and Rift Cores improving your relics, or to break unwanted relics down.",
        [grid("hollowdeep:hollow_forge"),
         H2("Using it"),
         P("Use the forge (right-click / tap) anywhere. It lists every rolled relic in your inventory; pick one to see what you can do with it. "
           "Greyed-out options show what you're missing."),
         TABLE([["Action", "What it does"],
                ["Ascend", "Raises the rarity one step. Every bonus scales up to the new rarity and the relic gains a new bonus."],
                ["Temper", "Adds a star (up to five). Each star raises every bonus by 10% (at least +1). Vigor grows on the 3rd and 5th star."],
                ["Reroll", "Pick one bonus: it's replaced by a bonus the relic doesn't have, rolled at its rarity and stars."],
                ["Salvage", "Destroys the relic for Essence (and Cores for Epic and Legendary)."]]),
         H2("Costs"),
         TABLE([["Rarity", "Ascend", "Reroll", "Salvage gives"]] + [
                [rar_n[r], cost(fg["ascend"][r]) if r < 3 else "max", cost(fg["reroll"][r]), cost(fg["salvage"][r])] for r in range(4)]),
         TABLE([["Temper to", *[f"{'★' * (t + 1)}" for t in range(5)]]] + [
                [rar_n[r], *[cost(fg["temper"][r][t]) for t in range(5)]] for r in range(4)]),
         P(f"Salvage gives {fg['salvagePerStar']} more Essence per star, and unique relics give 3 more Cores. "
           "[[Delver ranks|Delver rank]] 2 takes 10% off every Essence cost, and rank 6 takes 20%.")],
        aliases=["Forge", "Ascend", "Temper", "Reroll", "Salvage"]))
    rk = js["ranks"]
    its.append(ENTRY("Delver ranks", icon("hollowdeep:rift_ledger"),
        "Every kill and clear earns Delver XP. Ten ranks, each with a permanent perk.",
        [H2("Earning XP"),
         TABLE([["Deed", "XP"], ["Kill a mob", 1], ["Kill an elite", 5], ["Kill a Mimic", 8], ["Kill a Champion", 15],
                ["Clear a rift (everyone alive at the end)", "60 × tier"], ["Beat an Ascended boss", "100 more"]]),
         H2("Ranks"),
         TABLE([["Rank", "Name", "XP", "Perk"]] + [[i + 1, r["name"], f"{r['xp']:,}", r["perk"] or "-"] for i, r in enumerate(rk)]),
         P("Perks add up: a rank keeps every perk below it (the forge discount and relic slots take the best one). "
           "Your rank, XP and perks are in the [[Rift Ledger]]. Ranking up shows a title and plays a sound.")],
        aliases=["Delver rank", "Ranks", "Delver XP", "XP"]))
    cats.append({"title": "Items", "group": "Loot and gear",
                 "blurb": "Keys, materials, the Hollow Forge, Delver ranks, the Soul Tether and the Rift Ledger.", "entries": its})

    # ============================================================ Commands
    cmds = [ENTRY("Commands", icon("minecraft:command_block"),
        "Hollowdeep's commands all use /scriptevent, so they need cheats on (or a command block).",
        [
            H2("Admin and testing"),
            TABLE([["Command", "What it does"],
                   ["<code>/scriptevent hollowdeep:open 3</code>", "Opens a rift of tier 1 to 5 for you, without a key."],
                   ["<code>/scriptevent hollowdeep:key 3</code>", "Gives you a Rift Key of tier 1 to 5."],
                   ["<code>/scriptevent hollowdeep:end</code>", "Closes every open rift and sends everyone home."],
                   ["<code>/scriptevent hollowdeep:stats</code>", "Shows your [[Rift Ledger]] stats."],
                   ["<code>/scriptevent hollowdeep:top</code>", "Shows the Top Delvers."],
                   ["<code>/scriptevent hollowdeep:board</code>", "Shows Rift Clears on the sidebar."],
                   ["<code>/scriptevent hollowdeep:forge</code>", "Opens the [[Hollow Forge]] without the item."],
                   ["<code>/scriptevent hollowdeep:relic 3</code>", "Gives you a random relic rolled at tier 1 to 5."],
                   ["<code>/scriptevent hollowdeep:xp 500</code>", "Gives you Delver XP (see [[Delver ranks]])."]]),
            P("There's no command to spawn a [[Rift Gates|Rift Gate]]; use <code>hollowdeep:open</code> to test rifts."),
            H2("For other add-ons"),
            P("Other add-ons can add their items to vault chests. Registrations are saved in the world."),
            TABLE([["Command", "What it does"],
                   ["<code>/scriptevent hollowdeep:register_drop &lt;item&gt; &lt;chance%&gt; &lt;min&gt; &lt;max&gt; &lt;minTier&gt;</code>",
                    "Every vault chest in a rift of at least that tier has that % chance to get min to max of the item. Registering the same item again replaces it."],
                   ["<code>/scriptevent hollowdeep:unregister_drop &lt;item&gt;</code>", "Removes it."],
                   ["<code>/scriptevent hollowdeep:drops</code>", "Lists what's registered."]]),
            P("Example: <code>/scriptevent hollowdeep:register_drop myaddon:star_shard 25 1 3 2</code>"),
            P("Hollowdeep also announces what happens, as <code>/scriptevent hollowdeep:event</code> with a JSON message, so other add-ons can react:"),
            TABLE([["type", "Sent when", "Data"],
                   ["<code>rift_open</code>", "A rift opens", "tier, theme, mods, players"],
                   ["<code>boss_kill</code>", "A boss dies", "tier, theme, mods, players, ticks (clear time)"],
                   ["<code>elite_kill</code>", "A player kills an elite", "player, affix, tier"]]),
        ], aliases=["Admin commands", "scriptevent"])]
    cats.append({"title": "Commands", "group": "Reference",
                 "blurb": "Admin and testing commands, and hooks for other add-ons.", "entries": cmds})
    return cats
