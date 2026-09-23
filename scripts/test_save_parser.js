// Synthetic tests for the Elden Ring save parser (no real .sl2).
const fs = require("fs");
const path = require("path");
const ER_SAVE = require("../js/save-parser.js");

function fail(msg) {
  console.error("FAIL:", msg);
  process.exit(1);
}

function assert(cond, msg) {
  if (!cond) fail(msg);
}

function hexToBytes(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

// NIST AES-128 ECB vector via CBC with a zero IV.
{
  const key = hexToBytes("000102030405060708090a0b0c0d0e0f");
  const cipher = hexToBytes("69c4e0d86a7b0430d8cdb78070b4c55a");
  const iv = new Uint8Array(16);
  const plain = ER_SAVE.aesCbcDecrypt(key, iv, cipher);
  const got = Array.from(plain).map((b) => b.toString(16).padStart(2, "0")).join("");
  assert(got === "00112233445566778899aabbccddeeff", `AES decrypt mismatch: ${got}`);
}

{
  const bytes = new Uint8Array([0x42, 0x4e, 0x44, 0x34, 0x00]);
  const out = ER_SAVE.unwrapSave(bytes);
  assert(out === bytes, "plaintext BND4 should pass through");
}

assert(ER_SAVE.gaitemRecordSize(0) === 8, "empty gaitem is 8 bytes");
assert(ER_SAVE.gaitemRecordSize(0x80000001) === 21, "weapon gaitem is 21 bytes");
assert(ER_SAVE.gaitemRecordSize(0x90000001) === 16, "armor gaitem is 16 bytes");
assert(ER_SAVE.gaitemRecordSize(0xa0000001) === 8, "accessory gaitem is 8 bytes compact");
assert(ER_SAVE.gaitemRecordSize(0xa0000001, "wide") === 16, "accessory gaitem is 16 bytes wide");
assert(ER_SAVE.gaitemRecordSize(0xc0000001) === 8, "gem gaitem is 8 bytes");

assert(ER_SAVE.weaponLookupId(2000010) === 2000000, "strip +10 upgrade");
assert(ER_SAVE.weaponLookupId(2000105) === 2000100, "strip upgrade from heavy");

{
  const heavy10 = ER_SAVE.decodeWeaponId(2000110);
  assert(heavy10.upgrade === 10, `heavy +10 upgrade ${heavy10.upgrade}`);
  assert(heavy10.affinity === 100, `heavy affinity ${heavy10.affinity}`);
  assert(heavy10.baseId === 2000000, `heavy base ${heavy10.baseId}`);
  const std = ER_SAVE.decodeWeaponId(2000000);
  assert(std.affinity === 0 && std.upgrade === 0, "standard +0");
}

const gameIds = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "game_ids.json"), "utf8"));
assert(ER_SAVE.lookupWeapon(gameIds, 2000000) === "longsword", "longsword base id");
assert(ER_SAVE.lookupWeapon(gameIds, 2000010) === "longsword", "longsword +10");
assert(ER_SAVE.lookupWeapon(gameIds, 2000100) === "longsword", "heavy longsword");
assert(gameIds.armor["40000"] === "helm-iron-helmet", "iron helmet id");
assert(gameIds.armor["1100200"] === "gauntlets-gauntlets", "chain set gauntlets id");
assert(gameIds.armor["5350000"] === "helm-silver-grooved-helm", "silver grooved helm id");
assert(gameIds.weapons["31540000"] === "silver-grooved-shield", "silver grooved shield id");
assert(gameIds.weapons["1060100"] === "celebrant-s-sickle", "infix affinity sickle");
assert(gameIds.talismans["1000"] === "crimson-amber-medallion", "crimson amber id");
assert(gameIds.greatRunes["191"] === "godrick-s-great-rune", "godrick restored id");
assert(gameIds.greatRunes["8148"] === "godrick-s-great-rune", "godrick unrestored id");
assert(gameIds.greatRunes["8150"] === "morgott-s-great-rune", "morgott goods id is not the sharpshot talisman");

const mapped = ER_SAVE.mapOwned({
  weapons: [2000010, 99999999],
  armor: [40000, 0x0eadbeef],
  talismans: [1000, 42],
}, gameIds);
assert(mapped.owned.weapons.has("longsword"), "owned longsword");
assert(mapped.owned.armor.has("helm-iron-helmet"), "owned iron helmet");
assert(mapped.owned.talismans.has("crimson-amber-medallion"), "owned medallion");
assert(mapped.skipped === 3, `expected 3 skipped, got ${mapped.skipped}`);
assert(mapped.matched === 3, `expected 3 matched, got ${mapped.matched}`);
assert(mapped.instances.longsword, "owned instances for longsword");
assert(mapped.instances.longsword[0].upgrade === 10, "owned longsword +10");
assert(mapped.instances.longsword[0].affinity === 0, "owned longsword standard");

