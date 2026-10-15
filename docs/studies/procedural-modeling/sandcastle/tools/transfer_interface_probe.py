"""Read selected Sandcastle UnityPlayer PE pointers and exact code references.

This is a static, bounded PE lookup. Four-byte RIP windows are candidates until
their surrounding instructions have been checked in a disassembly.
"""

import argparse
import json
import struct
from pathlib import Path

from unity_player_xref_probe import pe_layout


VIRTUAL_ADDRESSES = (
    0x181F9A1D8,  # stack interface vtable loaded at 0x1815c15fc
    0x18216D2D0,  # virtual-call receiver at 0x1815c18e8
    0x181EB1A30,  # proven PlayerSettings object vtable
)
DIRECT_TARGETS = (0x1815C14B0, 0x18120FB30)


def mapped_offset(sections, base, va, width):
    rva = va - base
    matches = [section for section in sections
               if section["rva"] <= rva and
               rva + width <= section["rva"] + section["size"]]
    if len(matches) != 1:
        return None
    section = matches[0]
    return section["offset"] + rva - section["rva"]


def rip_candidates(data, sections, base, target, limit=200):
    result = []
    for section in sections:
        if not section["executable"]:
            continue
        body = data[section["offset"]:section["offset"] + section["size"]]
        for index in range(0, len(body) - 3):
            displacement = struct.unpack_from("<i", body, index)[0]
            if base + section["rva"] + index + 4 + displacement == target:
                result.append({"displacement_va": hex(base + section["rva"] + index),
                               "surrounding_hex": body[max(0, index - 5):index + 9].hex()})
                if len(result) > limit:
                    raise ValueError(f"More than {limit} RIP candidates for {target:#x}")
    return result


def direct_call_candidates(data, sections, base, target):
    result = []
    for section in sections:
        if not section["executable"]:
            continue
        body = data[section["offset"]:section["offset"] + section["size"]]
        position = 0
        while (position := body.find(b"\xe8", position)) >= 0:
            if position + 5 <= len(body):
                displacement = struct.unpack_from("<i", body, position + 1)[0]
                if base + section["rva"] + position + 5 + displacement == target:
                    result.append(hex(base + section["rva"] + position))
            position += 1
    return result


def probe(path):
    data = path.read_bytes()
    base, sections = pe_layout(data)
    if base != 0x180000000:
        raise ValueError(f"Unexpected image base {base:#x}")
    selected = []
    for va in VIRTUAL_ADDRESSES:
        offset = mapped_offset(sections, base, va, 8)
        value = struct.unpack_from("<Q", data, offset)[0] if offset is not None else None
        entry = {"va": hex(va), "file_offset": offset,
                 "initial_qword": hex(value) if value is not None else None,
                 "rip_candidates": rip_candidates(data, sections, base, va)}
        start = mapped_offset(sections, base, va, 0xA0)
        if start is not None:
            entry["direct_qwords"] = [hex(x) for x in struct.unpack_from("<20Q", data, start)]
        selected.append(entry)
    return {"binary": str(path), "image_base": hex(base), "selected": selected,
            "direct_call_candidates": {hex(target): direct_call_candidates(data, sections, base, target)
                                       for target in DIRECT_TARGETS},
            "coverage": "initialized PE section bytes and all executable four-byte RIP windows"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    result = probe(args.binary.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
