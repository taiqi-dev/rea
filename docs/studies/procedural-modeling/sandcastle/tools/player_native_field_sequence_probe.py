"""Compare a bounded UnityPlayer field-name registration slice with Release tree.

The disassembly and PE are read-only inputs. Name order is evidence of a
registration path, not by itself proof of serialized payload byte offsets.
"""

import argparse
import difflib
import json
import re
import struct
from pathlib import Path

from unity_player_xref_probe import pe_layout
from player_color_space_probe import ObjectReader, release_node, resource_index


LINE = re.compile(r"^\s+([0-9A-F]{16}):\s+lea\s+([a-z][a-z0-9]*),\[([0-9A-F]{16})h\]$", re.I)
VERSION = "6000.4.10f1"
FUNCTION_START = 0x180E637D0
FUNCTION_END = 0x180E652AA
INSTRUCTION = re.compile(r"^\s+([0-9A-F]{16}):\s+(.*)$", re.I)
CALL = re.compile(r"call\s+([0-9A-F]{16})", re.I)
NODE_SIZE = re.compile(r"mov\s+dword ptr \[rdx\+rcx\+0Ch\],([0-9A-F]+)", re.I)


def string_at_va(binary, image_base, sections, va):
    rva = va - image_base
    section = next((s for s in sections
                    if s["rva"] <= rva < s["rva"] + s["size"]), None)
    if section is None:
        raise ValueError(f"VA {va:#x} not mapped to initialized PE bytes")
    offset = section["offset"] + rva - section["rva"]
    end = binary.find(b"\0", offset, min(len(binary), offset + 256))
    if end < 0:
        raise ValueError(f"No bounded NUL-terminated name at VA {va:#x}")
    return binary[offset:end].decode("ascii", errors="strict"), offset


