#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from param_io import PARAM_DIR, i32, iter_param_rows, paramdef_offsets, u16

xml = Path(r"C:\Users\SysAdmin\repos\JS\ER-loadout-calc\Smithbox_2_2_5_2026_08_29_a\Assets\PARAM\ER\Defs\EquipParamProtector.xml")
offs = paramdef_offsets(xml)
print("iconIdM", offs["iconIdM"], "iconIdF", offs["iconIdF"])
for pid, name, _o, data in iter_param_rows(PARAM_DIR / "EquipParamProtector.param"):
    if "chain" in name.lower() or name.strip() in ("Gauntlets", "Chain Gauntlets"):
        im = u16(data, offs["iconIdM"])
        iff = u16(data, offs["iconIdF"])
        print(pid, repr(name), "M", im, "F", iff, "same" if im==iff else "DIFF")
