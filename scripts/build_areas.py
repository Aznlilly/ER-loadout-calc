#!/usr/bin/env python3
"""Tag armor/weapons/talismans with the region(s) where the player obtains them.

Used for progression gating: a Limgrave-only pool should not include a
Volcano Manor quest reward just because the hunt target invades in Limgrave.

Obtain text (armor acquire / talisman location) is the source of truth for
unique/quest/shop items. Wiki per-region item lists fill in generic world
drops and anything with no obtain region yet. Also writes a "wiki" URL.

Existing fields such as "icon" are preserved.
"""
import json
import re
import urllib.parse
from collections import defaultdict
from pathlib import Path

WIKI_BASE = "https://eldenring.wiki.fextralife.com/"

ROOT = Path(__file__).resolve().parents[1]

PIECE_SUFFIXES = tuple(sorted((
    "glintstone crown", "pointy hat", "headband",
    "gauntlets", "manchettes", "leggings", "trousers", "bracers",
    "anklets", "loincloth", "surcoat", "tabard", "raiment",
    "helmet", "greaves", "gloves", "boots", "shoes", "skirt",
    "armor", "robe", "garb", "cloak", "mantle", "attire",
    "wraps", "wrap", "feathers", "crown", "circlet", "visor",
    "coif", "cowl", "hood", "mask", "helm", "hat",
), key=len, reverse=True))

