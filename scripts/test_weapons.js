// Weapon variant expansion / ranking (affinities from EquipParamWeapon).
const fs = require("fs");
const path = require("path");
const { expandWeaponVariants, rankWeapons } = require("../js/weapons.js");

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

console.log("weapon variant tests ok");
