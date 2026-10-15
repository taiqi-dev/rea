"""Bounded PE callback/table and binary-reader check for Sandcastle PlayerSettings.

Only reads the shipped UnityPlayer and saved disassembly. Static cursor arithmetic
is conditional on the observed SerializedFile payload and does not execute code.
"""

import argparse
import array
import json
import re
import struct
from pathlib import Path

from unity_player_xref_probe import pe_layout
from player_color_space_probe import ObjectReader, release_node, resource_index


TARGET = 0x180E637D0
WRAPPER = 0x180E634E0
READER_THUNK = 0x180E63530
READER = 0x180E652B0
TABLE = 0x181EB1AB0
VERSION = "6000.4.10f1"
ASM_LINE = re.compile(r"^\s+([0-9A-F]{16}):\s+(.*)$", re.I)


def section_at_offset(sections, offset):
    return next((s for s in sections if s["offset"] <= offset < s["offset"] + s["size"]), None)


def pointer_hits(data, base, sections, target):
    needle = struct.pack("<Q", target)
    hits = []
    at = 0
    while (at := data.find(needle, at)) >= 0:
        sec = section_at_offset(sections, at)
        hits.append({"file_offset": at, "section": sec["name"] if sec else None,
                     "va": base + sec["rva"] + at - sec["offset"] if sec else None})
        at += 1
    return hits


def code_displacement_hits(data, base, sections, target):
    destination_rva = target - base
    hits = []
    windows = 0
    for sec in sections:
        if not sec["executable"]:
            continue
        body = data[sec["offset"]:sec["offset"] + sec["size"]]
        for alignment in range(4):
            usable = (len(body) - alignment) & ~3
            words = array.array("I")
            words.frombytes(body[alignment:alignment + usable])
            for i, raw in enumerate(words):
                relative = alignment + 4 * i
                displacement = raw if raw < 0x80000000 else raw - 0x100000000
                if sec["rva"] + relative + 4 + displacement == destination_rva:
                    hits.append({"displacement_va": base + sec["rva"] + relative,
                                 "displacement_file_offset": sec["offset"] + relative,
                                 "preceding_opcode": body[relative - 1] if relative else None})
            windows += len(words)
    return windows, hits


def va_to_file(base, sections, va):
    rva = va - base
    matches = [s for s in sections if s["rva"] <= rva < s["rva"] + s["size"]]
    if len(matches) != 1:
        raise ValueError(f"VA {va:#x} has no unique initialized section")
    sec = matches[0]
    return sec["offset"] + rva - sec["rva"]


def pdata_function(data, base, sections, va):
    pdata = next((s for s in sections if s["name"] == ".pdata"), None)
    if pdata is None:
        raise ValueError("Missing PE .pdata")
    wanted = va - base
    found = []
    for at in range(pdata["offset"], pdata["offset"] + pdata["size"] - 11, 12):
        begin, end, unwind = struct.unpack_from("<III", data, at)
        if begin <= wanted < end:
            found.append({"record_file_offset": at, "begin_va": base + begin,
                          "end_va": base + end, "unwind_va": base + unwind})
    if len(found) != 1:
        raise ValueError(f"No unique .pdata function for {va:#x}")
    return found[0]


def instructions(path):
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = ASM_LINE.match(line)
        if match:
            result[int(match.group(1), 16)] = match.group(2)
    if not result:
        raise ValueError(f"No instructions in {path}")
    return result


def require(mapping, va, fragment):
    instruction = mapping.get(va, "")
    if fragment.lower() not in instruction.lower():
        raise ValueError(f"Expected {fragment!r} at {va:#x}, got {instruction!r}")
    return {"va": va, "instruction": instruction}


