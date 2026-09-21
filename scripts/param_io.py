"""Read Elden Ring regulation .param files exported from Smithbox."""
from __future__ import annotations

import re
import struct
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAM_DIR = ROOT / "test-save-data"
SMITHBOX_PARAMDEF = (
    ROOT / "Smithbox_2_2_5_2026_08_29_a" / "Assets" / "PARAM" / "ER" / "Defs"
)

# NpcParam.itemLotId_enemy / itemLotId_map. Recomputed from Paramdex if present.
NPC_ITEMLOT_ENEMY = 48
NPC_ITEMLOT_MAP = 52
NPC_SLEEP_ITEMLOT_ENEMY = 592

# EquipParamProtector fields we actually use. Offsets checked against
# wiki-known pieces (Fur Raiment, Gelmir Knight set, Fire Monk, TE armor).
PROTECTOR = {
    "weight": 36,
    "toughnessCorrectRate": 20,
    "resistSleep": 12,
    "resistPoison": 196,
    "resistBlood": 200,
    "resistCurse": 202,
    "neutralDamageCutRate": 228,
    "slashDamageCutRate": 232,
    "blowDamageCutRate": 236,
    "thrustDamageCutRate": 240,
    "magicDamageCutRate": 244,
    "fireDamageCutRate": 248,
    "thunderDamageCutRate": 252,
    "darkDamageCutRate": 284,
}

ITEMLOT_WEAPON = 2
ITEMLOT_ARMOR = 3
ITEMLOT_ACCESSORY = 4
SHOP_WEAPON = 0
SHOP_PROTECTOR = 1
SHOP_ACCESSORY = 2
ITEMLOT_KIND = {2: "weapons", 3: "armor", 4: "talismans"}
SHOP_KIND = {0: "weapons", 1: "armor", 2: "talismans"}


def read_utf16z(buf: bytes, offset: int) -> str:
    if offset <= 0 or offset >= len(buf):
        return ""
    chars: list[str] = []
    pos = offset
    while pos + 1 < len(buf):
        code = struct.unpack_from("<H", buf, pos)[0]
        if code == 0:
            break
        chars.append(chr(code))
        pos += 2
    return "".join(chars).strip()


def iter_param_rows(path: Path) -> list[tuple[int, str, int, bytes]]:
    """Return (id, name, data_offset, row_bytes) for each named row."""
    buf = path.read_bytes()
    if len(buf) < 0x40:
        raise ValueError(f"{path.name} is too small to be a PARAM")
    row_count = struct.unpack_from("<H", buf, 0x0A)[0]
    index = []
    for i in range(row_count):
        off = 0x40 + i * 24
        if off + 24 > len(buf):
            break
        pid = struct.unpack_from("<I", buf, off)[0]
        data_off = struct.unpack_from("<I", buf, off + 8)[0]
        name_off = struct.unpack_from("<I", buf, off + 16)[0]
        index.append((pid, data_off, name_off))
    rows = []
    for i, (pid, data_off, name_off) in enumerate(index):
        name = read_utf16z(buf, name_off)
        next_off = index[i + 1][1] if i + 1 < len(index) else name_off
        end = next_off if next_off > data_off else data_off + 512
        rows.append((pid, name, data_off, buf[data_off:end]))
    return rows


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0]


def i32(data: bytes, off: int) -> int:
    return struct.unpack_from("<i", data, off)[0]


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def absorb(rate: float) -> float:
    return round((1.0 - rate) * 100.0, 1)


def poise(toughness: float) -> float:
    return float(round(toughness * 1000.0))


def protector_stats(data: bytes) -> dict:
    p = PROTECTOR
    return {
        "weight": round(f32(data, p["weight"]), 1),
        "phy": absorb(f32(data, p["neutralDamageCutRate"])),
        "strike": absorb(f32(data, p["blowDamageCutRate"])),
        "slash": absorb(f32(data, p["slashDamageCutRate"])),
        "pierce": absorb(f32(data, p["thrustDamageCutRate"])),
        "magic": absorb(f32(data, p["magicDamageCutRate"])),
        "fire": absorb(f32(data, p["fireDamageCutRate"])),
        "lightning": absorb(f32(data, p["thunderDamageCutRate"])),
        "holy": absorb(f32(data, p["darkDamageCutRate"])),
        "immunity": float(u16(data, p["resistPoison"])),
        "robustness": float(u16(data, p["resistBlood"])),
        "focus": float(u16(data, p["resistSleep"])),
        "vitality": float(u16(data, p["resistCurse"])),
        "poise": poise(f32(data, p["toughnessCorrectRate"])),
    }


