"""Export ID + name lines from Smithbox/regulation .param files."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DEFAULT_DIR = ROOT / "test-save-data"


def read_utf16z(buf: bytes, offset: int) -> str:
    if offset <= 0 or offset >= len(buf):
        return ""
    chars: list[str] = []
    pos = offset
    while pos + 1 < len(buf):
        code = struct.unpack_from("<H", buf, pos)[0]
        if code == 0:
            break
        chars.append(chr(code))
        pos += 2
    return "".join(chars).strip()


def parse_param_rows(path: Path) -> list[tuple[int, str]]:
    buf = path.read_bytes()
    if len(buf) < 0x40:
        raise ValueError(f"{path.name} is too small to be a PARAM")
    row_count = struct.unpack_from("<H", buf, 0x0A)[0]
    rows: list[tuple[int, str]] = []
    for i in range(row_count):
        off = 0x40 + i * 24
        if off + 24 > len(buf):
            break
        param_id = struct.unpack_from("<I", buf, off)[0]
        name_off = struct.unpack_from("<I", buf, off + 16)[0]
        name = read_utf16z(buf, name_off)
        if name:
            rows.append((param_id, name))
    return rows


def write_names(rows: list[tuple[int, str]], dest: Path) -> None:
    dest.write_text("".join(f"{pid} {name}\n" for pid, name in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        type=Path,
        default=DEFAULT_DIR,
        help="Folder containing EquipParamWeapon.param and EquipParamProtector.param",
    )
    args = parser.parse_args()
    src = args.src
    mapping = {
        "EquipParamWeapon.param": RAW / "EquipParamWeapon.txt",
        "EquipParamProtector.param": RAW / "EquipParamProtector.txt",
        "EquipParamAccessory.param": RAW / "EquipParamAccessory.txt",
    }
    for filename, dest in mapping.items():
        path = src / filename
        if not path.exists():
            raise SystemExit(f"missing {path}")
        rows = parse_param_rows(path)
        write_names(rows, dest)
        print(f"{filename}: {len(rows)} named rows -> {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
