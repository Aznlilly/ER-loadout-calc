// weapons.js — filtering & ranking weapons against a character's stats.
//
// IMPORTANT SCOPE NOTE: computing a weapon's true Attack Rating for an
// arbitrary stat spread requires FromSoftware's per-weapon scaling-curve
// tables (which differ by weapon "correction" type and are not published in
// structured form). We do NOT invent those numbers. Instead:
//   - `referenceAttack` is the wiki's reference AR at a fixed, high stat
//     investment (shown for comparison, clearly labeled as a reference).
//   - Weapons are ranked primarily by whether the character meets/exceeds
//     requirements and by a stat-weighted "scaling payoff" score computed
//     from the letter grade (S/A/B/C/D/E) and the character's own stat in
//     that category — a good proxy for "how much this stat spread benefits
//     this weapon" without fabricating a precise AR number.

const GRADE_WEIGHT = { S: 5, A: 4, B: 3, C: 2, D: 1, E: 0.5 };

function gradeWeight(grade) {
  return GRADE_WEIGHT[grade] || 0;
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
function scalingPayoff(weapon, stats) {
  let total = 0;
  for (const stat of ["str", "dex", "int", "fai", "arc"]) {
    const grade = weapon.scaling[stat];
    if (!grade) continue;
    total += gradeWeight(grade) * (stats[stat] || 0);
  }
  return total;
}

/**
 * Filters and ranks weapons for a character.
 * @param weapons full weapon list
 * @param stats {str,dex,int,fai,arc}
 * @param opts {twoHanding, onlyMeetable, category, includeDlc}
 */
function rankWeapons(weapons, stats, opts = {}) {
  const { twoHanding = false, onlyMeetable = true, category = null, includeDlc = true } = opts;
  let list = weapons;
  if (category) list = list.filter((w) => w.category === category || w.type === category);

  const scored = list.map((w) => {
    const { met, shortfalls } = checkRequirements(w, stats, twoHanding);
    return {
      weapon: w,
      met,
      shortfalls,
      payoff: scalingPayoff(w, stats),
      referenceAttack: w.attack,
    };
  });

  const filtered = onlyMeetable ? scored.filter((s) => s.met) : scored;
  filtered.sort((a, b) => b.payoff - a.payoff);
  return filtered;
}

if (typeof module !== "undefined") {
  module.exports = { checkRequirements, scalingPayoff, rankWeapons, effectiveStat, gradeWeight };
}
