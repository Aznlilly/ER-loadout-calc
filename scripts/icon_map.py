#!/usr/bin/env python3
"""Apply scraped icon paths onto built item JSON (id -> relative path)."""
import json
from pathlib import Path

MAP_PATH = Path("data/raw/icon_map.json")


def load_icon_map():
    if not MAP_PATH.exists():
        return {}
    with MAP_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def apply_icons(items):
    imap = load_icon_map()
    for it in items:
        it["icon"] = imap.get(it["id"], it.get("icon") or "")
    return items
