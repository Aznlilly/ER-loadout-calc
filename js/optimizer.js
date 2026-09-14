// optimizer.js — picks the best one-item-per-slot armor combination.
//
// This is a Multiple-Choice Knapsack Problem (MCKP): choose exactly one item
// from each of up to 4 groups (helm/chest/gauntlets/legs) to maximize a
// per-item "value" subject to a total weight budget. Solved with a weight-
// discretized DP. Capacity is floored and item weights are ceiled so a
// selected combo never exceeds the real kg budget (inner approximation).

const SLOT_ORDER = ["helm", "chest", "gauntlets", "legs"];
const WEIGHT_RESOLUTION = 10; // discretize weight into 1/10ths of a unit
const WEIGHT_EPS = 1e-9;
const NEGATION_TYPES = ["phy", "strike", "slash", "pierce", "magic", "fire", "lightning", "holy"];

function negationObjective(stat) {
  const weights = {};
  for (const dt of NEGATION_TYPES) weights[dt] = 0;
  if (stat && Object.prototype.hasOwnProperty.call(weights, stat)) weights[stat] = 1;
  return { type: "negation", stat, weights };
}

function toCapacityUnits(weight) {
  return Math.max(0, Math.floor(weight * WEIGHT_RESOLUTION + WEIGHT_EPS));
}

function toItemUnits(weight) {
  return Math.max(0, Math.ceil(weight * WEIGHT_RESOLUTION - WEIGHT_EPS));
}

function selectionWeight(selection) {
  let w = 0;
  for (const key in selection) {
    const it = selection[key];
    if (it && typeof it.weight === "number") w += it.weight;
  }
  return w;
}

/**
 * Scores one armor piece for a given objective.
 *   objective: {type: "poise"} |
 *              {type: "negation", weights?: {phy:1, strike:0, ...}, stat?: "fire"} |
 *              {type: "resistance", stat: "immunity"|"robustness"|"focus"|"vitality"}
 */
function scoreItem(item, objective) {
  switch (objective.type) {
    case "poise":
      return (item.resistance && item.resistance.poise) || 0;
    case "resistance":
      return (item.resistance && item.resistance[objective.stat]) || 0;
    case "negation": {
      const w = objective.weights || {};
      let total = 0;
      if (!item.negation) return 0;
      for (const dt of Object.keys(item.negation)) {
        const weight = w[dt] !== undefined ? w[dt] : 1;
        total += item.negation[dt] * weight;
      }
      return total;
    }
    default:
      return 0;
  }
}

/**
 * Maximizes total score across one item per slot subject to a weight budget.
 *
 * @param itemsBySlot {helm: [...], chest: [...], gauntlets: [...], legs: [...]}
 * @param objective   see scoreItem()
 * @param maxWeightUnits total weight budget, already in real units (e.g. kg-equivalent)
 * @param requiredSlots  optional subset of SLOT_ORDER to include (default: all four)
 * @returns {selection: {slot: item}, totalWeight, totalScore} or null if infeasible
 */
