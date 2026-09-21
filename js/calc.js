// calc.js — core Elden Ring stat calculations: equip load, poise, negation,
// HP/FP/stamina, and status-screen totals from equipped gear.
// HP/FP/Stamina formulas are the wiki's CalcCorrectGraph-style piecewise
// curves (always floored). Equip load uses the in-game Endurance table.
// Armor absorption is additive (equipment screen); talisman absorption and
// "damage taken" penalties are extra multiplicative layers.

const DAMAGE_TYPES = ["phy", "strike", "slash", "pierce", "magic", "fire", "lightning", "holy"];
const RESIST_TYPES = ["immunity", "robustness", "focus", "vitality", "poise"];
const PHYSICAL_TYPES = ["phy", "strike", "slash", "pierce"];
const ELEMENTAL_TYPES = ["magic", "fire", "lightning", "holy"];

const STAT_KEYS = ["vig", "mind", "end", "str", "dex", "int", "fai", "arc"];
const STAT_LABELS = { vig: "Vigor", mind: "Mind", end: "Endurance", str: "Strength", dex: "Dexterity", int: "Intelligence", fai: "Faith", arc: "Arcane" };

const STAT_NAME_TO_KEY = {
  vigor: "vig",
  mind: "mind",
  endurance: "end",
  strength: "str",
  dexterity: "dex",
  dexerity: "dex",
  intelligence: "int",
  faith: "fai",
  arcane: "arc",
};

const STAT_NAME_RE = "vigor|mind|endurance|strength|dexterity|dexerity|intelligence|faith|arcane";
const RESIST_NAME_RE = "immunity|robustness|focus|vitality";

function emptyAttributeBonuses() {
  const out = {};
  for (const key of STAT_KEYS) out[key] = 0;
  return out;
}

function emptyResistBonuses() {
  return { immunity: 0, robustness: 0, focus: 0, vitality: 0 };
}

function emptyResourceBonuses() {
  return { hp: 0, fp: 0, stamina: 0, equipLoad: 0 };
}

function emptyRemainingMul() {
  const out = {};
  for (const dt of DAMAGE_TYPES) out[dt] = 1;
  return out;
}

function copyStats(stats) {
  const out = {};
  for (const key of STAT_KEYS) {
    const value = stats && stats[key];
    out[key] = Number.isFinite(value) ? value : 0;
  }
  return out;
}

function clampAttr(n) {
  return Math.max(1, Math.min(99, Math.round(n)));
}

function namesFromPhrase(phrase) {
  const names = String(phrase).match(new RegExp(STAT_NAME_RE, "gi")) || [];
  return names.map((name) => STAT_NAME_TO_KEY[name.toLowerCase()]).filter(Boolean);
}

function resistNamesFromPhrase(phrase) {
  const names = String(phrase).match(new RegExp(RESIST_NAME_RE, "gi")) || [];
  return names.map((name) => name.toLowerCase());
}

/**
 * Parses attribute bonuses out of Great Rune / talisman / armor effect text.
 * Data-driven so catalog regenerations keep working without a hardcoded list.
 */
