"""Decode two narrow, PDB-identified unversioned properties in shipped Zen exports.

This is not a general Unreal asset parser. It fails closed if the expected export,
property selection, or nested struct layout is different. The property indices
come from the matching executable's generated PropPointers, not this reader.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def u16(data: bytes, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def u32(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def unversioned_header(data: bytes, start: int) -> tuple[list[dict], int]:
    """Return selected property indices and value start for UE's fragment header."""
    at = start
    property_index = 0
    fragments = []
    while True:
        word = u16(data, at)
        at += 2
        skip = word & 0x7F
        count = word >> 9
        property_index += skip
        fragments.append({
            "word": f"0x{word:04x}",
            "start_index": property_index,
            "value_count": count,
            "zero_mask": bool(word & 0x80),
            "last": bool(word & 0x100),
        })
        property_index += count
        if word & 0x100:
            break
        if len(fragments) > 256:
            raise ValueError("unversioned fragment header exceeds bound")
    zero_bits = []
    selected = []
    for fragment in fragments:
        count = fragment["value_count"]
        if fragment["zero_mask"]:
            width = (count + 7) // 8
            mask = data[at:at + width]
            if len(mask) != width:
                raise ValueError("truncated zero mask")
            at += width
            zero_bits.extend((mask[i // 8] >> (i % 8)) & 1 for i in range(count))
        else:
            zero_bits.extend([0] * count)
        selected.extend(range(fragment["start_index"], fragment["start_index"] + count))
    if len(selected) != len(zero_bits):
        raise ValueError("zero mask/property count mismatch")
    for index, zero in zip(selected, zero_bits):
        if zero:
            for fragment in fragments:
                if fragment["start_index"] <= index < fragment["start_index"] + fragment["value_count"]:
                    fragment.setdefault("zero_indices", []).append(index)
                    break
    return fragments, at


def export(zen: dict, index: int, cls: str) -> dict:
    item = zen["exports"][index]
    if item["index"] != index or item["class_script"] != cls:
        raise ValueError(f"unexpected export {index}: {item}")
    return item


def referenced_import(zen: dict, package_index: int) -> dict:
    if package_index >= 0:
        raise ValueError(f"expected import, got {package_index}")
    item = zen["imports"][-package_index - 1]
    if item["package_index"] != package_index:
        raise ValueError(f"import index mismatch: {package_index}")
    return item


def coal_slot(data: bytes, zen: dict) -> dict:
    item = export(zen, 2, "/Script/Engine.StaticMesh")
    if item["name"] != "SM_Ore_Coal":
        raise ValueError("not SM_Ore_Coal")
    start = item["data_offset"]
    end = start + item["size"]
    if end > len(data):
        raise ValueError("coal export outside input")
    header, at = unversioned_header(data, start)
    if [(f["start_index"], f["value_count"]) for f in header] != [(3, 4), (26, 1)]:
        raise ValueError(f"unexpected coal property selection: {header}")
    count_at = at
    count = i32(data, at)
    at += 4
    if count != 1:
        raise ValueError(f"unexpected StaticMaterials count: {count}")
    struct_start = at
    struct_header, at = unversioned_header(data, at)
    if [(f["start_index"], f["value_count"]) for f in struct_header] != [(0, 4)]:
        raise ValueError(f"unexpected FStaticMaterial selection: {struct_header}")
    material_at = at
    material_index = i32(data, at)
    material = referenced_import(zen, material_index)
    at += 4
    slots = []
    for field in ("MaterialSlotName", "ImportedMaterialSlotName"):
        index, number = u32(data, at), u32(data, at + 4)
        if index >= len(zen["names"]):
            raise ValueError(f"bad FName index {index}")
        slots.append({"field": field, "index": index, "number": number,
                      "name": zen["names"][index], "offset_in_export": at - start})
        at += 8
    return {
        "export": item["name"], "export_file_offset": start,
        "header": header, "values_start_in_export": count_at - start,
        "static_materials_count": count, "array_count_offset_in_export": count_at - start,
        "struct_start_in_export": struct_start - start, "struct_header": struct_header,
        "material_slot": 0, "material_offset_in_export": material_at - start,
        "material_package_index": material_index,
        "material_import": material,
        "names": slots,
        "unparsed_after_names": "UVChannelData and remaining StaticMesh fields",
    }


def world_selection(data: bytes, zen: dict) -> dict:
    item = export(zen, 1611, "/Script/Voxel.VoxelWorld")
    if item["name"] != "VoxelWorld":
        raise ValueError("not MainLevel VoxelWorld")
    start = item["data_offset"]
    end = start + item["size"]
    if end > len(data):
        raise ValueError("world export outside input")
    header, at = unversioned_header(data, start)
    expected = [
        (4, 3), (19, 2), (23, 2), (31, 2), (35, 1), (41, 1),
        (43, 1), (61, 1), (63, 2), (67, 1), (74, 1), (77, 1),
        (90, 2), (99, 4), (104, 3), (113, 1), (171, 1),
    ]
    if [(f["start_index"], f["value_count"]) for f in header] != expected:
        raise ValueError(f"unexpected VoxelWorld property selection: {header}")
    if [f.get("zero_indices", []) for f in header if f["zero_mask"]] != [[61]]:
        raise ValueError("unexpected VoxelWorld zero mask")
    values_start = at
    fields = {}

    def integer(name: str) -> int:
        nonlocal at
        offset = at - start
        value = i32(data, at)
        at += 4
        fields[name] = {"value": value, "offset_in_export": offset}
        return value

    def byte(name: str) -> int:
        nonlocal at
        offset = at - start
        value = data[at]
        at += 1
        if value not in (0, 1):
            raise ValueError(f"{name} has non-bool value {value}")
        fields[name] = {"value": value, "offset_in_export": offset}
        return value

    for name, expected_name in (
        ("WorldRoot", "Root"), ("LineBatchComponent", "LineBatchComponent"),
    ):
        package_index = integer(name)
        referred = zen["exports"][package_index - 1]
        if referred["name"] != expected_name:
            raise ValueError(f"{name} points to unexpected export {referred['name']}")
        fields[name]["referenced_export"] = referred["name"]
    integer("SaveObject")
    offset = at - start
    value = struct.unpack_from("<f", data, at)[0]
    at += 4
    fields["VoxelSize"] = {"value": value, "offset_in_export": offset}
    generator_header, at = unversioned_header(data, at)
    if [(f["start_index"], f["value_count"]) for f in generator_header] != [(1, 1)]:
        raise ValueError("unexpected generator struct")
    generator_ref = integer("GeneratorReference")
    fields["GeneratorReference"]["import"] = referenced_import(zen, generator_ref)
    byte("bCreateWorldAutomatically")
    byte("bUseCameraIfNoInvokersFound")
    integer("RenderOctreeDepth")
    integer("WorldSizeInVoxel")
    integer("MaxLOD")
    material_ref = integer("VoxelMaterial")
    fields["VoxelMaterial"]["import"] = referenced_import(zen, material_ref)
    lod_count = integer("LODMaterialsCount")
    if lod_count != 1:
        raise ValueError(f"unexpected LODMaterials count: {lod_count}")
    lod_header, at = unversioned_header(data, at)
    if [(f["start_index"], f["value_count"]) for f in lod_header] != [(0, 3)]:
        raise ValueError("unexpected FVoxelLODMaterials selection")
    lod_ref = integer("LODMaterial")
    fields["LODMaterial"]["import"] = referenced_import(zen, lod_ref)
    integer("LODStart")
    integer("LODEnd")
    proc_ref = integer("ProcMeshClass")
    fields["ProcMeshClass"]["import"] = referenced_import(zen, proc_ref)
    integer("ChunksCullingLOD")
    byte("bOptimizeIndices")
    byte("bMergeChunks")
    return {
        "export": item["name"], "export_file_offset": start,
        "header": header, "values_start_in_export": values_start - start,
        "generator_header": generator_header, "lod_material_header": lod_header,
        "fields": fields, "parsed_through_export_offset": at - start,
        "omitted_properties": {
            "ChunksClustersSize": 75,
            "bDoNotMergeCollisionsAndNavmesh": 76,
        },
        "unparsed_after_merge_flag": "remaining VoxelWorld fields",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mainlevel", type=Path, required=True)
    parser.add_argument("--mainlevel-zen", type=Path, required=True)
    parser.add_argument("--coal", type=Path, required=True)
    parser.add_argument("--coal-zen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "scope": "shipped Zen export static property values only",
        "world": world_selection(args.mainlevel.read_bytes(), json.loads(args.mainlevel_zen.read_text(encoding="utf-8"))),
        "coal": coal_slot(args.coal.read_bytes(), json.loads(args.coal_zen.read_text(encoding="utf-8"))),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
