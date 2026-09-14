#!/usr/bin/env python3
"""Download Elden Ring item icons from the Fextralife wiki into img/.

Resumable: existing files are skipped, HTML is cached, and data/raw/icon_map.json
is updated as we go so a later run only fetches leftovers.

This is a one-off fan-tool scrape of wiki thumbnails for offline/GitHub Pages
display. Item images remain copyright FromSoftware / wiki contributors.
"""
from __future__ import annotations

import hashlib
import html as htmlmod
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from icon_map import apply_icons  # noqa: E402

UA = "ER-loadout-calc/1.0 (local fan tool; icon fetch for offline display)"
BASE = "https://eldenring.wiki.fextralife.com/"
IMG_HOST = "https://static0.fextralifeimages.com/file/eldenring/"
CACHE_DIR = ROOT / "data" / "raw" / "wiki_cache"
ICON_MAP_PATH = ROOT / "data" / "raw" / "icon_map.json"
PAGE_DELAY = 0.4
IMG_DELAY = 0.08

ARMOR_PAGES = [
    ("armor", "Helms"),
    ("armor", "Chest Armor"),
    ("armor", "Gauntlets"),
    ("armor", "Leg Armor"),
]

WEAPON_PAGE_ALIASES = {
    "Glintstone Staffs": ["Glintstone Staffs", "Glintstone Staves"],
    "Hand-to-Hand Arts": ["Hand-to-Hand Arts", "Hand to Hand Arts", "Hand-to-Hand"],
    "Sacred Seals": ["Sacred Seals", "Sacred Seal"],
    "Greatshields": ["Greatshields", "Great Shields"],
    "Small Shields": ["Small Shields"],
    "Medium Shields": ["Medium Shields"],
    "Thrusting Shields": ["Thrusting Shields"],
}

SKIP_TITLES = {
    "shadow of the erdtree",
    "enemies",
    "bosses",
    "merchants",
    "player trade",
    "trophy and achievement guide",
    "talisman pouches",
    "talisman pouch",
    "legendary talismans",
    "elden ring",
    "armor",
    "weapons",
    "helms",
    "chest armor",
    "gauntlets",
    "leg armor",
}

# In-game name collides with a wiki category page. Use the Chain Set piece page.
ITEM_PAGE_OVERRIDES = {
    "Gauntlets": "Chain_Gauntlets",
}


def norm_name(s: str) -> str:
    s = htmlmod.unescape(s or "")
    s = s.lower().replace("’", "'").replace("`", "'")
    s = re.sub(r"\s*\(altered\)\s*", " altered ", s, flags=re.I)
    s = s.replace("+", " ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def wiki_url(page: str) -> str:
    slug = page.strip().replace(" ", "_")
    return BASE + urllib.parse.quote(slug)


def fetch_html(page: str) -> str | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_name = re.sub(r"[^a-z0-9]+", "-", page.lower()).strip("-") + ".html"
    cache_path = CACHE_DIR / cache_name
    if cache_path.exists() and cache_path.stat().st_size > 1000:
        return cache_path.read_text(encoding="utf-8", errors="replace")
    url = wiki_url(page)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"  skip {page}: HTTP {e.code}", flush=True)
        return None
    except Exception as e:
        print(f"  skip {page}: {e}", flush=True)
        return None
    cache_path.write_text(raw, encoding="utf-8")
    time.sleep(PAGE_DELAY)
    return raw


def canonical_image_url(url: str) -> str:
    url = htmlmod.unescape(url).split("?")[0].strip()
    m = re.match(
        r"https://static0\.fextralifeimages\.com/file/eldenring/thumb/([^/]+)/([^/]+)/([^/]+)/",
        url,
    )
    if m:
        return f"{IMG_HOST}{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return url


def is_item_image(url: str) -> bool:
    u = url.lower()
    if "static0.fextralifeimages.com/file/eldenring/" not in u:
        return False
    if any(bad in u for bad in ("favicon", "/icon_", "logo.png", "sote-new", "navsprite")):
        return False
    if "damage_negation_icon" in u or "resisntace_icon" in u or "runes-currency" in u:
        return False
    # Base-game thumbs use wiki_guide; Tarnished Edition infoboxes use wiki-guide.
    return "wiki_guide" in u or "wiki-guide" in u or "/thumb/" in u


def add_pair(out: dict[str, str], title: str, img_url: str) -> None:
    title = htmlmod.unescape(title or "").strip()
    # Wiki table typos like "Steel GauntletsA"
    title = re.sub(r"([a-z])A$", r"\1", title)
    if not title or len(title) < 2:
        return
    key = norm_name(title)
    if not key or key in SKIP_TITLES:
        return
    if not is_item_image(img_url):
        return
    canon = canonical_image_url(img_url)
    if key not in out:
        out[key] = canon