function parseAttributeBonuses(effectText) {
  const out = emptyAttributeBonuses();
  if (!effectText) return out;
  const text = String(effectText);

  const all = text.match(/all attributes by\s*\+?(\d+)/i);
  if (all) {
    const n = parseInt(all[1], 10);
    for (const key of STAT_KEYS) out[key] += n;
  }

  const clauseRe = new RegExp(`(?:raises|increases|boosts)\\s+([^.;]+?)\\s+by\\s+\\+?(\\d+)(?!%)`, "gi");
  let match;
  while ((match = clauseRe.exec(text))) {
    const phrase = match[1];
    if (/all attributes/i.test(phrase)) continue;
    const leftover = phrase
      .replace(new RegExp(STAT_NAME_RE, "gi"), "")
      .replace(/and|,/gi, "")
      .replace(/\s+/g, "");
    if (leftover) continue;
    const n = parseInt(match[2], 10);
    for (const key of namesFromPhrase(phrase)) out[key] += n;
  }

  const chained = new RegExp(`by\\s+\\+?\\d+\\s+and\\s+(${STAT_NAME_RE})\\s+by\\s+\\+?(\\d+)(?!%)`, "gi");
  while ((match = chained.exec(text))) {
    const key = STAT_NAME_TO_KEY[match[1].toLowerCase()];
    if (key) out[key] += parseInt(match[2], 10);
  }

  const plusStatRe = new RegExp(`\\+(\\d+)\\s+(?:to\\s+)?((?:${STAT_NAME_RE})(?:\\s*,\\s*(?:and\\s+)?(?:${STAT_NAME_RE}))*)`, "gi");
  while ((match = plusStatRe.exec(text))) {
    const n = parseInt(match[1], 10);
    for (const key of namesFromPhrase(match[2])) out[key] += n;
  }

  const statPlusRe = new RegExp(`\\b(${STAT_NAME_RE})\\s*\\+(\\d+)`, "gi");
  while ((match = statPlusRe.exec(text))) {
    const key = STAT_NAME_TO_KEY[match[1].toLowerCase()];
    if (key) out[key] += parseInt(match[2], 10);
  }
  return out;
}

function addAttributeBonuses(into, extra) {
  if (!extra) return into;
  for (const key of STAT_KEYS) into[key] += extra[key] || 0;
  return into;
}

function itemAttributeBonuses(items) {
  const out = emptyAttributeBonuses();
  for (const item of items || []) {
    addAttributeBonuses(out, parseAttributeBonuses(item && item.effect));
  }
  return out;
}

function talismanAttributeBonuses(talismans) {
  return itemAttributeBonuses(talismans);
}

function greatRuneAttributeBonuses(rune, active) {
  if (!active || !rune) return emptyAttributeBonuses();
  if (rune.statBonus) {
    const out = emptyAttributeBonuses();
    for (const key of STAT_KEYS) out[key] = rune.statBonus;
    return out;
  }
  return parseAttributeBonuses(rune.effect);
}

function applyAttributeBonuses(stats, bonuses) {
  const out = copyStats(stats);
  if (!bonuses) return out;
  for (const key of STAT_KEYS) {
    const bonus = bonuses[key] || 0;
    if (!bonus) continue;
    out[key] = Math.max(1, Math.min(99, out[key] + bonus));
  }
  return out;
}

function applyEffectiveStats(stats, items, rune, runeActive) {
  const bonuses = itemAttributeBonuses(items);
  addAttributeBonuses(bonuses, greatRuneAttributeBonuses(rune, runeActive));
  return applyAttributeBonuses(stats, bonuses);
}

function applyGreatRuneStats(stats, rune, active) {
  return applyEffectiveStats(stats, [], rune, active);
}

function resourceKey(name) {
  const n = String(name).toLowerCase();
  if (n === "hp") return "hp";
  if (n === "fp") return "fp";
  if (n === "stamina") return "stamina";
  if (n === "equip load") return "equipLoad";
  return null;
}

/**
 * Percentage HP / FP / Stamina / Equip Load modifiers from effect text.
 * Positive = raise max; negative = reduce max. Flask restoration is ignored.
 */
