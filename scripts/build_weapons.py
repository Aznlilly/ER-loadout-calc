#!/usr/bin/env python3
"""Merge the raw weapon data sources into data/weapons.json.

Sources (all in data/raw/):
  weapons_global_stats.json  - name,type,phy,mag,fir,lit,hol,cri,sta,
                                str,dex,int,fai,arc (scaling grades),any,upgrade
  weapons_global_guard.json  - name,type,phy,mag,fir,lit,hol (guard negation %),
                                bst,rst,wgt,upgrade
  weapon_reqs_melee_clean.json / weapon_reqs_other_clean.json
                              - name,category,str,dex,int,fai,arc (requirement
                                numbers),weight,skill
  weapon_reqs_other.json      - shield category tables (attack + guard in the
                                same cells). Small/medium/greatshields are not
                                in the global weapon comparison tables.
  Tarnished Pack item pages  - the global comparison tables omit TE weapons,
                                and the melee requirement scrape garbled several
                                rows, so those eight are parsed from wiki
                                infoboxes.
"""
import html as htmlmod
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icon_map import apply_icons
from scrape_icons import fetch_html


SHIELD_CATEGORIES = {
    "Small_Shields": "Small Shields",
    "Medium_Shields": "Medium Shields",
    "Greatshields": "Greatshields",
    "Thrusting_Shields": "Thrusting Shields",
}

# Not in weapons_global_stats.json. Wiki item infoboxes are authoritative.
TARNISHED_WEAPON_PAGES = [
    "Idus Sword",
    "Silver Grooved Shield",
    "Hefty Scimitar",
    "Leontiel's Greatsword",
    "Golden Order Flail",
    "Reverse-Bladed Sword",
    "Reed Great Katana",
    "Ritual Thrusting Shield",
]


