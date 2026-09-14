#!/usr/bin/env python3
import hashlib
import urllib.request

UA = "ER-loadout-calc/1.0"
IMG_HOST = "https://static0.fextralifeimages.com/file/eldenring/"
names = [
    "gauntlets_elden_ring_wiki_guide_200px.png",
    "Gauntlets_elden_ring_wiki_guide_200px.png",
    "gauntlets-elden-ring-wiki-guide-200px.png",
    "chain_gauntlets_female_elden_ring_wiki_guide_200px.png",
    "Chain_gauntlets_female_elden_ring_wiki_guide_200px.png",
    "gauntlets_female_elden_ring_wiki_guide_200px.png",
    "female_gauntlets_elden_ring_wiki_guide_200px.png",
    "chain_gauntlets_f_elden_ring_wiki_guide_200px.png",
    "gauntlets2_elden_ring_wiki_guide_200px.png",
    "Gauntlets2-elden-ring-wiki-guide.png",
    "gauntlets-elden-ring-wiki-guide.png",
]

def url_for(filename: str) -> str:
    digest = hashlib.md5(filename.encode("utf-8")).hexdigest()
    return f"{IMG_HOST}{digest[0]}/{digest[:2]}/{filename}"

for name in names:
    url = url_for(name)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://eldenring.wiki.fextralife.com/"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read(32)
        print("OK", name, url, data[:8])
    except Exception as e:
        print("NO", name, type(e).__name__)