function parseResourceBonuses(effectText) {
  const out = emptyResourceBonuses();
  if (!effectText) return out;
  const text = String(effectText);

  const apply = (name, pct, negative) => {
    const key = resourceKey(name);
    const n = parseFloat(pct) / 100;
    if (!key || !Number.isFinite(n)) return;
    out[key] += negative ? -n : n;
  };

  const trio = text.match(/(?:raises|increases|boosts)\s+maximum\s+HP,\s*FP\s+and\s+Stamina\s+by\s+([\d.]+)%/i);
  if (trio) {
    apply("HP", trio[1], false);
    apply("FP", trio[1], false);
    apply("Stamina", trio[1], false);
  }

  const parenRe = /(HP|FP|Stamina|Equip Load)\s*\(([\d.]+)%\)/gi;
  let match;
  while ((match = parenRe.exec(text))) apply(match[1], match[2], false);

  const isReduced = /max(?:imum)?\s+(HP|FP|Stamina)\s+is reduced\s+by\s+([\d.]+)%/gi;
  while ((match = isReduced.exec(text))) apply(match[1], match[2], true);

  const reduces = /reduces\s+max(?:imum)?\s+(HP|FP|Stamina)(?:\s+and\s+max(?:imum)?\s+(HP|FP|Stamina))?\s+by\s+([\d.]+)%/gi;
  while ((match = reduces.exec(text))) {
    apply(match[1], match[3], true);
    if (match[2]) apply(match[2], match[3], true);
  }

  const raises = /(?:boosts|raises|increases)\s+max(?:imum)?\s+(HP|FP|Stamina|Equip Load)\s+by\s+([\d.]+)%/gi;
  while ((match = raises.exec(text))) apply(match[1], match[2], false);

  if (!trio) {
    const trailing = /(?:,|and)\s+(HP|FP|Stamina|Equip Load)\s+by\s+([\d.]+)%/gi;
    while ((match = trailing.exec(text))) apply(match[1], match[2], false);
  }

  return out;
}

function talismanEquipLoadBonus(effectText) {
  return parseResourceBonuses(effectText).equipLoad;
}

function talismanPoiseBonus(effectText) {
  if (!effectText) return 0;
  const m = String(effectText).match(/(?:Raises|Increases|Boosts) Poise by\s*([\d.]+)%(?!\s+after)/i);
  if (m) return parseFloat(m[1]) / 100;
  return 0;
}

function parseResistanceBonuses(effectText) {
  const out = emptyResistBonuses();
  if (!effectText) return out;
  const text = String(effectText);

  const raiseRe = new RegExp(`(?:vastly\\s+)?(?:raises|increases|boosts)\\s+((?:${RESIST_NAME_RE})(?:\\s*,\\s*(?:and\\s+)?(?:${RESIST_NAME_RE}))*)\\s+by\\s+(\\d+)`, "gi");
  let match;
  while ((match = raiseRe.exec(text))) {
    const n = parseInt(match[2], 10);
    for (const key of resistNamesFromPhrase(match[1])) out[key] += n;
  }

  const lowerRe = /(?:lowers|reduces)\s+(immunity|robustness|focus|vitality)\s+by\s+-?(\d+)/gi;
  while ((match = lowerRe.exec(text))) {
    out[match[1].toLowerCase()] -= parseInt(match[2], 10);
  }
  return out;
}

function parseDiscoveryBonus(effectText) {
  if (!effectText) return 0;
  const m = String(effectText).match(/item discovery by\s+(\d+)/i);
  return m ? parseInt(m[1], 10) : 0;
}

function parseMemorySlotBonus(effectText) {
  if (!effectText) return 0;
  const m = String(effectText).match(/memory slots by\s+(\d+)/i);
  return m ? parseInt(m[1], 10) : 0;
}

function isConditionalDefenseText(text) {
  return /when HP|while guarding|when at heavy load|when overloaded|after using a flask/i.test(text);
}

function scaleTypes(types, remaining, factor) {
  for (const dt of types) remaining[dt] *= factor;
}

/**
 * Extra damage-taken / negation layers as remaining-damage multipliers.
 * Conditional effects (low HP, guarding, heavy load, flask poise) are skipped.
 */