def load_protectors(path: Path | None = None) -> dict[int, dict]:
    path = path or PARAM_DIR / "EquipParamProtector.param"
    out = {}
    for pid, name, _off, data in iter_param_rows(path):
        if not name or len(data) < 288:
            continue
        stats = protector_stats(data)
        stats["name"] = name
        out[pid] = stats
    return out


def s8(data: bytes, off: int) -> int:
    return struct.unpack_from("<b", data, off)[0]


_STATUS_ADD = (
    ("addLifeForceStatus", "vig"),
    ("addWillpowerStatus", "mind"),
    ("addEndureStatus", "end"),
    ("addStrengthStatus", "str"),
    ("addDexterityStatus", "dex"),
    ("addMagicStatus", "int"),
    ("addFaithStatus", "fai"),
    ("addLuckStatus", "arc"),
)
_STATUS_POINT = (
    ("changeStrengthPoint", "str"),
    ("changeAgilityPoint", "dex"),
    ("changeMagicPoint", "int"),
    ("changeFaithPoint", "fai"),
    ("changeLuckPoint", "arc"),
)
_RESOURCE_RATE = (
    ("maxHpRate", "hp"),
    ("maxMpRate", "fp"),
    ("maxStaminaRate", "stamina"),
    ("equipWeightChangeRate", "equipLoad"),
)
_STAT_EFFECT_LABELS = {
    "vig": "Vigor",
    "mind": "Mind",
    "end": "Endurance",
    "str": "Strength",
    "dex": "Dexterity",
    "int": "Intelligence",
    "fai": "Faith",
    "arc": "Arcane",
}
_RESOURCE_EFFECT_LABELS = {
    "hp": "max HP",
    "fp": "max FP",
    "stamina": "max Stamina",
    "equipLoad": "Equip Load",
}


def _empty_status_mods() -> dict:
    return {"statBonus": {}, "resourceBonus": {}}


def _speffect_status_mods(data: bytes, offs: dict[str, int]) -> dict:
    mods = _empty_status_mods()
    for field, key in _STATUS_ADD:
        off = offs.get(field)
        if off is None or off >= len(data):
            continue
        n = s8(data, off)
        if n:
            mods["statBonus"][key] = mods["statBonus"].get(key, 0) + n
    for field, key in _STATUS_POINT:
        off = offs.get(field)
        if off is None or off + 4 > len(data):
            continue
        n = i32(data, off)
        if n:
            mods["statBonus"][key] = mods["statBonus"].get(key, 0) + n
    for field, key in _RESOURCE_RATE:
        off = offs.get(field)
        if off is None or off + 4 > len(data):
            continue
        rate = f32(data, off)
        delta = round(rate - 1.0, 4)
        if abs(delta) > 1e-6:
            mods["resourceBonus"][key] = round(mods["resourceBonus"].get(key, 0) + delta, 4)
    return mods


def _merge_status_mods(into: dict, extra: dict) -> dict:
    for key, n in (extra.get("statBonus") or {}).items():
        into["statBonus"][key] = into["statBonus"].get(key, 0) + n
    for key, n in (extra.get("resourceBonus") or {}).items():
        into["resourceBonus"][key] = round(into["resourceBonus"].get(key, 0) + n, 4)
    return into


@lru_cache(maxsize=1)
def _speffect_status_table() -> dict[int, dict]:
    path = PARAM_DIR / "SpEffectParam.param"
    xml = SMITHBOX_PARAMDEF / "SpEffect.xml"
    if not path.exists() or not xml.exists():
        return {}
    offs = paramdef_offsets(xml)
    out: dict[int, dict] = {}
    for pid, _name, _off, data in iter_param_rows(path):
        mods = _speffect_status_mods(data, offs)
        if mods["statBonus"] or mods["resourceBonus"]:
            out[pid] = mods
    return out


def _mods_for_speffect_ids(ids: list[int]) -> dict:
    table = _speffect_status_table()
    mods = _empty_status_mods()
    for eid in ids:
        if eid <= 0:
            continue
        extra = table.get(eid)
        if extra:
            _merge_status_mods(mods, extra)
    if not mods["statBonus"] and not mods["resourceBonus"]:
        return {}
    return mods


@lru_cache(maxsize=1)
def _protector_def_offsets() -> dict[str, int]:
    return paramdef_offsets(SMITHBOX_PARAMDEF / "EquipParamProtector.xml")