def probe(binary_path, disassembly_path, schema_path, resource_path):
    binary = binary_path.read_bytes()
    image_base, sections = pe_layout(binary)
    lines = disassembly_path.read_text(encoding="utf-8-sig").splitlines()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("Version") != VERSION:
        raise ValueError("Schema version mismatch")
    matches = [x for x in schema.get("Classes", [])
               if x.get("TypeID") == 129 and x.get("Name") == "PlayerSettings"]
    if len(matches) != 1:
        raise ValueError("Missing unique PlayerSettings class")
    release = release_node(schema_path)["SubNodes"]
    expected = [x["Name"] for x in release]
    instructions = [INSTRUCTION.match(line) for line in lines]
    instructions = [(int(match.group(1), 16), match.group(2))
                    for match in instructions if match]
    if not instructions or instructions[0][0] != FUNCTION_START or instructions[-1][0] != FUNCTION_END:
        raise ValueError("Disassembly does not cover exact bounded PlayerSettings function")
    native = []
    all_field_names = []
    for i, line in enumerate(lines):
        match = LINE.match(line)
        if not match:
            continue
        address = int(match.group(1), 16)
        register = match.group(2).lower()
        string_va = int(match.group(3), 16)
        try:
            name, file_offset = string_at_va(binary, image_base, sections, string_va)
        except (UnicodeDecodeError, ValueError):
            continue
        if name in expected:
            all_field_names.append({"name_lea_va": address, "register": register,
                                    "name": name,
                                    "string_va": string_va,
                                    "string_file_offset": file_offset})
        # Scalar/PPtr registration specifically passes a field name to
        # this helper. Other top-level types use different helpers.
        following = "\n".join(lines[i + 1:i + 7])
        if register != "rdx" or "call        000000018120F4F0" not in following:
            continue
        native.append({"call_site_name_lea_va": address, "string_va": string_va,
                       "string_file_offset": file_offset, "name": name})
    observed = [x["name"] for x in native]
    matcher = difflib.SequenceMatcher(a=expected, b=observed, autojunk=False)
    operations = [{"tag": tag, "release_range": [a0, a1],
                   "native_range": [b0, b1], "release": expected[a0:a1],
                   "native": observed[b0:b1]}
                  for tag, a0, a1, b0, b1 in matcher.get_opcodes()]
    all_observed = [x["name"] for x in all_field_names]
    all_matcher = difflib.SequenceMatcher(a=expected, b=all_observed, autojunk=False)
    all_operations = [{"tag": tag, "release_range": [a0, a1],
                       "native_range": [b0, b1], "release": expected[a0:a1],
                       "native": all_observed[b0:b1]}
                      for tag, a0, a1, b0, b1 in all_matcher.get_opcodes()]
    # The last known nonzero string gives an independent payload anchor; the
    # trailing all-zero run cannot by itself identify an inserted field.
    data, index = resource_index(resource_path)
    if index["unity"] != VERSION or index["format"] != 22 or index["type_trees"]:
        raise ValueError("Resource is not the expected stripped Unity 6000.4.10f1 file")
    objects = [x for x in index["objects"] if x["class_id"] == 129 and x["path_id"] == 1]
    if len(objects) != 1 or objects[0]["bytes"] != 916:
        raise ValueError("Missing exact 916-byte PlayerSettings object")
    obj = objects[0]
    payload = data[obj["offset"]:obj["offset"] + obj["bytes"]]
    reader = ObjectReader(payload)
    values = reader.parse(matches[0]["ReleaseRootNode"])
    if reader.pos != 912 or values.get("projectName") != "Sandcastle" or values.get("organizationId") != "fweibel":
        raise ValueError("PlayerSettings payload anchors or Release consumption changed")
    tail_fields = [field for field in reader.fields if field["name"] in expected[139:]]
    tail_name_leas = [field for field in all_field_names if field["name"] in expected[139:]]
    if [field["name"] for field in tail_fields] != expected[139:] or [field["name"] for field in tail_name_leas] != expected[139:]:
        raise ValueError("Final 35 field names do not match Release order")
    field_nodes = {field["Name"]: field for field in release[139:]}
    native_tail = []
    for i, field in enumerate(tail_name_leas):
        begin = field["name_lea_va"]
        end = tail_name_leas[i + 1]["name_lea_va"] if i + 1 < len(tail_name_leas) else FUNCTION_END
        segment = [asm for va, asm in instructions if begin <= va < end]
        calls = [int(match.group(1), 16) for asm in segment if (match := CALL.search(asm))]
        sizes = [int(match.group(1), 16) for asm in segment if (match := NODE_SIZE.search(asm))]
        public = field_nodes[field["name"]]
        native_tail.append({"name": field["name"], "name_lea_va": begin,
                            "native_calls_until_next_field": [hex(call) for call in calls],
                            "native_direct_node_size_stores": sizes,
                            "release_type": public["TypeName"],
                            "release_byte_size": public["ByteSize"],
                            "release_meta_flag": public["MetaFlag"],
                            "serialized_offset": tail_fields[i]["relative_offset"],
                            "serialized_bytes": tail_fields[i]["bytes"],
                            "serialized_value": tail_fields[i]["value"]})
    if payload[0x354:0x390] != bytes(0x390 - 0x354) or payload[0x390:0x394] != struct.pack("<I", 3):
        raise ValueError("Expected zero suffix and final three changed")
    return {"binary": str(binary_path), "disassembly": str(disassembly_path),
            "schema": str(schema_path), "resource": str(resource_path), "version": VERSION,
            "release_fields": len(expected), "native_registrations": len(observed),
            "native_sequence": native, "comparison": operations,
            "all_matching_name_leas": all_field_names,
            "all_name_comparison": all_operations,
            "native_tail": native_tail,
            "payload_boundary": {"object_file_offset": obj["offset"],
                                 "object_length": obj["bytes"],
                                 "last_independent_string": "organizationId=fweibel",
                                 "last_string_end": 0x354,
                                 "zero_suffix_start": 0x354,
                                 "zero_suffix_end": 0x390,
                                 "zero_suffix_bytes": 0x390 - 0x354,
                                 "last_two_uint32": list(struct.unpack("<II", payload[0x38c:0x394]))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--disassembly", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--resource", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    result = probe(args.binary.resolve(strict=True), args.disassembly.resolve(strict=True),
                   args.schema.resolve(strict=True), args.resource.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"release_fields": result["release_fields"],
                      "native_registrations": result["native_registrations"],
                      "all_name_leas": len(result["all_matching_name_leas"]),
                      "tail_fields": len(result["native_tail"]),
                      "all_diff_tags": [x["tag"] for x in result["all_name_comparison"]],
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
