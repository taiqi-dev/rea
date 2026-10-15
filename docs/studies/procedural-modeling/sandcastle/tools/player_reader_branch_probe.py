"""Inspect the shipped class-129 SerializedFile type and object records.

Static, bounded reader for the already identified Unity v22 resource. It does
not execute the target or assign semantics to an unmapped payload word.
"""

import argparse
import json
import struct
from pathlib import Path


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 48:
        raise ValueError("short file")
    _, _, version, _ = struct.unpack_from(">4I", data)
    metadata_size, file_size, data_offset, _ = struct.unpack_from(">IQQQ", data, 20)
    if version != 22 or data[16] != 0 or file_size != len(data):
        raise ValueError("expected little-endian SerializedFile v22")
    pos = 48
    metadata_end = 48 + metadata_size
    if not 48 <= metadata_end <= data_offset <= len(data):
        raise ValueError("invalid metadata bounds")

    def read(fmt: str):
        nonlocal pos
        count = struct.calcsize("<" + fmt)
        if pos + count > metadata_end:
            raise ValueError("metadata read outside bounds")
        offset = pos
        values = struct.unpack_from("<" + fmt, data, pos)
        pos += count
        return offset, values[0] if len(values) == 1 else values

    end = data.find(b"\0", pos, metadata_end)
    if end < 0:
        raise ValueError("missing Unity version")
    unity = data[pos:end].decode("utf-8")
    pos = end + 1
    _, platform = read("i")
    _, has_tree = read("B")
    if has_tree != 0:
        raise ValueError("this probe requires a stripped type tree")
    _, type_count = read("i")
    if not 0 <= type_count <= (metadata_end - pos) // 23:
        raise ValueError("invalid type count")
    types = []
    for ordinal in range(type_count):
        record_offset = pos
        _, class_id = read("i")
        _, stripped = read("B")
        _, script_index = read("h")
        script_id = None
        if class_id == 114:
            _, script_id = read("16s")
        read("16s")  # Advance past the stored type identifier; do not calculate a digest.
        types.append({
            "ordinal": ordinal, "metadata_offset": record_offset,
            "class_id": class_id, "is_stripped_type": stripped,
            "script_type_index": script_index,
            "script_id": script_id.hex() if script_id is not None else None,
        })
    _, object_count = read("i")
    if not 0 <= object_count <= (metadata_end - pos) // 24:
        raise ValueError("invalid object count")
    objects = []
    for ordinal in range(object_count):
        pos = (pos + 3) & ~3
        record_offset = pos
        _, (path_id, relative_start, length, type_index) = read("qQIi")
        start = data_offset + relative_start
        if not 0 <= type_index < len(types) or start > len(data) or length > len(data) - start:
            raise ValueError("invalid object range or type index")
        if types[type_index]["class_id"] == 129:
            objects.append({
                "ordinal": ordinal, "metadata_offset": record_offset,
                "path_id": path_id, "type_index": type_index,
                "type_record": types[type_index],
                "relative_start": relative_start, "file_start": start,
                "length": length, "file_end": start + length,
                "first_16_bytes": data[start:start + 16].hex(" "),
                "bytes_0x10_to_0x28": data[start + 0x10:start + 0x28].hex(" "),
                "word_at_0x38c": struct.unpack_from("<I", data, start + 0x38c)[0]
                if length >= 0x390 else None,
                "word_at_0x390": struct.unpack_from("<I", data, start + 0x390)[0]
                if length >= 0x394 else None,
            })
    return {
        "resource": str(path), "unity": unity, "version": version,
        "platform": platform, "type_tree_enabled": bool(has_tree),
        "type_count": type_count, "object_count": object_count,
        "data_offset": data_offset, "class_129_objects": objects,
    }


def direct_call_candidates(path: Path, target_va: int) -> dict:
    """Find E8 rel32 byte candidates; disassembly must validate each hit."""
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError("expected PE")
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("missing PE header")
    machine, section_count, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    optional = pe + 24
    if machine != 0x8664 or struct.unpack_from("<H", data, optional)[0] != 0x20b:
        raise ValueError("expected x64 PE32+")
    image_base = struct.unpack_from("<Q", data, optional + 24)[0]
    section_start = optional + optional_size
    candidates = []
    for i in range(section_count):
        name, virtual_size, rva, raw_size, raw_start, _, _, _, _, flags = struct.unpack_from(
            "<8sIIIIIIHHI", data, section_start + 40 * i)
        if not flags & 0x20000000:
            continue
        if raw_start + raw_size > len(data):
            raise ValueError("PE section outside file")
        end = raw_start + min(raw_size, virtual_size)
        at = raw_start
        while True:
            at = data.find(b"\xe8", at, end)
            if at < 0 or at + 5 > end:
                break
            displacement = struct.unpack_from("<i", data, at + 1)[0]
            call_va = image_base + rva + at - raw_start
            if call_va + 5 + displacement == target_va:
                candidates.append({"file_offset": at, "call_va": f"0x{call_va:x}"})
            at += 1
    return {"binary": str(path), "target_va": f"0x{target_va:x}",
            "kind": "E8 byte candidates requiring disassembly", "candidates": candidates}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", type=Path, required=True)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.resource.resolve(strict=True))
    if args.binary is not None:
        result["loader_direct_call_candidates"] = direct_call_candidates(
            args.binary.resolve(strict=True), 0x18121ec50)
    if len(result["class_129_objects"]) != 1:
        raise ValueError("expected exactly one class-129 object")
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
