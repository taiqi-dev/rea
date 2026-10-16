"""Find candidate direct E8 call sites to exact RVAs in a PE32+ .text section.

This is a read-only byte search. Validate each candidate with disassembly;
an E8-shaped byte sequence is not by itself a call instruction.
"""

import argparse
import json
import struct
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("rva", nargs="+", type=lambda value: int(value, 0))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")

    binary = args.binary.resolve(strict=True)
    with binary.open("rb") as stream:
        header = stream.read(4096)
        if len(header) < 64 or header[:2] != b"MZ":
            raise ValueError("Expected PE file")
        pe = struct.unpack_from("<I", header, 0x3C)[0]
        if pe + 26 > len(header):
            raise ValueError("PE header outside selected 4096-byte header window")
        if header[pe:pe + 4] != b"PE\0\0":
            raise ValueError("Expected PE signature")
        section_count = struct.unpack_from("<H", header, pe + 6)[0]
        optional_size = struct.unpack_from("<H", header, pe + 20)[0]
        if optional_size < 2:
            raise ValueError("Missing PE32+ optional header")
        if struct.unpack_from("<H", header, pe + 24)[0] != 0x20B:
            raise ValueError("Expected PE32+")
        section_table = pe + 24 + optional_size
        if section_table + 40 * section_count > len(header):
            raise ValueError("PE section table outside selected 4096-byte header window")
        sections = []
        for index in range(section_count):
            offset = section_table + 40 * index
            name = header[offset:offset + 8].rstrip(b"\0")
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from("<IIII", header, offset + 8)
            if name == b".text":
                sections.append((rva, min(virtual_size, raw_size), raw_offset))
        if len(sections) != 1:
            raise ValueError("Expected exactly one .text section")
        text_rva, text_size, raw_offset = sections[0]
        stream.seek(raw_offset)
        body = stream.read(text_size)
        if len(body) != text_size:
            raise ValueError("Truncated .text section")

    targets = set(args.rva)
    matches = {f"0x{target:x}": [] for target in sorted(targets)}
    for offset in range(len(body) - 4):
        if body[offset] != 0xE8:
            continue
        displacement = struct.unpack_from("<i", body, offset + 1)[0]
        site = text_rva + offset
        target = site + 5 + displacement
        if target in targets:
            matches[f"0x{target:x}"].append(f"0x{site:x}")
    result = {
        "binary": str(binary), "binary_bytes": binary.stat().st_size,
        "text_rva": f"0x{text_rva:x}", "text_bytes_examined": len(body),
        "kind": "candidate E8 byte pattern; validate instruction boundaries",
        "matches": matches,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({key: len(value) for key, value in matches.items()}))


if __name__ == "__main__":
    main()
