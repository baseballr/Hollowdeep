// Reads the numbers the wiki needs out of the add-on's scripts and prints them as JSON.
// usage: node tools/jsdata.mjs <path to Hollowdeep_BP/scripts>
//
// config.js has no imports, so it is imported as a module. Other files import @minecraft/server,
// so the object literals the wiki needs are cut out of their source and evaluated on their own.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const dir = process.argv[2];
const src = (f) => fs.readFileSync(path.join(dir, f), "utf8");

/** Text of the object/array literal assigned to `const NAME`, matched by brackets. */
function literal(file, name) {
  const text = src(file);
  const m = new RegExp(`const ${name}\\s*=\\s*`).exec(text);
  if (!m) throw new Error(`${name} not found in ${file}`);
  let i = m.index + m[0].length;
  const open = text[i], close = open === "{" ? "}" : "]";
  let depth = 0, str = null;
  for (let j = i; j < text.length; j++) {
    const c = text[j];
    if (str) { if (c === "\\") j++; else if (c === str) str = null; continue; }
    if (c === '"' || c === "'" || c === "`") str = c;
    else if (c === open) depth++;
    else if (c === close && --depth === 0) return text.slice(i, j + 1);
  }
  throw new Error(`unbalanced ${name} in ${file}`);
}
const value = (file, name) => Function(`"use strict"; return (${literal(file, name)});`)();

/** Numbers from a regex, or fail loudly so a changed script can't silently give the wiki wrong numbers. */
function num(file, re) {
  const m = re.exec(src(file));
  if (!m) throw new Error(`${re} not found in ${file}`);
  return m.slice(1).map(Number);
}

const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "hd-")), "config.mjs");
fs.copyFileSync(path.join(dir, "config.js"), tmp);
const cfg = await import(pathToFileURL(tmp).href);

// Boss ability damage: D(rift, base, perTier) inside each ability of bosses.js.
const abilities = {};
const abilityText = src("bosses.js").split("const ABILITY = {")[1];
for (const part of abilityText.split(/\n  (?=\w+\(rift, boss)/).slice(1)) {
  const name = /^(\w+)/.exec(part)[1];
  abilities[name] = [...part.matchAll(/D\(rift, (\d+(?:\.\d+)?), (\d+(?:\.\d+)?)\)/g)].map((m) => [Number(m[1]), Number(m[2])]);
}

// Relic cooldowns: ready(p, "blink_charm", 20 * 6) or ready(p, "stormcaller_staff", 40).
const cooldowns = {};
for (const m of src("relics.js").matchAll(/ready\(p, "(\w+)", ([\d *]+)\)/g)) cooldowns[m[1]] = Function(`return (${m[2]})`)() / 20;

const out = {
  version: (/VERSION = "([\d.]+)"/.exec(src("version.js")) ?? [])[1] ?? null,
  tiers: cfg.TIERS,
  bossTune: cfg.BOSS_TUNE,
  rarityWeights: cfg.RARITY_WEIGHTS,
  themes: cfg.THEMES,
  pools: cfg.POOLS,
  affixes: cfg.AFFIXES,
  mobLabel: cfg.MOB_LABEL,
  limits: {
    maxRifts: cfg.MAX_RIFTS, emptyGrace: cfg.EMPTY_GRACE / 20, lootWindow: cfg.LOOT_WINDOW / 20,
    joinRadius: cfg.JOIN_RADIUS, origin: cfg.ORIGIN,
  },
  mods: value("modifiers.js", "MODS"),
  bonuses: value("rolls.js", "BONUSES"),
  rarities: value("rolls.js", "RARITIES"),
  relicNames: value("rolls.js", "RELIC_NAMES"),
  bosses: value("bosses.js", "BOSSES"),
  abilities,
  cooldowns,
  curses: value("mobs.js", "CURSES"),
  gates: {
    max: num("gates.js", /MAX_GATES = (\d+)/)[0],
    chance: num("gates.js", /SPAWN_CHANCE = ([\d.]+)/)[0],
    lifetimeMin: num("gates.js", /GATE_LIFETIME_MS = (\d+) \* 60 \* 1000/)[0],
    distances: num("gates.js", /d < (\d+) \? 1 : d < (\d+) \? 2 : d < (\d+) \? 3 : d < (\d+) \? 4 : 5/),
    range: num("gates.js", /r = rand\((\d+), (\d+)\)/),
    height: num("gates.js", /p\.location\.y < (\d+) \|\| p\.location\.y > (\d+)/),
  },
};
process.stdout.write(JSON.stringify(out));
