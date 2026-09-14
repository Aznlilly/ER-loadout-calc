"""Tests for save import data + gaitem sizing (no real .sl2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gaitem_record_size(handle: int, mode: str = "compact") -> int:
    h = handle & 0xFFFFFFFF
    if h == 0:
        return 8
    kind = h & 0xF0000000
    if kind == 0x80000000:
        return 21
    if kind == 0x90000000:
        return 16
    if kind == 0xC0000000:
        return 8
    if mode == "wide":
        return 16
    return 8


def weapon_lookup_id(item_id: int) -> int:
    return item_id - (item_id % 100)


def main() -> None:
    assert gaitem_record_size(0) == 8
    assert gaitem_record_size(0x80000001) == 21
    assert gaitem_record_size(0x90000001) == 16
    assert gaitem_record_size(0xA0000001) == 8
    assert gaitem_record_size(0xA0000001, "wide") == 16
    assert gaitem_record_size(0xC0000001) == 8
    assert weapon_lookup_id(2000010) == 2000000
    assert weapon_lookup_id(2000105) == 2000100

    game_ids = json.loads((ROOT / "data" / "game_ids.json").read_text(encoding="utf-8"))
    assert game_ids["weapons"]["2000000"] == "longsword"
    assert game_ids["weapons"]["2000100"] == "longsword"
    assert game_ids["armor"]["40000"] == "helm-iron-helmet"
    assert game_ids["armor"]["1100200"] == "gauntlets-gauntlets"
    assert game_ids["armor"]["5350000"] == "helm-silver-grooved-helm"
    assert game_ids["armor"]["5370000"] == "helm-steel-helm"
    assert game_ids["weapons"]["31540000"] == "silver-grooved-shield"
    assert game_ids["weapons"]["67530000"] == "idus-sword"
    assert game_ids["talismans"]["1000"] == "crimson-amber-medallion"
    assert game_ids["talismans"]["6110"] == "ancestral-spirit-s-horn"

    weapons = json.loads((ROOT / "data" / "weapons.json").read_text(encoding="utf-8"))
    armor = json.loads((ROOT / "data" / "armor.json").read_text(encoding="utf-8"))
    talismans = json.loads((ROOT / "data" / "talismans.json").read_text(encoding="utf-8"))
    mapped_w = set(game_ids["weapons"].values())
    mapped_a = set(game_ids["armor"].values())
    mapped_t = set(game_ids["talismans"].values())
    missing_w = [w["name"] for w in weapons if w["id"] not in mapped_w]
    missing_a = [a["name"] for a in armor if a["id"] not in mapped_a]
    missing_t = [t["name"] for t in talismans if t["id"] not in mapped_t]
    assert not missing_w, missing_w
    assert not missing_a, missing_a
    assert not missing_t, missing_t
    assert game_ids["weapons"]["1060100"] == "celebrant-s-sickle"
    assert game_ids["weapons"]["14060500"] == "celebrant-s-cleaver"

    sys.path.insert(0, str(ROOT / "scripts"))
    import validate_game_ids

    validate_game_ids.main()
    print("save parser data tests ok")

    save_path = ROOT / "test-save-data" / "ER0000.co2"
    if not save_path.exists():
        print("skip real save (test-save-data/ER0000.co2 not present)")
        return

    import inspect_save

    buf = save_path.read_bytes()
    assert buf[:4] == b"BND4"
    chosen = inspect_save.parse_slot(buf, 0, "compact")
    assert chosen and chosen["name"] == "Morrigan", chosen and chosen["name"]
    stats = chosen["stats"]
    assert stats["level"] == 104
    assert stats["gender"] == 0
    assert (stats["vig"], stats["end"], stats["str"]) == (16, 26, 22)
    profile0 = 0x19003A0 + 0x10 + 0x195E
    assert buf[profile0 : profile0 + 16].decode("utf-16le").rstrip("\x00") == "Morrigan"
    assert int.from_bytes(buf[profile0 + 0x22 : profile0 + 0x26], "little") == 104
    morr_seconds = int.from_bytes(buf[profile0 + 0x26 : profile0 + 0x2A], "little")
    assert 6 * 3600 < morr_seconds < 8 * 3600, morr_seconds
    held = inspect_save.summarize(chosen["held"])
    assert held["talismans"] >= 1, held
    assert held["weapons"] >= 1 and held["armor"] >= 1
    names = []
    for slot in range(10):
        parsed = inspect_save.parse_slot(buf, slot, "compact")
        if parsed:
            names.append(parsed["name"])
    assert "Lilly" in names and "Sablethorn" in names

    def map_eq(parsed, slot):
        rec = (parsed.get("equipped") or {}).get(slot)
        if not rec:
            return None
        kind, pid = rec
        table = game_ids[kind]
        if kind == "weapons":
            base = pid - (pid % 100)
            aff = base % 10000
            if 100 <= aff <= 1200 and aff % 100 == 0:
                base -= aff
            return table.get(str(base))
        return table.get(str(pid))

    assert map_eq(chosen, "r1") == "claymore"
    assert map_eq(chosen, "l1") == "brass-shield"
    assert map_eq(chosen, "chest") == "chest-old-aristocrat-gown"
    assert map_eq(chosen, "tal1") == "assassin-s-crimson-dagger"
    assert map_eq(chosen, "helm") is None
    assert map_eq(chosen, "tal2") is None

    lilly = None
    for slot in range(10):
        parsed = inspect_save.parse_slot(buf, slot, "compact")
        if parsed and parsed["name"] == "Lilly":
            lilly = parsed
            break
    assert lilly, "Lilly character missing from test save"
    assert map_eq(lilly, "r1") == "lordsworn-s-greatsword"
    assert map_eq(lilly, "l1") == "brass-shield"
    assert map_eq(lilly, "l2") == "longbow"
    assert map_eq(lilly, "l3") == "torch"
    assert map_eq(lilly, "chest") == "chest-aristocrat-coat"
    assert map_eq(lilly, "tal1") == "assassin-s-crimson-dagger"
    assert map_eq(lilly, "helm") is None
    assert map_eq(lilly, "r2") is None

    nymera = None
    for slot in range(10):
        parsed = inspect_save.parse_slot(buf, slot, "compact")
        if parsed and parsed["name"] == "Nymera":
            nymera = parsed
            break
    assert nymera, "Nymera character missing from test save"
    assert nymera["stats"]["gender"] == 0
    assert map_eq(nymera, "gauntlets") == "gauntlets-gauntlets"
    assert map_eq(nymera, "helm") == "helm-godrick-soldier-helm"
    assert map_eq(nymera, "chest") == "chest-kaiden-armor"
    print("real save tests ok", names)


if __name__ == "__main__":
    main()
