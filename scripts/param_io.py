"""Read Elden Ring regulation .param files exported from Smithbox."""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAM_DIR = ROOT / "test-save-data"

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
