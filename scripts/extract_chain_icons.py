#!/usr/bin/env python3
"""Pull MENU_Knowledge DDS files out of the unpacked 00_solo.tpfbdt."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from msb_io import decompress_dcx

ROOT = Path(__file__).resolve().parents[1]
SOLO = ROOT / "Smithbox_2_2_5_2026_08_29_a" / "test" / "menu" / "hi" / "00_solo.tpfbdt"
OUT = ROOT / "Smithbox_2_2_5_2026_08_29_a" / "test"

WANTED = {
    "MENU_Knowledge_14890",
    "MENU_Knowledge_14891",
    "MENU_Knowledge_14892",
    "MENU_Knowledge_14893",
    "MENU_Knowledge_14895",
    "MENU_Knowledge_14896",
    "MENU_Knowledge_14897",
}


def tpf_textures(buf: bytes) -> list[tuple[str, bytes]]:
    if buf[:4] != b"TPF\x00":
        return []
    count = struct.unpack_from("<i", buf, 8)[0]
    if count <= 0 or count > 64:
        return []
    out = []
    for i in range(count):
        rec = 0x10 + i * 16
        if rec + 16 > len(buf):
            return []
        data_off, data_size, _fmt, name_off = struct.unpack_from("<IIII", buf, rec)
        if name_off <= 0 or name_off >= len(buf) or data_off < 0 or data_size <= 0:
            continue
        if data_off + data_size > len(buf):
            continue
        chars = []
        pos = name_off
        while pos + 1 < len(buf):
            code = struct.unpack_from("<H", buf, pos)[0]
            if code == 0:
                break
            chars.append(chr(code))
            pos += 2
        name = "".join(chars)
        out.append((name, buf[data_off : data_off + data_size]))
    return out


def main() -> None:
    data = SOLO.read_bytes()
    found: dict[str, bytes] = {}
    pos = 0
    scanned = 0
    while True:
        i = data.find(b"DCX\x00", pos)
        if i < 0:
            break
        if i + 0x4C > len(data):
            break
        method = data[i + 0x28 : i + 0x2C]
        if method != b"KRAK":
            pos = i + 4
            continue
        uncompressed = struct.unpack_from(">I", data, i + 0x1C)[0]
        compressed_size = struct.unpack_from(">I", data, i + 0x20)[0]
        total = 0x4C + compressed_size
        if uncompressed > 8_000_000 or compressed_size > 8_000_000 or i + total > len(data):
            pos = i + 4
            continue
        blob = data[i : i + total]
        pos = i + max(total, 4)
        scanned += 1
        try:
            raw = decompress_dcx(blob)
        except Exception:
            continue
        for name, payload in tpf_textures(raw):
            if name in WANTED and name not in found:
                found[name] = payload
                dest = OUT / f"{name}.dds"
                dest.write_bytes(payload)
                print("wrote", dest.name, len(payload))
                if found.keys() >= WANTED:
                    print("all wanted textures found after", scanned, "dcx")
                    return
        if scanned % 500 == 0:
            print("scanned", scanned, "found", sorted(found))
    print("done scanned", scanned, "found", sorted(found))


if __name__ == "__main__":
    main()
