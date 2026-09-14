#!/usr/bin/env python3
import re
import urllib.request

UA = "ER-loadout-calc/1.0"
url = "https://eldenring.wiki.fextralife.com/Chain_Gauntlets"
req = urllib.request.Request(url, headers={"User-Agent": UA})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
imgs = re.findall(r"https://static0\.fextralifeimages\.com/file/eldenring/[^\"'\s>]+", html)
print("count", len(imgs))
for u in dict.fromkeys(imgs):
    print(u)
print("--- alts ---")
for alt, src in re.findall(r'alt="([^"]*)"[^>]*src="(https://static0\.fextralifeimages\.com/file/eldenring/[^"]+)"', html):
    print(alt, "=>", src)
for src, alt in re.findall(r'src="(https://static0\.fextralifeimages\.com/file/eldenring/[^"]+)"[^>]*alt="([^"]*)"', html):
    print(alt, "=>", src)
