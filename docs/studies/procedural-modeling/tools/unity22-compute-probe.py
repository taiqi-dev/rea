"""Read selected Unity format-22 object indexes and Windows DXBC disassembly.

Offline research helper; never loads game assemblies or executes shaders.
Supports only the observed little-endian format with stripped type trees.
"""

import argparse
import collections
import ctypes
import json
import re
import struct
from pathlib import Path


def resource_index(path, include_externals=False):
    data = path.read_bytes()
    if len(data) < 48:
        raise ValueError(f"Short serialized file: {path}")
    _, _, version, _ = struct.unpack_from(">4I", data)
    if version != 22 or data[16] != 0:
        raise ValueError(f"Unsupported serialized format/endian: {version}, {data[16]}")
    metadata_size, size, data_offset, _ = struct.unpack_from(">IQQQ", data, 20)
    if size != len(data) or not 48 <= data_offset <= size:
        raise ValueError("Invalid file size or data offset")
    pos = 48

    def read(fmt):
        nonlocal pos
        count = struct.calcsize("<" + fmt)
        if pos + count > data_offset:
            raise ValueError("Metadata read exceeds data offset")
        result = struct.unpack_from("<" + fmt, data, pos)
        pos += count
        return result[0] if len(result) == 1 else result

    end = data.index(0, pos, data_offset)
    unity = data[pos:end].decode("utf-8")
    pos = end + 1
    platform = read("i")
    if read("?"):
        raise ValueError("Type trees are outside this probe's supported profile")
    type_count = read("i")
    if not 0 <= type_count <= (data_offset - pos) // 23:
        raise ValueError("Invalid type count")
    types = []
    for _ in range(type_count):
        class_id = read("i")
        read("?")
        read("h")
        if class_id == 114:
            read("16s")
        read("16s")
        types.append(class_id)
    object_count = read("i")
    if not 0 <= object_count <= (data_offset - pos) // 24:
        raise ValueError("Invalid object count")
    objects = []
    for _ in range(object_count):
        pos = (pos + 3) & ~3
        path_id, start, length, type_id = read("qQIi")
        start += data_offset
        if not 0 <= type_id < len(types) or start > size or length > size - start:
            raise ValueError("Invalid serialized object range or type")
        item = {"path_id": path_id, "class_id": types[type_id], "offset": start, "bytes": length}
        if types[type_id] in (28, 43, 48, 49, 72) and length >= 4:
            name_length = struct.unpack_from("<i", data, start)[0]
            if 0 <= name_length <= min(512, length - 4):
                item["name"] = data[start + 4:start + 4 + name_length].decode("utf-8", errors="replace")
        objects.append(item)
    index = {"file": str(path), "unity": unity, "format": version, "platform": platform,
             "type_trees": False, "object_count": object_count,
             "classes": dict(collections.Counter(x["class_id"] for x in objects)), "objects": objects}
    if include_externals:
        # Format-22 metadata ordering: objects, script identifiers, externals,
        # reference types, user information. External PPtr file IDs are 1-based.
        script_count = read("i")
        if not 0 <= script_count <= (data_offset - pos) // 12:
            raise ValueError("Invalid script identifier count")
        scripts = []
        for _ in range(script_count):
            file_index = read("i")
            pos = (pos + 3) & ~3
            scripts.append({"file_index": file_index, "path_id": read("q")})

        def cstring():
            nonlocal pos
            end = data.index(0, pos, data_offset)
            value = data[pos:end].decode("utf-8", errors="strict")
            pos = end + 1
            return value

        external_count = read("i")
        if not 0 <= external_count <= (data_offset - pos) // 22:
            raise ValueError("Invalid external file count")
        externals = []
        for ordinal in range(external_count):
            empty = cstring()
            if empty:
                raise ValueError("Unexpected nonempty external file prefix")
            guid = read("16s")
            kind = read("i")
            externals.append({"file_id": ordinal + 1, "guid_bytes": guid.hex(),
                              "type": kind, "path": cstring()})
        ref_count = read("i")
        if not 0 <= ref_count <= (data_offset - pos) // 23:
            raise ValueError("Invalid reference type count")
        ref_types = []
        for _ in range(ref_count):
            class_id = read("i")
            stripped = read("?")
            script_index = read("h")
            if script_index >= 0:
                read("16s")
            read("16s")
            ref_types.append({"class_id": class_id, "stripped": stripped,
                              "script_type_index": script_index})
        user_info = cstring()
        if pos != 48 + metadata_size:
            raise ValueError("Serialized metadata not fully consumed")
        index.update({"script_identifiers": scripts, "externals": externals,
                      "reference_types": ref_types, "user_information": user_info,
                      "metadata_consumed_end": pos})
    return data, index


def disassemble(bytecode, hexadecimal=False):
    dll = ctypes.WinDLL("d3dcompiler_47.dll")
    call = dll.D3DDisassemble
    call.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
    call.restype = ctypes.c_long
    source = ctypes.create_string_buffer(bytecode)
    blob = ctypes.c_void_p()
    # SDK flags: instruction numbering 0x4, byte offsets 0x20, hex literals 0x80.
    result = call(source, len(bytecode), 0x24 | (0x80 if hexadecimal else 0), None, ctypes.byref(blob))
    if result < 0:
        raise RuntimeError(f"D3DDisassemble failed: 0x{result & 0xffffffff:08x}")
    table = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])
    try:
        pointer = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(table[3])(blob)
        size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(table[4])(blob)
        return ctypes.string_at(pointer, size).rstrip(b"\0").decode("utf-8")
    finally:
        release(blob)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--names", nargs="+", default=["Ground", "Water", "Readback"])
    args = parser.parse_args()
    data, index = resource_index(args.resource.resolve(strict=True))
    args.output.mkdir(parents=True, exist_ok=True)
    modules = []
    for item in index["objects"]:
        if item["class_id"] != 72 or item.get("name") not in args.names:
            continue
        raw = data[item["offset"]:item["offset"] + item["bytes"]]
        ordinal = 0
        for match in re.finditer(b"DXBC", raw):
            offset = match.start()
            if offset + 32 > len(raw):
                continue
            marker, size, chunks = struct.unpack_from("<III", raw, offset + 20)
            if marker != 1 or not 1 <= chunks <= 64 or size > len(raw) - offset or size < 32 + chunks * 4:
                continue
            valid = True
            for chunk in struct.unpack_from("<" + "I" * chunks, raw, offset + 32):
                if chunk < 32 + chunks * 4 or chunk + 8 > size:
                    valid = False
                    break
                length = struct.unpack_from("<I", raw, offset + chunk + 4)[0]
                if length > size - chunk - 8:
                    valid = False
                    break
            if not valid:
                raise ValueError(f"Invalid DXBC chunk table at {item['offset'] + offset}")
            ordinal += 1
            name = f"{item['name']}-{ordinal:02d}.asm.txt"
            text = disassemble(raw[offset:offset + size])
            (args.output / name).write_text(text, encoding="utf-8")
            hex_name = name.replace(".asm.txt", ".hex.txt")
            (args.output / hex_name).write_text(disassemble(raw[offset:offset + size], True), encoding="utf-8")
            modules.append({"object": item["name"], "path_id": item["path_id"], "ordinal": ordinal,
                            "file_offset": item["offset"] + offset, "bytes": size, "disassembly": name,
                            "hexadecimal_disassembly": hex_name})
    index["modules"] = modules
    (args.output / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"objects": index["object_count"], "selected_modules": len(modules), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