@lru_cache(maxsize=1)
def _accessory_def_offsets() -> dict[str, int]:
    return paramdef_offsets(SMITHBOX_PARAMDEF / "EquipParamAccessory.xml")


def protector_status_mods(data: bytes) -> dict:
    xml = SMITHBOX_PARAMDEF / "EquipParamProtector.xml"
    if not xml.exists() or len(data) < 52:
        return {}
    offs = _protector_def_offsets()
    ids = [
        i32(data, offs["residentSpEffectId"]),
        i32(data, offs["residentSpEffectId2"]),
        i32(data, offs["residentSpEffectId3"]),
    ]
    return _mods_for_speffect_ids(ids)


def accessory_status_mods(data: bytes) -> dict:
    xml = SMITHBOX_PARAMDEF / "EquipParamAccessory.xml"
    if not xml.exists() or len(data) < 8:
        return {}
    offs = _accessory_def_offsets()
    ids = [i32(data, offs["refId"])]
    for key in (
        "residentSpEffectId1",
        "residentSpEffectId2",
        "residentSpEffectId3",
        "residentSpEffectId4",
    ):
        off = offs.get(key)
        if off is not None and off + 4 <= len(data):
            ids.append(i32(data, off))
    return _mods_for_speffect_ids(ids)


def catalog_status_mods(kind: str, game_ids: dict) -> dict[str, dict]:
    """catalog id -> {statBonus, resourceBonus} from regulation SpEffects."""
    table = game_ids.get(kind) or {}
    out: dict[str, dict] = {}
    if kind == "armor":
        path = PARAM_DIR / "EquipParamProtector.param"
        reader = protector_status_mods
    elif kind == "talismans":
        path = PARAM_DIR / "EquipParamAccessory.param"
        reader = accessory_status_mods
    else:
        return out
    if not path.exists():
        return out
    for pid, _name, _off, data in iter_param_rows(path):
        cid = table.get(str(pid))
        if not cid:
            continue
        mods = reader(data)
        if mods:
            out[cid] = mods
    return out


def ensure_status_in_effect(effect: str, mods: dict) -> str:
    """Append hidden attribute / resource bonuses the wiki special field omitted."""
    stats = mods.get("statBonus") or {}
    resources = mods.get("resourceBonus") or {}
    text = (effect or "").strip()
    if text in ("-", "—", "–"):
        text = ""
    lower = text.lower()
    missing: list[str] = []
    for key, label in _STAT_EFFECT_LABELS.items():
        n = stats.get(key)
        if n and label.lower() not in lower:
            missing.append(f"{n:+d} {label}")
    for key, label in _RESOURCE_EFFECT_LABELS.items():
        n = resources.get(key)
        if not n:
            continue
        if any(token in lower for token in (label.lower(), key if key != "equipLoad" else "equip load")):
            continue
        pct = round(n * 100, 1)
        pct_s = str(int(pct)) if pct == int(pct) else str(pct)
        missing.append(f"{'+' if n > 0 else ''}{pct_s}% {label}")
    if not missing:
        return text
    extra = "; ".join(missing) + "."
    if not text.strip():
        return extra
    trimmed = text.rstrip()
    if trimmed[-1] not in ".!?":
        trimmed += "."
    return trimmed + " " + extra


def item_lot_armor_ids(*paths: Path) -> set[int]:
    ids: set[int] = set()
    for path in paths:
        if not path.exists():
            continue
        for _pid, _name, _off, data in iter_param_rows(path):
            if len(data) < 64:
                continue
            lot_ids = [i32(data, i * 4) for i in range(8)]
            cats = [i32(data, 32 + i * 4) for i in range(8)]
            for item_id, cat in zip(lot_ids, cats):
                if cat == 3 and item_id > 0:
                    ids.add(item_id)
    return ids


def shop_protector_ids(path: Path | None = None) -> set[int]:
    path = path or PARAM_DIR / "ShopLineupParam.param"
    ids: set[int] = set()
    if not path.exists():
        return ids
    for _pid, _name, _off, data in iter_param_rows(path):
        if len(data) < 24:
            continue
        equip_id = i32(data, 0)
        equip_type = data[23]
        if equip_type == SHOP_PROTECTOR and equip_id > 0:
            ids.add(equip_id)
    return ids