def extract_pairs(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    rows = re.findall(r"<tr[\s\S]*?</tr>", html, flags=re.I)
    for row in rows:
        imgs = [
            u for u in re.findall(
                r"https://static0\.fextralifeimages\.com/file/eldenring/[^\"'\s>]+",
                row,
            )
            if is_item_image(u)
        ]
        links = re.findall(r'<a[^>]+href="(/[^"]+)"[^>]*(?:title="([^"]*)")?[^>]*>([^<]*)</a>', row)
        item_links = []
        for href, title, text in links:
            if href.startswith("/File:") or href.startswith("/file/"):
                continue
            label = (title or text or "").strip()
            if label:
                item_links.append(label)
        if item_links and imgs:
            add_pair(out, item_links[0], imgs[0])

    for href, title, img in re.findall(
        r'<a[^>]+href="(/[^"]+)"[^>]*title="([^"]+)"[^>]*>[\s\S]{0,240}?<img[^>]+src="(https://static0\.fextralifeimages\.com/file/eldenring/[^"]+)"',
        html,
    ):
        if href.startswith("/File:"):
            continue
        add_pair(out, title, img)

    for img, href, text in re.findall(
        r'<img[^>]+src="(https://static0\.fextralifeimages\.com/file/eldenring/[^"]+)"[^>]*>[\s\S]{0,280}?<a[^>]+href="(/[^"]+)"[^>]*>([^<]+)</a>',
        html,
    ):
        if href.startswith("/File:"):
            continue
        add_pair(out, text, img)

    for alt, src in re.findall(
        r'<img[^>]+alt="([^"]+)"[^>]+src="(https://static0\.fextralifeimages\.com/file/eldenring/[^"]+)"',
        html,
        flags=re.I,
    ):
        cleaned = re.sub(
            r"\s+(helm|chest armor|gauntlets|leg armor|talisman|weapon)s?\s+elden ring.*$",
            "",
            alt,
            flags=re.I,
        )
        cleaned = re.sub(r"\s+elden ring.*$", "", cleaned, flags=re.I)
        add_pair(out, cleaned, src)

    return out


def fallback_item_page(name: str) -> str | None:
    page = ITEM_PAGE_OVERRIDES.get(name, name.replace(" ", "_"))
    html = fetch_html(page)
    if not html:
        return None
    infobox = re.search(
        r'<div class="er-(?:armor|weapon)-image"[^>]*>\s*<img[^>]+src="(https://static0\.fextralifeimages\.com/file/eldenring/[^"]+)"',
        html,
        flags=re.I,
    )
    if infobox and is_item_image(infobox.group(1)):
        return canonical_image_url(infobox.group(1))
    imgs = re.findall(
        r'<img[^>]+src="(https://static0\.fextralifeimages\.com/file/eldenring/[^"]+)"[^>]*(?:alt="([^"]*)")?',
        html,
        flags=re.I,
    )
    # img tags often have alt before src
    imgs2 = re.findall(
        r'<img[^>]+alt="([^"]*)"[^>]+src="(https://static0\.fextralifeimages\.com/file/eldenring/[^"]+)"',
        html,
        flags=re.I,
    )
    candidates = []
    for src, alt in imgs:
        candidates.append((alt, src))
    for alt, src in imgs2:
        candidates.append((alt, src))
    want = norm_name(name)
    for alt, src in candidates:
        if not is_item_image(src):
            continue
        if want and want in norm_name(alt or ""):
            return canonical_image_url(src)
    for alt, src in candidates:
        if is_item_image(src) and (
            "wiki_guide_200px" in src.lower() or "wiki-guide" in src.lower()
        ):
            return canonical_image_url(src)
    return guess_cdn_image_url(name)


def guess_cdn_image_url(name: str) -> str | None:
    """Some Tarnished Edition pages list File: n/a but the CDN file still exists."""
    stem = (name or "").replace("'", "").replace("’", "").replace(" ", "_")
    if not stem:
        return None
    for filename in (
        f"{stem}-elden-ring-wiki-guide.png",
        f"{stem}2-elden-ring-wiki-guide.png",
    ):
        digest = hashlib.md5(filename.encode("utf-8")).hexdigest()
        url = f"{IMG_HOST}{digest[0]}/{digest[:2]}/{filename}"
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read(80)
            if len(data) >= 80:
                return url
        except Exception:
            continue
    return None


def ext_for(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        if path.endswith(ext):
            return ext
    return ".png"


def download(url: str, dest: Path, force: bool = False) -> bool:
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
    except Exception as e:
        print(f"  download fail {dest.name}: {e}", flush=True)
        return False
    if len(data) < 80:
        print(f"  too small {dest.name} ({len(data)} bytes)", flush=True)
        return False
    dest.write_bytes(data)
    time.sleep(IMG_DELAY)
    return True


def load_json(rel: str):
    with open(ROOT / rel, encoding="utf-8") as f:
        return json.load(f)


def save_json(rel: str, data) -> None:
    with open(ROOT / rel, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


def match_url(item_name: str, name_to_url: dict[str, str]) -> str | None:
    key = norm_name(item_name)
    if key in name_to_url:
        return name_to_url[key]
    no_alt = re.sub(r"\s+altered$", "", key).strip()
    if no_alt in name_to_url:
        return name_to_url[no_alt]
    if key + " altered" in name_to_url:
        return name_to_url[key + " altered"]
    for suffix in (" helm", " armor", " gauntlets", " greaves", " talisman", " weapon"):
        if key + suffix in name_to_url:
            return name_to_url[key + suffix]
    return None


def collect_catalog() -> dict[str, str]:
    catalog: dict[str, str] = {}

    for _kind, page in ARMOR_PAGES:
        print(f"fetch {page}", flush=True)
        html = fetch_html(page)
        if html:
            pairs = extract_pairs(html)
            print(f"  {len(pairs)} names", flush=True)
            catalog.update(pairs)

    print("fetch Talismans", flush=True)
    html = fetch_html("Talismans")
    if html:
        pairs = extract_pairs(html)
        print(f"  {len(pairs)} names", flush=True)
        catalog.update(pairs)

    weapons = load_json("data/weapons.json")
    cats = sorted({(w.get("category") or w.get("type") or "").strip() for w in weapons if w.get("category") or w.get("type")})
    for cat in cats:
        pages = WEAPON_PAGE_ALIASES.get(cat, [cat])
        for page in pages:
            print(f"fetch {page}", flush=True)
            html = fetch_html(page)
            if not html:
                continue
            pairs = extract_pairs(html)
            print(f"  {len(pairs)} names", flush=True)
            catalog.update(pairs)
            break

    print(f"catalog size {len(catalog)}", flush=True)
    return catalog


def process_items(kind: str, items: list, catalog: dict[str, str], icon_map: dict[str, str]) -> None:
    pending_dl = []
    missing = []
    for it in items:
        item_id = it["id"]
        if item_id in icon_map and (ROOT / icon_map[item_id]).exists() and it["name"] not in ITEM_PAGE_OVERRIDES:
            continue
        url = None
        if it["name"] in ITEM_PAGE_OVERRIDES:
            url = fallback_item_page(it["name"])
        if not url:
            url = match_url(it["name"], catalog)
        if not url:
            missing.append(it)
            continue
        dest = ROOT / "img" / kind / f"{item_id}{ext_for(url)}"
        pending_dl.append((it, url, dest, it["name"] in ITEM_PAGE_OVERRIDES))

    print(f"{kind}: {len(pending_dl)} catalog hits to download, {len(missing)} unmatched", flush=True)
    for i, (it, url, dest, force) in enumerate(pending_dl, 1):
        rel = dest.relative_to(ROOT).as_posix()
        if download(url, dest, force=force):
            icon_map[it["id"]] = rel
        if i % 50 == 0:
            print(f"  {kind} downloaded {i}/{len(pending_dl)}", flush=True)
            write_icon_map(icon_map)

    if missing:
        print(f"{kind}: {len(missing)} unmatched, trying item pages…", flush=True)
        for it in missing:
            url = fallback_item_page(it["name"])
            if not url:
                print(f"  no icon: {it['name']}", flush=True)
                continue
            dest = ROOT / "img" / kind / f"{it['id']}{ext_for(url)}"
            rel = dest.relative_to(ROOT).as_posix()
            if download(url, dest):
                icon_map[it["id"]] = rel


def write_icon_map(icon_map: dict[str, str]) -> None:
    ICON_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ICON_MAP_PATH.open("w", encoding="utf-8") as f:
        json.dump(dict(sorted(icon_map.items())), f, indent=1)
        f.write("\n")


def patch_built_json() -> None:
    for rel in ("data/armor.json", "data/weapons.json", "data/talismans.json"):
        items = load_json(rel)
        apply_icons(items)
        save_json(rel, items)
        have = sum(1 for it in items if it.get("icon"))
        print(f"{rel}: {have}/{len(items)} icons", flush=True)


def main() -> None:
    icon_map = {}
    if ICON_MAP_PATH.exists():
        with ICON_MAP_PATH.open(encoding="utf-8") as f:
            icon_map = json.load(f)

    catalog = collect_catalog()
    armor = load_json("data/armor.json")
    weapons = load_json("data/weapons.json")
    talismans = load_json("data/talismans.json")

    process_items("armor", armor, catalog, icon_map)
    write_icon_map(icon_map)
    process_items("weapons", weapons, catalog, icon_map)
    write_icon_map(icon_map)
    process_items("talismans", talismans, catalog, icon_map)
    write_icon_map(icon_map)
    patch_built_json()
    print("done: icon scrape complete", flush=True)


if __name__ == "__main__":
    main()
