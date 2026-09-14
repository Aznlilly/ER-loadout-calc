#!/usr/bin/env python3
"""Compare wiki, map lots, MSB enemy drops, and catalog areas."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_areas import infer_areas_from_text, norm  # noqa: E402
from msb_io import (  # noqa: E402
    PART_DUMMY_ENEMY,
    PART_ENEMY,
    _i32,
    _i64,
    _u32,
    decompress_dcx,
    find_msb_dir,
    iter_msb_params,
    iter_msb_placements,
)
from param_io import (  # noqa: E402
    PARAM_DIR,
    SMITHBOX_PARAMDEF,
    _all_lot_items,
    _catalog_id,
    _npc_lot_offsets,
    i32,
    iter_map_lot_items,
    iter_param_rows,
    lot_id_to_map,
    npc_item_lots,
    paramdef_offsets,
    u16,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-save-data" / "source_audit.json"

CASES = [
    "Banished Knight Armor",
    "Banished Knight Armor (Altered)",
    "Banished Knight Helm",
    "Banished Knight Helm (Altered)",
    "Banished Knight Gauntlets",
    "Exile Hood",
    "Scaled Helm",
    "Mausoleum Knight Armor",
    "Foot Soldier Gauntlets",
    "Crucible Axe Helm",
    "Kaiden Helm",
    "Godrick Soldier Helm",
]


def load_catalog():
    out = {}
    for kind, fname in (("armor", "armor.json"), ("weapons", "weapons.json"), ("talismans", "talismans.json")):
        rows = json.loads((ROOT / "data" / fname).read_text(encoding="utf-8"))
        out[kind] = {r["id"]: r for r in rows}
        out[f"{kind}_by_name"] = {r["name"]: r for r in rows}
    return out


def wiki_areas():
    """Region chips inferred from wiki acquire/location text only (no overrides)."""
    cat = load_catalog()
    by_norm = {
        "armor": defaultdict(list),
        "weapons": defaultdict(list),
        "talismans": defaultdict(list),
    }
    for kind in ("armor", "weapons", "talismans"):
        for row in cat[kind].values():
            by_norm[kind][norm(row["name"])].append(row["id"])

    areas = {"armor": defaultdict(set), "weapons": defaultdict(set), "talismans": defaultdict(set)}
    for fname, kind, field in (
        ("helms.json", "armor", "acquire"),
        ("chest.json", "armor", "acquire"),
        ("gauntlets.json", "armor", "acquire"),
        ("legs.json", "armor", "acquire"),
        ("talismans.json", "talismans", "location"),
    ):
        path = ROOT / "data" / "raw" / fname
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            inferred = infer_areas_from_text(row.get(field, "") or "")
            n = norm(row.get("name", ""))
            for cid in by_norm[kind].get(n, ()):
                areas[kind][cid].update(inferred)
    return areas


def resolve_maps(map_ids, mids):
    found = set()
    for mid in mids:
        rec = map_ids.get(mid)
        if rec and rec.get("areas"):
            found.update(rec["areas"])
            continue
        parts = mid.split("_")
        if len(parts) != 4:
            continue
        for cand in (f"{parts[0]}_{parts[1]}_{parts[2]}_00", f"{parts[0]}_{parts[1]}_00_00"):
            rec = map_ids.get(cand)
            if rec and rec.get("areas"):
                found.update(rec["areas"])
                break
    return sorted(found)


def lot_chance_off():
    xml = SMITHBOX_PARAMDEF / "ItemLotParam.xml"
    offs = paramdef_offsets(xml)
    return [offs[f"lotItemBasePoint{i:02d}"] for i in range(1, 9)]


def msb_stats():
    msb_dir = find_msb_dir()
    disable = Counter()
    dummy = 0
    enemy = 0
    treasure_ok = 0
    treasure_mismatch = 0
    treasure_nomap = 0
    maps_with_enemies = 0
    for path in sorted(msb_dir.glob("*.msb.dcx")):
        stem = path.name.split(".")[0]
        if stem.endswith("_99"):
            continue
        buf = decompress_dcx(path.read_bytes())
        had_enemy = False
        for name, entries in iter_msb_params(buf):
            if name == "PARTS_PARAM_ST":
                for eoff in entries:
                    typ = _u32(buf, eoff + 12)
                    if typ == PART_DUMMY_ENEMY:
                        dummy += 1
                    if typ != PART_ENEMY:
                        continue
                    enemy += 1
                    had_enemy = True
                    disable[_u32(buf, eoff + 68)] += 1
            elif name == "EVENT_PARAM_ST":
                for eoff in entries:
                    if _u32(buf, eoff + 12) != 4:
                        continue
                    lot = _i32(buf, eoff + _i64(buf, eoff + 32) + 16)
                    if lot <= 0:
                        continue
                    decoded = lot_id_to_map(lot)
                    if not decoded:
                        treasure_nomap += 1
                    elif decoded.startswith(stem[:10]) or stem.startswith(decoded[:10]):
                        treasure_ok += 1
                    else:
                        treasure_mismatch += 1
        if had_enemy:
            maps_with_enemies += 1
    return {
        "enemyParts": enemy,
        "dummyEnemyParts": dummy,
        "mapsWithEnemies": maps_with_enemies,
        "gameEditionDisable": {str(k): v for k, v in sorted(disable.items())},
        "treasureLotMapMatch": treasure_ok,
        "treasureLotMapMismatch": treasure_mismatch,
        "treasureLotNoMapId": treasure_nomap,
    }


def family_vs_pointed(game_ids):
    """How often the 100-wide family adds catalog items beyond the pointed lot."""
    e_off, m_off, s_off = _npc_lot_offsets()
    existing = _all_lot_items()
    extra_items = 0
    same = 0
    npcs = 0
    extra_examples = []
    for pid, name, _off, data in iter_param_rows(PARAM_DIR / "NpcParam.param"):
        lot = i32(data, e_off)
        if lot <= 0:
            continue
        pointed = set()
        for kind, item_id in existing.get(lot, ()):
            cid = _catalog_id(kind, item_id, game_ids)
            if cid:
                pointed.add((kind, cid))
        family = set()
        base = lot - (lot % 100)
        for n in range(base, base + 100):
            for kind, item_id in existing.get(n, ()):
                cid = _catalog_id(kind, item_id, game_ids)
                if cid:
                    family.add((kind, cid))
        if not family:
            continue
        npcs += 1
        added = family - pointed
        if added:
            extra_items += 1
            if len(extra_examples) < 12:
                extra_examples.append({
                    "npc": pid,
                    "name": name,
                    "lot": lot,
                    "pointed": sorted(f"{k}:{c}" for k, c in pointed),
                    "extra": sorted(f"{k}:{c}" for k, c in added),
                })
        else:
            same += 1
    return {
        "npcsWithCatalogFamily": npcs,
        "familyAddsCatalogItems": extra_items,
        "familyEqualsPointedLot": same,
        "examples": extra_examples,
    }


def bk_lot_chances(game_ids):
    offs = lot_chance_off()
    rows = []
    for pid, name, _off, data in iter_param_rows(PARAM_DIR / "ItemLotParam_enemy.param"):
        if "Banished Knight" not in name:
            continue
        slots = []
        for i in range(8):
            item_id = i32(data, i * 4)
            cat = i32(data, 32 + i * 4)
            if item_id <= 0:
                continue
            kind = {2: "weapons", 3: "armor", 4: "talismans"}.get(cat)
            cid = _catalog_id(kind, item_id, game_ids) if kind else None
            chance = u16(data, offs[i]) if len(data) > offs[i] + 1 else None
            if cid or kind:
                slots.append({"cid": cid, "kind": kind, "itemId": item_id, "chance": chance})
        if slots:
            rows.append({"lot": pid, "name": name, "slots": slots})
    return rows


def case_rows(cat, wiki, msb_areas, maplot_areas):
    out = []
    for name in CASES:
        row = cat["armor_by_name"].get(name) or cat["weapons_by_name"].get(name)
        if not row:
            continue
        kind = "armor" if name in cat["armor_by_name"] else "weapons"
        cid = row["id"]
        out.append({
            "name": name,
            "id": cid,
            "wiki": sorted(wiki[kind].get(cid, ())),
            "mapLots": sorted(maplot_areas[kind].get(cid, ())),
            "msb": sorted(msb_areas[kind].get(cid, ())),
            "catalog": row.get("areas") or [],
        })
    return out


def diffs(cat, wiki, msb_areas, maplot_areas):
    msb_only = []
    wiki_only_generic = []
    for kind in ("armor", "weapons", "talismans"):
        for cid, row in cat[kind].items():
            w = set(wiki[kind].get(cid, ()))
            m = set(msb_areas[kind].get(cid, ()))
            final = set(row.get("areas") or ())
            name = row["name"]
            if m - w:
                msb_only.append({
                    "kind": kind, "name": name, "id": cid,
                    "msbExtra": sorted(m - w), "wiki": sorted(w), "catalog": sorted(final),
                })
            if w - m - set(maplot_areas[kind].get(cid, ())) and m:
                # wiki has regions MSB+maplots don't; only if MSB also tagged it
                pass
    msb_only.sort(key=lambda r: (-len(r["msbExtra"]), r["name"]))
    return msb_only[:40]


def main() -> int:
    game_ids = json.loads((ROOT / "data" / "game_ids.json").read_text(encoding="utf-8"))
    map_ids = json.loads((ROOT / "data" / "map_ids.json").read_text(encoding="utf-8"))
    msb_maps = json.loads((ROOT / "data" / "msb_maps.json").read_text(encoding="utf-8"))
    cat = load_catalog()
    wiki = wiki_areas()

    msb_areas = {k: defaultdict(set) for k in ("armor", "weapons", "talismans")}
    for kind, items in msb_maps.items():
        for cid, mids in items.items():
            msb_areas[kind][cid].update(resolve_maps(map_ids, mids))

    maplot_areas = {k: defaultdict(set) for k in ("armor", "weapons", "talismans")}
    for cid, kind, mid in iter_map_lot_items(game_ids):
        maplot_areas[kind][cid].update(resolve_maps(map_ids, [mid]))

    print("MSB placement stats...")
    stats = msb_stats()
    fam = family_vs_pointed(game_ids)
    bk = bk_lot_chances(game_ids)

    tagged = {
        "armor": sum(1 for r in cat["armor"].values() if r.get("areas")),
        "weapons": sum(1 for r in cat["weapons"].values() if r.get("areas")),
        "talismans": sum(1 for r in cat["talismans"].values() if r.get("areas")),
        "msbArmor": len(msb_maps.get("armor") or {}),
        "msbWeapons": len(msb_maps.get("weapons") or {}),
        "msbTalismans": len(msb_maps.get("talismans") or {}),
        "mapLotArmor": len(maplot_areas["armor"]),
        "wikiArmor": sum(1 for v in wiki["armor"].values() if v),
    }

    report = {
        "counts": tagged,
        "msb": stats,
        "lotFamily": fam,
        "cases": case_rows(cat, wiki, msb_areas, maplot_areas),
        "msbAddsRegionsWikiMissed": diffs(cat, wiki, msb_areas, maplot_areas),
        "banishedKnightLots": bk[:20],
        "npcLotOffsets": list(_npc_lot_offsets()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": tagged, "msb": stats, "lotFamily": {
        k: fam[k] for k in ("npcsWithCatalogFamily", "familyAddsCatalogItems", "familyEqualsPointedLot")
    }}, indent=2))
    print("cases:")
    for row in report["cases"]:
        print(f"  {row['name']}")
        print(f"    wiki    {row['wiki']}")
        print(f"    mapLots {row['mapLots']}")
        print(f"    msb     {row['msb']}")
        print(f"    catalog {row['catalog']}")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