function parseDamageRemaining(effectText) {
  const remaining = emptyRemainingMul();
  if (!effectText || isConditionalDefenseText(effectText)) return remaining;
  const text = String(effectText);

  const takenAll = text.match(/increases(?:\s+all)?\s+damage taken by\s+([\d.]+)%/i);
  if (takenAll) scaleTypes(DAMAGE_TYPES, remaining, 1 + parseFloat(takenAll[1]) / 100);

  const takenPhy = text.match(/increases\s+Physical Damage taken by\s+([\d.]+)%/i);
  if (takenPhy) scaleTypes(PHYSICAL_TYPES, remaining, 1 + parseFloat(takenPhy[1]) / 100);

  const reducePhy = text.match(/(?:reduces\s+Physical Damage taken|boosts\s+Physical(?:\s+Damage)?\s+negation) by\s+([\d.]+)%/i);
  if (reducePhy) scaleTypes(PHYSICAL_TYPES, remaining, 1 - parseFloat(reducePhy[1]) / 100);

  const elemTaken = [
    ["magic", /(?:reduces\s+Magic Damage taken|boosts\s+magic damage negation) by\s+([\d.]+)%/i],
    ["fire", /(?:reduces\s+Fire Damage taken|boosts\s+fire damage negation) by\s+([\d.]+)%/i],
    ["lightning", /(?:reduces\s+Lightning Damage taken|boosts\s+lightning damage negation) by\s+([\d.]+)%/i],
    ["holy", /(?:reduces\s+Holy Damage taken|boosts\s+holy damage negation) by\s+([\d.]+)%/i],
  ];
  for (const [key, re] of elemTaken) {
    const m = text.match(re);
    if (m) remaining[key] *= 1 - parseFloat(m[1]) / 100;
  }

  const nonPhys = text.match(/boosts\s+non-physical damage negation by\s+([\d.]+)%/i);
  if (nonPhys) scaleTypes(ELEMENTAL_TYPES, remaining, 1 - parseFloat(nonPhys[1]) / 100);

  return remaining;
}

function combineItemEffects(items) {
  const resources = emptyResourceBonuses();
  const resist = emptyResistBonuses();
  const remaining = emptyRemainingMul();
  let discovery = 0;
  let memorySlots = 0;
  let poise = 0;
  for (const item of items || []) {
    const effect = item && item.effect;
    const res = parseResourceBonuses(effect);
    resources.hp += res.hp;
    resources.fp += res.fp;
    resources.stamina += res.stamina;
    resources.equipLoad += res.equipLoad;
    const rb = parseResistanceBonuses(effect);
    resist.immunity += rb.immunity;
    resist.robustness += rb.robustness;
    resist.focus += rb.focus;
    resist.vitality += rb.vitality;
    const rem = parseDamageRemaining(effect);
    for (const dt of DAMAGE_TYPES) remaining[dt] *= rem[dt];
    discovery += parseDiscoveryBonus(effect);
    memorySlots += parseMemorySlotBonus(effect);
    poise += talismanPoiseBonus(effect);
  }
  return { resources, resist, remaining, discovery, memorySlots, poise };
}

function hpFromVigor(vigor) {
  const v = clampAttr(vigor);
  if (v <= 25) return Math.floor(300 + 500 * ((v - 1) / 24) ** 1.5);
  if (v <= 40) return Math.floor(800 + 650 * ((v - 25) / 15) ** 1.1);
  if (v <= 60) return Math.floor(1450 + 450 * (1 - (1 - (v - 40) / 20) ** 1.2));
  return Math.floor(1900 + 200 * (1 - (1 - (v - 60) / 39) ** 1.2));
}

function fpFromMind(mind) {
  const m = clampAttr(mind);
  if (m <= 15) return Math.floor(50 + 45 * ((m - 1) / 14));
  if (m <= 35) return Math.floor(95 + 105 * ((m - 15) / 20));
  if (m <= 60) return Math.floor(200 + 150 * (1 - (1 - (m - 35) / 25) ** 1.2));
  return Math.floor(350 + 100 * ((m - 60) / 39));
}

function staminaFromEndurance(endurance) {
  const e = clampAttr(endurance);
  if (e <= 15) return Math.floor(80 + 25 * ((e - 1) / 14));
  if (e <= 30) return Math.floor(105 + 25 * ((e - 15) / 15));
  if (e <= 50) return Math.floor(130 + 25 * ((e - 30) / 20));
  return Math.floor(155 + 15 * ((e - 50) / 49));
}

