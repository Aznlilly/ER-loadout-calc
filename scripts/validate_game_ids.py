"""Validate EquipParam dumps against the catalog and game_ids.json.

Run after exporting .param files and rebuilding game_ids:
  python scripts/export_param_names.py
  python scripts/build_game_ids.py
  python scripts/validate_game_ids.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_game_ids import (  # noqa: E402
    AFFINITY_OFFSETS,
    exact_catalog_id,
    index_catalog,
    match_rows,
    parse_paramdex,
)
from export_param_names import parse_param_rows  # noqa: E402

# Param rows that are real player-facing names but are not in the wiki catalog.
KNOWN_CATALOG_GAPS = {
    "armor": {
        610000: "Ragged Hat",
        610100: "Ragged Armor",
        611000: "Ragged Hat (Altered)",
        611100: "Ragged Armor (Altered)",
        700000: "Brave's Cord Circlet",
        701000: "Brave's Leather Helm",
        702000: "Brave's Battlewear (Altered)",
        920000: "Grass Hair Ornament",
    },
    "weapons": {},
    "talismans": {},
}

SKIP_PARAM_NAME = re.compile(
    r"^(type \d+|head|body|arms|legs|travel hairstyle)$"
    r"|\[npc\]|^unarmed$|arrow|bolt|greatarrow|greatbolt"
    r"|throwing dagger| pot$|^roped |perfume|dart|kukri|fragment"
    r"|stone clump|^explosive stone|^poisoned stone"
    r"|bairn|glintstone scrap|gravity stone|wraith calling"
    r"|aromatic|spraymist|harpoon|lamenter|spritestone"
    r"|call of tibia|surging frenzied|fire coil|innard meat"
    r"|glinting nail|ancestral infant|radahn.s spear"
    r"|fan daggers|miranda.s prayer|cuckoo glintstone",
    re.I,
)

TE_ARMOR_IDS = {
    "Broken Gold Mask": "5340000",
    "Gold Tattoo (Chest)": "5340100",
    "Gold Tattoo (Arm)": "5340200",
    "Gold Tattoo (Leg)": "5340300",
    "Silver Grooved Helm": "5350000",
    "Silver Grooved Armor": "5350100",
    "Silver Grooved Gauntlets": "5350200",
    "Silver Grooved Greaves": "5350300",
    "Leontiel's Hat": "5360000",
    "Leontiel's Hat (Altered)": "5361000",
    "Silver Grooved Armor (Altered)": "5351100",
    "Leontiel's Armor": "5360100",
    "Leontiel's Leather Gloves": "5360200",
    "Leontiel's Boots": "5360300",
    "Steel Helm": "5370000",
    "Steel Armor": "5370100",
    "Steel Gauntlets": "5370200",
    "Steel Greaves": "5370300",
}

TE_WEAPON_IDS = {
    "Leontiel's Greatsword": "3560000",
    "Hefty Scimitar": "8530000",
    "Golden Order Flail": "13510000",
    "Silver Grooved Shield": "31540000",
    "Ritual Thrusting Shield": "62520000",
    "Reverse-Bladed Sword": "64530000",
    "Reed Great Katana": "66530000",
    "Idus Sword": "67530000",
}

STABLE_IDS = {
    "weapons": {
        "2000000": "longsword",
        "2000100": "longsword",
        "31540000": "silver-grooved-shield",
        "67530000": "idus-sword",
    },
    "armor": {
        "1760300": "legs-gelmir-knight-greaves",
        "300300": "legs-fur-leggings",
        "350300": "legs-fire-monk-greaves",
        "40000": "helm-iron-helmet",
        "1100200": "gauntlets-gauntlets",
        "5350000": "helm-silver-grooved-helm",
        "5370000": "helm-steel-helm",
    },
    "talismans": {
        "1000": "crimson-amber-medallion",
        "6110": "ancestral-spirit-s-horn",
    },
}


def load(name: str):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def invert(mapping: dict[str, str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for pid, cid in mapping.items():
        out.setdefault(cid, []).append(pid)
    return out


def playerish(name: str) -> bool:
    n = name.strip()
    if not n or SKIP_PARAM_NAME.search(n):
        return False
    if n.startswith("[") or n.startswith("Virtual "):
        return False
    return True


def main() -> None:
    errors: list[str] = []
    armor = load("armor.json")
    weapons = load("weapons.json")
    talismans = load("talismans.json")
    game_ids = load("game_ids.json")

    kinds = [
        ("armor", armor, ROOT / "data" / "raw" / "EquipParamProtector.txt", ROOT / "test-save-data" / "EquipParamProtector.param", TE_ARMOR_IDS),
        ("weapons", weapons, ROOT / "data" / "raw" / "EquipParamWeapon.txt", ROOT / "test-save-data" / "EquipParamWeapon.param", TE_WEAPON_IDS),
        ("talismans", talismans, ROOT / "data" / "raw" / "EquipParamAccessory.txt", None, {}),
    ]

    print("=== Catalog coverage ===")
    for kind, items, txt, param_path, te_expected in kinds:
        rows = parse_paramdex(txt)
        catalog = index_catalog(items)
        mapping = match_rows(rows, catalog, kind)
        if mapping != game_ids[kind]:
            errors.append(f"{kind}: game_ids.json is stale — rerun scripts/build_game_ids.py")

        inv = invert(game_ids[kind])
        missing = [it["name"] for it in items if it["id"] not in inv]
        te_items = [it for it in items if it.get("source") == "Tarnished Edition"]
        print(f"{kind}: {len(items) - len(missing)}/{len(items)} catalog ids, TE {sum(1 for it in te_items if it['id'] in inv)}/{len(te_items)}")
        if missing:
            errors.append(f"{kind} catalog missing param ids: {missing}")

        for name, pid in te_expected.items():
            got = game_ids[kind].get(pid)
            item = next((it for it in items if it["name"] == name), None)
            if not item:
                errors.append(f"{kind} TE catalog missing {name}")
                continue
            if got != item["id"]:
                errors.append(f"{kind} TE {name}: expected {pid}->{item['id']}, got {got}")
            else:
                extra = len(inv[item["id"]]) - 1
                suffix = f" (+{extra} affinity rows)" if extra > 0 else ""
                print(f"    {name:32} {pid}{suffix}")

        for pid, cid in STABLE_IDS[kind].items():
            if game_ids[kind].get(pid) != cid:
                errors.append(f"{kind} stable id {pid} should be {cid}, got {game_ids[kind].get(pid)}")

        if param_path and param_path.exists():
            from_param = parse_param_rows(param_path)
            from_txt = parse_paramdex(txt)
            if from_param != from_txt:
                errors.append(f"{kind}: {param_path.name} does not match {txt.name}")
            else:
                print(f"  {param_path.name} matches {txt.name} ({len(from_txt)} named rows)")

        gaps = KNOWN_CATALOG_GAPS[kind]
        leftover = []
        mismatches = []
        unexpected_gaps = []
        for pid, name in rows:
            if str(pid) in game_ids[kind]:
                continue
            if not playerish(name):
                continue
            if exact_catalog_id(name, catalog):
                mismatches.append((pid, name))
                continue
            expected = gaps.get(pid)
            if expected is None:
                unexpected_gaps.append((pid, name))
            elif expected != name:
                leftover.append((pid, name, f"allowlist says {expected}"))
        missing_gaps = [f"{pid} {nm}" for pid, nm in gaps.items() if not any(p == pid for p, n in rows)]
        print(f"  known catalog gaps: {len(gaps)}")
        for pid, name in sorted(gaps.items()):
            print(f"    {pid:>10} {name}")
        if mismatches:
            errors.append(f"{kind} name mismatches: {mismatches[:20]}")
        if unexpected_gaps:
            errors.append(f"{kind} unexpected unmatched params: {unexpected_gaps[:20]}")
        if leftover:
            errors.append(f"{kind} allowlist name drift: {leftover}")
        if missing_gaps:
            errors.append(f"{kind} allowlisted ids missing from param dump: {missing_gaps}")

        if kind == "weapons":
            names_by_id = {pid: name for pid, name in rows}
            for pid, name in rows:
                cid = game_ids[kind].get(str(pid))
                if not cid or exact_catalog_id(name, catalog) == cid:
                    continue
                family = pid - (pid % 10000)
                family_exact = {
                    exact_catalog_id(names_by_id[fid], catalog)
                    for off in AFFINITY_OFFSETS
                    if (fid := family + off) in names_by_id
                    and exact_catalog_id(names_by_id[fid], catalog)
                }
                if family_exact and cid not in family_exact:
                    errors.append(
                        f"affinity mismatch {pid} {name} -> {cid} (family exact {family_exact})"
                    )
                    break
        print()

    if errors:
        print("FAILED")
        for err in errors:
            print(" -", err)
        raise SystemExit(1)
    print("ok")


if __name__ == "__main__":
    main()
