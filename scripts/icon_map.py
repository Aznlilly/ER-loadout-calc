#!/usr/bin/env python3
"""Apply scraped icon paths onto built item JSON (id -> relative path)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "data" / "raw" / "icon_map.json"


def load_icon_map():
    if not MAP_PATH.exists():
        return {}
    with MAP_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def female_icon_path(icon: str) -> str:
    if not icon.endswith(".png"):
        return ""
    cand = icon[:-4] + "-f.png"
    return cand.replace("\\", "/") if (ROOT / cand).exists() else ""


def apply_icons(items):
    imap = load_icon_map()
    for it in items:
        icon = imap.get(it["id"], it.get("icon") or "")
        it["icon"] = icon
        female = female_icon_path(icon)
        if female:
            it["iconFemale"] = female
        else:
            it.pop("iconFemale", None)
    return items