function resistanceFromLevel(level) {
  const L = Math.max(1, level || 1);
  let r = 75;
  const a = Math.min(L, 71);
  r += 0.2 * (a - 1);
  if (L > 71) r += 1.0 * (Math.min(L, 111) - 71);
  if (L > 111) r += 0.3 * (Math.min(L, 161) - 111);
  if (L > 161) r += 0.03 * (L - 161);
  return r;
}

function resistanceFromAttribute(stat, startsAt) {
  const s = clampAttr(stat);
  if (startsAt === 1) {
    let r = 1 * (Math.min(s, 15) - 1);
    if (s > 15) r += 0.6 * (Math.min(s, 40) - 15);
    if (s > 40) r += 0.5 * (Math.min(s, 60) - 40);
    if (s > 60) r += 0.25 * (Math.min(s, 99) - 60);
    return r;
  }
  if (s < 31) return 0;
  let r = 3 * (Math.min(s, 40) - 30);
  if (s > 40) r += 0.5 * (Math.min(s, 60) - 40);
  if (s > 60) r += 0.25 * (Math.min(s, 99) - 60);
  return r;
}

function baseResistances(level, stats) {
  const lvl = resistanceFromLevel(level);
  return {
    immunity: lvl + resistanceFromAttribute(stats.vig, 31),
    robustness: lvl + resistanceFromAttribute(stats.end, 31),
    focus: lvl + resistanceFromAttribute(stats.mind, 31),
    vitality: lvl + resistanceFromAttribute(stats.arc, 1),
  };
}

function combineAbsorption(armorNeg, remainingMul) {
  const out = {};
  for (const dt of DAMAGE_TYPES) {
    const armorRemain = 1 - ((armorNeg && armorNeg[dt]) || 0) / 100;
    const finalRemain = Math.max(0, armorRemain * ((remainingMul && remainingMul[dt]) || 1));
    out[dt] = (1 - finalRemain) * 100;
  }
  return out;
}

function baseEquipLoadForEndurance(endurance, equipLoadTable) {
  const end = clampAttr(endurance);
  return equipLoadTable[String(end)] ?? equipLoadTable["99"];
}

function computeMaxEquipLoad(endurance, items, equipLoadTable) {
  const base = baseEquipLoadForEndurance(endurance, equipLoadTable);
  let bonus = 0;
  for (const item of items || []) {
    bonus += parseResourceBonuses(item && item.effect).equipLoad;
  }
  return base * (1 + bonus);
}

function totalWeight(items) {
  return (items || []).reduce((sum, it) => sum + (it && it.weight ? it.weight : 0), 0);
}

function loadClass(ratio) {
  if (ratio >= 1.0) return "overloaded";
  if (ratio >= 0.70) return "heavy";
  if (ratio >= 0.30) return "medium";
  return "light";
}

const LOAD_CLASS_RANK = { light: 0, medium: 1, heavy: 2, overloaded: 3 };

function allowedLoadClass(maxRatio) {
  return loadClass(maxRatio);
}

function isHeavierLoadClass(actual, allowed) {
  return (LOAD_CLASS_RANK[actual] || 0) > (LOAD_CLASS_RANK[allowed] || 0);
}

function computeTotalPoise(armorPieces, equippedTalismans) {
  let base = 0;
  for (const a of armorPieces || []) {
    base += (a.resistance && a.resistance.poise) || 0;
  }
  let bonus = 0;
  for (const t of equippedTalismans || []) {
    bonus += talismanPoiseBonus(t.effect);
  }
  return base * (1 + bonus);
}

function computeNegation(armorPieces) {
  const totals = {};
  for (const dt of DAMAGE_TYPES) totals[dt] = 0;
  for (const a of armorPieces || []) {
    if (!a.negation) continue;
    for (const dt of DAMAGE_TYPES) totals[dt] += a.negation[dt] || 0;
  }
  return totals;
}

function computeResistances(armorPieces) {
  const totals = { immunity: 0, robustness: 0, focus: 0, vitality: 0 };
  for (const a of armorPieces || []) {
    if (!a.resistance) continue;
    totals.immunity += a.resistance.immunity || 0;
    totals.robustness += a.resistance.robustness || 0;
    totals.focus += a.resistance.focus || 0;
    totals.vitality += a.resistance.vitality || 0;
  }
  return totals;
}

