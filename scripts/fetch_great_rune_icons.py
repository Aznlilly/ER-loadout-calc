#!/usr/bin/env python3
"""Download Great Rune icons from the Fextralife wiki into img/great-runes/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scrape_icons as s  # noqa: E402
from icon_map import load_icon_map  # noqa: E402


def main() -> None:
    runes = json.loads((ROOT / "data" / "great-runes.json").read_text(encoding="utf-8"))
    imap = load_icon_map()
    (ROOT / "img" / "great-runes").mkdir(parents=True, exist_ok=True)

    html = s.fetch_html("Great_Runes")
    catalog = s.extract_pairs(html) if html else {}
    print(f"great runes catalog: {len(catalog)} names", flush=True)

    for it in runes:
        url = catalog.get(s.norm_name(it["name"])) or s.match_url(it["name"], catalog)
        if not url:
            print(f"page fallback {it['name']}", flush=True)
            url = s.fallback_item_page(it["name"])
        print(f"{it['name']} -> {url}", flush=True)
        if not url:
            continue
        dest = ROOT / "img" / "great-runes" / f"{it['id']}{s.ext_for(url)}"
        if s.download(url, dest, force=True):
            rel = dest.relative_to(ROOT).as_posix()
            imap[it["id"]] = rel
            it["icon"] = rel
            print(f"  saved {rel} ({dest.stat().st_size} bytes)", flush=True)
        else:
            print("  FAILED", flush=True)

    (ROOT / "data" / "great-runes.json").write_text(
        json.dumps(runes, indent=1) + "\n", encoding="utf-8"
    )
    s.write_icon_map(imap)
    print("done", flush=True)


if __name__ == "__main__":
    main()