# Longer needles first so "leyndell, ashen capital" wins over "leyndell".
LOCATION_HINTS = [
    ("leyndell, ashen capital", "Leyndell, Ashen Capital"),
    ("ashen capital", "Leyndell, Ashen Capital"),
    ("leyndell, royal capital", "Leyndell, Royal Capital"),
    ("leyndell royal capital", "Leyndell, Royal Capital"),
    ("noble broken mask", "Leyndell, Royal Capital"),
    ("miquella's haligtree", "Miquella's Haligtree"),
    ("elphael, brace of the haligtree", "Miquella's Haligtree"),
    ("elphael", "Miquella's Haligtree"),
    ("haligtree", "Miquella's Haligtree"),
    ("crumbling farum azula", "Crumbling Farum Azula"),
    ("farum azula", "Crumbling Farum Azula"),
    ("mountaintops of the giants", "Mountaintops of the Giants"),
    ("consecrated snowfield", "Consecrated Snowfield"),
    ("liurnia of the lakes", "Liurnia of the Lakes"),
    ("weeping peninsula", "Weeping Peninsula"),
    ("capital outskirts", "Capital Outskirts"),
    ("outer wall battleground", "Capital Outskirts"),
    ("hermit merchant's shack", "Capital Outskirts"),
    ("nokstella, eternal city", "Nokstella, Eternal City"),
    ("nokron, eternal city", "Nokron, Eternal City"),
    ("deeproot depths", "Deeproot Depths"),
    ("mohgwyn palace", "Mohgwyn Palace"),
    ("palace approach ledge-road", "Mohgwyn Palace"),
    ("lake of rot", "Lake of Rot"),
    ("siofra river", "Siofra River"),
    ("ainsel river", "Ainsel River"),
    ("roundtable hold", "Roundtable Hold"),
    ("twin maiden husks", "Roundtable Hold"),
    ("finger reader enia", "Roundtable Hold"),
    ("ancient ruins of rauh", "Ancient Ruins of Rauh"),
    ("rauh base", "Ancient Ruins of Rauh"),
    ("belurat, tower settlement", "Belurat, Tower Settlement"),
    ("belurat tower", "Belurat, Tower Settlement"),
    ("charo's hidden grave", "Charo's Hidden Grave"),
    ("cerulean coast", "Cerulean Coast"),
    ("abyssal woods", "Abyssal Woods"),
    ("abandoned ailing village", "Gravesite Plain"),
    ("church of benediction", "Gravesite Plain"),
    ("scorched ruins", "Gravesite Plain"),
    ("castle ensis", "Gravesite Plain"),
    ("prospect town", "Gravesite Plain"),
    ("fog rift fort", "Gravesite Plain"),
    ("gravesite plain", "Gravesite Plain"),
    ("cathedral of manus metyr", "Scadu Altus"),
    ("bonny village", "Scadu Altus"),
    ("castle watering hole", "Scadu Altus"),
    ("scadu altus", "Scadu Altus"),
    ("fingerbirn", "Scaduview"),
    ("scaduview", "Scaduview"),
    ("shadow keep", "Shadow Keep"),
    ("enir-ilim", "Enir-Ilim"),
    ("enir ilim", "Enir-Ilim"),
    ("jagged peak", "Jagged Peak"),
    ("leyndell", "Leyndell, Royal Capital"),
    ("altus plateau", "Altus Plateau"),
    ("shaded castle", "Altus Plateau"),
    ("windmill village", "Altus Plateau"),
    ("mt. gelmir", "Mt. Gelmir"),
    ("mt gelmir", "Mt. Gelmir"),
    ("volcano manor", "Mt. Gelmir"),
    ("fort laiedd", "Mt. Gelmir"),
    ("hermit village", "Mt. Gelmir"),
    ("dragonbarrow", "Dragonbarrow"),
    ("bestial sanctum", "Dragonbarrow"),
    ("fort faroth", "Dragonbarrow"),
    ("greyoll", "Dragonbarrow"),
    ("redmane castle", "Caelid"),
    ("swamp of aeonia", "Caelid"),
    ("starscourge radahn", "Caelid"),
    ("sellia", "Caelid"),
    ("grand cathedral of dragon communion", "Jagged Peak"),
    ("cathedral of dragon communion", "Caelid"),
    ("caelid", "Caelid"),
    ("raya lucaria", "Liurnia of the Lakes"),
    ("caria manor", "Liurnia of the Lakes"),
    ("academy gate", "Liurnia of the Lakes"),
    ("three sisters", "Liurnia of the Lakes"),
    ("village of the albinaurics", "Liurnia of the Lakes"),
    ("laskyar", "Liurnia of the Lakes"),
    ("jarburg", "Liurnia of the Lakes"),
    ("liurnia", "Liurnia of the Lakes"),
    ("castle morne", "Weeping Peninsula"),
    ("isolated merchant weeping", "Weeping Peninsula"),
    ("stormveil", "Limgrave"),
    ("church of elleh", "Limgrave"),
    ("warmaster's shack", "Limgrave"),
    ("fort haight", "Limgrave"),
    ("gatefront", "Limgrave"),
    ("mistwood", "Limgrave"),
    ("murkwater", "Limgrave"),
    ("coastal cave", "Limgrave"),
    ("agheel", "Limgrave"),
    ("stormhill", "Limgrave"),
    ("limgrave", "Limgrave"),
    ("castle sol", "Mountaintops of the Giants"),
    ("forbidden lands", "Mountaintops of the Giants"),
    ("flame peak", "Mountaintops of the Giants"),
    ("mountaintops", "Mountaintops of the Giants"),
    ("ordina", "Consecrated Snowfield"),
    ("nokstella", "Nokstella, Eternal City"),
    ("nokron", "Nokron, Eternal City"),
    ("siofra", "Siofra River"),
    ("ainsel", "Ainsel River"),
    ("deeproot", "Deeproot Depths"),
    ("mohgwyn", "Mohgwyn Palace"),
    ("gelmir", "Mt. Gelmir"),
    ("belurat", "Belurat, Tower Settlement"),
    ("war counselor iji", "Liurnia of the Lakes"),
    ("preceptor seluvis", "Liurnia of the Lakes"),
    ("ravine north", "Ancient Ruins of Rauh"),
    ("altus tunnel", "Altus Plateau"),
    ("sainted hero", "Altus Plateau"),
    ("abandoned cave", "Caelid"),
    ("great-jar", "Dragonbarrow"),
    ("great jar", "Dragonbarrow"),
    ("caelid colosseum", "Dragonbarrow"),
    ("bellum church", "Liurnia of the Lakes"),
    ("liurnia lake shore", "Liurnia of the Lakes"),
    ("knight leontiel", "Caelid"),
    ("radahn's arena", "Caelid"),
    ("radahn arena", "Caelid"),
]

