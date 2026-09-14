"""Read Elden Ring MSB placements (enemy NPCParam IDs, treasure ItemLotIDs).

MSBs are DCX_KRAK. Decompression uses Smithbox's bundled Oodle DLL.
"""
from __future__ import annotations

import ctypes
import struct
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMITHBOX = ROOT / "Smithbox_2_2_5_2026_08_29_a"

MSB_DIRS = [
    SMITHBOX / "test" / "unpack" / "map" / "mapstudio",
    ROOT / "test-save-data" / "map" / "mapstudio",
]

OODLE_DLLS = [
    SMITHBOX / "oo2core_9_win64.dll",
    SMITHBOX / "oo2core_6_win64.dll",
]

PART_ENEMY = 2
PART_DUMMY_ENEMY = 10
EVENT_TREASURE = 4

_OODLE = None


def find_msb_dir() -> Path | None:
    for path in MSB_DIRS:
        if path.is_dir() and any(path.glob("*.msb.dcx")):
            return path
    return None


def _load_oodle():
    global _OODLE
    if _OODLE is not None:
        return _OODLE
    path = next((p for p in OODLE_DLLS if p.exists()), None)
    if path is None:
        raise FileNotFoundError(
            "Oodle DLL not found; expected Smithbox oo2core_9_win64.dll"
        )
    lib = ctypes.WinDLL(str(path))
    fn = lib.OodleLZ_Decompress
    fn.restype = ctypes.c_long
    fn.argtypes = [
        ctypes.c_char_p, ctypes.c_int64,
        ctypes.c_char_p, ctypes.c_int64,
        ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.c_int64,
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_int64,
        ctypes.c_int,
    ]
    _OODLE = fn
    return fn


def decompress_dcx(data: bytes) -> bytes:
    if data[:4] != b"DCX\x00":
        if data[:4] == b"MSB ":
            return data
        raise ValueError("not DCX or MSB")
    method = data[0x28:0x2C]
    if method != b"KRAK":
        raise ValueError(f"unsupported DCX method {method!r}")
    uncompressed = struct.unpack_from(">I", data, 0x1C)[0]
    compressed_size = struct.unpack_from(">I", data, 0x20)[0]
    compressed = data[0x4C:0x4C + compressed_size]
    dst = ctypes.create_string_buffer(uncompressed)
    n = _load_oodle()(
        compressed, len(compressed), dst, uncompressed,
        0, 0, 0, None, 0, None, None, None, 0, 3,
    )
    if n != uncompressed:
        raise ValueError(f"Oodle decompressed {n}, expected {uncompressed}")
    return dst.raw


def _u16z(buf: bytes, off: int) -> str:
    chars: list[str] = []
    pos = off
    while pos + 1 < len(buf):
        code = struct.unpack_from("<H", buf, pos)[0]
        if code == 0:
            break
        chars.append(chr(code))
        pos += 2
    return "".join(chars)


def _i32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<i", buf, off)[0]


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _i64(buf: bytes, off: int) -> int:
    return struct.unpack_from("<q", buf, off)[0]


def iter_msb_params(buf: bytes):
    """Yield (name, entry_offsets) for each MSB param. Offsets are absolute."""
    pos = 16
    while pos and pos < len(buf):
        offset_count = _i32(buf, pos + 4)
        name = _u16z(buf, _i64(buf, pos + 8))
        n_entries = offset_count - 1
        if n_entries < 0:
            break
        next_param = _i64(buf, pos + 16 + 8 * n_entries)
        entries = [_i64(buf, pos + 16 + 8 * i) for i in range(n_entries)]
        yield name, entries
        if next_param == 0:
            break
        pos = next_param


def parse_msb(buf: bytes) -> tuple[list[int], list[int]]:
    """Return (npc_param_ids, treasure_item_lot_ids) from one MSB."""
    npcs: list[int] = []
    lots: list[int] = []
    for name, entries in iter_msb_params(buf):
        if name == "PARTS_PARAM_ST":
            for eoff in entries:
                if _u32(buf, eoff + 12) != PART_ENEMY:
                    continue
                # 1 = disabled in the released game
                if _u32(buf, eoff + 68) == 1:
                    continue
                type_data = eoff + _i64(buf, eoff + 104)
                npc = _i32(buf, type_data + 12)
                if npc > 0:
                    npcs.append(npc)
        elif name == "EVENT_PARAM_ST":
            for eoff in entries:
                if _u32(buf, eoff + 12) != EVENT_TREASURE:
                    continue
                type_data = eoff + _i64(buf, eoff + 32)
                lot = _i32(buf, type_data + 16)
                if lot > 0:
                    lots.append(lot)
    return npcs, lots


def map_id_from_stem(stem: str) -> str:
    # m10_00_00_00.msb.dcx -> stem m10_00_00_00
    return stem.replace(".msb", "")


@lru_cache(maxsize=1)
def _msb_files(directory: str) -> tuple[Path, ...]:
    path = Path(directory)
    files = []
    for p in sorted(path.glob("*.msb.dcx")):
        stem = p.name.split(".")[0]
        if stem.endswith("_99"):
            continue
        files.append(p)
    return tuple(files)


def iter_msb_placements(msb_dir: Path | None = None):
    """Yield (map_id, npc_ids, treasure_lot_ids) for each playable MSB."""
    directory = msb_dir or find_msb_dir()
    if directory is None:
        return
    files = _msb_files(str(directory))
    for i, path in enumerate(files, 1):
        map_id = map_id_from_stem(path.name.split(".")[0])
        try:
            buf = decompress_dcx(path.read_bytes())
            npcs, lots = parse_msb(buf)
        except (ValueError, OSError, struct.error):
            continue
        if i % 50 == 0 or i == len(files):
            print(f"  MSB {i}/{len(files)} {map_id}", flush=True)
        yield map_id, npcs, lots
