"""Decode selected BeachRenderPipeline property-name literals from file-backed IL2CPP usage slots.

The caller supplies slots observed in the local .cctor disassembly.  This tool
does not execute the target, infer arbitrary fields, or scan unrelated files.
"""

import argparse
import json
import struct
from pathlib import Path

from map_codegen import PE
from metadata39 import Metadata39


def parse_binding(value: str) -> tuple[str, int, int, str]:
    parts = value.split(":", 3)
    if len(parts) != 4 or not parts[0] or not parts[3]:
        raise argparse.ArgumentTypeError("binding must be field:static-offset:slot-va:expected-literal")
    try:
        return parts[0], int(parts[1], 0), int(parts[2], 0), parts[3]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def literal_at(metadata: Metadata39, ordinal: int) -> tuple[int, int, str]:
    table, table_size, count = metadata.sections["string_lit"]
    data_start, data_size, _ = metadata.sections["string_lit_data"]
    if table_size != 4 * count or not 0 <= ordinal < count - 1:
        raise ValueError(f"invalid string-literal ordinal {ordinal}")
    start = struct.unpack_from("<I", metadata.data, table + 4 * ordinal)[0]
    end = struct.unpack_from("<I", metadata.data, table + 4 * (ordinal + 1))[0]
    if not 0 <= start <= end <= data_size:
        raise ValueError(f"invalid literal data range {start}:{end}")
    return start, end, metadata.data[data_start + start:data_start + end].decode("utf-8", "strict")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--binding", type=parse_binding, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    pe = PE(args.binary)
    metadata = Metadata39(args.metadata)
    seen_fields: set[str] = set()
    results = []
    for field, static_offset, slot_va, expected in args.binding:
        if field in seen_fields:
            raise ValueError(f"duplicate field {field}")
        seen_fields.add(field)
        file_offset = pe.va_to_file(slot_va)
        if file_offset is None or pe.section_at(file_offset) != ".data":
            raise ValueError(f"slot {field} at {slot_va:#x} is not file-backed .data")
        encoded = struct.unpack_from("<Q", pe.data, file_offset)[0]
        if encoded >> 32 or (encoded & 0xE0000000) != 0xA0000000:
            raise ValueError(f"unexpected metadata usage encoding at {field}: {encoded:#x}")
        encoded_index = encoded & 0x1FFFFFFF
        if not encoded_index & 1:
            raise ValueError(f"even literal usage index at {field}: {encoded_index:#x}")
        ordinal = (encoded_index - 1) // 2
        start, end, actual = literal_at(metadata, ordinal)
        if actual != expected:
            raise ValueError(f"literal mismatch for {field}: {actual!r} != {expected!r}")
        results.append({"field": field, "static_offset": hex(static_offset),
                        "slot_va": hex(slot_va), "slot_file_offset": hex(file_offset),
                        "encoded_usage": hex(encoded), "literal_ordinal": ordinal,
                        "literal_data_offset": start, "literal_bytes": end - start,
                        "literal": actual})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"binary": str(args.binary), "metadata": str(args.metadata),
               "read_only": True, "bindings": results}
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f"decoded {len(results)} bindings to {args.output}")


if __name__ == "__main__":
    main()
