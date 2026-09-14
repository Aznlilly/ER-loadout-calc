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
    assert game_ids["talismans"]["1000"] == "crimson-amber-medallion"
    assert game_ids["talismans"]["6110"] == "ancestral-spirit-s-horn"

    weapons = json.loads((ROOT / "data" / "weapons.json").read_text(encoding="utf-8"))
    talismans = json.loads((ROOT / "data" / "talismans.json").read_text(encoding="utf-8"))
    mapped_w = set(game_ids["weapons"].values())
    mapped_t = set(game_ids["talismans"].values())
    missing_w = [w["name"] for w in weapons if w["id"] not in mapped_w and w.get("source") != "Tarnished Edition"]
    missing_t = [t["name"] for t in talismans if t["id"] not in mapped_t]
    assert not missing_w, missing_w
    assert not missing_t, missing_t
    print("save parser data tests ok")

    save_path = ROOT / "test-save-data" / "ER0000.co2"
    if not save_path.exists():
        print("skip real save (test-save-data/ER0000.co2 not present)")
        return

    sys.path.insert(0, str(ROOT / "scripts"))
    import inspect_save

    buf = save_path.read_bytes()
    assert buf[:4] == b"BND4"
    chosen = inspect_save.parse_slot(buf, 0, "compact")
    assert chosen and chosen["name"] == "Morrigan", chosen and chosen["name"]
    stats = chosen["stats"]
    assert stats["level"] == 104
    assert (stats["vig"], stats["end"], stats["str"]) == (16, 26, 22)
    held = inspect_save.summarize(chosen["held"])
    assert held["talismans"] >= 1, held
    assert held["weapons"] >= 1 and held["armor"] >= 1
    names = []
    for slot in range(10):
        parsed = inspect_save.parse_slot(buf, slot, "compact")
        if parsed:
            names.append(parsed["name"])
    assert "Lilly" in names and "Sablethorn" in names
    print("real save tests ok", names)


if __name__ == "__main__":
    main()