NAME_ALIASES = {
    "golden scarab": ["gold scarab"],
    "gold scarab": ["golden scarab"],
    "beast claw (weapon)": ["beast claw"],
    "beast claw": ["beast claw"],
}


DLC_REGIONS = {
    "Gravesite Plain", "Scadu Altus", "Ancient Ruins of Rauh", "Cerulean Coast",
    "Charo's Hidden Grave", "Jagged Peak", "Abyssal Woods", "Scaduview",
    "Shadow Keep", "Enir-Ilim", "Belurat, Tower Settlement",
}

STARTING_GEAR = "Starting Gear"

# TE kits (shop text omits "starting") plus every class's starting arms.
# Base-game armor kits are inferred from acquire prose.
STARTING_GEAR_EXTRA = {
    "Silver Grooved Helm", "Silver Grooved Armor", "Silver Grooved Gauntlets",
    "Silver Grooved Greaves", "Silver Grooved Shield", "Idus Sword",
    "Steel Helm", "Steel Armor", "Steel Gauntlets", "Steel Greaves",
    "Hefty Scimitar",
    "Longsword", "Halberd", "Heater Shield",
    "Scimitar", "Riveted Wooden Shield",
    "Battle Axe", "Large Leather Shield",
    "Great Knife", "Shortbow", "Buckler",
    "Astrologer's Staff", "Short Sword", "Scripture Wooden Shield",
    "Short Spear", "Finger Seal", "Rickety Shield",
    "Uchigatana", "Longbow", "Red Thorn Roundshield",
    "Estoc", "Glintstone Staff",
    "Broadsword", "Blue Crest Heater Shield",
    "Club",
}

STARTING_CLASS_ORDER = [
    "Vagabond", "Warrior", "Hero", "Bandit", "Astrologer",
    "Prophet", "Samurai", "Prisoner", "Confessor", "Wretch",
    "Heavy Knight", "Idus Knight",
]

STARTING_CLASS_BY_NAME = {
    "Silver Grooved Helm": ["Idus Knight"],
    "Silver Grooved Armor": ["Idus Knight"],
    "Silver Grooved Gauntlets": ["Idus Knight"],
    "Silver Grooved Greaves": ["Idus Knight"],
    "Silver Grooved Shield": ["Idus Knight"],
    "Idus Sword": ["Idus Knight"],
    "Steel Helm": ["Heavy Knight"],
    "Steel Armor": ["Heavy Knight"],
    "Steel Gauntlets": ["Heavy Knight"],
    "Steel Greaves": ["Heavy Knight"],
    "Hefty Scimitar": ["Heavy Knight"],
    "Longsword": ["Vagabond"],
    "Halberd": ["Vagabond"],
    "Heater Shield": ["Vagabond"],
    "Scimitar": ["Warrior"],
    "Riveted Wooden Shield": ["Warrior"],
    "Battle Axe": ["Hero"],
    "Large Leather Shield": ["Hero"],
    "Great Knife": ["Bandit"],
    "Shortbow": ["Bandit"],
    "Buckler": ["Bandit"],
    "Astrologer's Staff": ["Astrologer"],
    "Short Sword": ["Astrologer"],
    "Scripture Wooden Shield": ["Astrologer"],
    "Short Spear": ["Prophet"],
    "Finger Seal": ["Prophet", "Confessor"],
    "Rickety Shield": ["Prophet"],
    "Uchigatana": ["Samurai"],
    "Longbow": ["Samurai"],
    "Red Thorn Roundshield": ["Samurai"],
    "Estoc": ["Prisoner"],
    "Glintstone Staff": ["Prisoner"],
    "Broadsword": ["Confessor"],
    "Blue Crest Heater Shield": ["Confessor"],
    "Club": ["Wretch"],
}


def norm(s):
    s = (s or "").lower().strip()
    # Keep "(Altered)" so cape vs no-cape pieces do not share an index key.
    # Drop only "(weapon)"; keep "(Cat)" / "(Wolf)" so those helms stay distinct.
    s = re.sub(r"\s*\(weapon\)\s*", " ", s, flags=re.I)
    s = re.sub(r"\+(\d+)", r" \1", s)
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_piece_words(n):
    for suf in PIECE_SUFFIXES:
        if n.endswith(" " + suf):
            return n[: -(len(suf) + 1)].strip()
    return n


