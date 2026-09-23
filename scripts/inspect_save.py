"""Dump character names, stats, and inventory/chest counts from a real SL2/CO2."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLOT0 = 0x300
STRIDE = 0x280010
HANDLE_WEAPON = 0x80000000
HANDLE_ARMOR = 0x90000000
HANDLE_ACCESSORY = 0xA0000000
HANDLE_GOODS = 0xB0000000
ITEM_ARMOR = 0x10000000
ITEM_ACCESSORY = 0x20000000
ITEM_GOODS = 0x40000000
GREAT_RUNE_IDS = {191, 192, 193, 194, 195, 196, 8148, 8149, 8150, 8151, 8152, 8153}
HELD_COMMON, HELD_KEY = 0xA80, 0x180
CHEST_COMMON, CHEST_KEY = 0x780, 0x80
EQUIPPED_OFFSETS = [
    ("l1", 0x00),
    ("r1", 0x04),
    ("l2", 0x08),
    ("r2", 0x0C),
    ("l3", 0x10),
    ("r3", 0x14),
    ("helm", 0x30),
    ("chest", 0x34),
    ("gauntlets", 0x38),
    ("legs", 0x3C),
    ("rune", 0x28),
    ("tal1", 0x44),
    ("tal2", 0x48),
    ("tal3", 0x4C),
    ("tal4", 0x50),
]


def gaitem_size(handle: int, mode: str) -> int:
    h = handle & 0xFFFFFFFF
    if h == 0:
        return 8
    kind = h & 0xF0000000
    if kind == HANDLE_WEAPON:
        return 21
    if kind == HANDLE_ARMOR:
        return 16
    if kind == 0xC0000000:
        return 8
    if mode == "wide":
        return 16
    return 8


def u32(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off : off + 4], "little")


def utf16(buf: bytes, off: int, n: int = 32) -> str:
    raw = buf[off : off + n]
    return raw.decode("utf-16le", errors="ignore").split("\x00", 1)[0].strip()


def looks_like_name(name: str) -> bool:
    if not name or len(name) > 16:
        return False
    return all(ch.isalnum() or ch in " .'-" for ch in name)


def decode_item(handle: int, item_id: int) -> tuple[str, int] | None:
    kind = handle & 0xF0000000
    if handle == 0 or item_id in (0, 0xFFFFFFFF):
        return None
    if kind == HANDLE_WEAPON:
        return "weapons", item_id
    if kind == HANDLE_ARMOR:
        raw = item_id if not (item_id & ITEM_ARMOR) else item_id ^ ITEM_ARMOR
        return "armor", raw
    if kind == HANDLE_ACCESSORY:
        raw = item_id if not (item_id & ITEM_ACCESSORY) else item_id ^ ITEM_ACCESSORY
        return "talismans", raw or (handle ^ HANDLE_ACCESSORY)
    if kind == HANDLE_GOODS:
        raw = decode_goods_id(item_id) or (handle ^ HANDLE_GOODS)
        if raw in GREAT_RUNE_IDS:
            return "greatRunes", raw
    return None


def collect(buf: bytes, data_off: int, mode: str):
    version = u32(buf, data_off)
    if version == 0:
        return None
    count = 5120 if version > 81 else 5118
    off = data_off + 0x20
    handles = {}
    owned = {"weapons": [], "armor": [], "talismans": [], "greatRunes": []}
    for _ in range(count):
        handle = u32(buf, off)
        item_id = u32(buf, off + 4)
        size = gaitem_size(handle, mode)
        decoded = decode_item(handle, item_id)
        if decoded:
            kind, pid = decoded
            owned[kind].append(pid)
            handles[handle] = decoded
        off += size
        if off + 8 > len(buf):
            return None
    name = utf16(buf, off + 0x94)
    stats = {
        "vig": u32(buf, off + 0x34),
        "mind": u32(buf, off + 0x38),
        "end": u32(buf, off + 0x3C),
        "str": u32(buf, off + 0x40),
        "dex": u32(buf, off + 0x44),
        "int": u32(buf, off + 0x48),
        "fai": u32(buf, off + 0x4C),
        "arc": u32(buf, off + 0x50),
        "level": u32(buf, off + 0x60),
        "talismanExtra": buf[off + 0xBE],
        "gender": buf[off + 0xB6],
        "greatRuneOn": buf[off + 0xF7] != 0,
    }
    return {"version": version, "owned": owned, "handles": handles, "name": name, "stats": stats, "pgd": off}


def take_inv_item(handle, handles, items):
    if handle in handles:
        items.append(handles[handle])
    elif (handle & 0xF0000000) == HANDLE_ACCESSORY:
        items.append(("talismans", handle ^ HANDLE_ACCESSORY))
    elif (handle & 0xF0000000) == HANDLE_GOODS:
        gid = handle ^ HANDLE_GOODS
        if gid in GREAT_RUNE_IDS:
            items.append(("greatRunes", gid))


def decode_goods_id(item_id: int) -> int:
    iid = item_id & 0xFFFFFFFF
    if iid in (0, 0xFFFFFFFF):
        return 0
    if iid & ITEM_GOODS:
        return iid ^ ITEM_GOODS
    return iid


def decode_great_rune(handle, item_id, handles):
    h = handle & 0xFFFFFFFF
    iid = item_id & 0xFFFFFFFF
    if h in (0, 0xFFFFFFFF) and iid in (0, 0xFFFFFFFF):
        return None
    rec = handles.get(h)
    if rec and rec[0] == "greatRunes":
        return rec
    goods = decode_goods_id(iid)
    if not goods and (h & 0xF0000000) == HANDLE_GOODS:
        goods = h ^ HANDLE_GOODS
    if goods in GREAT_RUNE_IDS:
        return ("greatRunes", goods)
    if (iid & 0xF0000000) == HANDLE_GOODS:
        gid = iid ^ HANDLE_GOODS
        if gid in GREAT_RUNE_IDS:
            return ("greatRunes", gid)
    return None


def first_restored_great_rune(items):
    for kind, pid in items or []:
        if kind == "greatRunes" and 191 <= pid <= 196:
            return kind, pid
    return None


def fill_equipped_great_rune(parsed, held, chest):
    equipped = parsed.get("equipped") or {}
    if equipped.get("rune"):
        return
    if not parsed.get("stats", {}).get("greatRuneOn"):
        return
    rec = first_restored_great_rune(held) or first_restored_great_rune(chest)
    if rec:
        equipped["rune"] = rec
        parsed["equipped"] = equipped


def resolve_equipped(handle, item_id, handles):
    h = handle & 0xFFFFFFFF
    iid = item_id & 0xFFFFFFFF
    if h in (0, 0xFFFFFFFF) and iid in (0, 0xFFFFFFFF):
        return None
    if h in handles:
        return handles[h]
    if (h & 0xF0000000) == HANDLE_ACCESSORY:
        return ("talismans", h ^ HANDLE_ACCESSORY)
    if iid not in (0, 0xFFFFFFFF):
        if iid & ITEM_ARMOR:
            return ("armor", iid ^ ITEM_ARMOR)
        if iid & ITEM_ACCESSORY:
            return ("talismans", iid ^ ITEM_ACCESSORY)
        return ("weapons", iid)
    return None


def read_equipped(buf: bytes, pgd: int, handles: dict):
    ids = pgd + 0x1B0 + 0xD0 + 0x58 + 0x1C
    hs = ids + 0x58
    out = {}
    for name, off in EQUIPPED_OFFSETS:
        hid = u32(buf, hs + off)
        iid = u32(buf, ids + off)
        if name == "rune":
            out[name] = decode_great_rune(hid, iid, handles)
        else:
            out[name] = resolve_equipped(hid, iid, handles)
    return out


def read_inv(buf: bytes, off: int, common_cap: int, key_cap: int, handles: dict):
    common_count = u32(buf, off)
    off += 4
    items = []
    for _ in range(common_cap):
        handle = u32(buf, off)
        off += 12
        take_inv_item(handle, handles, items)
    key_count = u32(buf, off)
    off += 4
    for _ in range(key_cap):
        handle = u32(buf, off)
        off += 12
        take_inv_item(handle, handles, items)
    off += 8
    return off, items, common_count, key_count


def parse_slot(buf: bytes, slot: int, mode: str):
    data_off = SLOT0 + slot * STRIDE + 0x10
    parsed = collect(buf, data_off, mode)
    if not parsed:
        return None
    parsed["equipped"] = read_equipped(buf, parsed["pgd"], parsed["handles"])
    off = parsed["pgd"] + 0x1B0
    off += 0xD0 + 0x58 + 0x1C + 0x58 + 0x58
    off, held, held_c, held_k = read_inv(buf, off, HELD_COMMON, HELD_KEY, parsed["handles"])
    off += 0x74 + 0x8C + 0x18
    proj = u32(buf, off)
    if proj > 20000:
        parsed["proj_bad"] = proj
        parsed["held"] = held
        parsed["held_counts"] = (held_c, held_k)
        parsed["chest"] = []
        fill_equipped_great_rune(parsed, held, [])
        return parsed
    off += 4 + proj * 8
    off += 0x9C + 0xC + 0x12F
    off, chest, chest_c, chest_k = read_inv(buf, off, CHEST_COMMON, CHEST_KEY, parsed["handles"])
    parsed["held"] = held
    parsed["chest"] = chest
    parsed["held_counts"] = (held_c, held_k)
    parsed["chest_counts"] = (chest_c, chest_k)
    parsed["proj"] = proj
    fill_equipped_great_rune(parsed, held, chest)
    return parsed


def summarize(items):
    counts = {"weapons": 0, "armor": 0, "talismans": 0}
    for kind, _ in items:
        counts[kind] += 1
    return counts


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "test-save-data" / "ER0000.co2")
    buf = path.read_bytes()
    print("file", path.name, "size", len(buf), "magic", buf[:4])
    game_ids = json.loads((ROOT / "data" / "game_ids.json").read_text(encoding="utf-8"))

    def named(kind, pid):
        table = game_ids[kind]
        if kind == "weapons":
            base = pid - (pid % 100)
            aff = base % 10000
            if 100 <= aff <= 1200 and aff % 100 == 0:
                base -= aff
            return table.get(str(base))
        return table.get(str(pid))

    for slot in range(10):
        data_off = SLOT0 + slot * STRIDE + 0x10
        ver = u32(buf, data_off)
        if ver == 0:
            continue
        compact = parse_slot(buf, slot, "compact")
        wide = parse_slot(buf, slot, "wide")
        chosen = compact if compact and looks_like_name(compact["name"]) else wide
        if chosen is None:
            print(f"slot {slot} version {ver} unreadable")
            continue
        s = chosen["stats"]
        print(f"\nslot {slot} {chosen['name']!r} RL {s['level']} stats { {k: s[k] for k in ('vig','mind','end','str','dex','int','fai','arc')} }")
        print("  gaitem", {k: len(v) for k, v in chosen["owned"].items()}, "name_ok", looks_like_name(chosen["name"]))
        print("  held", chosen.get("held_counts"), summarize(chosen.get("held", [])), "chest", chosen.get("chest_counts"), summarize(chosen.get("chest", [])), "proj", chosen.get("proj"), "proj_bad", chosen.get("proj_bad"))
        eq_names = []
        for slot, rec in (chosen.get("equipped") or {}).items():
            if not rec:
                continue
            kind, pid = rec
            n = named(kind, pid)
            eq_names.append(f"{slot}={n or hex(pid)}")
        print("  equipped", eq_names or "empty")
        for label, bag in (("held", chosen.get("held", [])), ("chest", chosen.get("chest", []))):
            names = []
            for kind, pid in bag:
                n = named(kind, pid)
                if n:
                    names.append(n)
            print(f"  {label} mapped {len(names)} sample", names[:12])


if __name__ == "__main__":
    main()