def chara_protector_ids(path: Path | None = None) -> set[int]:
    path = path or PARAM_DIR / "CharaInitParam.param"
    ids: set[int] = set()
    if not path.exists():
        return ids
    for _pid, _name, _off, data in iter_param_rows(path):
        if len(data) < 48:
            continue
        for off in (32, 36, 40, 44):  # helm, chest, gauntlets, legs
            item_id = i32(data, off)
            if item_id > 0:
                ids.add(item_id)
    return ids


def obtainable_armor_ids() -> set[int]:
    """Player-facing: map/enemy item lots and shops. CharaInit includes NPCs."""
    lots = item_lot_armor_ids(
        PARAM_DIR / "ItemLotParam_map.param",
        PARAM_DIR / "ItemLotParam_enemy.param",
    )
    return lots | shop_protector_ids()


def _catalog_id(kind: str, item_id: int, game_ids: dict) -> str | None:
    table = game_ids.get(kind) or {}
    for cand in (item_id, item_id - (item_id % 100)):
        cid = table.get(str(cand))
        if cid:
            return cid
    if kind != "weapons":
        return None
    stripped = item_id - (item_id % 100)
    code = stripped % 10000
    if 100 <= code <= 1200 and code % 100 == 0:
        return table.get(str(stripped - code))
    return None


def lot_id_to_map(lot_id: int) -> str | None:
    """ItemLotParam_map row ID -> mAA_BB_CC_DD. Overworld uses a 10-digit form."""
    pid = int(lot_id)
    if pid >= 1_000_000_000:
        s = f"{pid:010d}"
        prefix, rest = s[:2], s[2:]
        aa, bb, cc = rest[0:2], rest[2:4], rest[4:6]
        if prefix == "10":
            return f"m60_{aa}_{bb}_{cc}_00"
        if prefix == "20":
            return f"m61_{aa}_{bb}_{cc}_00"
        return None
    if pid >= 10_000_000:
        s = f"{pid:08d}"
        return f"m{s[0:2]}_{s[2:4]}_{s[4:6]}_00"
    return None


def iter_map_lot_items(game_ids: dict):
    """Yield (catalog_id, kind, map_id) for every map-lot item, named or not."""
    path = PARAM_DIR / "ItemLotParam_map.param"
    if not path.exists():
        return
    for pid, _name, _off, data in iter_param_rows(path):
        if len(data) < 64:
            continue
        mid = lot_id_to_map(pid)
        if not mid:
            continue
        lot_ids = [i32(data, i * 4) for i in range(8)]
        cats = [i32(data, 32 + i * 4) for i in range(8)]
        for item_id, cat in zip(lot_ids, cats):
            kind = ITEMLOT_KIND.get(cat)
            if not kind or item_id <= 0:
                continue
            cid = _catalog_id(kind, item_id, game_ids)
            if cid:
                yield cid, kind, mid


_FIELD_DEF = re.compile(
    r"^(dummy8|u8|s8|u16|s16|u32|s32|f32)\s+(\w+)(?::(\d+))?(?:\[(\d+)\])?"
)


def paramdef_offsets(xml_path: Path) -> dict[str, int]:
    """Byte offsets from a Smithbox/Paramdex PARAMDEF XML."""
    text = xml_path.read_text(encoding="utf-8")
    offsets: dict[str, int] = {}
    off = 0
    bit = 0
    for defn in re.findall(r'<Field Def="([^"]+)"', text):
        defn = defn.split("=")[0].strip()
        m = _FIELD_DEF.match(defn)
        if not m:
            continue
        typ, name, bits, arr = m.group(1), m.group(2), m.group(3), m.group(4)
        count = int(arr) if arr else 1
        if bits:
            if name not in offsets:
                offsets[name] = off
            bit += int(bits)
            off += bit // 8
            bit %= 8
            continue
        if bit:
            off += (bit + 7) // 8
            bit = 0
        size = {"u8": 1, "s8": 1, "dummy8": 1, "u16": 2, "s16": 2, "u32": 4, "s32": 4, "f32": 4}[typ]
        offsets[name] = off
        off += size * count
    return offsets


def _npc_lot_offsets() -> tuple[int, int, int]:
    xml = SMITHBOX_PARAMDEF / "NpcParam.xml"
    if xml.exists():
        offs = paramdef_offsets(xml)
        return (
            offs["itemLotId_enemy"],
            offs["itemLotId_map"],
            offs.get("sleepCollectorItemLotId_enemy", NPC_SLEEP_ITEMLOT_ENEMY),
        )
    return NPC_ITEMLOT_ENEMY, NPC_ITEMLOT_MAP, NPC_SLEEP_ITEMLOT_ENEMY