function optimizeArmor(itemsBySlot, objective, maxWeight, requiredSlots) {
  const slots = (requiredSlots && requiredSlots.length ? requiredSlots : SLOT_ORDER)
    .filter((s) => itemsBySlot[s] && itemsBySlot[s].length);
  const capacity = toCapacityUnits(maxWeight);
  if (capacity < 0 || !slots.length) return null;

  // dp[w] = best score achievable using EXACTLY w weight-units so far (only
  // w=0 is reachable before any slot is filled — everything else starts
  // unreachable so items can't be "paid for" with phantom starting slack).
  const NEG_INF = -Infinity;
  let dpScore = new Array(capacity + 1).fill(NEG_INF);
  dpScore[0] = 0;
  let dpChoice = new Array(capacity + 1).fill(null);
  dpChoice[0] = {};

  for (const slot of slots) {
    const items = itemsBySlot[slot];
    const newScore = new Array(capacity + 1).fill(NEG_INF);
    const newChoice = new Array(capacity + 1).fill(null);

    for (let w = 0; w <= capacity; w++) {
      if (dpScore[w] === NEG_INF) continue;
      // Option: try adding each candidate item in this slot.
      for (const item of items) {
        const iw = toItemUnits(item.weight);
        const nw = w + iw;
        if (nw > capacity) continue;
        const ns = dpScore[w] + scoreItem(item, objective);
        if (ns > newScore[nw]) {
          newScore[nw] = ns;
          newChoice[nw] = { ...dpChoice[w], [slot]: item };
        }
      }
    }
    dpScore = newScore;
    dpChoice = newChoice;
  }

  // Best score among combos that also fit the real kg budget, not just the
  // discretized table (a lighter cell can win on actual weight).
  let bestW = -1;
  let bestScore = NEG_INF;
  let bestActual = 0;
  for (let w = 0; w <= capacity; w++) {
    if (dpScore[w] === NEG_INF) continue;
    const actual = selectionWeight(dpChoice[w]);
    if (actual > maxWeight + WEIGHT_EPS) continue;
    if (dpScore[w] > bestScore) {
      bestScore = dpScore[w];
      bestW = w;
      bestActual = actual;
    }
  }
  if (bestW < 0 || bestScore === NEG_INF) return null;

  return {
    selection: dpChoice[bestW],
    totalWeight: bestActual,
    totalScore: bestScore,
  };
}

/**
 * Minimizes total weight subject to reaching at least `targetScore` on the
 * given objective. Uses a DP over score instead of weight (score is summed
 * from item values, which for poise/resistance/negation are all >= 0).
 *
 * @param maxScoreUnits ceiling on target score to size the DP table (pass a
 *        generous upper bound, e.g. sum of the best possible per-slot values).
 */
function minimizeWeightForTarget(itemsBySlot, objective, targetScore, requiredSlots) {
  const slots = (requiredSlots && requiredSlots.length ? requiredSlots : SLOT_ORDER)
    .filter((s) => itemsBySlot[s] && itemsBySlot[s].length);
  if (!slots.length) return null;

  // Score resolution: round to nearest integer (poise/resistance/negation
  // values in this data set are already whole numbers or one decimal place;
  // we scale by 10 for one-decimal precision).
  const SCORE_RES = 10;
  const target = Math.ceil(targetScore * SCORE_RES);

  // Compute the maximum achievable score to size the table.
  let maxPossible = 0;
  for (const slot of slots) {
    let best = 0;
    for (const item of itemsBySlot[slot]) {
      best = Math.max(best, scoreItem(item, objective));
    }
    maxPossible += best;
  }
  const cap = Math.max(target, Math.ceil(maxPossible * SCORE_RES));

  const INF = Infinity;
  let dpWeight = new Array(cap + 1).fill(0);
  let dpChoice = new Array(cap + 1).fill(null).map(() => ({}));
  dpWeight[0] = 0;
  for (let s = 1; s <= cap; s++) dpWeight[s] = INF;

  for (const slot of slots) {
    const items = itemsBySlot[slot];
    const newWeight = new Array(cap + 1).fill(INF);
    const newChoice = new Array(cap + 1).fill(null);

    for (let s = 0; s <= cap; s++) {
      if (dpWeight[s] === INF) continue;
      for (const item of items) {
        const sc = Math.round(scoreItem(item, objective) * SCORE_RES);
        const ns = Math.min(cap, s + sc);
        const nw = dpWeight[s] + item.weight;
        if (nw < newWeight[ns]) {
          newWeight[ns] = nw;
          newChoice[ns] = { ...dpChoice[s], [slot]: item };
        }
      }
    }
    dpWeight = newWeight;
    dpChoice = newChoice;
  }

  // Find the cheapest weight among all score levels >= target.
  let bestS = -1;
  let bestWeight = INF;
  for (let s = target; s <= cap; s++) {
    if (dpWeight[s] < bestWeight) {
      bestWeight = dpWeight[s];
      bestS = s;
    }
  }
  if (bestS < 0 || bestWeight === INF) return null;

  return {
    selection: dpChoice[bestS],
    totalWeight: bestWeight,
    totalScore: bestS / SCORE_RES,
  };
}

if (typeof module !== "undefined") {
  module.exports = { SLOT_ORDER, NEGATION_TYPES, negationObjective, scoreItem, optimizeArmor, minimizeWeightForTarget };
}