def is_altered_item(item):
    if item.get("altered"):
        return True
    return "(altered)" in (item.get("name") or "").lower()


def unaltered_name(name):
    return re.sub(r"\s*\(altered\)\s*$", "", name, flags=re.IGNORECASE).strip()


SKIP_SENTENCE = (
    "prior to",
    "prevent the",
    "may prevent",
    "before entering",
    "instead of",
    "without entering",
)

# Quest-association clauses that name a hub without being the pickup spot.
QUEST_FLUFF = (
    r"as part of (?:the )?(?:final )?contract for the volcano manor questline",
    r"after obtaining the second to last letter from volcano manor",
    r"letter from volcano manor",
)


def wiki_url_for(name):
    slug = (name or "").strip().replace(" ", "_")
    return WIKI_BASE + urllib.parse.quote(slug, safe="_()")


def is_generic_farm(text):
    """True when the item is a repeatable enemy/world drop, not a unique pickup."""
    tl = (text or "").lower()
    if re.search(
        r"questline|assassination|contract for the volcano|"
        r"letter from volcano manor|starting equipment|"
        r"sold by|purchased from|given by tanith",
        tl,
    ):
        return False
    return bool(re.search(r"\b(dropped by|dropped from|drop by|drops from|chance to drop)\b", tl))


def is_alter_only_acquire(text):
    """True when the only way to get this piece is altering an already-owned original."""
    tl = (text or "").lower()
    if re.search(r"\b(dropped by|drops from|sold by|purchased from|looted from|found in)\b", tl):
        return False
    return bool(re.search(
        r"boc the seamster can alter|"
        r"you \(or boc\) can alter|"
        r"can alter it at a grace|"
        r"can alter the original|"
        r"alter .+ into .+",
        tl,
    ))


def raw_name_is_altered(raw_name):
    return bool(re.search(r"\(altered\)|\baltered\b", raw_name or "", re.I))


def altered_sibling_owns_region(item, region, obtain_info, armor_by_norm):
    """True when only the (Altered) sibling's acquire names this region."""
    if is_altered_item(item):
        return False
    for alt in armor_by_norm.get(norm(item["name"]) + " altered", []):
        info = obtain_info.get(alt["id"])
        if not info or region not in info[0]:
            continue
        una = obtain_info.get(item["id"])
        una_inferred = una[0] if una else set()
        if region not in una_inferred:
            return True
    return False


def scrub_quest_fluff(text):
    out = text or ""
    for pat in QUEST_FLUFF:
        out = re.sub(pat, " ", out, flags=re.I)
    return out


def location_snippets(text):
    """Keep the first sentence plus later sentences that describe a drop/shop.

    Wiki blurbs often mention other regions as quest-failure warnings.
    """
    cleaned = re.sub(r"\s+", " ", (text or "").replace("\n", ". "))
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", cleaned) if p.strip()]
    keep = []
    for i, part in enumerate(parts):
        pl = part.lower()
        if any(s in pl for s in SKIP_SENTENCE):
            continue
        if i == 0:
            keep.append(part)
            continue
        if any(needle in pl for needle, _ in LOCATION_HINTS):
            keep.append(part)
            continue
        if any(k in pl for k in (
            "purchased", "sold", "dropped", "found", "located",
            "starting equipment", "obtained", "reward", "defeat",
            "can be", "merchant", "enia",
        )):
            keep.append(part)
    return " ".join(keep) if keep else cleaned


def infer_areas_from_text(text):
    if not text:
        return set()
    snippet = location_snippets(scrub_quest_fluff(text))
    hay = " " + snippet.lower() + " "
    found = set()
    if re.search(r"starting equipment|starting weapon", hay):
        found.add(STARTING_GEAR)
    for needle, region in LOCATION_HINTS:
        if needle in hay:
            found.add(region)
    return found


