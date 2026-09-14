// save-parser.js — read-only Elden Ring PC SL2/CO2 parser for owned gear.
// Layout: https://elden-ring-save-manager.readthedocs.io/en/main/technical/save-file-structure/

const ER_SAVE = (() => {
  const SLOT_COUNT = 10;
  const SLOT0_OFFSET = 0x300;
  const SLOT_STRIDE = 0x280010; // MD5 + 0x280000 data
  const SLOT_DATA_SIZE = 0x280000;
  const UD10_OFFSET = 0x19003A0; // PC BND4: MD5 of UserData10
  const UD10_ACTIVE_SLOTS = 0x1954; // from UD10 data, after MenuSystemSaveLoad
  const UD10_PROFILE_BASE = 0x195E;
  const PROFILE_NAME_BYTES = 0x20;
  const PROFILE_LEVEL = 0x22;
  const PROFILE_SECONDS = 0x26;
  const PROFILE_SIZE = 0x24C;
  const GAITEM_OLD = 5118;
  const GAITEM_NEW = 5120;
  const HANDLE_WEAPON = 0x80000000;
  const HANDLE_ARMOR = 0x90000000;
  const HANDLE_ACCESSORY = 0xA0000000;
  const ITEM_ARMOR_PREFIX = 0x10000000;
  const ITEM_ACCESSORY_PREFIX = 0x20000000;

  const AES_KEY = new Uint8Array([
    0x99, 0xad, 0x2d, 0x50, 0xed, 0xf2, 0xfb, 0x01,
    0xc5, 0xf3, 0xec, 0x3a, 0x2b, 0xca, 0xb6, 0x9d,
  ]);

  const SBOX = new Uint8Array([
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
  ]);

  const INV_SBOX = new Uint8Array(256);
  for (let i = 0; i < 256; i++) INV_SBOX[SBOX[i]] = i;

  const RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36];

  function expandKey(key) {
    const w = new Uint8Array(176);
    w.set(key);
    for (let i = 4; i < 44; i++) {
      let t0 = w[(i - 1) * 4], t1 = w[(i - 1) * 4 + 1], t2 = w[(i - 1) * 4 + 2], t3 = w[(i - 1) * 4 + 3];
      if (i % 4 === 0) {
        const k = t0;
        t0 = SBOX[t1] ^ RCON[i / 4];
        t1 = SBOX[t2];
        t2 = SBOX[t3];
        t3 = SBOX[k];
      }
      const p = (i - 4) * 4;
      w[i * 4] = w[p] ^ t0;
      w[i * 4 + 1] = w[p + 1] ^ t1;
      w[i * 4 + 2] = w[p + 2] ^ t2;
      w[i * 4 + 3] = w[p + 3] ^ t3;
    }
    return w;
  }

  function gmul(a, b) {
    let p = 0;
    for (let i = 0; i < 8; i++) {
      if (b & 1) p ^= a;
      const hi = a & 0x80;
      a = (a << 1) & 0xff;
      if (hi) a ^= 0x1b;
      b >>= 1;
    }
    return p;
  }

  function invMixColumn(s, i) {
    const a = s[i], b = s[i + 1], c = s[i + 2], d = s[i + 3];
    s[i]     = gmul(a, 0x0e) ^ gmul(b, 0x0b) ^ gmul(c, 0x0d) ^ gmul(d, 0x09);
    s[i + 1] = gmul(a, 0x09) ^ gmul(b, 0x0e) ^ gmul(c, 0x0b) ^ gmul(d, 0x0d);
    s[i + 2] = gmul(a, 0x0d) ^ gmul(b, 0x09) ^ gmul(c, 0x0e) ^ gmul(d, 0x0b);
    s[i + 3] = gmul(a, 0x0b) ^ gmul(b, 0x0d) ^ gmul(c, 0x09) ^ gmul(d, 0x0e);
  }

  function decryptBlock(roundKeys, input, output, outOff) {
    const s = new Uint8Array(16);
    s.set(input);
    const rk = (r, c) => roundKeys[r * 16 + c];

    for (let i = 0; i < 16; i++) s[i] ^= rk(10, i);

    for (let round = 9; round >= 1; round--) {
      const t = new Uint8Array(16);
      t[0] = s[0]; t[1] = s[13]; t[2] = s[10]; t[3] = s[7];
      t[4] = s[4]; t[5] = s[1]; t[6] = s[14]; t[7] = s[11];
      t[8] = s[8]; t[9] = s[5]; t[10] = s[2]; t[11] = s[15];
      t[12] = s[12]; t[13] = s[9]; t[14] = s[6]; t[15] = s[3];
      for (let i = 0; i < 16; i++) s[i] = INV_SBOX[t[i]];
      for (let i = 0; i < 16; i++) s[i] ^= rk(round, i);
      invMixColumn(s, 0);
      invMixColumn(s, 4);
      invMixColumn(s, 8);
      invMixColumn(s, 12);
    }

    const t = new Uint8Array(16);
    t[0] = s[0]; t[1] = s[13]; t[2] = s[10]; t[3] = s[7];
    t[4] = s[4]; t[5] = s[1]; t[6] = s[14]; t[7] = s[11];
    t[8] = s[8]; t[9] = s[5]; t[10] = s[2]; t[11] = s[15];
    t[12] = s[12]; t[13] = s[9]; t[14] = s[6]; t[15] = s[3];
    for (let i = 0; i < 16; i++) output[outOff + i] = INV_SBOX[t[i]] ^ rk(0, i);
  }

  function aesCbcDecrypt(key, iv, cipher) {
    if (cipher.length % 16 !== 0) {
      throw new Error("Encrypted save is not a multiple of 16 bytes");
    }
    const roundKeys = expandKey(key);
    const out = new Uint8Array(cipher.length);
    let prev = iv;
    const block = new Uint8Array(16);
    for (let off = 0; off < cipher.length; off += 16) {
      const slice = cipher.subarray(off, off + 16);
      decryptBlock(roundKeys, slice, block, 0);
      for (let i = 0; i < 16; i++) out[off + i] = block[i] ^ prev[i];
      prev = slice;
    }
    return out;
  }

  function startsWith(bytes, ascii, offset = 0) {
    if (bytes.length < offset + ascii.length) return false;
    for (let i = 0; i < ascii.length; i++) {
      if (bytes[offset + i] !== ascii.charCodeAt(i)) return false;
    }
    return true;
  }

  function unwrapSave(bytes) {
    if (startsWith(bytes, "BND4") || startsWith(bytes, "SL2\0")) return bytes;
    if (bytes.length < 32) throw new Error("File is too small to be an Elden Ring save");
    const iv = bytes.subarray(0, 16);
    const decrypted = aesCbcDecrypt(AES_KEY, iv, bytes.subarray(16));
    if (!startsWith(decrypted, "BND4") && !startsWith(decrypted, "SL2\0")) {
      throw new Error("Unsupported save (need a PC Steam .sl2 / Seamless .co2 / same-format mod save)");
    }
    return decrypted;
  }

  function gaitemRecordSize(handle, mode) {
    const h = handle >>> 0;
    if (h === 0) return 8;
    const kind = (h & 0xF0000000) >>> 0;
    if (kind === HANDLE_WEAPON) return 21;
    if (kind === HANDLE_ARMOR) return 16;
    if (kind === 0xC0000000) return 8;
    if (mode === "wide") return 16;
    return 8;
  }

  function looksLikeName(name) {
    if (!name) return false;
    return /^[\p{L}\p{N} .'\-]{1,16}$/u.test(name);
  }

  const HELD_COMMON = 0xA80;
  const HELD_KEY = 0x180;
  const CHEST_COMMON = 0x780;
  const CHEST_KEY = 0x80;
  const MAX_PROJECTILES = 20000;
  const EQUIPPED_SLOT_OFFSETS = {
    l1: 0x00,
    r1: 0x04,
    l2: 0x08,
    r2: 0x0C,
    l3: 0x10,
    r3: 0x14,
    helm: 0x30,
    chest: 0x34,
    gauntlets: 0x38,
    legs: 0x3C,
    tal1: 0x44,
    tal2: 0x48,
    tal3: 0x4C,
    tal4: 0x50,
  };

  function emptyOwned() {
    return { weapons: [], armor: [], talismans: [] };
  }

  function decodeGaItem(handle, itemId) {
    const h = handle >>> 0;
    const rawId = itemId >>> 0;
    const kind = (h & 0xF0000000) >>> 0;
    if (!h || rawId === 0 || rawId === 0xFFFFFFFF) return null;
    if (kind === HANDLE_WEAPON) return { type: "weapons", id: rawId };
    if (kind === HANDLE_ARMOR) {
      const id = (rawId & ITEM_ARMOR_PREFIX) ? (rawId ^ ITEM_ARMOR_PREFIX) >>> 0 : rawId;
      return { type: "armor", id };
    }
    if (kind === HANDLE_ACCESSORY) {
      const id = (rawId & ITEM_ACCESSORY_PREFIX) ? (rawId ^ ITEM_ACCESSORY_PREFIX) >>> 0 : rawId;
      return { type: "talismans", id: id || ((h ^ HANDLE_ACCESSORY) >>> 0) };
    }
    return null;
  }

  function decodeLooseHandle(handle) {
    const h = handle >>> 0;
    if (!h) return null;
    const kind = (h & 0xF0000000) >>> 0;
    if (kind === HANDLE_ACCESSORY) return { type: "talismans", id: (h ^ HANDLE_ACCESSORY) >>> 0 };
    return null;
  }

  function readStats(view, pgdOffset) {
    const extra = view.getUint8(pgdOffset + 0xBE);
    // PlayerGameData +0xB6: 0 = female, 1 = male (same as other From saves).
    const gender = view.getUint8(pgdOffset + 0xB6) === 0 ? "female" : "male";
    return {
      vig: view.getUint32(pgdOffset + 0x34, true),
      mind: view.getUint32(pgdOffset + 0x38, true),
      end: view.getUint32(pgdOffset + 0x3C, true),
      str: view.getUint32(pgdOffset + 0x40, true),
      dex: view.getUint32(pgdOffset + 0x44, true),
      int: view.getUint32(pgdOffset + 0x48, true),
      fai: view.getUint32(pgdOffset + 0x4C, true),
      arc: view.getUint32(pgdOffset + 0x50, true),
      level: view.getUint32(pgdOffset + 0x60, true),
      talismanSlotCount: Math.max(1, Math.min(4, 1 + extra)),
      gender,
    };
  }

  function collectGaItems(view, dataOffset, mode) {
    const version = view.getUint32(dataOffset, true);
    if (version === 0) return null;
    const count = version > 81 ? GAITEM_NEW : GAITEM_OLD;
    let off = dataOffset + 0x20;
    const handleMap = new Map();
    for (let i = 0; i < count; i++) {
      if (off + 8 > view.byteLength) return null;
      const handle = view.getUint32(off, true);
      const itemId = view.getUint32(off + 4, true);
      const size = gaitemRecordSize(handle, mode);
      if (off + size > view.byteLength) return null;
      const decoded = decodeGaItem(handle, itemId);
      if (decoded) handleMap.set(handle >>> 0, decoded);
      off += size;
    }
    const name = readUtf16(view, off + 0x94, 32);
    const stats = readStats(view, off);
    return { version, handleMap, name, stats, pgdOffset: off };
  }

  function parseGaItems(view, dataOffset) {
    const compact = collectGaItems(view, dataOffset, "compact");
    const wide = collectGaItems(view, dataOffset, "wide");
    const compactOk = compact && looksLikeName(compact.name);
    const wideOk = wide && looksLikeName(wide.name);
    if (compactOk && !wideOk) return compact;
    if (wideOk && !compactOk) return wide;
    if (compactOk && wideOk) {
      return compact.handleMap.size >= wide.handleMap.size ? compact : wide;
    }
    return compact || wide;
  }

  function takeInventoryItem(handle, handleMap, owned) {
    const h = handle >>> 0;
    if (!h) return;
    const rec = handleMap.get(h) || decodeLooseHandle(h);
    if (rec) owned[rec.type].push(rec.id);
  }

  function readInventory(view, off, commonCap, keyCap, handleMap) {
    if (off + 8 > view.byteLength) return null;
    const commonCount = view.getUint32(off, true);
    off += 4;
    if (commonCount > commonCap) return null;
    const owned = emptyOwned();
    const commonBytes = commonCap * 12;
    if (off + commonBytes + 4 > view.byteLength) return null;
    for (let i = 0; i < commonCap; i++) {
      takeInventoryItem(view.getUint32(off, true), handleMap, owned);
      off += 12;
    }
    const keyCount = view.getUint32(off, true);
    off += 4;
    if (keyCount > keyCap) return null;
    const keyBytes = keyCap * 12;
    if (off + keyBytes + 8 > view.byteLength) return null;
    for (let i = 0; i < keyCap; i++) {
      takeInventoryItem(view.getUint32(off, true), handleMap, owned);
      off += 12;
    }
    off += 8;
    return { off, owned, commonCount, keyCount };
  }

  function ownedFromHandleMap(handleMap) {
    const owned = emptyOwned();
    for (const rec of handleMap.values()) owned[rec.type].push(rec.id);
    return owned;
  }

  function isEmptyEquip(handle, itemId) {
    const h = handle >>> 0;
    const iid = itemId >>> 0;
    return (!h || h === 0xFFFFFFFF) && (iid === 0 || iid === 0xFFFFFFFF);
  }

  function resolveEquipped(handle, itemId, handleMap) {
    const h = handle >>> 0;
    const iid = itemId >>> 0;
    if (isEmptyEquip(h, iid)) return null;
    const rec = handleMap.get(h) || decodeLooseHandle(h);
    if (rec) return rec;
    if (iid && iid !== 0xFFFFFFFF) {
      if (iid & ITEM_ARMOR_PREFIX) return { type: "armor", id: (iid ^ ITEM_ARMOR_PREFIX) >>> 0 };
      if (iid & ITEM_ACCESSORY_PREFIX) return { type: "talismans", id: (iid ^ ITEM_ACCESSORY_PREFIX) >>> 0 };
      return { type: "weapons", id: iid };
    }
    return null;
  }

  function equippedItemIdsOffset(pgdOffset) {
    return pgdOffset + 0x1B0 + 0xD0 + 0x58 + 0x1C;
  }

  function readEquipped(view, pgdOffset, handleMap) {
    const idsOff = equippedItemIdsOffset(pgdOffset);
    const handlesOff = idsOff + 0x58;
    const equipped = {};
    if (handlesOff + 0x58 > view.byteLength) {
      for (const slot of Object.keys(EQUIPPED_SLOT_OFFSETS)) equipped[slot] = null;
      return equipped;
    }
    for (const [slot, off] of Object.entries(EQUIPPED_SLOT_OFFSETS)) {
      equipped[slot] = resolveEquipped(
        view.getUint32(handlesOff + off, true),
        view.getUint32(idsOff + off, true),
        handleMap
      );
    }
    return equipped;
  }

  function parseSlotBags(view, parsed) {
    const equipped = readEquipped(view, parsed.pgdOffset, parsed.handleMap);
    let off = equippedItemIdsOffset(parsed.pgdOffset) + 0x58 + 0x58;
    const held = readInventory(view, off, HELD_COMMON, HELD_KEY, parsed.handleMap);
    let inventory = held ? held.owned : ownedFromHandleMap(parsed.handleMap);
    let chest = emptyOwned();
    if (!held) return { inventory, chest, equipped };
    off = held.off + 0x74 + 0x8C + 0x18;
    if (off + 4 > view.byteLength) return { inventory, chest, equipped };
    const proj = view.getUint32(off, true);
    if (proj > MAX_PROJECTILES) return { inventory, chest, equipped };
    off += 4 + proj * 8 + 0x9C + 0xC + 0x12F;
    const stored = readInventory(view, off, CHEST_COMMON, CHEST_KEY, parsed.handleMap);
    if (stored) chest = stored.owned;
    return { inventory, chest, equipped };
  }

  function readUtf16(view, offset, maxBytes) {
    const chars = [];
    for (let i = 0; i < maxBytes; i += 2) {
      const c = view.getUint16(offset + i, true);
      if (c === 0) break;
      if (c < 32 && c !== 9) return "";
      chars.push(String.fromCharCode(c));
    }
    return chars.join("").trim();
  }

  function allZero(bytes, offset, length) {
    for (let i = 0; i < length; i++) {
      if (bytes[offset + i] !== 0) return false;
    }
    return true;
  }

  function slotDataOffset(index) {
    return SLOT0_OFFSET + index * SLOT_STRIDE + 0x10;
  }

  function parseProfiles(bytes) {
    const dataStart = UD10_OFFSET + 0x10;
    const activeOff = dataStart + UD10_ACTIVE_SLOTS;
    const base = dataStart + UD10_PROFILE_BASE;
    if (bytes.length < base + SLOT_COUNT * PROFILE_SIZE) return [];
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const profiles = [];
    for (let i = 0; i < SLOT_COUNT; i++) {
      const off = base + i * PROFILE_SIZE;
      const name = readUtf16(view, off, PROFILE_NAME_BYTES);
      const level = view.getUint32(off + PROFILE_LEVEL, true);
      const seconds = view.getUint32(off + PROFILE_SECONDS, true);
      const active = activeOff + i < bytes.length ? bytes[activeOff + i] : 0;
      profiles.push({ index: i, name, level, seconds, active: active !== 0 });
    }
    return profiles;
  }

  function formatPlaytime(seconds) {
    if (!seconds || seconds < 0) return "";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }

  function parseSave(arrayBuffer) {
    const wrapped = new Uint8Array(arrayBuffer);
    const bytes = unwrapSave(wrapped);
    if (bytes.length < slotDataOffset(9) + 0x24) {
      throw new Error("Save file is truncated");
    }
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const profiles = parseProfiles(bytes);
    const characters = [];
    for (let i = 0; i < SLOT_COUNT; i++) {
      const dataOff = slotDataOffset(i);
      if (dataOff + 4 > bytes.length) break;
      if (allZero(bytes, SLOT0_OFFSET + i * SLOT_STRIDE, 16) && view.getUint32(dataOff, true) === 0) {
        continue;
      }
      let parsed;
      try {
        parsed = parseGaItems(view, dataOff);
      } catch (err) {
        continue;
      }
      if (!parsed) continue;
      const bags = parseSlotBags(view, parsed);
      const profile = profiles[i] || {};
      let name = parsed.name;
      if (!looksLikeName(name)) name = profile.name;
      if (!name) name = `Slot ${i + 1}`;
      const stats = parsed.stats || {};
      characters.push({
        index: i,
        name,
        level: stats.level || profile.level || 0,
        seconds: profile.seconds || 0,
        playtime: formatPlaytime(profile.seconds || 0),
        gender: stats.gender || "male",
        stats,
        inventory: bags.inventory,
        chest: bags.chest,
        equipped: bags.equipped,
      });
    }
    if (!characters.length) {
      throw new Error("No characters found in this save");
    }
    return { characters };
  }

  function weaponLookupId(itemId) {
    let id = (itemId >>> 0) - ((itemId >>> 0) % 100);
    return id;
  }

  const AFFINITY_NAMES = {
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

  function decodeWeaponId(itemId) {
    const raw = itemId >>> 0;
    const upgrade = raw % 100;
    const stripped = raw - upgrade;
    const code = stripped % 10000;
    let affinity = 0;
    let baseId = stripped;
    if (code >= 100 && code <= 1200 && code % 100 === 0) {
      affinity = code;
      baseId = stripped - code;
    }
    return { baseId, lookupId: stripped, affinity, upgrade };
  }

  function lookupWeapon(gameIds, itemId) {
    const weapons = gameIds.weapons || {};
    let id = weaponLookupId(itemId);
    if (weapons[id] || weapons[String(id)]) return weapons[id] || weapons[String(id)];
    const affinity = id % 10000;
    if (affinity >= 100 && affinity <= 1200 && affinity % 100 === 0) {
      const base = id - affinity;
      return weapons[base] || weapons[String(base)] || null;
    }
    return null;
  }

  function mapOwned(ownedRaw, gameIds) {
    const owned = { armor: new Set(), weapons: new Set(), talismans: new Set() };
    const instances = {};
    let matched = 0;
    let skipped = 0;

    for (const id of ownedRaw.weapons || []) {
      const catalogId = lookupWeapon(gameIds, id);
      if (catalogId) {
        if (!owned.weapons.has(catalogId)) matched++;
        owned.weapons.add(catalogId);
        const dec = decodeWeaponId(id);
        const list = instances[catalogId] || (instances[catalogId] = []);
        const hit = list.find((x) => x.affinity === dec.affinity);
        if (hit) hit.upgrade = Math.max(hit.upgrade, dec.upgrade);
        else list.push({ affinity: dec.affinity, upgrade: dec.upgrade });
      } else skipped++;
    }
    for (const id of ownedRaw.armor || []) {
      const catalogId = (gameIds.armor || {})[id] || (gameIds.armor || {})[String(id)];
      if (catalogId) {
        if (!owned.armor.has(catalogId)) matched++;
        owned.armor.add(catalogId);
      } else skipped++;
    }
    for (const id of ownedRaw.talismans || []) {
      const catalogId = (gameIds.talismans || {})[id] || (gameIds.talismans || {})[String(id)];
      if (catalogId) {
        if (!owned.talismans.has(catalogId)) matched++;
        owned.talismans.add(catalogId);
      } else skipped++;
    }
    return { owned, matched, skipped, instances };
  }

  function catalogIdFor(rec, gameIds) {
    if (!rec) return null;
    if (rec.type === "weapons") return lookupWeapon(gameIds, rec.id);
    const table = gameIds[rec.type] || {};
    return table[rec.id] || table[String(rec.id)] || null;
  }

  function mapEquipped(equipped, gameIds) {
    const slots = {};
    let filled = 0;
    let skipped = 0;
    for (const slot of Object.keys(EQUIPPED_SLOT_OFFSETS)) {
      const rec = equipped && equipped[slot];
      if (!rec) {
        slots[slot] = null;
        continue;
      }
      const catalogId = catalogIdFor(rec, gameIds);
      if (catalogId) {
        const extra = rec.type === "weapons" ? decodeWeaponId(rec.id) : { affinity: 0, upgrade: 0 };
        slots[slot] = {
          id: catalogId,
          affinity: extra.affinity || 0,
          upgrade: extra.upgrade || 0,
        };
        filled++;
      } else {
        slots[slot] = null;
        skipped++;
      }
    }
    return { slots, filled, skipped };
  }

  return {
    AES_KEY,
    unwrapSave,
    aesCbcDecrypt,
    gaitemRecordSize,
    parseGaItems,
    parseProfiles,
    parseSave,
    weaponLookupId,
    decodeWeaponId,
    lookupWeapon,
    mapOwned,
    mapEquipped,
    mergeOwnedBags: (...bags) => {
      const out = emptyOwned();
      for (const bag of bags) {
        if (!bag) continue;
        for (const type of ["weapons", "armor", "talismans"]) {
          out[type].push(...(bag[type] || []));
        }
      }
      return out;
    },
    HANDLE_WEAPON,
    HANDLE_ARMOR,
    HANDLE_ACCESSORY,
  };
})();

if (typeof module !== "undefined") {
  module.exports = ER_SAVE;
}
