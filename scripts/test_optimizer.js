// Quick sanity test for the optimizer + calc engine against real data.
const fs = require("fs");
const path = require("path");

const { computeMaxEquipLoad, totalWeight, loadClass, allowedLoadClass, isHeavierLoadClass } =
  require("../js/calc.js");
const { optimizeArmor, minimizeWeightForTarget } = require("../js/optimizer.js");

const dataDir = path.join(__dirname, "..", "data");
const armor = JSON.parse(fs.readFileSync(path.join(dataDir, "armor.json")));
const talismans = JSON.parse(fs.readFileSync(path.join(dataDir, "talismans.json")));
const equipLoadTable = JSON.parse(fs.readFileSync(path.join(dataDir, "equip_load_table.json")));

function bySlot(items, dlcOk) {
  const out = { helm: [], chest: [], gauntlets: [], legs: [] };
  for (const a of items) {
    if (!dlcOk && a.dlc) continue;
    if (a.altered) continue; // skip altered variants for a cleaner default pool
    out[a.slot].push(a);
  }
  return out;
}

function fail(msg) {
  console.error("FAIL:", msg);
  process.exit(1);
}

function assertWithinCap(result, maxLoad, ratio, label) {
  if (!result) fail(`${label}: optimizer returned null`);
  const actual = totalWeight(Object.values(result.selection));
  if (actual > maxLoad * ratio + 1e-9) {
    fail(`${label}: combo ${actual.toFixed(2)} exceeded cap ${(maxLoad * ratio).toFixed(2)}`);
  }
  const cls = loadClass(actual / maxLoad);
  const allowed = allowedLoadClass(ratio);
  if (isHeavierLoadClass(cls, allowed)) {
    fail(`${label}: ${cls} is heavier than allowed ${allowed} at ratio ${ratio}`);
  }
}

// --- Test 1: max poise at 60 Endurance, Medium load (<=69.9%), DLC included ---
const endurance = 60;
const maxLoad = computeMaxEquipLoad(endurance, [], equipLoadTable);
console.log(`Max equip load @ ${endurance} END:`, maxLoad);

const budget = maxLoad * 0.699;
console.log("Medium-load budget:", budget.toFixed(2));

const pool = bySlot(armor, true);
console.log("Pool sizes:", Object.fromEntries(Object.entries(pool).map(([k, v]) => [k, v.length])));

const t0 = Date.now();
const result = optimizeArmor(pool, { type: "poise" }, budget);
console.log("optimizeArmor(poise) took", Date.now() - t0, "ms");
console.log("Total weight:", result.totalWeight.toFixed(2), "/ budget", budget.toFixed(2));
console.log("Total poise score:", result.totalScore);
for (const slot of ["helm", "chest", "gauntlets", "legs"]) {
  const it = result.selection[slot];
  console.log(` ${slot}: ${it.name} (wgt ${it.weight}, poise ${it.resistance.poise}, dlc=${it.dlc})`);
}
const actualPoiseWeight = totalWeight(Object.values(result.selection));
const poiseRatio = actualPoiseWeight / maxLoad;
console.log("Ratio:", (poiseRatio * 100).toFixed(1) + "%", loadClass(poiseRatio));
assertWithinCap(result, maxLoad, 0.699, "medium poise");

// --- Test 2: max total negation, Heavy load ---
const budget2 = maxLoad * 0.999;
const t1 = Date.now();
const result2 = optimizeArmor(pool, { type: "negation" }, budget2);
console.log("\noptimizeArmor(negation) took", Date.now() - t1, "ms");
console.log("Total weight:", result2.totalWeight.toFixed(2), "/ budget", budget2.toFixed(2));
console.log("Total negation score:", result2.totalScore.toFixed(1));
for (const slot of ["helm", "chest", "gauntlets", "legs"]) {
  const it = result2.selection[slot];
  console.log(` ${slot}: ${it.name} (wgt ${it.weight})`);
}
const actualNegWeight = totalWeight(Object.values(result2.selection));
assertWithinCap(result2, maxLoad, 0.999, "heavy negation");

// --- Test 3: min weight to reach poise >= 60 ---
const t2 = Date.now();
const result3 = minimizeWeightForTarget(pool, { type: "poise" }, 60);
console.log("\nminimizeWeightForTarget(poise>=60) took", Date.now() - t2, "ms");
if (result3) {
  console.log("Total weight:", result3.totalWeight.toFixed(2), "Total poise:", result3.totalScore);
  for (const slot of ["helm", "chest", "gauntlets", "legs"]) {
    const it = result3.selection[slot];
    console.log(` ${slot}: ${it.name} (wgt ${it.weight}, poise ${it.resistance.poise})`);
  }
} else {
  console.log("infeasible");
}

