"""Decode a caller-selected, observed Unity shader LZ4 table and DXBC records.

This does not parse the complete Shader schema or identify shader entry names.
The table offset must be justified separately from the original object bytes.
"""

import argparse
import importlib.util
import json
import re
import struct
from pathlib import Path


def decode_lz4(source, expected):
    output = bytearray()
    pos = 0

    def extended(length):
        nonlocal pos
        if length == 15:
            while True:
                if pos >= len(source):
                    raise ValueError("Truncated LZ4 length")
                value = source[pos]
                pos += 1
                length += value
                if value != 255:
                    break
        return length

    while pos < len(source):
        token = source[pos]
        pos += 1
        length = extended(token >> 4)
        if length > len(source) - pos or length > expected - len(output):
            raise ValueError("LZ4 literal exceeds declared range")
        output.extend(source[pos:pos + length])
        pos += length
        if pos == len(source):
            break
        if pos + 2 > len(source):
            raise ValueError("Truncated LZ4 match offset")
        offset = int.from_bytes(source[pos:pos + 2], "little")
        pos += 2
        if not 0 < offset <= len(output):
            raise ValueError("Invalid LZ4 match offset")
        length = extended(token & 15) + 4
        if length > expected - len(output):
            raise ValueError("LZ4 match exceeds declared decoded size")
        for _ in range(length):
            output.append(output[-offset])
    if len(output) != expected:
        raise ValueError("LZ4 decoded size differs from declaration")
    return bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", type=Path)
    parser.add_argument("--object-id", required=True, type=int)
    parser.add_argument("--table-offset", required=True, type=lambda x: int(x, 0))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    helper_path = Path(__file__).with_name("unity22-compute-probe.py")
    spec = importlib.util.spec_from_file_location("unity_compute_probe", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    data, resource = helper.resource_index(args.resource.resolve(strict=True))
    matches = [x for x in resource["objects"] if x["path_id"] == args.object_id and x["class_id"] == 48]
    if len(matches) != 1:
        raise ValueError("Expected exactly one selected Shader object")
    item = matches[0]
    raw = data[item["offset"]:item["offset"] + item["bytes"]]
    pos = args.table_offset

    def uint():
        nonlocal pos
        if pos < 0 or pos + 4 > len(raw):
            raise ValueError("Shader table exceeds object")
        value = struct.unpack_from("<I", raw, pos)[0]
        pos += 4
        return value

    def array(limit):
        count = uint()
        if not 1 <= count <= min(limit, (len(raw) - pos) // 4):
            raise ValueError("Invalid shader table array count")
        return [uint() for _ in range(count)]

    platforms = array(8)
    tables = []
    for _ in range(3):
        if uint() != len(platforms):
            raise ValueError("Shader table platform dimensions differ")
        tables.append([array(128) for _ in platforms])
    compressed_size = uint()
    if compressed_size > len(raw) - pos:
        raise ValueError("Compressed shader blob exceeds object")
    args.output.mkdir(parents=True, exist_ok=True)
    modules = []
    for platform_index, platform in enumerate(platforms):
        offsets, compressed, decoded = [x[platform_index] for x in tables]
        if not len(offsets) == len(compressed) == len(decoded):
            raise ValueError("Shader section dimensions differ")
        if platform != 4:
            continue
        for section, (offset, length, expected) in enumerate(zip(offsets, compressed, decoded)):
            if offset > compressed_size or length > compressed_size - offset or not 0 < expected <= 16 * 1024 * 1024:
                raise ValueError("Invalid shader section range or decoded allocation")
            decoded_bytes = decode_lz4(raw[pos + offset:pos + offset + length], expected)
            ordinal = 0
            for match in re.finditer(b"DXBC", decoded_bytes):
                location = match.start()
                if location + 32 > expected:
                    continue
                marker, size, chunks = struct.unpack_from("<III", decoded_bytes, location + 20)
                if marker != 1 or not 1 <= chunks <= 64 or size > expected - location or size < 32 + chunks * 4:
                    continue
                for chunk in struct.unpack_from("<" + "I" * chunks, decoded_bytes, location + 32):
                    if chunk < 32 + chunks * 4 or chunk + 8 > size:
                        raise ValueError("Invalid DXBC chunk offset")
                    chunk_size = struct.unpack_from("<I", decoded_bytes, location + chunk + 4)[0]
                    if chunk_size > size - chunk - 8:
                        raise ValueError("Invalid DXBC chunk size")
                ordinal += 1
                name = f"shader-{args.object_id}-{section}-{ordinal:02d}"
                code = decoded_bytes[location:location + size]
                (args.output / (name + ".asm.txt")).write_text(helper.disassemble(code), encoding="utf-8")
                (args.output / (name + ".hex.txt")).write_text(helper.disassemble(code, True), encoding="utf-8")
                modules.append({"section": section, "ordinal": ordinal, "decoded_offset": location,
                                "bytes": size, "disassembly": name + ".asm.txt"})
    if not modules:
        raise ValueError("No Direct3D DXBC records decoded")
    result = {"resource": resource["file"], "object": item, "table_file_offset": item["offset"] + args.table_offset,
              "blob_file_offset": item["offset"] + pos, "platforms": platforms, "section_tables": tables,
              "compressed_blob_bytes": compressed_size, "modules": modules}
    (args.output / f"shader-{args.object_id}-index.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"object": args.object_id, "modules": len(modules), "output": str(args.output)}))


if __name__ == "__main__":
    main()
