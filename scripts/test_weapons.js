// Weapon variant expansion / ranking (affinities from EquipParamWeapon).
const fs = require("fs");
const path = require("path");
const { expandWeaponVariants, rankWeapons, affinityCodesForWeapon, maxUpgradeForWeapon, clampWeaponMeta } = require("../js/weapons.js");

function fail(msg) {
  console.error("FAIL:", msg);
  process.exit(1);
}
function assert(cond, msg) {
  if (!cond) fail(msg);
}

const weapons = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "weapons.json"), "utf8"));
const variants = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "weapon_variants.json"), "utf8"));
const longsword = weapons.find((w) => w.id === "longsword");
assert(longsword, "catalog has longsword");
assert(variants.longsword && variants.longsword["100"], "Heavy longsword variant");

{
  const rows = expandWeaponVariants([longsword], { includeAffinities: false, variants });
  assert(rows.length === 1 && rows[0].affinity === 0, "affinities off is one standard row");
}

{
  const rows = expandWeaponVariants([longsword], { includeAffinities: true, variants });
  assert(rows.length > 5, `all infusions when no save: ${rows.length}`);
  assert(rows.some((r) => r.affinity === 100 && r.label.startsWith("Heavy ")), "includes Heavy Longsword");
}

{
  const ownedInstances = { longsword: [{ affinity: 100, upgrade: 12 }] };
  const rows = expandWeaponVariants([longsword], {
    includeAffinities: true,
    includeUpgrades: true,
    variants,
    ownedInstances,
  });
  assert(rows.length === 1, "save import ranks only owned infusion");
  assert(rows[0].affinity === 100 && rows[0].upgrade === 12, "Heavy +12 from save");
  assert(rows[0].label === "Heavy Longsword +12", rows[0].label);
}

{
  const stats = { str: 80, dex: 12, int: 9, fai: 9, arc: 7 };
  const ranked = rankWeapons([longsword], stats, {
    onlyMeetable: true,
    includeAffinities: true,
    variants,
  });
  const heavy = ranked.find((r) => r.affinity === 100);
  const keen = ranked.find((r) => r.affinity === 200);
  assert(heavy && keen, "ranks Heavy and Keen longsword");
  assert(heavy.payoff > keen.payoff, "80 STR should prefer Heavy over Keen");
}

{
  const codes = affinityCodesForWeapon(longsword, variants);
  assert(codes[0] === 0, "Standard is always first");
  assert(codes.includes(1200), "Longsword can be Occult");
  assert(maxUpgradeForWeapon(longsword, variants) === 25, "smithing longsword max +25");
  const base = clampWeaponMeta(longsword, undefined, undefined, variants);
  assert(base.affinity === 0 && base.upgrade === 0, "missing meta clamps to Standard +0");
  const occult = clampWeaponMeta(longsword, 1200, 15, variants);
  assert(occult.affinity === 1200 && occult.upgrade === 15, "Occult +15 stays");
  const over = clampWeaponMeta(longsword, 9999, 40, variants);
  assert(over.affinity === 0 && over.upgrade === 25, "invalid infusion falls back to Standard, upgrade caps");
  const moonveil = weapons.find((w) => w.id === "moonveil");
  assert(moonveil, "catalog has moonveil");
  const uniqueCodes = affinityCodesForWeapon(moonveil, variants);
  assert(uniqueCodes.length === 1 && uniqueCodes[0] === 0, "unique weapons only offer Standard");
  assert(maxUpgradeForWeapon(moonveil, variants) === 10, "somber unique max +10");
  const meteor = weapons.find((w) => w.id === "meteorite-staff");
  assert(maxUpgradeForWeapon(meteor, variants) === 0, "Meteorite Staff cannot be upgraded");
}

console.log("weapon variant tests ok");
