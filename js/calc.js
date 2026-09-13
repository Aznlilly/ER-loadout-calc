// calc.js — core Elden Ring stat calculations: equip load, poise, negation.
// All formulas sourced from the in-game Equip Load stat table (Endurance -> max load)
// and the standard additive-negation model used by the game's armor stat screen.

const DAMAGE_TYPES = ["phy", "strike", "slash", "pierce", "magic", "fire", "lightning", "holy"];
const RESIST_TYPES = ["immunity", "robustness", "focus", "vitality", "poise"];

/**
 * Max equip load contributed by Endurance alone, from the game's lookup table.
 * Endurance is clamped to [1, 99].
 */
function baseEquipLoadForEndurance(endurance, equipLoadTable) {
  const end = Math.max(1, Math.min(99, Math.round(endurance)));
  return equipLoadTable[String(end)] ?? equipLoadTable["99"];
}

/**
 * Parses known equip-load-boosting effects out of a talisman's effect text.
 * Returns an additive percentage bonus to MAX equip load (e.g. 0.05 for +5%).
 * This is data-driven (regex over the effect string) rather than a hardcoded
 * item list, so it keeps working if the data set is regenerated/expanded.
 */
function talismanEquipLoadBonus(effectText) {
  if (!effectText) return 0;
  const m = effectText.match(/Equip Load\s*\(?([\d.]+)%\)?/i) || effectText.match(/Equip Load by\s*([\d.]+)%/i);
  if (m) return parseFloat(m[1]) / 100;
  return 0;
}

/**
 * Parses known poise-boosting effects out of a talisman's effect text.
 * Returns an additive percentage bonus to total poise (e.g. 0.33 for +33%).
 */
function talismanPoiseBonus(effectText) {
  if (!effectText) return 0;
  const m = effectText.match(/(?:Raises|Increases|Boosts) Poise by\s*([\d.]+)%/i);
  if (m) return parseFloat(m[1]) / 100;
  return 0;
}

/**
 * Computes the character's maximum equip load given Endurance and a list of
 * equipped talismans (objects with an `effect` string).
 */
function computeMaxEquipLoad(endurance, equippedTalismans, equipLoadTable) {
  const base = baseEquipLoadForEndurance(endurance, equipLoadTable);
  let bonus = 0;
  for (const t of equippedTalismans || []) {
    bonus += talismanEquipLoadBonus(t.effect);
  }
  return base * (1 + bonus);
}

/**
 * Sums the weight of a set of equipped items (armor pieces, talismans,
 * weapons) — anything with a `.weight` field.
 */
function totalWeight(items) {
  return (items || []).reduce((sum, it) => sum + (it && it.weight ? it.weight : 0), 0);
}

/** Classifies a weight ratio (0-1+) into the game's load status. */
function loadClass(ratio) {
  if (ratio >= 1.0) return "overloaded";
  if (ratio >= 0.70) return "heavy";
  if (ratio >= 0.30) return "medium";
  return "light";
}

/**
 * Sums poise across a set of armor pieces, then applies any poise-boosting
 * talisman bonuses (e.g. Bull-Goat's Talisman).
 */
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

/** Sums damage negation percentages across a set of armor pieces. */
function computeNegation(armorPieces) {
  const totals = {};
  for (const dt of DAMAGE_TYPES) totals[dt] = 0;
  for (const a of armorPieces || []) {
    if (!a.negation) continue;
    for (const dt of DAMAGE_TYPES) totals[dt] += a.negation[dt] || 0;
  }
  return totals;
}

/** Sums the four non-poise resistance stats across a set of armor pieces. */
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

if (typeof module !== "undefined") {
  module.exports = {
    DAMAGE_TYPES,
    RESIST_TYPES,
    baseEquipLoadForEndurance,
    talismanEquipLoadBonus,
    talismanPoiseBonus,
    computeMaxEquipLoad,
    totalWeight,
    loadClass,
    computeTotalPoise,
    computeNegation,
    computeResistances,
  };
}
