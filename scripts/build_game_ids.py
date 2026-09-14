"""Match EquipParam names to catalog ids for save-file import."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "game_ids.json"

AFFINITY_PREFIXES = (
    "Flame Art",
    "Heavy",
    "Keen",
    "Quality",
    "Lightning",
    "Sacred",
    "Magic",
    "Cold",
    "Poison",
    "Bloody",
    "Blood",
    "Occult",
    "Fire",
)

NAME_OVERRIDES = {
    "ancestral spirit s horne": "ancestral spirit s horn",
}

PARAM_ID_OVERRIDES = {
    "talismans": {"6110": "ancestral-spirit-s-horn"},
}


def norm(name: str) -> str:
    s = name.lower().replace("\u2019", "'").replace("`", "'")
    s = s.replace("&", " and ")
    s = re.sub(r"\s*\+\s*", "+", s)
    s = re.sub(r"[^a-z0-9+]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_paramdex(path: Path) -> list[tuple[int, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\d+)\s+(.+)$", line)
        if not m:
            continue
        rows.append((int(m.group(1)), m.group(2).strip()))
    return rows


def catalog_names(item: dict) -> list[str]:
    names = [item["name"]]
    if item.get("altered") and "(altered)" not in item["name"].lower():
        names.append(f"{item['name']} (Altered)")
    return names


def index_catalog(items: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        for name in catalog_names(item):
            key = norm(name)
            out.setdefault(key, item["id"])
    return out


def strip_affinity(name: str) -> str | None:
    for prefix in AFFINITY_PREFIXES:
        if name.startswith(prefix + " "):
            return name[len(prefix) + 1 :]
    return None


def match_rows(rows: list[tuple[int, str]], catalog: dict[str, str], kind: str) -> dict[str, str]:
    mapping: dict[str, str] = dict(PARAM_ID_OVERRIDES.get(kind, {}))
    for param_id, name in rows:
        key = NAME_OVERRIDES.get(norm(name), norm(name))
        catalog_id = catalog.get(key)
        if catalog_id is None:
            stripped = strip_affinity(name)
            if stripped:
                catalog_id = catalog.get(norm(stripped))
        if catalog_id is None:
            continue
        mapping[str(param_id)] = catalog_id
    return mapping


def coverage(items: list[dict], mapping: dict[str, str]) -> tuple[int, list[str]]:
    mapped = set(mapping.values())
    missing = [it["name"] for it in items if it["id"] not in mapped]
    return len(items) - len(missing), missing


def main() -> None:
    armor = json.loads((ROOT / "data" / "armor.json").read_text(encoding="utf-8"))
    weapons = json.loads((ROOT / "data" / "weapons.json").read_text(encoding="utf-8"))
    talismans = json.loads((ROOT / "data" / "talismans.json").read_text(encoding="utf-8"))

    result = {
        "weapons": match_rows(parse_paramdex(RAW / "EquipParamWeapon.txt"), index_catalog(weapons), "weapons"),
        "armor": match_rows(parse_paramdex(RAW / "EquipParamProtector.txt"), index_catalog(armor), "armor"),
        "talismans": match_rows(parse_paramdex(RAW / "EquipParamAccessory.txt"), index_catalog(talismans), "talismans"),
    }

    OUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")

    for label, items, mapping in (
        ("weapons", weapons, result["weapons"]),
        ("armor", armor, result["armor"]),
        ("talismans", talismans, result["talismans"]),
    ):
        hit, missing = coverage(items, mapping)
        te_missing = [n for n, it in ((it["name"], it) for it in items) if it["id"] not in set(mapping.values()) and it.get("source") == "Tarnished Edition"]
        other_missing = [it["name"] for it in items if it["id"] not in set(mapping.values()) and it.get("source") != "Tarnished Edition"]
        print(f"{label}: {hit}/{len(items)} catalog items mapped ({len(mapping)} param ids)")
        if other_missing:
            print(f"  unmatched non-TE ({len(other_missing)}): {other_missing[:20]}")
        if te_missing:
            print(f"  unmatched Tarnished Edition: {len(te_missing)}")


if __name__ == "__main__":
    main()
