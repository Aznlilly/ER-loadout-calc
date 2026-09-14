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

const gameIds = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "game_ids.json"), "utf8"));
assert(ER_SAVE.lookupWeapon(gameIds, 2000000) === "longsword", "longsword base id");
assert(ER_SAVE.lookupWeapon(gameIds, 2000010) === "longsword", "longsword +10");
assert(ER_SAVE.lookupWeapon(gameIds, 2000100) === "longsword", "heavy longsword");
assert(gameIds.armor["40000"] === "helm-iron-helmet", "iron helmet id");
assert(gameIds.talismans["1000"] === "crimson-amber-medallion", "crimson amber id");

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
  const recs = [...parsed.handleMap.values()];
  assert(recs.some((r) => r.type === "weapons" && r.id === 2000000), "mini slot weapon id");
}

console.log("save parser tests ok");
