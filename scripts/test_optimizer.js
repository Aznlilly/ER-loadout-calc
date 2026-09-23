// Quick sanity test for the optimizer + calc engine against real data.
const fs = require("fs");
const path = require("path");

const { computeMaxEquipLoad, totalWeight, loadClass, allowedLoadClass, isHeavierLoadClass, applyGreatRuneStats, parseAttributeBonuses, parseResourceBonuses, parseResistanceBonuses, parseDamageDealt, applyEffectiveStats, itemAttributeBonuses, hpFromVigor, fpFromMind, staminaFromEndurance, computeCharacterStatus } =
  require("../js/calc.js");
const { optimizeArmor, minimizeWeightForTarget, negationObjective, scoreItem } = require("../js/optimizer.js");

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

// --- Test 9: specific fire negation uses only fire, and beats total-negation's fire ---
{
  const fireObj = negationObjective("fire");
  const dummy = { negation: { phy: 10, strike: 1, slash: 1, pierce: 1, magic: 1, fire: 4, lightning: 1, holy: 1 } };
  if (Math.abs(scoreItem(dummy, fireObj) - 4) > 1e-9) fail("fire objective should score only fire negation");
  if (Math.abs(scoreItem(dummy, { type: "negation" }) - 20) > 1e-9) fail("unweighted negation should sum all types");

  const fireResult = optimizeArmor(pool, fireObj, budget2);
  if (!fireResult) fail("fire optimizeArmor returned null");
  const fireSum = ["helm", "chest", "gauntlets", "legs"].reduce(
    (s, slot) => s + ((fireResult.selection[slot].negation && fireResult.selection[slot].negation.fire) || 0),
    0
  );
  if (Math.abs(fireResult.totalScore - fireSum) > 1e-6) {
    fail(`fire score ${fireResult.totalScore} should equal summed fire ${fireSum}`);
  }
  const totalNegFire = ["helm", "chest", "gauntlets", "legs"].reduce(
    (s, slot) => s + ((result2.selection[slot].negation && result2.selection[slot].negation.fire) || 0),
    0
  );
  if (fireSum + 1e-9 < totalNegFire) {
    fail(`fire-focused combo fire ${fireSum} should be >= total-negation combo fire ${totalNegFire}`);
  }
  assertWithinCap(fireResult, maxLoad, 0.999, "heavy fire");
  console.log("\nmax fire negation @ heavy load:", fireSum.toFixed(1), "vs total-negation fire", totalNegFire.toFixed(1));
}

