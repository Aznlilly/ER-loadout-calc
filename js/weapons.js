// weapons.js — filtering & ranking weapons against a character's stats.
//
// IMPORTANT SCOPE NOTE: computing a weapon's true Attack Rating for an
// arbitrary stat spread requires FromSoftware's per-weapon scaling-curve
// tables (which differ by weapon "correction" type and are not published in
// structured form). We do NOT invent those numbers. Instead:
//   - `referenceAttack` is the wiki's reference AR at a fixed, high stat
//     investment (shown for comparison, clearly labeled as a reference).
//   - When affinities are enabled, payoff uses EquipParamWeapon correction
//     percents for that infusion (Heavy/Keen/…). Upgrade level from a save is
//     shown and used as a tiny tie-break only — true +N Attack Rating needs
//     the game's reinforce graphs, which this build does not compute.

const GRADE_WEIGHT = { S: 5, A: 4, B: 3, C: 2, D: 1, E: 0.5 };

const AFFINITY_LABELS = {
  0: "Standard",
  100: "Heavy",
  200: "Keen",
  300: "Quality",
  400: "Fire",
  500: "Flame Art",
  600: "Lightning",
  700: "Sacred",
  800: "Magic",
  900: "Cold",
  1000: "Poison",
  1100: "Blood",
  1200: "Occult",
};

function gradeWeight(grade) {
  return GRADE_WEIGHT[grade] || 0;
}

function scalingLetterFromCorrect(percent) {
  if (percent == null || percent <= 0.05) return null;
  if (percent >= 180) return "S";
  if (percent >= 140) return "A";
  if (percent >= 90) return "B";
  if (percent >= 60) return "C";
  if (percent >= 25) return "D";
  return "E";
}

function variantDisplayName(weapon, affinityCode, upgrade, includeUpgrades) {
  const aff = AFFINITY_LABELS[Number(affinityCode)] || "Standard";
  let name = weapon.name;
  if (aff && aff !== "Standard") name = `${aff} ${name}`;
  if (includeUpgrades && upgrade > 0) name += ` +${upgrade}`;
  return name;
}

function scalingFromVariant(weapon, variant) {
  if (variant && variant.correct) {
    const c = variant.correct;
    return {
      str: scalingLetterFromCorrect(c.str),
      dex: scalingLetterFromCorrect(c.dex),
      int: scalingLetterFromCorrect(c.int),
      fai: scalingLetterFromCorrect(c.fai),
      arc: scalingLetterFromCorrect(c.arc),
    };
  }
  return weapon.scaling || {};
}

function scalingPayoffFromCorrect(correct, stats) {
  let total = 0;
  for (const stat of ["str", "dex", "int", "fai", "arc"]) {
    const pct = correct[stat] || 0;
    if (pct <= 0) continue;
    total += (pct / 20) * (stats[stat] || 0);
  }
  return total;
}

/**
 * Effective requirement for a stat, accounting for two-handing (which
 * multiplies effective Strength by 1.5, rounded down, per the game's rules).
 */
function effectiveStat(stats, statKey, twoHanding) {
  const val = stats[statKey] || 0;
  if (twoHanding && statKey === "str") return Math.floor(val * 1.5);
  return val;
}

/** Returns {met: bool, shortfalls: {stat: amount}} for a weapon's requirements. */
function checkRequirements(weapon, stats, twoHanding) {
  const shortfalls = {};
  let met = true;
  for (const stat of ["str", "dex", "int", "fai", "arc"]) {
    const req = weapon.requirements[stat] || 0;
    if (req <= 0) continue;
    const have = effectiveStat(stats, stat, twoHanding);
    if (have < req) {
      met = false;
      shortfalls[stat] = req - have;
    }
  }
  return { met, shortfalls };
}

/** Stat-weighted scaling payoff score (see module note above). */
function scalingPayoff(weapon, stats, variant) {
  if (variant && variant.correct) return scalingPayoffFromCorrect(variant.correct, stats);
  let total = 0;
  for (const stat of ["str", "dex", "int", "fai", "arc"]) {
    const grade = weapon.scaling[stat];
    if (!grade) continue;
    total += gradeWeight(grade) * (stats[stat] || 0);
  }
  return total;
}

function expandWeaponVariants(weapons, opts = {}) {
  const {
    includeAffinities = false,
    includeUpgrades = false,
    variants = {},
    ownedInstances = {},
  } = opts;
  const out = [];
  for (const w of weapons) {
    const table = variants[w.id] || {};
    const owned = ownedInstances[w.id] || [];
    const hasSaveInstances = Object.keys(ownedInstances).length > 0;
    let codes;
    if (includeAffinities && owned.length) {
      codes = [...new Set(owned.map((o) => String(o.affinity || 0)))];
    } else if (includeAffinities && !hasSaveInstances && Object.keys(table).length) {
      codes = Object.keys(table);
    } else {
      codes = ["0"];
      if (!table["0"] && Object.keys(table).length === 1) codes = Object.keys(table);
    }
    for (const code of codes) {
      const variant = table[code] || table["0"] || null;
      let upgrade = 0;
      if (includeUpgrades && owned.length) {
        const matches = owned.filter((o) => String(o.affinity || 0) === String(code));
        for (const m of matches) upgrade = Math.max(upgrade, m.upgrade || 0);
      }
      out.push({
        weapon: w,
        affinity: Number(code),
        upgrade,
        variant,
        label: variantDisplayName(w, code, upgrade, includeUpgrades),
        scaling: scalingFromVariant(w, variant),
      });
    }
  }
  return out;
}

/**
 * Filters and ranks weapons for a character.
 * @param weapons full weapon list
 * @param stats {str,dex,int,fai,arc}
 * @param opts {twoHanding, onlyMeetable, category, includeDlc, includeAffinities, includeUpgrades, variants, ownedInstances}
 */
function rankWeapons(weapons, stats, opts = {}) {
  const {
    twoHanding = false,
    onlyMeetable = true,
    category = null,
    includeAffinities = false,
    includeUpgrades = false,
    variants = {},
    ownedInstances = {},
  } = opts;
  let list = weapons;
  if (category) list = list.filter((w) => w.category === category || w.type === category);

  const expanded = expandWeaponVariants(list, {
    includeAffinities,
    includeUpgrades,
    variants,
    ownedInstances,
  });

  const scored = expanded.map((row) => {
    const { met, shortfalls } = checkRequirements(row.weapon, stats, twoHanding);
    let payoff = scalingPayoff(row.weapon, stats, row.variant);
    if (includeUpgrades && row.upgrade > 0) payoff += row.upgrade * 0.01;
    return {
      weapon: row.weapon,
      affinity: row.affinity,
      upgrade: row.upgrade,
      variant: row.variant,
      label: row.label,
      scaling: row.scaling,
      met,
      shortfalls,
      payoff,
      referenceAttack: row.weapon.attack,
    };
  });

  const filtered = onlyMeetable ? scored.filter((s) => s.met) : scored;
  filtered.sort((a, b) => b.payoff - a.payoff);
  return filtered;
}

if (typeof module !== "undefined") {
  module.exports = {
    checkRequirements,
    scalingPayoff,
    rankWeapons,
    effectiveStat,
    gradeWeight,
    expandWeaponVariants,
    variantDisplayName,
    AFFINITY_LABELS,
  };
}
