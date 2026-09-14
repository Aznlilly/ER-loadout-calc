#!/usr/bin/env python3
"""Build data/map_ids.json from Smithbox's map list + our region chips."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_areas import LOCATION_HINTS, DLC_REGIONS, STARTING_GEAR  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "test-save-data" / "map-list.txt"
RAW_COPY = ROOT / "data" / "raw" / "map-list.txt"
OUT = ROOT / "data" / "map_ids.json"

MAP_RE = re.compile(r"(m\d{2}_\d{2}_\d{2}_\d{2})\s*:?(.*)$")

MASTER_REGIONS = [
    STARTING_GEAR,
    "Limgrave", "Weeping Peninsula", "Liurnia of the Lakes", "Caelid", "Dragonbarrow",
    "Altus Plateau", "Mt. Gelmir", "Capital Outskirts", "Leyndell, Royal Capital",
    "Mountaintops of the Giants", "Consecrated Snowfield", "Miquella's Haligtree",
    "Crumbling Farum Azula", "Siofra River", "Ainsel River", "Lake of Rot",
    "Nokron, Eternal City", "Nokstella, Eternal City", "Deeproot Depths",
    "Mohgwyn Palace", "Leyndell, Ashen Capital", "Roundtable Hold",
    *sorted(DLC_REGIONS, key=len, reverse=True),
]

SKIP_TITLES = {
    "unknown", "ending cutscenes",
}

EXTRA_HINTS = [
    ("chapel of anticipation", "Limgrave"),
    ("stone platform", "Leyndell, Ashen Capital"),
    ("specimen storehouse", "Shadow Keep"),
    ("west rampart", "Shadow Keep"),
    ("finger birthing", "Scadu Altus"),
    ("midra's manse", "Abyssal Woods"),
    ("stone coffin fissure", "Gravesite Plain"),
    ("ruin-strewn precipice", "Altus Plateau"),
    ("subterranean shunning", "Leyndell, Royal Capital"),
    ("divine tower of limgrave", "Limgrave"),
    ("divine tower of liurnia", "Liurnia of the Lakes"),
    ("divine tower of caelid", "Caelid"),
    ("divine tower of east altus", "Capital Outskirts"),
    ("divine tower of west altus", "Altus Plateau"),
    ("isolated divine tower", "Weeping Peninsula"),
    ("moonlight altar", "Liurnia of the Lakes"),
    ("four belfries", "Liurnia of the Lakes"),
    ("four belries", "Liurnia of the Lakes"),
    ("gate town", "Liurnia of the Lakes"),
    ("bellum", "Liurnia of the Lakes"),
    ("frenzied flame village", "Liurnia of the Lakes"),
    ("grand lift of dectus", "Altus Plateau"),
    ("volano manor", "Mt. Gelmir"),
    ("volcano manor outskirts", "Mt. Gelmir"),
    ("summonwater", "Limgrave"),
    ("aeonia", "Caelid"),
    ("grand lift of rold", "Mountaintops of the Giants"),
    ("zamor ruins", "Mountaintops of the Giants"),
    ("apostate derelict", "Consecrated Snowfield"),
    ("forge of the giants", "Mountaintops of the Giants"),
    ("freezing lake", "Mountaintops of the Giants"),
    ("royal colosseum", "Leyndell, Royal Capital"),
    ("rauh ruins", "Ancient Ruins of Rauh"),
    ("finger ruins of rhia", "Cerulean Coast"),
    ("finger ruins of dheo", "Scaduview"),
]


def infer_areas(title: str) -> list[str]:
    hay = " " + (title or "").lower() + " "
    if not title or title.strip().lower() in SKIP_TITLES:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for region in sorted((r for r in MASTER_REGIONS if r != STARTING_GEAR), key=len, reverse=True):
        if region.lower() in hay and region not in seen:
            found.append(region)
            seen.add(region)
    for needle, region in list(EXTRA_HINTS) + list(LOCATION_HINTS):
        if needle in hay and region not in seen:
            found.append(region)
            seen.add(region)
    if "Leyndell, Ashen Capital" in seen:
        found = [r for r in found if r != "Leyndell, Royal Capital"]
        seen.discard("Leyndell, Royal Capital")
    return found


def parse_map_list(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    current = None
    buf: list[str] = []
    title = ""

    def flush():
        nonlocal current, buf, title
        if not current:
            return
        blob = " ".join(buf)
        areas = infer_areas(title) or infer_areas(blob)
        out[current] = {"name": title.strip(), "areas": areas}
        current, buf, title = None, [], ""

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = MAP_RE.search(line)
        if m and (line.startswith("m") or line.startswith("(") or " m" in line[:6]):
            flush()
            current = m.group(1)
            title = (m.group(2) or "").strip(" :")
            buf = [title]
            continue
        if current:
            buf.append(line)
    flush()
    return out


def main() -> None:
    src = SRC if SRC.exists() else RAW_COPY
    if not src.exists():
        raise SystemExit(f"missing map list at {SRC} or {RAW_COPY}")
    RAW_COPY.parent.mkdir(parents=True, exist_ok=True)
    if src != RAW_COPY:
        shutil.copyfile(src, RAW_COPY)
    maps = parse_map_list(src.read_text(encoding="utf-8"))
    OUT.write_text(json.dumps(maps, indent=1) + "\n", encoding="utf-8")
    tagged = sum(1 for v in maps.values() if v["areas"])
    missing = [f"{mid} {v['name']}" for mid, v in maps.items() if v["name"] and not v["areas"]]
    print(f"wrote {len(maps)} maps, {tagged} with regions -> {OUT.relative_to(ROOT)}")
    if missing:
        print(f"unmapped named maps ({len(missing)}):")
        for row in missing[:25]:
            print(" ", row)


if __name__ == "__main__":
    main()
