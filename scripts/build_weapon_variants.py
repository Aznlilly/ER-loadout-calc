"""Build per-affinity scaling/requirements from EquipParamWeapon.param."""
from __future__ import annotations

import json
import struct
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from param_io import PARAM_DIR, f32, iter_param_rows  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "weapon_variants.json"

AFFINITY_NAMES = {
    0: "Standard",
    100: "Heavy",
    200: "Keen",
    300: "Quality",
    400: "Fire",
    500: "Flame Art",
    600: "Lightning",
    700: "Sacred",
    800: "Magic",
    900: "Cold",
    1000: "Poison",
    1100: "Blood",
    1200: "Occult",
}

# Early EquipParamWeapon fields (before the late packed flags).
WEIGHT = 16
CORRECT_STR = 36
CORRECT_DEX = 40
CORRECT_INT = 44
CORRECT_FAI = 48


def u8(data: bytes, off: int) -> int:
    return data[off] if 0 <= off < len(data) else 0


def find_reqs(data: bytes) -> tuple[int, int, int, int, int]:
    """Longsword is 10/10/0/0/0; scan for that pattern once, then reuse offset."""
    return (0, 0, 0, 0, 0)


def decode_affinity(param_id: int) -> tuple[int, int]:
    base = param_id - (param_id % 100)
    code = base % 10000
    if 100 <= code <= 1200 and code % 100 == 0:
        return base - code, code
    return base, 0


def letter(percent: float) -> str | None:
    if percent <= 0.05:
        return None
    if percent >= 180:
        return "S"
    if percent >= 140:
        return "A"
    if percent >= 90:
        return "B"
    if percent >= 60:
        return "C"
    if percent >= 25:
        return "D"
    return "E"


def main() -> None:
    path = PARAM_DIR / "EquipParamWeapon.param"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    game_ids = json.loads((ROOT / "data" / "game_ids.json").read_text(encoding="utf-8"))
    weapons = json.loads((ROOT / "data" / "weapons.json").read_text(encoding="utf-8"))
    by_catalog = {w["id"]: w for w in weapons}

    rows = {}
    for pid, name, _off, data in iter_param_rows(path):
        if len(data) < 52:
            continue
        rows[pid] = (name, data)

    # Discover requirement offset from Longsword 2000000 = 10/10/0/0.
    longsword = rows.get(2000000)
    req_off = None
    if longsword:
        data = longsword[1]
        for off in range(80, min(len(data) - 4, 400)):
            if data[off : off + 4] == bytes((10, 10, 0, 0)):
                req_off = off
                break
    luck_off = None
    if req_off is not None:
        # properLuck is later; Occult Longsword 2001200 should have arc req 0 still
        # but high correctLuck. Search correctLuck by Heavy vs Occult change.
        pass

    # Discover correctLuck: Occult longsword has arcane scaling, Standard does not.
    luck_off = CORRECT_STR  # dummy
    occult = rows.get(2001200)
    standard = rows.get(2000000)
    if occult and standard:
        sdata, odata = standard[1], occult[1]
        candidates = []
        for off in range(0, min(len(sdata), len(odata)) - 3, 4):
            sv = f32(sdata, off)
            ov = f32(odata, off)
            if sv < 1 and ov > 40:
                candidates.append((off, sv, ov))
        # prefer later field (correctLuck is after the early four)
        late = [c for c in candidates if c[0] > 48]
        luck_off = (late[-1][0] if late else (candidates[-1][0] if candidates else None))

    print("req_off", req_off, "luck_off", luck_off)
    if standard:
        d = standard[1]
        print("longsword weight", round(f32(d, WEIGHT), 2), "correct", [round(f32(d, o), 1) for o in (CORRECT_STR, CORRECT_DEX, CORRECT_INT, CORRECT_FAI)])
        if req_off is not None:
            print("longsword reqs", list(d[req_off : req_off + 4]))
    if occult and luck_off:
        print("occult luck", round(f32(occult[1], luck_off), 1), "std luck", round(f32(standard[1], luck_off), 1))
    heavy = rows.get(2000100)
    if heavy:
        d = heavy[1]
        print("heavy correct", [round(f32(d, o), 1) for o in (CORRECT_STR, CORRECT_DEX, CORRECT_INT, CORRECT_FAI)])

    out: dict[str, dict] = {}
    for pid, (name, data) in rows.items():
        cid = game_ids["weapons"].get(str(pid))
        if not cid or cid not in by_catalog:
            continue
        _base, code = decode_affinity(pid)
        if code not in AFFINITY_NAMES:
            continue
        reqs = {"str": 0, "dex": 0, "int": 0, "fai": 0, "arc": 0}
        if req_off is not None and req_off + 3 < len(data):
            reqs["str"] = int(data[req_off])
            reqs["dex"] = int(data[req_off + 1])
            reqs["int"] = int(data[req_off + 2])
            reqs["fai"] = int(data[req_off + 3])
        if req_off is not None:
            # properLuck is not adjacent; leave arc 0 unless we find it near req_off+...
            pass
        variant = {
            "affinity": AFFINITY_NAMES[code],
            "weight": round(f32(data, WEIGHT), 1),
            "correct": {
                "str": round(f32(data, CORRECT_STR), 1),
                "dex": round(f32(data, CORRECT_DEX), 1),
                "int": round(f32(data, CORRECT_INT), 1),
                "fai": round(f32(data, CORRECT_FAI), 1),
                "arc": round(f32(data, luck_off), 1) if luck_off is not None else 0.0,
            },
            "requirements": reqs,
        }
        out.setdefault(cid, {})[str(code)] = variant

    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    infusable = sum(1 for v in out.values() if len(v) > 1)
    print(f"wrote {len(out)} weapons, {infusable} infusable, {sum(len(v) for v in out.values())} variants -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
