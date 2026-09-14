#!/usr/bin/env python3
"""Join MSB enemy placements to NpcParam item lots -> data/msb_maps.json."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from msb_io import find_msb_dir  # noqa: E402
from param_io import iter_msb_enemy_items  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "msb_maps.json"


def main() -> int:
    msb_dir = find_msb_dir()
    if msb_dir is None:
        print("no mapstudio MSBs found (unpack map/mapstudio first)")
        return 1
    game_ids = json.loads((ROOT / "data" / "game_ids.json").read_text(encoding="utf-8"))
    buckets = {"armor": defaultdict(set), "weapons": defaultdict(set), "talismans": defaultdict(set)}
    n = 0
    for cid, kind, mid in iter_msb_enemy_items(game_ids, msb_dir):
        bucket = buckets.get(kind)
        if bucket is None:
            continue
        if mid not in bucket[cid]:
            n += 1
        bucket[cid].add(mid)
    out = {
        kind: {cid: sorted(maps) for cid, maps in sorted(bucket.items())}
        for kind, bucket in buckets.items()
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} from {msb_dir}")
    print(
        "MSB enemies tagged",
        f"{len(out['armor'])} armor,",
        f"{len(out['weapons'])} weapons,",
        f"{len(out['talismans'])} talismans",
        f"({n} item-map pairs)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
