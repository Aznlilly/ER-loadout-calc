#!/usr/bin/env python3
"""Merge data/raw/{helms,chest,gauntlets,legs}.json into data/armor.json."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icon_map import apply_icons

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
                "effect": r.get("special", "") or "",
                "source": source,
                "dlc": is_dlc,
                "altered": "(altered)" in name.lower(),
            }
            if name in WEIGHT_OVERRIDES:
                item["weight"] = WEIGHT_OVERRIDES[name]
            out.append(item)

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
