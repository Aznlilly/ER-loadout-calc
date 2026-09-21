#!/usr/bin/env python3
"""Merge data/raw/{helms,chest,gauntlets,legs}.json into data/armor.json."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icon_map import apply_icons
from param_io import PARAM_DIR, load_protectors

SLOTS = {
    "helms.json": "helm",
    "chest.json": "chest",
    "gauntlets.json": "gauntlets",
    "legs.json": "legs",
}


def to_num(s):
    s = (s or "").strip()
    if s in ("-", "", "—"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def classify_source(available_text):
    # "Tarnished Edition" here means content bundled with the Nintendo
    # Switch 2 "Elden Ring Tarnished Edition" release / the cross-platform
    # "Tarnished Pack" DLC (released August 28, 2026 via Patch 1.17) — it is
    # normal, obtainable content for anyone who owns that pack, exactly like
    # Shadow of the Erdtree is obtainable content for anyone who owns that
    # DLC. It is NOT unobtainable or special/hidden content; don't describe
    # it that way in the UI or docs.
    a = (available_text or "").lower()
    if "tarnished edition" in a:
        return "Tarnished Edition"
    if "shadow of the erdtree" in a:
        return "Shadow of the Erdtree"
    if "base game" in a:
        return "Elden Ring"
    return "Elden Ring"  # default/unknown treated as base


# Wiki comparison tables can be wrong; these win after the raw scrape.
WEIGHT_OVERRIDES = {
    "Mausoleum Knight Armor": 11.8,
}


def overlay_param_stats(items):
    """Replace wiki numbers with EquipParamProtector values when the dump is present."""
    path = PARAM_DIR / "EquipParamProtector.param"
    if not path.exists():
        print("skip param overlay (EquipParamProtector.param not found)")
        return
    from build_game_ids import NAME_OVERRIDES, index_catalog, norm

    protectors = load_protectors(path)
    catalog = index_catalog(items)
    by_id = {it["id"]: it for it in items}
    applied = 0
    changed = 0
    for stats in protectors.values():
        key = NAME_OVERRIDES.get(norm(stats["name"]), norm(stats["name"]))
        cid = catalog.get(key)
        if not cid:
            continue
        item = by_id[cid]
        new_neg = {
            "phy": stats["phy"],
            "strike": stats["strike"],
            "slash": stats["slash"],
            "pierce": stats["pierce"],
            "magic": stats["magic"],
            "fire": stats["fire"],
            "lightning": stats["lightning"],
            "holy": stats["holy"],
        }
        new_res = {
            "immunity": stats["immunity"],
            "robustness": stats["robustness"],
            "focus": stats["focus"],
            "vitality": stats["vitality"],
            "poise": stats["poise"],
        }
        if (
            item["weight"] != stats["weight"]
            or item["negation"] != new_neg
            or item["resistance"] != new_res
        ):
            changed += 1
        item["weight"] = stats["weight"]
        item["negation"] = new_neg
        item["resistance"] = new_res
        applied += 1
    print(f"param overlay: {applied}/{len(items)} pieces, {changed} differed from wiki scrape")


def overlay_param_status(items):
    """Hidden attribute / HP-FP-stamina bonuses from resident SpEffects."""
    from param_io import catalog_status_mods, ensure_status_in_effect

    ids_path = Path("data/game_ids.json")
    if not ids_path.exists():
        print("skip status overlay (data/game_ids.json not found)")
        return
    with open(ids_path) as fh:
        game_ids = json.load(fh)
    mods_by_id = catalog_status_mods("armor", game_ids)
    if not mods_by_id:
        print("skip status overlay (no SpEffect bonuses matched)")
        return
    applied = 0
    for item in items:
        mods = mods_by_id.get(item["id"])
        if not mods:
            continue
        if mods.get("statBonus"):
            item["statBonus"] = mods["statBonus"]
        if mods.get("resourceBonus"):
            item["resourceBonus"] = mods["resourceBonus"]
        item["effect"] = ensure_status_in_effect(item.get("effect") or "", mods)
        applied += 1
    print(f"status overlay: {applied} pieces with hidden attribute/resource bonuses")


def main():
    out = []
    seen_ids = {}
    for fname, slot in SLOTS.items():
        with open(f"data/raw/{fname}") as fh:
            rows = json.load(fh)
        for r in rows:
            name = r["name"].strip()
            source = classify_source(r.get("available", ""))
            is_dlc = source == "Shadow of the Erdtree"
            base_id = slug(f"{slot}-{name}")
            item_id = base_id
            n = 2
            while item_id in seen_ids:
                item_id = f"{base_id}-{n}"
                n += 1
            seen_ids[item_id] = True

            effect = (r.get("special", "") or "").strip()
            if effect in ("-", "—", "–"):
                effect = ""
            item = {
                "id": item_id,
                "name": name,
                "slot": slot,
                "weight": to_num(r.get("weight")),
                "negation": {
                    "phy": to_num(r.get("phy")),
                    "strike": to_num(r.get("strike")),
                    "slash": to_num(r.get("slash")),
                    "pierce": to_num(r.get("pierce")),
                    "magic": to_num(r.get("magic")),
                    "fire": to_num(r.get("fire")),
                    "lightning": to_num(r.get("lightning")),
                    "holy": to_num(r.get("holy")),
                },
                "resistance": {
                    "immunity": to_num(r.get("immunity")),
                    "robustness": to_num(r.get("robustness")),
                    "focus": to_num(r.get("focus")),
                    "vitality": to_num(r.get("vitality")),
                    "poise": to_num(r.get("poise")),
                },
                "effect": effect,
                "source": source,
                "dlc": is_dlc,
                "altered": "(altered)" in name.lower(),
            }
            if name in WEIGHT_OVERRIDES:
                item["weight"] = WEIGHT_OVERRIDES[name]
            out.append(item)

    overlay_param_stats(out)
    overlay_param_status(out)
    apply_icons(out)
    with open("data/armor.json", "w") as f:
        json.dump(out, f, indent=1)

    by_slot = {}
    for a in out:
        by_slot[a["slot"]] = by_slot.get(a["slot"], 0) + 1
    from collections import Counter
    print(f"wrote {len(out)} armor pieces to data/armor.json")
    print("by slot:", by_slot)
    print("by source:", Counter(a["source"] for a in out))


if __name__ == "__main__":
    main()