@lru_cache(maxsize=1)
def npc_item_lots() -> dict[int, list[int]]:
    """NpcParam ID -> item-lot IDs that can drop (enemy / map / sleep).

    Elden Ring stores one lot ID on the NPC; armor/weapon siblings live in
    the same 100-wide lot family (301000000 greatsword, 301000002 helm, ...).
    """
    path = PARAM_DIR / "NpcParam.param"
    if not path.exists():
        return {}
    e_off, m_off, s_off = _npc_lot_offsets()
    existing = set(_all_lot_items())
    out: dict[int, list[int]] = {}
    for pid, _name, _off, data in iter_param_rows(path):
        if len(data) < max(e_off, m_off, s_off) + 4:
            continue
        family: list[int] = []
        seen: set[int] = set()
        for off in (e_off, m_off, s_off):
            lot = i32(data, off)
            if lot <= 0:
                continue
            base = lot - (lot % 100)
            for n in range(base, base + 100):
                if n in existing and n not in seen:
                    seen.add(n)
                    family.append(n)
        if family:
            out[pid] = family
    return out


def _lot_items(path: Path) -> dict[int, list[tuple[str, int]]]:
    """lot id -> [(kind, item_id), ...]"""
    out: dict[int, list[tuple[str, int]]] = {}
    if not path.exists():
        return out
    for pid, _name, _off, data in iter_param_rows(path):
        if len(data) < 64:
            continue
        items = []
        lot_ids = [i32(data, i * 4) for i in range(8)]
        cats = [i32(data, 32 + i * 4) for i in range(8)]
        for item_id, cat in zip(lot_ids, cats):
            kind = ITEMLOT_KIND.get(cat)
            if kind and item_id > 0:
                items.append((kind, item_id))
        if items:
            out[pid] = items
    return out


@lru_cache(maxsize=1)
def _all_lot_items() -> dict[int, list[tuple[str, int]]]:
    merged: dict[int, list[tuple[str, int]]] = {}
    merged.update(_lot_items(PARAM_DIR / "ItemLotParam_map.param"))
    merged.update(_lot_items(PARAM_DIR / "ItemLotParam_enemy.param"))
    return merged


def iter_msb_enemy_items(game_ids: dict, msb_dir=None):
    """Yield (catalog_id, kind, map_id) from MSB enemy parts -> NpcParam lots."""
    try:
        from msb_io import iter_msb_placements
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from msb_io import iter_msb_placements
    lots_by_npc = npc_item_lots()
    lot_items = _all_lot_items()
    if not lots_by_npc:
        return
    for map_id, npc_ids, _treasure in iter_msb_placements(msb_dir):
        seen = set()
        for npc in npc_ids:
            if npc <= 0 or npc == 1_000_000:
                continue
            if npc in seen:
                continue
            seen.add(npc)
            for lot_id in lots_by_npc.get(npc, ()):
                for kind, item_id in lot_items.get(lot_id, ()):
                    cid = _catalog_id(kind, item_id, game_ids)
                    if cid:
                        yield cid, kind, map_id


def iter_labeled_item_sources(game_ids: dict):
    """Yield (catalog_id, kind, label) from named map/enemy lots and shops."""
    for fname, origin in (
        ("ItemLotParam_map.param", "map"),
        ("ItemLotParam_enemy.param", "enemy"),
    ):
        path = PARAM_DIR / fname
        if not path.exists():
            continue
        for _pid, name, _off, data in iter_param_rows(path):
            if not name or len(data) < 64:
                continue
            lot_ids = [i32(data, i * 4) for i in range(8)]
            cats = [i32(data, 32 + i * 4) for i in range(8)]
            for item_id, cat in zip(lot_ids, cats):
                kind = ITEMLOT_KIND.get(cat)
                if not kind or item_id <= 0:
                    continue
                cid = _catalog_id(kind, item_id, game_ids)
                if cid:
                    yield cid, kind, name, origin

    path = PARAM_DIR / "ShopLineupParam.param"
    if not path.exists():
        return
    for _pid, name, _off, data in iter_param_rows(path):
        if not name or len(data) < 24:
            continue
        kind = SHOP_KIND.get(data[23])
        equip_id = i32(data, 0)
        if not kind or equip_id <= 0:
            continue
        cid = _catalog_id(kind, equip_id, game_ids)
        if cid:
            yield cid, kind, name, "shop"