{
  const base = { vig: 10, mind: 10, end: 10, str: 10, dex: 10, int: 10, fai: 10, arc: 10 };
  const off = applyGreatRuneStats(base, { statBonus: 5 }, false);
  const on = applyGreatRuneStats(base, { statBonus: 5 }, true);
  const capped = applyGreatRuneStats({ ...base, str: 97 }, { statBonus: 5 }, true);
  if (off.end !== 10) fail("inactive Godrick should leave endurance alone");
  if (on.end !== 15 || on.str !== 15) fail("active Godrick should add +5 to attributes");
  if (capped.str !== 99) fail("Godrick's bonus should cap at 99");

  const soreseal = parseAttributeBonuses("Raises Vigor, Endurance, Strength, and Dexterity by 5, but increases all damage taken by 15%.");
  const marika = parseAttributeBonuses("Raises Mind, Intelligence, Faith, and Arcane by 3, but increases all damage taken by 10%.");
  const heirloom = parseAttributeBonuses("Raises Strength by 5.");
  const millicent = parseAttributeBonuses("Raises dexterity by 5 and raises attack power with successive attacks (4% → 6% → 11%).");
  const outerGod = parseAttributeBonuses("Raises arcane +5");
  const godrickText = parseAttributeBonuses("Raises all attributes by +5");
  const poise = parseAttributeBonuses("Raises Poise by 33%.");
  if (soreseal.str !== 5 || soreseal.end !== 5 || soreseal.mind !== 0) fail("Radagon's Soreseal should boost VIG/END/STR/DEX");
  if (marika.mind !== 3 || marika.int !== 3 || marika.str !== 0) fail("Marika's Scarseal should boost MIN/INT/FAI/ARC");
  if (heirloom.str !== 5 || heirloom.dex !== 0) fail("Starscourge Heirloom should boost Strength only");
  if (millicent.dex !== 5 || millicent.str !== 0) fail("Millicent's Prosthesis should boost Dexterity only");
  if (outerGod.arc !== 5) fail("Outer God Heirloom should parse 'Raises arcane +5'");
  if (godrickText.vig !== 5 || godrickText.arc !== 5) fail("all-attributes text should boost every stat");
  if (poise.str !== 0 || poise.end !== 0) fail("poise bonuses must not be treated as attributes");

  const stacked = applyEffectiveStats(
    base,
    [{ effect: "Raises Vigor, Endurance, Strength, and Dexterity by 5, but increases all damage taken by 15%." }],
    { statBonus: 5 },
    true
  );
  if (stacked.end !== 20 || stacked.str !== 20 || stacked.mind !== 15) {
    fail("Godrick + Radagon's Soreseal should stack (+10 VIG/END/STR/DEX, +5 elsewhere)");
  }

  const expectedTalismanBonuses = {
    "radagon-s-scarseal": { vig: 3, end: 3, str: 3, dex: 3 },
    "radagon-s-soreseal": { vig: 5, end: 5, str: 5, dex: 5 },
    "marika-s-scarseal": { mind: 3, int: 3, fai: 3, arc: 3 },
    "marika-s-soreseal": { mind: 5, int: 5, fai: 5, arc: 5 },
    "starscourge-heirloom": { str: 5 },
    "prosthesis-wearer-heirloom": { dex: 5 },
    "stargazer-heirloom": { int: 5 },
    "two-fingers-heirloom": { fai: 5 },
    "outer-god-heirloom": { arc: 5 },
    "millicent-s-prosthesis": { dex: 5 },
  };
  for (const t of talismans) {
    const got = parseAttributeBonuses(t.effect);
    const want = expectedTalismanBonuses[t.id] || {};
    for (const key of ["vig", "mind", "end", "str", "dex", "int", "fai", "arc"]) {
      if ((got[key] || 0) !== (want[key] || 0)) {
        fail(`talisman ${t.id} ${key} bonus ${got[key]} != ${want[key] || 0}`);
      }
    }
  }
  const greatRunes = JSON.parse(fs.readFileSync(path.join(dataDir, "great-runes.json")));
  for (const rune of greatRunes) {
    const got = parseAttributeBonuses(rune.effect);
    if (rune.id === "godrick-s-great-rune") {
      if (got.str !== 5 || got.arc !== 5) fail("Godrick effect text should parse +5 all");
    } else if (["vig", "mind", "end", "str", "dex", "int", "fai", "arc"].some((key) => got[key])) {
      fail(`${rune.name} effect should not parse as attributes`);
    }
  }

  if (hpFromVigor(10) !== 414) fail("Vigor 10 should be 414 HP");
  if (hpFromVigor(40) !== 1450) fail("Vigor 40 should be 1450 HP");
  if (staminaFromEndurance(10) !== 96) fail("Endurance 10 should be 96 stamina");
  if (fpFromMind(1) !== 50) fail("Mind 1 should be 50 FP");

  const erdtree = parseResourceBonuses("Raises maximum HP (3%), Stamina (7%), and Equip Load (5%)");
  if (erdtree.hp !== 0.03 || erdtree.stamina !== 0.07 || erdtree.equipLoad !== 0.05) {
    fail("Erdtree's Favor should parse HP/Stamina/Equip Load percents");
  }
  const radahn = parseResourceBonuses("Raises maximum HP, FP and Stamina by 15%");
  if (radahn.hp !== 0.15 || radahn.fp !== 0.15 || radahn.stamina !== 0.15) fail("Radahn's Great Rune should parse +15% HP/FP/Stamina");
  const morgott = parseResourceBonuses("Raises maximum HP by 25%");
  if (morgott.hp !== 0.25 || morgott.fp !== 0) fail("Morgott's Great Rune should parse +25% HP only");
  const primal = parseResourceBonuses("Spells consume 25% less FP, but maximum HP is reduced by 15%.");
  if (Math.abs(primal.hp + 0.15) > 1e-9) fail("Primal Glintstone Blade should reduce max HP 15%");
  const fireHelm = parseResourceBonuses("Increases maximum HP by 2%, Stamina by 5%, and Equip Load by 4%.");
  if (fireHelm.hp !== 0.02 || fireHelm.stamina !== 0.05 || fireHelm.equipLoad !== 0.04) {
    fail("Fire Knight Helm should parse HP/Stamina/Equip Load percents");
  }
  const flask = parseResourceBonuses("Boosts HP restoration from Flask of Crimson Tears by 20%");
  if (flask.hp !== 0) fail("flask restoration text must not count as max HP");

  const helm = parseAttributeBonuses("+1 to Intelligence, Faith, and Arcane\nBoosts the power of Miquella's incantations by 10%.");
  if (helm.int !== 1 || helm.fai !== 1 || helm.arc !== 1 || helm.str !== 0) fail("Circlet of Light should parse +1 INT/FAI/ARC");
  const storm = parseAttributeBonuses("Heightens intensity of the storm by 4%, boosts Strength by +3 and Dexerity by +3, but reduces restorative effect of sacred tears by -9% and lowers focus by -45.");
  if (storm.str !== 3 || storm.dex !== 3) fail("Divine Beast helm should parse STR/DEX despite Dexerity typo");
  const albinauric = parseAttributeBonuses("+2 Intelligence, +2 Faith. Reduces max HP by 9%.");
  if (albinauric.int !== 2 || albinauric.fai !== 2) fail("Albinauric mask-style +N STAT lists should parse");

  const mottled = parseResistanceBonuses("Raises Immunity, Robustness, and Focus by 40");
  if (mottled.immunity !== 40 || mottled.focus !== 40 || mottled.vitality !== 0) fail("Mottled Necklace should parse three resistances");

  const magicScorp = parseDamageDealt("Raises Magic Damage by 12%, but increases Physical Damage taken by 10%.");
  if (magicScorp.magic !== 0.12 || magicScorp.phy !== 0) fail("Magic Scorpion Charm should raise magic damage 12% only");
  const fireScorp = parseDamageDealt("Raises Fire Damage, but increases Physical Damage taken by 10%.");
  if (fireScorp.fire !== 0.12) fail("Fire Scorpion Charm missing wiki percent should still be 12%");
  const rakshasa = parseDamageDealt("Boosts All Damage by 2% but increases damage taken");
  if (rakshasa.phy !== 0.02 || rakshasa.holy !== 0.02) fail("Rakshasa-style all-damage should apply to every attack type");
  const rotExult = parseDamageDealt("Raises attack power (+10% AR) for 20 seconds when something nearby suffers from poison or rot.");
  if (rotExult.phy !== 0) fail("conditional attack-power text must not count as always-on damage");

  const atkStatus = computeCharacterStatus({
    invested: base,
    armor: [{ name: "Rakshasa Armor", effect: "Boosts All Damage by 2%" }],
    talismans: [{ name: "Fire Scorpion Charm", effect: "Raises Fire Damage, but increases Physical Damage taken by 10%." }],
    rune: null,
    runeActive: false,
    weapons: [
      { name: "Longsword", attack: { phy: 100, magic: 0, fire: 0, lightning: 0, holy: 0 } },
      { name: "Magma Blade", attack: { phy: 50, fire: 50 } },
    ],
    attackWeapon: { name: "Magma Blade", attack: { phy: 50, fire: 50 } },
    attackSlot: "r1",
    attackLeftWeapon: { name: "Longsword", attack: { phy: 100, magic: 0, fire: 0, lightning: 0, holy: 0 } },
    attackLeftSlot: "l1",
    equipLoadTable,
    level: 1,
  });
  if (Math.abs(atkStatus.attack.phy - 51) > 1e-6) fail(`physical attack should be the selected weapon 50 + 2%: ${atkStatus.attack.phy}`);
  if (Math.abs(atkStatus.attack.fire - 57) > 1e-6) fail(`fire attack should be 50 + 12% + 2%: ${atkStatus.attack.fire}`);
  if (atkStatus.attackSlot !== "r1") fail("attackSlot should round-trip");
  if (Math.abs(atkStatus.attackLeft.phy - 102) > 1e-6) fail(`left-hand physical should be Longsword 100 + 2%: ${atkStatus.attackLeft.phy}`);
  if (Math.abs(atkStatus.attackLeft.fire - 0) > 1e-6) fail(`left-hand fire should stay 0 without a fire weapon: ${atkStatus.attackLeft.fire}`);
  if (atkStatus.attackLeftSlot !== "l1") fail("attackLeftSlot should round-trip");
  const fireTip = (atkStatus.breakdown.attack.fire || []).map((row) => `${row.name} ${row.value}`).join("; ");
  if (!/magma blade/i.test(fireTip) || !/fire scorpion/i.test(fireTip) || !/rakshasa/i.test(fireTip)) {
    fail(`fire attack breakdown missing a contributor: ${fireTip}`);
  }
  const dualHands = computeCharacterStatus({
    invested: base,
    armor: [],
    talismans: [],
    rune: null,
    runeActive: false,
    weapons: [
      { name: "Longsword", attack: { phy: 100 } },
      { name: "Magma Blade", attack: { phy: 50, fire: 50 } },
    ],
    attackWeapon: { name: "Longsword", attack: { phy: 100 } },
    attackSlot: "r1",
    attackLeftWeapon: { name: "Magma Blade", attack: { phy: 50, fire: 50 } },
    attackLeftSlot: "l1",
    equipLoadTable,
    level: 1,
  });
  if (Math.abs(dualHands.attack.phy - 100) > 1e-6) fail(`status Attack Power is one armament, not both hands: ${dualHands.attack.phy}`);
  if (Math.abs(dualHands.attack.fire - 0) > 1e-6) fail(`off-hand fire should not add into right-hand Attack Power: ${dualHands.attack.fire}`);
  if (Math.abs(dualHands.attackLeft.phy - 50) > 1e-6) fail(`left-hand Attack Power should be Magma Blade physical: ${dualHands.attackLeft.phy}`);
  if (Math.abs(dualHands.attackLeft.fire - 50) > 1e-6) fail(`left-hand Attack Power should keep Magma Blade fire: ${dualHands.attackLeft.fire}`);

  const status = computeCharacterStatus({
    invested: base,
    armor: [],
    talismans: [{ name: "Radagon's Soreseal", effect: "Raises Vigor, Endurance, Strength, and Dexterity by 5, but increases all damage taken by 15%.", weight: 0.8 }],
    rune: { name: "Godrick's Great Rune", effect: "Raises all attributes by +5", statBonus: 5 },
    runeActive: true,
    weapons: [],
    equipLoadTable,
    level: 1,
  });
  if (status.effective.end !== 20 || status.effective.mind !== 15) fail("status effective stats should stack Soreseal + Godrick");
  if (status.hp <= hpFromVigor(10)) fail("Godrick vigor should raise HP above invested vigor");
  if (status.absorption.phy >= 0) fail("Soreseal 15% more damage taken should make naked physical absorption negative");
  const faithTip = (status.breakdown.attributes.fai || []).map((row) => row.name);
  if (!faithTip.some((name) => /godrick/i.test(name))) fail("faith breakdown should include Godrick's Great Rune");
  const hpTip = (status.breakdown.hp || []).map((row) => `${row.name} ${row.value}`).join("; ");
  if (!/godrick/i.test(hpTip) || !/soreseal/i.test(hpTip)) fail(`HP breakdown should list Vigor sources: ${hpTip}`);
  const absTip = (status.breakdown.absorption.phy || []).map((row) => `${row.name} ${row.value}`).join("; ");
  if (!/damage taken/i.test(absTip)) fail(`physical absorption breakdown should mention Soreseal damage taken: ${absTip}`);

  const faithMix = computeCharacterStatus({
    invested: base,
    armor: [armor.find((a) => a.id === "chest-commoner-s-simple-garb")],
    talismans: [talismans.find((t) => t.id === "two-fingers-heirloom")],
    rune: { name: "Godrick's Great Rune", effect: "Raises all attributes by +5", statBonus: 5 },
    runeActive: true,
    weapons: [],
    equipLoadTable,
    level: 1,
  });
  const mixNames = (faithMix.breakdown.attributes.fai || []).map((row) => `${row.name} ${row.value}`).join("; ");
  if (!/godrick/i.test(mixNames) || !/commoner/i.test(mixNames) || !/two fingers/i.test(mixNames)) {
    fail(`faith mix breakdown missing a contributor: ${mixNames}`);
  }
  if (!/\+5/.test(mixNames) || !/\+1/.test(mixNames)) fail(`faith mix breakdown should include amounts: ${mixNames}`);
  if (faithMix.effective.fai !== 21) fail("Godrick + Commoner's Simple Garb + Two Fingers Heirloom should be Faith 21");

  const armorById = Object.fromEntries(armor.map((a) => [a.id, a]));
  const hidden = {
    "chest-commoner-s-garb": { fai: 1 },
    "chest-commoner-s-simple-garb": { fai: 1 },
    "helm-haligtree-helm": { fai: 1 },
    "helm-haligtree-knight-helm": { fai: 2 },
    "helm-thiollier-s-mask": { arc: 3 },
    "chest-thiollier-s-garb": { arc: 2 },
    "chest-gold-tattoo-chest": { fai: 2 },
    "gauntlets-gold-tattoo-arm": { fai: 1 },
    "legs-gold-tattoo-leg": { fai: 1 },
    "helm-high-priest-hat": { int: 1, arc: 1 },
    "helm-salza-s-hood": { int: 2 },
    "helm-twinsage-glintstone-crown": { int: 6 },
    "helm-queen-s-crescent-crown": { int: 3 },
  };
  for (const [id, want] of Object.entries(hidden)) {
    const item = armorById[id];
    if (!item) fail(`missing armor ${id}`);
    const got = itemAttributeBonuses([item]);
    for (const key of ["vig", "mind", "end", "str", "dex", "int", "fai", "arc"]) {
      if ((got[key] || 0) !== (want[key] || 0)) fail(`${id} ${key} bonus ${got[key]} != ${want[key] || 0}`);
    }
  }
  const snow = armorById["helm-snow-witch-hat"];
  if (snow && itemAttributeBonuses([snow]).int) fail("Snow Witch Hat should not invent an Intelligence bonus");
  const twinsage = computeCharacterStatus({
    invested: base,
    armor: [armorById["helm-twinsage-glintstone-crown"]],
    talismans: [],
    rune: null,
    runeActive: false,
    weapons: [],
    equipLoadTable,
    level: 1,
  });
  if (twinsage.effective.int !== 16) fail("Twinsage Glintstone Crown should add +6 Intelligence");
  if (twinsage.hp >= hpFromVigor(10)) fail("Twinsage Glintstone Crown should reduce max HP");
}