// --- Test 4: max specific resistance (robustness), Light load ---
const budget4 = maxLoad * 0.299;
const result4 = optimizeArmor(pool, { type: "resistance", stat: "robustness" }, budget4);
console.log("\nmax robustness @ light load:");
console.log("Total weight:", result4.totalWeight.toFixed(2), "/ budget", budget4.toFixed(2));
console.log("Total robustness:", result4.totalScore);
for (const slot of ["helm", "chest", "gauntlets", "legs"]) {
  const it = result4.selection[slot];
  console.log(` ${slot}: ${it.name} (wgt ${it.weight}, robustness ${it.resistance.robustness})`);
}
const actualLightWeight = totalWeight(Object.values(result4.selection));
assertWithinCap(result4, maxLoad, 0.299, "light robustness");

// --- Test 5: locked chest stays fixed (one-item pool) ---
const bullGoatChest = pool.chest.find((a) => a.name === "Bull-Goat Armor");
if (!bullGoatChest) fail("Bull-Goat Armor missing from chest pool");
const lockedPool = {
  helm: pool.helm,
  chest: [bullGoatChest],
  gauntlets: pool.gauntlets,
  legs: pool.legs,
};
const result5 = optimizeArmor(lockedPool, { type: "poise" }, budget);
if (!result5) fail("locked-chest optimizeArmor returned null");
if (result5.selection.chest.id !== bullGoatChest.id) {
  fail(`chest should stay Bull-Goat Armor, got ${result5.selection.chest.name}`);
}
const lockedActual = totalWeight(Object.values(result5.selection));
if (lockedActual > budget + 1e-9) fail("locked combo exceeded budget");
console.log("\nlocked chest stays:", result5.selection.chest.name, "weight", lockedActual.toFixed(2));

// --- Test 6: omit helm via requiredSlots (locked empty helm) ---
const result6 = optimizeArmor(pool, { type: "poise" }, budget, ["chest", "gauntlets", "legs"]);
if (!result6) fail("requiredSlots without helm returned null");
if (result6.selection.helm) fail("helm should be omitted when not in requiredSlots");
if (!result6.selection.chest || !result6.selection.gauntlets || !result6.selection.legs) {
  fail("other slots should still be filled");
}
console.log("omitted helm, filled:", Object.keys(result6.selection).join(", "));

// --- Test 7: rounding must not admit a combo that only fits past the kg budget ---
const tightPool = {
  helm: [{ id: "h", name: "Circlet of Light", slot: "helm", weight: 1.0, resistance: { poise: 5 } }],
  chest: [{ id: "c", name: "Eye Surcoat", slot: "chest", weight: 9.2, resistance: { poise: 21 } }],
  gauntlets: [{ id: "g", name: "Ascetic's Wrist Guards", slot: "gauntlets", weight: 1.1, resistance: { poise: 2 } }],
  legs: [
    { id: "l-heavy", name: "Ascetic's Ankle Guards", slot: "legs", weight: 2.0, resistance: { poise: 6 } },
    { id: "l-light", name: "Lighter Ankles", slot: "legs", weight: 1.8, resistance: { poise: 5 } },
  ],
};
const tightBudget = 13.2139; // 56.1 * 0.699 - 26.0, the screenshot case
const result7 = optimizeArmor(tightPool, { type: "poise" }, tightBudget);
if (!result7) fail("tight medium budget should still pick the lighter combo");
const tightActual = totalWeight(Object.values(result7.selection));
if (tightActual > tightBudget + 1e-9) fail("inner approximation selected a combo heavier than the kg budget");
if (result7.selection.legs.id !== "l-light") {
  fail(`should reject 13.3 armor at budget ${tightBudget}, got ${result7.selection.legs.name} (${tightActual})`);
}
console.log("tight medium budget kept under kg cap:", tightActual.toFixed(2));

// --- Test 8: Light / custom / Heavy / breakpoint ratios stay in class ---
for (const ratio of [0.299, 0.30, 0.45, 0.699, 0.70, 0.999, 1.0]) {
  const custom = optimizeArmor(pool, { type: "poise" }, maxLoad * ratio);
  assertWithinCap(custom, maxLoad, ratio, `poise @ ${ratio}`);
  console.log(
    `cap ${((ratio) * 100).toFixed(1)}%:`,
    (totalWeight(Object.values(custom.selection)) / maxLoad * 100).toFixed(1) + "%",
    loadClass(totalWeight(Object.values(custom.selection)) / maxLoad)
  );
}