def sort_areas(areas):
    areas = sorted(areas)
    if STARTING_GEAR in areas:
        return [STARTING_GEAR] + [a for a in areas if a != STARTING_GEAR]
    return areas


def starting_classes_from_text(text):
    tl = text or ""
    if not re.search(r"starting equipment|starting weapon|starting class", tl, re.I):
        return []
    found = []
    for cls in STARTING_CLASS_ORDER:
        if re.search(rf"\b{re.escape(cls)}\b", tl, re.I):
            found.append(cls)
    return found


def starting_classes_for(name, acquire=""):
    found = set(starting_classes_from_text(acquire))
    found.update(STARTING_CLASS_BY_NAME.get(name, []))
    return [cls for cls in STARTING_CLASS_ORDER if cls in found]


def load_json(rel):
    with open(ROOT / rel, encoding="utf-8") as f:
        return json.load(f)


def write_json(rel, data):
    with open(ROOT / rel, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


def index_by_norm(items):
    out = defaultdict(list)
    for it in items:
        out[norm(it["name"])].append(it)
    return out


def tag(bucket, item_id, region):
    bucket[item_id].add(region)


def allow_region(obtain_info, item_id, region):
    """Skip wiki-list extras for unique pickups whose obtain text already named a region."""
    info = obtain_info.get(item_id)
    if not info:
        return True
    inferred, generic = info[0], info[1]
    if inferred and not generic and region not in inferred:
        return False
    return True


def is_dlc_item(item):
    return item.get("dlc") or item.get("source") in ("Shadow of the Erdtree", "Tarnished Edition")


def can_apply_region_list(a, raw_name, region, obtain_info, armor_by_norm):
    if is_altered_item(a) != raw_name_is_altered(raw_name):
        return False
    if not allow_region(obtain_info, a["id"], region):
        return False
    if altered_sibling_owns_region(a, region, obtain_info, armor_by_norm):
        return False
    return True


def match_set_or_piece(raw_name, armor, armor_by_norm, areas_by_armor_id, region, obtain_info):
    hit = False
    stripped_raw = raw_name.strip()
    if re.search(r"\bset$", stripped_raw, re.IGNORECASE):
        base = norm(re.sub(r"\s*set$", "", stripped_raw, flags=re.IGNORECASE))
        if base:
            extra_bases = {base}
            m = re.match(r"^(.+)\s+(foot soldier|soldier|sorcerer)$", base)
            if m and " " in m.group(1):
                extra_bases.add(m.group(1))
            for set_base in extra_bases:
                prefixes = (set_base + " ", set_base + "'s ")
                for a in armor:
                    if region not in DLC_REGIONS and is_dlc_item(a):
                        continue
                    n = norm(a["name"])
                    if n == set_base or n.startswith(prefixes) or strip_piece_words(n) == set_base:
                        if can_apply_region_list(a, raw_name, region, obtain_info, armor_by_norm):
                            tag(areas_by_armor_id, a["id"], region)
                        hit = True
    n = norm(raw_name)
    for key in {n, *NAME_ALIASES.get(n, [])}:
        for a in armor_by_norm.get(key, []):
            if can_apply_region_list(a, raw_name, region, obtain_info, armor_by_norm):
                tag(areas_by_armor_id, a["id"], region)
            hit = True
    return hit


def weapon_keys(n):
    keys = {n, *NAME_ALIASES.get(n, [])}
    if n.endswith(" weapon"):
        keys.add(n[:-7].strip())
    else:
        keys.add(n + " weapon")
    return keys


def main():
    region_items = load_json("data/raw/region_items.json")
    armor = load_json("data/armor.json")
    weapons = load_json("data/weapons.json")
    talismans = load_json("data/talismans.json")

    weapon_by_norm = index_by_norm(weapons)
    talisman_by_norm = index_by_norm(talismans)
    armor_by_norm = index_by_norm(armor)

    areas_by_armor_id = defaultdict(set)
    areas_by_weapon_id = defaultdict(set)
    areas_by_talisman_id = defaultdict(set)
    obtain_info = {}

    # Wiki category tables swapped merchants on some Tarnished Edition pieces.
    # Item pages are authoritative: Steel set = Isolated Merchant, Weeping
    # Peninsula; Silver Grooved set = Nomadic Merchant, North Liurnia.
    ACQUIRE_OVERRIDES = {
        "Steel Gauntlets": "Isolated Merchant Weeping Peninsula",
        "Steel Greaves": "Isolated Merchant Weeping Peninsula",
        "Silver Grooved Gauntlets": "Nomadic Merchant North Liurnia of the Lakes",
        "Silver Grooved Greaves": "Nomadic Merchant North Liurnia of the Lakes",
        # Wiki table for the unaltered chest/helm is generic or points at Stormveil,
        # which only drops the (Altered) pieces. Unaltered cape pieces are Castle Sol
        # / Cathedral of Dragon Communion.
        "Banished Knight Armor": (
            "Castle Sol and Cathedral of Dragon Communion. Dropped by Banished Knights."
        ),
        "Banished Knight Helm": "Castle Sol. Dropped by Banished Knights.",
    }

    for fname in ("helms.json", "chest.json", "gauntlets.json", "legs.json"):
        for row in load_json(f"data/raw/{fname}"):
            n = norm(row.get("name", ""))
            acquire = ACQUIRE_OVERRIDES.get(row.get("name", ""), row.get("acquire", ""))
            inferred = infer_areas_from_text(acquire)
            generic = is_generic_farm(acquire)
            for a in armor_by_norm.get(n, []):
                obtain_info[a["id"]] = (inferred, generic, acquire)
                areas_by_armor_id[a["id"]].update(inferred)

    for row in load_json("data/raw/talismans.json"):
        n = norm(row.get("name", ""))
        loc = row.get("location", "")
        inferred = infer_areas_from_text(loc)
        generic = is_generic_farm(loc)
        for t in talisman_by_norm.get(n, []):
            obtain_info[t["id"]] = (inferred, generic, loc)
            areas_by_talisman_id[t["id"]].update(inferred)

    unmatched = defaultdict(list)
    matched_count = 0
    total_count = 0

    for region, payload in region_items.items():
        for raw_name in payload["items"]:
            total_count += 1
            hit = match_set_or_piece(
                raw_name, armor, armor_by_norm, areas_by_armor_id, region, obtain_info
            )

            n = norm(raw_name)
            if not hit:
                for key in weapon_keys(n):
                    if key in weapon_by_norm:
                        for w in weapon_by_norm[key]:
                            tag(areas_by_weapon_id, w["id"], region)
                        hit = True

            if n in talisman_by_norm:
                for t in talisman_by_norm[n]:
                    if allow_region(obtain_info, t["id"], region):
                        tag(areas_by_talisman_id, t["id"], region)
                    hit = True
            else:
                for alias in NAME_ALIASES.get(n, []):
                    if alias in talisman_by_norm:
                        for t in talisman_by_norm[alias]:
                            if allow_region(obtain_info, t["id"], region):
                                tag(areas_by_talisman_id, t["id"], region)
                            hit = True

            if hit:
                matched_count += 1
            else:
                unmatched[region].append(raw_name)

    # Scaled Set is Tanith's reward at Volcano Manor after the Istvan hunt.
    AREA_OVERRIDES = {
        "Scaled Helm": ["Mt. Gelmir"],
        "Scaled Armor": ["Mt. Gelmir"],
        "Scaled Armor (Altered)": ["Mt. Gelmir"],
        "Scaled Gauntlets": ["Mt. Gelmir"],
        "Scaled Greaves": ["Mt. Gelmir"],
        # Wiki acquire text claims a Mausoleum Knight at the Weeping Peninsula
        # Walking Mausoleum. There isn't one; they farm in Liurnia.
        "Mausoleum Knight Armor": ["Liurnia of the Lakes"],
        "Mausoleum Knight Armor (Altered)": ["Liurnia of the Lakes"],
        "Mausoleum Knight Gauntlets": ["Liurnia of the Lakes"],
        "Mausoleum Knight Greaves": ["Liurnia of the Lakes"],
    }

    # Tarnished Pack weapons are not on the per-region wiki item lists.
    WEAPON_AREA_OVERRIDES = {
        "Idus Sword": ["Liurnia of the Lakes"],
        "Silver Grooved Shield": ["Liurnia of the Lakes"],
        "Hefty Scimitar": ["Limgrave"],
        "Leontiel's Greatsword": ["Caelid"],
        "Golden Order Flail": ["Leyndell, Royal Capital"],
        "Reverse-Bladed Sword": ["Roundtable Hold"],
        "Reed Great Katana": ["Dragonbarrow"],
        "Ritual Thrusting Shield": ["Dragonbarrow"],
    }

    # Boc / grace-only alters inherit the original's regions. World-drop
    # (Altered) pieces keep their own acquire locations.
    unaltered_by_key = {}
    for a in armor:
        if not is_altered_item(a):
            unaltered_by_key[(a["slot"], norm(unaltered_name(a["name"])))] = a
    for a in armor:
        if not is_altered_item(a):
            continue
        info = obtain_info.get(a["id"])
        acquire = info[2] if info else ""
        if not is_alter_only_acquire(acquire):
            continue
        sibling = unaltered_by_key.get((a["slot"], norm(unaltered_name(a["name"]))))
        if sibling:
            areas_by_armor_id[a["id"]].update(areas_by_armor_id.get(sibling["id"], set()))

    for a in armor:
        override = AREA_OVERRIDES.get(a["name"])
        if override is not None:
            areas_by_armor_id[a["id"]] = set(override)

    for w in weapons:
        override = WEAPON_AREA_OVERRIDES.get(w["name"])
        if override is not None:
            areas_by_weapon_id[w["id"]] = set(override)

    for a in armor:
        if a["name"] in STARTING_GEAR_EXTRA:
            areas_by_armor_id[a["id"]].add(STARTING_GEAR)
    for w in weapons:
        if w["name"] in STARTING_GEAR_EXTRA:
            areas_by_weapon_id[w["id"]].add(STARTING_GEAR)

    for a in armor:
        a["areas"] = sort_areas(areas_by_armor_id.get(a["id"], []))
        a["wiki"] = wiki_url_for(a["name"])
        info = obtain_info.get(a["id"])
        acquire = info[2] if info else ""
        classes = starting_classes_for(a["name"], acquire)
        if not classes and is_altered_item(a):
            sibling = unaltered_by_key.get((a["slot"], norm(unaltered_name(a["name"]))))
            if sibling:
                sinfo = obtain_info.get(sibling["id"])
                sacquire = sinfo[2] if sinfo else ""
                classes = starting_classes_for(sibling["name"], sacquire)
        if classes:
            a["startingClasses"] = classes
        else:
            a.pop("startingClasses", None)
    for w in weapons:
        w["areas"] = sort_areas(areas_by_weapon_id.get(w["id"], []))
        w["wiki"] = wiki_url_for(w["name"])
        classes = starting_classes_for(w["name"])
        if classes:
            w["startingClasses"] = classes
        else:
            w.pop("startingClasses", None)
    for t in talismans:
        t["areas"] = sort_areas(areas_by_talisman_id.get(t["id"], []))
        t["wiki"] = wiki_url_for(t["name"])
        t.pop("startingClasses", None)

    write_json("data/armor.json", armor)
    write_json("data/weapons.json", weapons)
    write_json("data/talismans.json", talismans)

    n_armor_tagged = sum(1 for a in armor if a["areas"])
    n_weapons_tagged = sum(1 for w in weapons if w["areas"])
    n_talismans_tagged = sum(1 for t in talismans if t["areas"])
    print(f"matched {matched_count}/{total_count} raw region-item mentions")
    print(f"armor tagged: {n_armor_tagged}/{len(armor)}")
    print(f"weapons tagged: {n_weapons_tagged}/{len(weapons)}")
    print(f"talismans tagged: {n_talismans_tagged}/{len(talismans)}")
    print()
    print("Sample unmatched (first 5 regions, first 8 each):")
    for region in list(unmatched)[:5]:
        print(f"  {region}: {unmatched[region][:8]}")


if __name__ == "__main__":
    main()
