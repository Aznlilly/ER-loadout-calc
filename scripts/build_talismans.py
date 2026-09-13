#!/usr/bin/env python3
"""Build data/talismans.json from data/raw/talismans.json."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icon_map import apply_icons


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


SMALL_WORDS = {"of", "the", "a", "an", "and", "in", "on"}


def smart_title(name):
    """Title-case a name without mangling possessives like "One's" -> "One'S"."""
    words = name.lower().split(" ")
    out = []
    for i, w in enumerate(words):
        if not w:
            out.append(w)
            continue
        if i > 0 and w in SMALL_WORDS:
            out.append(w)
            continue
        # Capitalize first alphabetic character only; leave the rest (so
        # "trina's" -> "Trina's", not "Trina'S").
        for j, ch in enumerate(w):
            if ch.isalpha():
                w = w[:j] + ch.upper() + w[j + 1:]
                break
        out.append(w)
    return " ".join(out)


def main():
    with open("data/raw/talismans.json") as fh:
        rows = json.load(fh)

    out = []
    for r in rows:
        name = smart_title(r["name"].strip())
        a = (r.get("available") or "").lower()
        if "tarnished edition" in a:
            source = "Tarnished Edition"
        elif "shadow of the erdtree" in a:
            source = "Shadow of the Erdtree"
        else:
            source = "Elden Ring"
        out.append({
            "id": slug(name),
            "name": name,
            "effect": r.get("effect", ""),
            "weight": to_num(r.get("weight")),
            "source": source,
            "dlc": source == "Shadow of the Erdtree",
        })

    apply_icons(out)
    with open("data/talismans.json", "w") as f:
        json.dump(out, f, indent=1)

    print(f"wrote {len(out)} talismans to data/talismans.json")
    print("dlc:", sum(1 for t in out if t["dlc"]))


if __name__ == "__main__":
    main()