{
  const infused = ER_SAVE.mapOwned({ weapons: [2000112, 2000005], armor: [], talismans: [] }, gameIds);
  const inst = infused.instances.longsword;
  const heavy = inst.find((x) => x.affinity === 100);
  const std = inst.find((x) => x.affinity === 0);
  assert(heavy && heavy.upgrade === 12, "keep heavy +12");
  assert(std && std.upgrade === 5, "keep standard +5");
}

{
  const eq = ER_SAVE.mapEquipped({
    r1: { type: "weapons", id: 2000010 },
    helm: { type: "armor", id: 40000 },
    chest: { type: "armor", id: 380100 },
    tal1: { type: "talismans", id: 1000 },
    r2: { type: "weapons", id: 99999999 },
    l1: null,
  }, gameIds);
  assert(eq.slots.r1 && eq.slots.r1.id === "longsword", "map equipped longsword");
  assert(eq.slots.r1.affinity === 0 && eq.slots.r1.upgrade === 10, "equipped longsword +10 standard");
  assert(eq.slots.helm && eq.slots.helm.id === "helm-iron-helmet", "map equipped iron helmet");
  assert(eq.slots.chest && eq.slots.chest.id === "chest-aristocrat-coat", "map equipped aristocrat coat");
  assert(eq.slots.tal1 && eq.slots.tal1.id === "crimson-amber-medallion", "map equipped medallion");
  assert(eq.slots.r2 === null, "unknown equipped weapon becomes empty");
  assert(eq.slots.l1 === null, "empty equipped slot stays empty");
  assert(eq.slots.rune === null, "missing great rune stays empty");
  assert(eq.filled === 4, `expected 4 filled, got ${eq.filled}`);
  assert(eq.skipped === 1, `expected 1 skipped, got ${eq.skipped}`);
}

{
  const godrick = ER_SAVE.mapEquipped({
    rune: { type: "greatRunes", id: 191 },
  }, gameIds);
  assert(godrick.slots.rune && godrick.slots.rune.id === "godrick-s-great-rune", "map restored Godrick great rune");
  const unrestored = ER_SAVE.mapEquipped({
    rune: { type: "greatRunes", id: 8148 },
  }, gameIds);
  assert(unrestored.slots.rune && unrestored.slots.rune.id === "godrick-s-great-rune", "map unrestored Godrick great rune id");
}

assert(ER_SAVE.RUNE_SLOT_OFFSET === 0x28, "equipped Great Rune is ChrAsm slot 10 at +0x28, not the 0x40 gap before talismans");

{
  const buf = new Uint8Array(0x400);
  const view = new DataView(buf.buffer);
  const idsOff = 0x1B0 + 0xD0 + 0x58 + 0x1C;
  view.setUint32(idsOff + ER_SAVE.RUNE_SLOT_OFFSET, 191, true);
  view.setUint32(idsOff + 0x40, 192, true);
  const eq = ER_SAVE.readEquipped(view, 0, new Map());
  assert(eq.rune && eq.rune.type === "greatRunes" && eq.rune.id === 191, `slot 10 should be Godrick, got ${JSON.stringify(eq.rune)}`);
  view.setUint32(idsOff + ER_SAVE.RUNE_SLOT_OFFSET, 0x40000000 + 8148, true);
  const prefixed = ER_SAVE.readEquipped(view, 0, new Map());
  assert(prefixed.rune && prefixed.rune.id === 8148, `prefixed unrestored Godrick id, got ${JSON.stringify(prefixed.rune)}`);
}

// Mini slot: version 1, one weapon, remaining empty gaitems, then PlayerGameData name/level.
{
  const count = 5118;
  const buf = new Uint8Array(0x20 + 21 + (count - 1) * 8 + 0x1B0);
  const view = new DataView(buf.buffer);
  view.setUint32(0, 1, true);
  view.setUint32(0x20, 0x80000001, true);
  view.setUint32(0x24, 2000000, true);
  let off = 0x20 + 21;
  for (let i = 1; i < count; i++) {
    view.setUint32(off, 0, true);
    view.setUint32(off + 4, 0xFFFFFFFF, true);
    off += 8;
  }
  view.setUint32(off + 0x60, 12, true);
  const name = "TestHero";
  for (let i = 0; i < name.length; i++) view.setUint16(off + 0x94 + i * 2, name.charCodeAt(i), true);
  const parsed = ER_SAVE.parseGaItems(view, 0);
  assert(parsed && parsed.name === "TestHero", `name ${parsed && parsed.name}`);
  assert(parsed.stats && parsed.stats.level === 12, `level ${parsed && parsed.stats && parsed.stats.level}`);
  assert(parsed.stats.gender === "female", `default gender ${parsed.stats.gender}`);
  assert(parsed.stats.greatRuneOn === false, "default great rune off");
  view.setUint8(off + 0xB6, 1);
  const male = ER_SAVE.parseGaItems(view, 0);
  assert(male && male.stats.gender === "male", `male gender ${male && male.stats && male.stats.gender}`);
  const recs = [...parsed.handleMap.values()];
  assert(recs.some((r) => r.type === "weapons" && r.id === 2000000), "mini slot weapon id");
}

console.log("save parser tests ok");
