"""Decode file-backed IL2CPP string usage at selected SetGlobalColor call sites.

Only the caller-selected disassembly and shipped PE/metadata are read.  A slot
is accepted when the disassembly loads it into RCX immediately before the
selected Shader.SetGlobalColor call.  This does not execute the game or prove
the GPU value for a particular frame.
"""

import argparse
import json
import re
import struct
from pathlib import Path

from camera_texture_probe import literal_at
from map_codegen import PE
from metadata39 import Metadata39


LINE = re.compile(r"^\s*([0-9A-F]{16}):\s*(.+)$", re.I)
SLOT = re.compile(r"mov\s+rcx,qword ptr \[([0-9A-F]{16})h\]", re.I)
CALL = re.compile(r"call\s+([0-9A-F]{16})", re.I)
SET_GLOBAL_COLOR = 0x181C1ACA0


def parse_site(value):
    parts = value.split(":", 2)
    if len(parts) != 3 or not parts[0] or not parts[2]:
        raise argparse.ArgumentTypeError("site must be label:call-VA:disassembly-path")
    try:
        return parts[0], int(parts[1], 0), Path(parts[2])
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def instructions(path):
    result = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = LINE.match(line)
        if match:
            result.append((int(match.group(1), 16), match.group(2)))
    if not result:
        raise ValueError(f"no disassembly in {path}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--site", type=parse_site, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    pe = PE(args.binary.resolve(strict=True))
    metadata = Metadata39(args.metadata.resolve(strict=True))
    results = []
    seen = set()
    for label, call_va, path in args.site:
        if label in seen:
            raise ValueError(f"duplicate site label {label}")
        seen.add(label)
        lines = instructions(path)
        hits = [i for i, (va, _) in enumerate(lines) if va == call_va]
        if len(hits) != 1:
            raise ValueError(f"call {call_va:#x} absent or duplicated in {path}")
        i = hits[0]
        target = CALL.fullmatch(lines[i][1])
        if not target or int(target.group(1), 16) != SET_GLOBAL_COLOR:
            raise ValueError(f"site {label} does not call Shader.SetGlobalColor")
        slots = [(va, int(match.group(1), 16)) for va, inst in lines[max(0, i - 14):i]
                 if (match := SLOT.fullmatch(inst))]
        if len(slots) != 1:
            raise ValueError(f"site {label} has {len(slots)} nearby RCX slot loads")
        load_va, slot_va = slots[0]
        offset = pe.va_to_file(slot_va)
        if offset is None or pe.section_at(offset) != ".data":
            raise ValueError(f"site {label} slot is not file-backed .data")
        encoded = struct.unpack_from("<Q", pe.data, offset)[0]
        if encoded >> 32 or (encoded & 0xE0000000) != 0xA0000000:
            raise ValueError(f"site {label} has unexpected usage encoding")
        index = encoded & 0x1FFFFFFF
        if not index & 1:
            raise ValueError(f"site {label} has even literal usage index")
        ordinal = (index - 1) // 2
        start, end, literal = literal_at(metadata, ordinal)
        results.append({"label": label, "call_va": hex(call_va), "slot_load_va": hex(load_va),
                        "slot_va": hex(slot_va), "slot_file_offset": hex(offset),
                        "encoded_usage": hex(encoded), "literal_ordinal": ordinal,
                        "literal_data_offset": start, "literal_bytes": end - start,
                        "literal": literal, "disassembly": str(path)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"binary": str(args.binary), "metadata": str(args.metadata),
                   "setter_va": hex(SET_GLOBAL_COLOR), "sites": results}, stream,
                  ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"decoded {len(results)} SetGlobalColor sites to {args.output}")


if __name__ == "__main__":
    main()
