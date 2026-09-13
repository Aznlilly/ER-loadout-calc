#!/usr/bin/env python3
"""Parse raw weapon requirement-table rows (from Fextralife category pages)
into clean {name, category, str, dex, int, fai, arc, weight, skill} records.

Each stat cell may contain multiple newline-separated values (e.g.
"8\n\nD" = requirement 8, scaling grade D). We only need the requirement
(first token) here since scaling grades come from the global comparison
table instead.
"""
import json
import re
import sys


def first_tok(s):
    if not s:
        return "-"
    parts = [p for p in re.split(r"\n+", s) if p != ""]
    return parts[0] if parts else "-"


def last_tok(s):
    if not s:
        return ""
    parts = [p for p in re.split(r"\n+", s) if p != ""]
    return parts[-1] if parts else ""


def to_num(s):
    s = (s or "").strip()
    if s in ("-", "", "—"):
        return 0
    try:
        return float(s)
    except ValueError:
        return 0


def parse_file(path):
    with open(path) as fh:
        rows = json.load(fh)
    out = []
    for r in rows:
        name = r.get("name", "").strip()
        if not name:
            continue
        out.append({
            "name": name,
            "category": r.get("category", "").replace("_", " "),
            "str": to_num(first_tok(r.get("str", ""))),
            "dex": to_num(first_tok(r.get("dex", ""))),
            "int": to_num(first_tok(r.get("int", ""))),
            "fai": to_num(first_tok(r.get("fai", ""))),
            "arc": to_num(first_tok(r.get("arc", ""))),
            "weight": to_num(r.get("wgt", "")),
            "skill": last_tok(r.get("skill", "")),
        })
    return out


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    data = parse_file(src)
    with open(dst, "w") as out:
        json.dump(data, out, indent=1)
    print(f"parsed {len(data)} weapon requirement records -> {dst}")
