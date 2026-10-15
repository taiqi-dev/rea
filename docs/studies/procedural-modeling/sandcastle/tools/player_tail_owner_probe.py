"""Bounded static follow-up for Sandcastle PlayerSettings tail ownership.

Checks the PlayerSettings constructor vptr, class registration, and adjacent
callbacks. It does not infer a generic loader from the presence of vtable slots.
"""

import argparse
import json
import re
import struct
from pathlib import Path

from player_callback_table_probe import (code_displacement_hits, instructions,
                                         pdata_function, pointer_hits, require,
                                         va_to_file)
from player_color_space_probe import resource_index
from unity_player_xref_probe import pe_layout


VTABLE_HEAD = 0x181EB1A30
POINTER_RUN_START = 0x181EB1988
POINTER_RUN_END = 0x181EB1AE0
CLASS_DESCRIPTOR = 0x1821755B0
CLASS_NAME = 0x181EB1EB0
CLASS_FACTORY = 0x180E63550
SECOND_SLOT = 0x180E63540
THIRD_SLOT = 0x180E63530
SECOND_BODY = 0x180E67200
THIRD_BODY = 0x180E652B0
VIRTUAL_CALL = re.compile(r"call\s+qword ptr \[r10\]", re.I)


def probe(binary_path, resource_path, thunks_path, second_path, third_tail_path,
          constructor_path, registration_path, registry_path, factory_path):
    data = binary_path.read_bytes()
    base, sections = pe_layout(data)
    if base != 0x180000000:
        raise ValueError("Unexpected UnityPlayer image base")
    table_offset = va_to_file(base, sections, VTABLE_HEAD)
    table = list(struct.unpack_from("<23Q", data, table_offset))
    if table[16:19] != [0x180E634E0, SECOND_SLOT, THIRD_SLOT]:
        raise ValueError("Adjacent PlayerSettings callbacks changed")
    pointer_run_offset = va_to_file(base, sections, POINTER_RUN_START)
    pointer_run = list(struct.unpack_from("<44Q", data, pointer_run_offset))
    text_sections = [s for s in sections if s["executable"]]
    def is_code_pointer(value):
        return any(base + s["rva"] <= value < base + s["rva"] + s["size"]
                   for s in text_sections)
    if not all(map(is_code_pointer, pointer_run)) or pointer_run[21:] != table:
        raise ValueError("Continuous code-pointer run changed")
    before = struct.unpack_from("<Q", data, pointer_run_offset - 8)[0]
    after = data[va_to_file(base, sections, POINTER_RUN_END + 8):
                 va_to_file(base, sections, POINTER_RUN_END + 8) + 24]
    if is_code_pointer(before) or not after.startswith(b"AndroidDeviceFilterData\x00"):
        raise ValueError("Pointer-run data boundaries changed")
    thunks = instructions(thunks_path)
    second = instructions(second_path)
    third = instructions(third_tail_path)
    constructor = instructions(constructor_path)
    registration = instructions(registration_path)
    registry = instructions(registry_path)
    factory = instructions(factory_path)
    anchors = {
        "second_clear": require(thunks, SECOND_SLOT, "byte ptr [rdx+6Dh],0"),
        "second_jump": require(thunks, 0x180E63544, f"jmp         {SECOND_BODY:016X}"),
        "third_jump": require(thunks, THIRD_SLOT, f"jmp         {THIRD_BODY:016X}"),
        "second_allowed_read": require(second, 0x180E67452, "eax,dword ptr [rdi+00000000000002C0h]"),
        "second_allowed_self_store": require(second, 0x180E6746B, "[rdi+00000000000002C0h],eax"),
        "second_return": require(second, 0x180E67476, "ret"),
        "third_allowed_store": require(third, 0x180E671C9, "[rdi+00000000000002C0h],ecx"),
        "third_return": require(third, 0x180E671FF, "ret"),
        "vptr_first_lea": require(constructor, 0x180E61DBA, "lea         rax,[0000000181EB1A30h]"),
        "vptr_first_store": require(constructor, 0x180E61DC4, "mov         qword ptr [rcx],rax"),
        "vptr_second_lea": require(constructor, 0x180E61F13, "lea         rax,[0000000181EB1A30h]"),
        "vptr_second_store": require(constructor, 0x180E61F24, "mov         qword ptr [rcx],rax"),
        "factory_lea": require(registration, 0x1816980E7, "lea         rax,[0000000180E63550h]"),
        "factory_native_size": require(factory, 0x180E63580, "mov         edx,530h"),
        "factory_constructor_jump": require(factory, 0x180E6359B, "jmp         0000000180E61F10"),
        "factory_store": require(registration, 0x1816980EE, "mov         qword ptr [00000001821755B8h],rax"),
        "descriptor_lea": require(registration, 0x1816980F5, "lea         rdx,[00000001821755B0h]"),
        "descriptor_register": require(registration, 0x18169813B, "call        0000000181690D10"),
        "registry_name_read": require(registry, 0x181690D23, "r8,qword ptr [rdx+10h]"),
        "registry_class_id_read": require(registry, 0x181690D2A, "edx,dword ptr [rdx+28h]"),
    }
    descriptor_offset = va_to_file(base, sections, CLASS_DESCRIPTOR)
    descriptor_name, = struct.unpack_from("<Q", data, descriptor_offset + 0x10)
    class_id, native_size = struct.unpack_from("<II", data, descriptor_offset + 0x28)
    name_offset = va_to_file(base, sections, CLASS_NAME)
    if descriptor_name != CLASS_NAME or data[name_offset:name_offset + 15] != b"PlayerSettings\x00" or class_id != 129 or native_size != 0x530:
        raise ValueError("Class descriptor identity changed")
    second_direct_cursor_advances = [{"va": va, "instruction": asm}
                                     for va, asm in second.items()
                                     if re.search(r"\b(add|inc|sub)\s+qword ptr \[rbx\+38h\]", asm, re.I)]
    if second_direct_cursor_advances:
        raise ValueError("Second callback now directly advances [rbx+38h]")
    virtual_calls = [{"va": va, "instruction": asm} for va, asm in second.items()
                     if VIRTUAL_CALL.search(asm)]
    if len(virtual_calls) != 6:
        raise ValueError("Second callback virtual call count changed")
    absolute_head = pointer_hits(data, base, sections, VTABLE_HEAD)
    windows, rip_head = code_displacement_hits(data, base, sections, VTABLE_HEAD)
    expected_displacements = [0x180E61DBD, 0x180E61F16]
    if absolute_head or sorted(h["displacement_va"] for h in rip_head) != expected_displacements:
        raise ValueError("Vtable-head constructor references changed")
    _, rip_factory = code_displacement_hits(data, base, sections, CLASS_FACTORY)
    if [h["displacement_va"] for h in rip_factory] != [0x1816980EA]:
        raise ValueError("Class factory registration reference changed")
    _, rip_second_body = code_displacement_hits(data, base, sections, SECOND_BODY)
    _, rip_third_body = code_displacement_hits(data, base, sections, THIRD_BODY)
    if len(rip_second_body) != 1 or rip_second_body[0]["displacement_va"] != 0x180E63545:
        raise ValueError("Second body does not have only its verified thunk jump")
    if len(rip_third_body) != 1 or rip_third_body[0]["displacement_va"] != 0x180E63531:
        raise ValueError("Third body does not have only its verified thunk jump")
    resource, index = resource_index(resource_path)
    objects = [obj for obj in index["objects"] if obj["class_id"] == 129 and obj["path_id"] == 1]
    if index["unity"] != "6000.4.10f1" or index["format"] != 22 or len(objects) != 1:
        raise ValueError("Unexpected resource identity")
    obj = objects[0]
    payload = resource[obj["offset"]:obj["offset"] + obj["bytes"]]
    if obj["bytes"] != 916 or payload[0x38C:0x394] != b"\x00\x00\x00\x00\x03\x00\x00\x00":
        raise ValueError("Unexpected PlayerSettings object tail")
    return {"binary": str(binary_path), "resource": str(resource_path),
            "resource_unity": index["unity"], "resource_format": index["format"],
            "player_settings_object": obj,
            "vtable_head_va": VTABLE_HEAD,
            "vtable_head_file_offset": table_offset,
            "continuous_code_pointer_run": {"start_va": POINTER_RUN_START,
                                            "end_va_inclusive": POINTER_RUN_END,
                                            "entry_count": len(pointer_run),
                                            "before_qword": before,
                                            "after_bytes_ascii": after.decode("ascii", errors="replace")},
            "class_descriptor": {"va": CLASS_DESCRIPTOR, "name_pointer": descriptor_name,
                                 "name": "PlayerSettings", "class_id": class_id,
                                 "native_object_size": native_size,
                                 "factory_slot_va": CLASS_DESCRIPTOR + 8,
                                 "factory_registered_at": 0x1816980EE,
                                 "factory_target": CLASS_FACTORY},
            "table_entries": [{"slot": i, "va": VTABLE_HEAD + 8 * i, "target": target}
                              for i, target in enumerate(table)],
            "second_function": pdata_function(data, base, sections, SECOND_BODY),
            "third_function": pdata_function(data, base, sections, THIRD_BODY),
            "verified_instructions": anchors,
            "second_virtual_calls": virtual_calls,
            "second_direct_cursor_advances": second_direct_cursor_advances,
            "exact_vtable_head_absolute_pointer_hits": absolute_head,
            "exact_vtable_head_rip_hits": rip_head,
            "factory_rip_hits": rip_factory,
            "verified_direct_vtable_head_references": [anchors["vptr_first_lea"], anchors["vptr_second_lea"]],
            "code_windows_scanned": windows,
            "second_body_rip_hits": rip_second_body,
            "third_body_rip_hits": rip_third_body,
            "reader_final_offset_from_prior_probe": 0x390,
            "object_length": obj["bytes"],
            "unassigned_tail_uint32": struct.unpack_from("<I", payload, 0x390)[0],
            "outer_loader_length_gate": "Unknown: class registration and vptr constructors are proven; no generic loader virtual-call target or final object-bound handling is identified",
            "runtime_invocation": "Not Run"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "resource", "thunks", "second", "third-tail", "constructor", "registration", "registry", "factory", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    paths = [getattr(args, name).resolve(strict=True) for name in
             ("binary", "resource", "thunks", "second", "third_tail", "constructor", "registration", "registry", "factory")]
    result = probe(*paths)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"second_virtual_calls": len(result["second_virtual_calls"]),
                      "tail_uint32": result["unassigned_tail_uint32"],
                      "outer_loader_length_gate": result["outer_loader_length_gate"],
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