def to_num(s):
    s = (s or "").strip()
    if s in ("-", "", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cell_parts(s):
    return [p.strip() for p in re.split(r"\n+", s or "") if p.strip()]


def attack_and_guard(s):
    """Wiki shield cells are 'attack\\nguard'; either side may be '-'."""
    vals = []
    for p in cell_parts(s):
        vals.append(None if p in ("-", "—") else to_num(p))
    if not vals:
        return None, None
    if len(vals) == 1:
        return vals[0], None
    return vals[0], vals[-1]


def req_and_grade(s):
    """Requirement tables swap column order between shield types."""
    req, grade = 0, None
    for p in cell_parts(s):
        if p in ("-", "—"):
            continue
        if re.fullmatch(r"[SABCDE]", p, re.I):
            grade = p.upper()
            continue
        n = to_num(p)
        if n is not None:
            req = n
    return req, grade


def crit_and_boost(row):
    raw = (
        row.get("guardboostcrit")
        or row.get("critguardboost")
        or row.get("critboost")
        or row.get("guardboost")
        or ""
    )
    nums = [to_num(p) for p in cell_parts(raw)]
    nums = [n for n in nums if n is not None]
    if not nums:
        return None, None
    if len(nums) == 1:
        v = nums[0]
        return (v, None) if v >= 100 else (None, v)
    a, b = nums[0], nums[1]
    if a == 100 and b != 100:
        return a, b
    if b == 100 and a != 100:
        return b, a
    if a >= 90 and b < 90:
        return a, b
    if b >= 90 and a < 90:
        return b, a
    return a, b


def skill_name(s):
    parts = cell_parts(s)
    for p in reversed(parts):
        if p in ("-", "—"):
            continue
        if re.fullmatch(r"[\d.]+", p):
            continue
        return p
    return ""


def type_from_category(category):
    if category.endswith("Shields"):
        return category[:-1]
    return category


def category_from_type(weapon_type):
    weapon_type = (weapon_type or "").strip()
    if not weapon_type:
        return ""
    if weapon_type.endswith("Shield"):
        return weapon_type + "s"
    if weapon_type.endswith("s"):
        return weapon_type
    return weapon_type + "s"


def inner_text(html_frag):
    text = re.sub(r"<[^>]+>", " ", html_frag or "")
    text = htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def first_p(html_frag):
    m = re.search(r"<p>([\s\S]*?)</p>", html_frag or "")
    return inner_text(m.group(1) if m else html_frag)


def parse_dash_num(s):
    s = (s or "").strip()
    if s.lower() in ("-", "—", "", "n/a"):
        return None
    return to_num(s)


def parse_req(s):
    n = parse_dash_num(s)
    return n if n is not None else 0


def parse_grade(s):
    s = (s or "").strip().upper()
    if s in ("-", "—", "", "N/A"):
        return None
    if re.fullmatch(r"[SABCDE]", s):
        return s
    return None


def atk_val(s):
    n = parse_dash_num(s)
    if n is None or n == 0:
        return None
    return n


def extract_section(box, class_name):
    m = re.search(
        rf'<div class="er-weapon-stat-section[^"]*{class_name}[^"]*"[\s\S]*?'
        r'(?=<div class="er-weapon-stat-section|<div class="er-weapon-double-section|'
        r'<div class="er-weapon-general"|<div class="er-passive-section"|$)',
        box,
    )
    return m.group(0) if m else ""


def stat_rows(section_html):
    out = {}
    for span, body in re.findall(
        r'<div class="er-stat-row [^"]+">\s*<span>([^<]+)</span>\s*<strong>([\s\S]*?)</strong>',
        section_html,
    ):
        out[span.strip().lower()] = first_p(body)
    return out


def attribute_map(section_html):
    out = {}
    for stat, body in re.findall(
        r'<div class="er-attribute-cell er-attribute-(\w+)">([\s\S]*?)</div>',
        section_html,
    ):
        out[stat.lower()] = first_p(body)
    return out


def general_cell(box, class_name):
    m = re.search(
        rf'<div class="er-general-cell {class_name}">[\s\S]*?<strong>([\s\S]*?)</strong>',
        box,
    )
    return inner_text(m.group(1)) if m else ""


def map_attack(rows):
    return {
        "phy": atk_val(rows.get("phy")),
        "magic": atk_val(rows.get("mag")),
        "fire": atk_val(rows.get("fire")),
        "lightning": atk_val(rows.get("ligt") or rows.get("lightning")),
        "holy": atk_val(rows.get("holy")),
        "critical": parse_dash_num(rows.get("crit")),
    }


def map_guard(rows):
    def g(*keys):
        for key in keys:
            if key in rows:
                return parse_dash_num(rows[key])
        return None

    return {
        "phy": g("phy"),
        "magic": g("mag"),
        "fire": g("fire"),
        "lightning": g("ligt", "lightning"),
        "holy": g("holy"),
        "boost": g("boost"),
        "resistance": None,
    }


def parse_weapon_infobox(html):
    m = re.search(r'<div class="er-weapon-infobox">([\s\S]*?)</div>\s*</aside>', html)
    if not m:
        return None
    box = m.group(1)
    name_m = re.search(r'<div class="er-weapon-name">([\s\S]*?)</div>', box)
    type_m = re.search(r'<div class="er-weapon-type">([\s\S]*?)</div>', box)
    name = first_p(name_m.group(1) if name_m else "")
    weapon_type = first_p(type_m.group(1) if type_m else "")
    if not name:
        return None

    attack_rows = stat_rows(extract_section(box, "er-attack-section"))
    guard_rows = stat_rows(extract_section(box, "er-guard-section"))
    scaling_raw = attribute_map(extract_section(box, "er-scaling-section"))
    req_raw = attribute_map(extract_section(box, "er-requirement-section"))

    skill = general_cell(box, "er-skill-cell")
    if skill.lower() in ("-", "—", "n/a"):
        skill = ""
    upgrade = general_cell(box, "er-upgrade-cell")
    if upgrade.lower() in ("-", "—", "n/a"):
        upgrade = ""
    weight = parse_dash_num(general_cell(box, "er-weight-cell")) or 0

    return {
        "id": slug(name),
        "name": name,
        "type": weapon_type,
        "category": category_from_type(weapon_type),
        "weight": weight,
        "requirements": {
            "str": parse_req(req_raw.get("str")),
            "dex": parse_req(req_raw.get("dex")),
            "int": parse_req(req_raw.get("int")),
            "fai": parse_req(req_raw.get("fai")),
            "arc": parse_req(req_raw.get("arc")),
        },
        "scaling": {
            "str": parse_grade(scaling_raw.get("str")),
            "dex": parse_grade(scaling_raw.get("dex")),
            "int": parse_grade(scaling_raw.get("int")),
            "fai": parse_grade(scaling_raw.get("fai")),
            "arc": parse_grade(scaling_raw.get("arc")),
        },
        "attack": map_attack(attack_rows),
        "staminaDamage": None,
        "guardNegation": map_guard(guard_rows),
        "skill": skill,
        "upgradeMaterial": upgrade,
        "source": "Tarnished Edition",
    }


def scrape_tarnished_weapons():
    """Global comparison tables omit Tarnished Pack weapons; scrape item pages."""
    out = []
    for page in TARNISHED_WEAPON_PAGES:
        html = fetch_html(page)
        if not html:
            print(f"  skip TE weapon {page}: no page")
            continue
        item = parse_weapon_infobox(html)
        if not item:
            print(f"  skip TE weapon {page}: infobox parse failed")
            continue
        out.append(item)
    return out


def scrape_shield_sources():
    """SOTE markers live in the wiki category tables, not the global weapon list."""
    out = {}
    for page in ("Small Shields", "Medium Shields", "Greatshields", "Thrusting Shields"):
        html = fetch_html(page)
        if not html:
            continue
        for row in re.findall(r"<tr[\s\S]*?</tr>", html, flags=re.I):
            is_sote = bool(re.search(r"sote-new|shadow of the erdtree dlc", row, re.I))
            is_te = bool(re.search(r"tarnished edition", row, re.I))
            item_name = None
            for href, title, text in re.findall(
                r'<a[^>]+href="(/[^"]+)"[^>]*(?:title="([^"]*)")?[^>]*>([^<]*)</a>',
                row,
            ):
                if href.lower().startswith("/file:"):
                    continue
                label = htmlmod.unescape((title or text or "").strip())
                if not label or label.lower() in ("sote new", "shadow of the erdtree"):
                    continue
                item_name = label
                break
            if not item_name:
                continue
            if is_sote:
                out[item_name] = "Shadow of the Erdtree"
            elif is_te:
                out[item_name] = "Tarnished Edition"
    return out


def shield_item(row, sources):
    cat_key = row.get("category", "")
    category = SHIELD_CATEGORIES[cat_key]
    name = (row.get("name") or "").strip()
    if not name:
        return None

    reqs = {}
    scaling = {}
    for stat in ("str", "dex", "int", "fai", "arc"):
        req, grade = req_and_grade(row.get(stat, ""))
        reqs[stat] = req
        scaling[stat] = grade

    phy_atk, phy_grd = attack_and_guard(row.get("phy", ""))
    mag_atk, mag_grd = attack_and_guard(row.get("mag", ""))
    fir_atk, fir_grd = attack_and_guard(row.get("fire", ""))
    lit_atk, lit_grd = attack_and_guard(row.get("ligh", "") or row.get("lit", ""))
    hol_atk, hol_grd = attack_and_guard(row.get("holy", ""))
    crit, boost = crit_and_boost(row)

    return {
        "id": slug(name),
        "name": name,
        "type": type_from_category(category),
        "category": category,
        "weight": to_num(row.get("wgt")) or 0,
        "requirements": reqs,
        "scaling": scaling,
        "attack": {
            "phy": phy_atk,
            "magic": mag_atk,
            "fire": fir_atk,
            "lightning": lit_atk,
            "holy": hol_atk,
            "critical": crit,
        },
        "staminaDamage": None,
        "guardNegation": {
            "phy": phy_grd,
            "magic": mag_grd,
            "fire": fir_grd,
            "lightning": lit_grd,
            "holy": hol_grd,
            "boost": boost,
            "resistance": None,
        },
        "skill": skill_name(row.get("skill", "")),
        "upgradeMaterial": "",
        "source": sources.get(name, "Elden Ring"),
    }


def main():
    stats = load("data/raw/weapons_global_stats.json")
    guard = load("data/raw/weapons_global_guard.json")
    reqs = load("data/raw/weapon_reqs_melee_clean.json") + load("data/raw/weapon_reqs_other_clean.json")
    sources = load("data/raw/weapon_sources.json")
    shield_sources = scrape_shield_sources()
    sources.update(shield_sources)

    def norm_key(n):
        n = re.sub(r"\s*\([^)]*\)\s*", "", n)  # drop "(Weapon)" style suffixes
        n = n.replace(".", "")
        return n.strip().lower()

    guard_by_name = {g["name"]: g for g in guard}
    reqs_by_name = {r["name"]: r for r in reqs}
    reqs_by_norm = {norm_key(r["name"]): r for r in reqs}

    out = []
    skipped = []
    for s in stats:
        name = s["name"]
        g = guard_by_name.get(name, {})
        r = reqs_by_name.get(name) or reqs_by_norm.get(norm_key(name))

        scaling = {
            "str": s.get("str") if s.get("str") not in ("-", "", None) else None,
            "dex": s.get("dex") if s.get("dex") not in ("-", "", None) else None,
            "int": s.get("int") if s.get("int") not in ("-", "", None) else None,
            "fai": s.get("fai") if s.get("fai") not in ("-", "", None) else None,
            "arc": s.get("arc") if s.get("arc") not in ("-", "", None) else None,
        }

        if r:
            requirements = {
                "str": r["str"], "dex": r["dex"], "int": r["int"],
                "fai": r["fai"], "arc": r["arc"],
            }
            weight = r["weight"] or to_num(g.get("wgt")) or 0
            skill = r.get("skill") or ""
            category = r.get("category") or s.get("type", "")
        else:
            requirements = {"str": 0, "dex": 0, "int": 0, "fai": 0, "arc": 0}
            weight = to_num(g.get("wgt")) or 0
            skill = ""
            category = s.get("type", "")
            skipped.append(name)

        item = {
            "id": slug(name),
            "name": name,
            "type": s.get("type", ""),
            "category": category,
            "weight": weight,
            "requirements": requirements,
            "scaling": scaling,
            "attack": {
                "phy": to_num(s.get("phy")),
                "magic": to_num(s.get("mag")),
                "fire": to_num(s.get("fir")),
                "lightning": to_num(s.get("lit")),
                "holy": to_num(s.get("hol")),
                "critical": to_num(s.get("cri")),
            },
            "staminaDamage": to_num(s.get("sta")),
            "guardNegation": {
                "phy": to_num(g.get("phy")),
                "magic": to_num(g.get("mag")),
                "fire": to_num(g.get("fir")),
                "lightning": to_num(g.get("lit")),
                "holy": to_num(g.get("hol")),
                "boost": to_num(g.get("bst")),
                "resistance": to_num(g.get("rst")),
            },
            "skill": skill,
            "upgradeMaterial": s.get("upgrade", ""),
            "source": sources.get(name, "Elden Ring"),
        }
        out.append(item)

    existing = {item["name"] for item in out}
    raw_other = load("data/raw/weapon_reqs_other.json")
    added_shields = 0
    for row in raw_other:
        if row.get("category") not in SHIELD_CATEGORIES:
            continue
        name = (row.get("name") or "").strip()
        if not name or name in existing:
            continue
        item = shield_item(row, sources)
        if not item:
            continue
        out.append(item)
        existing.add(name)
        added_shields += 1

    te_weapons = scrape_tarnished_weapons()
    by_name = {item["name"]: i for i, item in enumerate(out)}
    replaced_te = 0
    added_te = 0
    te_sources = {}
    for item in te_weapons:
        te_sources[item["name"]] = "Tarnished Edition"
        if item["name"] in by_name:
            out[by_name[item["name"]]] = item
            replaced_te += 1
        else:
            out.append(item)
            existing.add(item["name"])
            added_te += 1
    sources.update(te_sources)

    apply_icons(out)
    with open("data/weapons.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
        f.write("\n")

    if shield_sources or te_sources:
        sources_path = Path("data/raw/weapon_sources.json")
        merged = load(sources_path)
        merged.update(shield_sources)
        merged.update(te_sources)
        with sources_path.open("w", encoding="utf-8") as f:
            json.dump(merged, f, separators=(",", ":"))
            f.write("\n")

    from collections import Counter
    print(f"wrote {len(out)} weapons to data/weapons.json")
    print(f"added {added_shields} shields from category tables")
    print(f"Tarnished Pack weapons: added {added_te}, replaced {replaced_te}")
    print("by source:", Counter(item["source"] for item in out))
    print("by category:", Counter(item["category"] for item in out if "Shield" in (item.get("category") or "")))
    print(f"{len(skipped)} weapons had no requirement-table match (defaulted to 0 reqs):")
    for n in skipped[:40]:
        print("  -", n)


if __name__ == "__main__":
    main()