/**
 * Full status-screen totals from invested stats plus equipped gear / rune.
 * Live Attack Rating is not computed (needs unpublished reinforce graphs).
 */
function computeCharacterStatus(opts) {
  const invested = copyStats(opts && opts.invested);
  const armor = (opts && opts.armor) || [];
  const talismans = (opts && opts.talismans) || [];
  const rune = opts && opts.rune;
  const runeActive = !!(opts && opts.runeActive);
  const weapons = (opts && opts.weapons) || [];
  const equipLoadTable = (opts && opts.equipLoadTable) || {};
  const level = Math.max(1, (opts && opts.level) || 1);

  const gear = [...armor, ...talismans];
  const effective = applyEffectiveStats(invested, gear, rune, runeActive);
  const effectItems = runeActive && rune ? [...gear, rune] : gear;
  const effects = combineItemEffects(effectItems);

  const hpBase = hpFromVigor(effective.vig);
  const fpBase = fpFromMind(effective.mind);
  const stamBase = staminaFromEndurance(effective.end);
  const loadBase = baseEquipLoadForEndurance(effective.end, equipLoadTable);

  const hp = Math.max(1, Math.floor(hpBase * (1 + effects.resources.hp)));
  const fp = Math.max(1, Math.floor(fpBase * (1 + effects.resources.fp)));
  const stamina = Math.max(1, Math.floor(stamBase * (1 + effects.resources.stamina)));
  const maxLoad = loadBase * (1 + effects.resources.equipLoad);
  const weight = totalWeight([...armor, ...talismans, ...weapons]);
  const ratio = maxLoad > 0 ? weight / maxLoad : 0;

  const armorNeg = computeNegation(armor);
  const absorption = combineAbsorption(armorNeg, effects.remaining);
  const armorRes = computeResistances(armor);
  const baseRes = baseResistances(level, effective);
  const resistances = {
    immunity: Math.floor(baseRes.immunity + armorRes.immunity + effects.resist.immunity),
    robustness: Math.floor(baseRes.robustness + armorRes.robustness + effects.resist.robustness),
    focus: Math.floor(baseRes.focus + armorRes.focus + effects.resist.focus),
    vitality: Math.floor(baseRes.vitality + armorRes.vitality + effects.resist.vitality),
  };
  const poise = computeTotalPoise(armor, talismans);
  const discovery = Math.max(0, Math.floor(100 + (effective.arc - 1) + effects.discovery));
  const memorySlots = 2 + effects.memorySlots;

  return {
    invested,
    effective,
    level,
    hpBase,
    fpBase,
    stamBase,
    loadBase,
    hp,
    fp,
    stamina,
    maxLoad,
    weight,
    ratio,
    loadClass: loadClass(ratio),
    poise,
    discovery,
    memorySlots,
    armorNeg,
    absorption,
    resistances,
    resources: effects.resources,
  };
}

if (typeof module !== "undefined") {
  module.exports = {
    DAMAGE_TYPES,
    RESIST_TYPES,
    STAT_KEYS,
    STAT_LABELS,
    baseEquipLoadForEndurance,
    talismanEquipLoadBonus,
    talismanPoiseBonus,
    parseAttributeBonuses,
    parseResourceBonuses,
    parseResistanceBonuses,
    parseDamageRemaining,
    talismanAttributeBonuses,
    itemAttributeBonuses,
    applyAttributeBonuses,
    applyEffectiveStats,
    applyGreatRuneStats,
    hpFromVigor,
    fpFromMind,
    staminaFromEndurance,
    computeMaxEquipLoad,
    totalWeight,
    loadClass,
    allowedLoadClass,
    isHeavierLoadClass,
    computeTotalPoise,
    computeNegation,
    computeResistances,
    combineAbsorption,
    computeCharacterStatus,
  };
}