def probe(binary_path, resource_path, schema_path, caller_path, adjacent_path,
          reader_path, pptr_path, pptr_alt_path, vector_path):
    data = binary_path.read_bytes()
    base, sections = pe_layout(data)
    if base != 0x180000000:
        raise ValueError("Unexpected UnityPlayer image base")
    direct_pointers = pointer_hits(data, base, sections, TARGET)
    wrapper_pointers = pointer_hits(data, base, sections, WRAPPER)
    if direct_pointers or len(wrapper_pointers) != 1 or wrapper_pointers[0]["va"] != TABLE:
        raise ValueError("PlayerSettings callback pointer layout differs")
    table_offset = va_to_file(base, sections, TABLE)
    entries = list(struct.unpack_from("<5Q", data, table_offset))
    if entries[:3] != [WRAPPER, 0x180E63540, READER_THUNK]:
        raise ValueError("Unexpected adjacent PlayerSettings callback entries")
    windows, displacement_hits = code_displacement_hits(data, base, sections, TARGET)
    if len(displacement_hits) != 1 or displacement_hits[0]["displacement_va"] != 0x180E63518 or displacement_hits[0]["preceding_opcode"] != 0xE8:
        raise ValueError("Missing unique direct call to PlayerSettings field function")
    caller = instructions(caller_path)
    adjacent = instructions(adjacent_path)
    reader = instructions(reader_path)
    pptr = instructions(pptr_path)
    pptr_alt = instructions(pptr_alt_path)
    vector = instructions(vector_path)
    code = {
        "wrapper_to_field": require(caller, 0x180E63517, f"call        {TARGET:016X}"),
        "reader_thunk": require(adjacent, READER_THUNK, f"jmp         {READER:016X}"),
        "project_string_memory": require(reader, 0x180E66FCB, "[rdi+60h]"),
        "organization_string_memory": require(reader, 0x180E66FD7, "[rdi+0000000000000088h]"),
        "deny_vector": require(reader, 0x180E6714D, "call        0000000180E67FC0"),
        "allow_vector": require(reader, 0x180E6715C, "call        0000000180E67FC0"),
        "android_pptr": require(reader, 0x180E6717F, "call        0000000180093FC0"),
        "d3d12_pptr": require(reader, 0x180E6718E, "call        0000000180093FC0"),
        "allowed_memory": require(reader, 0x180E671A7, "[rdi+00000000000002C0h]"),
        "allowed_read": require(reader, 0x180E671C2, "dword ptr [rax]"),
        "allowed_cursor_advance": require(reader, 0x180E671C4, "[rbx+38h],4"),
        "allowed_store": require(reader, 0x180E671C9, "[rdi+00000000000002C0h],ecx"),
        "reader_return": require(reader, 0x180E671FF, "ret"),
        "pptr_fileid_advance": require(pptr, 0x180093FFF, "[rdx+38h],4"),
        "pptr_pathid_advance": require(pptr, 0x18009403F, "[rcx],8"),
        "pptr_alternate_fileid_advance": require(pptr_alt, 0x180094218, "[rdx+38h],4"),
        "pptr_alternate_pathid_advance": require(pptr_alt, 0x180094243, "[rcx],8"),
        "vector_count_advance": require(vector, 0x180E67FF6, "[rcx],4"),
        "vector_empty_exit": require(vector, 0x180E6802B, "cmp         rdi,rsi"),
    }
    resource, index = resource_index(resource_path)
    if index["unity"] != VERSION or index["format"] != 22 or index["type_trees"]:
        raise ValueError("Unexpected resource version, format or embedded type tree")
    objects = [obj for obj in index["objects"] if obj["class_id"] == 129 and obj["path_id"] == 1]
    if len(objects) != 1 or objects[0]["bytes"] != 916:
        raise ValueError("Missing expected PlayerSettings object")
    obj = objects[0]
    payload = resource[obj["offset"]:obj["offset"] + obj["bytes"]]
    node = release_node(schema_path)
    parser = ObjectReader(payload)
    values = parser.parse(node)
    if parser.pos != 912 or values.get("projectName") != "Sandcastle" or values.get("organizationId") != "fweibel":
        raise ValueError("Resource anchor values do not match")
    names = [field["name"] for field in parser.fields]
    tail = parser.fields[names.index("cloudEnabled"):]
    if tail[0]["relative_offset"] != 0x354 or tail[-1]["name"] != "allowedHttpConnections" or tail[-1]["relative_offset"] != 0x38C:
        raise ValueError("Unexpected suffix read positions")
    if any(payload[0x354:0x390]) or payload[0x390:0x394] != struct.pack("<I", 3):
        raise ValueError("Unexpected object suffix bytes")
    return {"binary": str(binary_path), "resource": str(resource_path),
            "schema": str(schema_path), "image_base": base,
            "resource_format": index["format"], "resource_unity_version": index["unity"],
            "function_ranges": {"wrapper": pdata_function(data, base, sections, WRAPPER),
                                "field": pdata_function(data, base, sections, TARGET),
                                "reader": pdata_function(data, base, sections, READER)},
            "direct_field_function_pointer_hits": direct_pointers,
            "wrapper_pointer_hits": wrapper_pointers,
            "table_entries": [{"slot": i, "va": TABLE + 8 * i,
                               "target": target} for i, target in enumerate(entries)],
            "code_windows_scanned": windows,
            "direct_call_displacement_hits": displacement_hits,
            "verified_instructions": code,
            "object": obj,
            "suffix_fields": tail,
            "static_binary_reader_mapping": {
                "precondition": "normal read branches, zero-length device-filter vectors, null 12-byte PPtrs, anchored organizationId end +0x354",
                "allowed_relative_offset": 0x38C,
                "allowed_uint32": struct.unpack_from("<I", payload, 0x38C)[0],
                "reader_end_relative_offset": 0x390,
                "remaining_relative_offset": 0x390,
                "remaining_uint32": struct.unpack_from("<I", payload, 0x390)[0],
                "actual_runtime_invocation": "Not Run"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "resource", "schema", "caller", "adjacent", "reader", "pptr", "pptr-alt", "vector", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    paths = [getattr(args, name).resolve(strict=True) for name in
             ("binary", "resource", "schema", "caller", "adjacent", "reader", "pptr", "pptr_alt", "vector")]
    result = probe(*paths)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"table": hex(TABLE), "reader": hex(READER),
                      "allowed_relative_offset": hex(result["static_binary_reader_mapping"]["allowed_relative_offset"]),
                      "allowed_uint32": result["static_binary_reader_mapping"]["allowed_uint32"],
                      "remaining_uint32": result["static_binary_reader_mapping"]["remaining_uint32"],
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
