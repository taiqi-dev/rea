"""Read the bounded MainLevel voxel mesher/collision configuration.

The parser checks this shipped Zen export and selected native instruction bytes.
It never loads or executes the game. It does not compute a content digest.
"""

import argparse
import json
import struct
import sys
from pathlib import Path

from voxel_render_config_probe import referenced_import, world_selection

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sandcastle/tools"))
from player_callback_table_probe import va_to_file
from unity_player_xref_probe import pe_layout


def probe(mainlevel: Path, zen_path: Path, binary: Path) -> dict:
    zen = json.loads(zen_path.read_text(encoding="utf-8"))
    level = mainlevel.read_bytes()
    world = world_selection(level, zen)
    start = world["export_file_offset"]
    if world["parsed_through_export_offset"] != 103:
        raise ValueError("unexpected first property boundary")
    selected = {i for f in world["header"] for i in range(f["start_index"], f["start_index"] + f["value_count"])}
    absent = {58: "RenderType", 73: "bEnableTransitions", 83: "bEnableCollisions",
              89: "bComputeVisibleChunksCollisions"}
    if any(i in selected for i in absent) or not {77, 90, 91}.issubset(selected):
        raise ValueError("unexpected selected mesher/collision properties")
    bounds = struct.unpack_from("<f", level, start + 103)[0]
    visible_lod = struct.unpack_from("<i", level, start + 107)[0]
    physics_material = struct.unpack_from("<i", level, start + 111)[0]
    if bounds != 20.0 or visible_lod != 2 or physics_material != -330:
        raise ValueError("unexpected selected collision values")
    physics_import = referenced_import(zen, physics_material)

    pe = binary.read_bytes()
    base, sections = pe_layout(pe)
    if base != 0x140000000 or len(pe) != 145180160:
        raise ValueError("unexpected selected PE profile")

    def exact(va: int, encoded: str) -> dict:
        wanted = bytes.fromhex(encoded)
        offset = va_to_file(base, sections, va)
        if pe[offset:offset + len(wanted)] != wanted:
            raise ValueError(f"native anchor changed: {va:#x}")
        return {"va": hex(va), "file_offset": offset, "bytes": encoded}

    def descriptor(va: int, name: str, member_offset: int) -> dict:
        offset = va_to_file(base, sections, va)
        name_va = struct.unpack_from("<Q", pe, offset)[0]
        name_offset = va_to_file(base, sections, name_va)
        expected_name = name.encode("ascii") + b"\0"
        array_dim, observed_offset = struct.unpack_from("<HH", pe, offset + 48)
        if (pe[name_offset:name_offset + len(expected_name)] != expected_name
                or array_dim != 1 or observed_offset != member_offset):
            raise ValueError(f"property descriptor changed: {name}")
        return {"va": hex(va), "file_offset": offset, "name_va": hex(name_va),
                "member_offset": hex(observed_offset), "array_dim": array_dim}

    anchors = {
        "ctor_render_type_zero": exact(0x1441C8BD2, "88 9f 7c 05 00 00"),
        "ctor_transitions_on_merge_off": exact(0x1441C8C2B, "66 c7 87 b0 05 00 00 01 00"),
        "ctor_collision_on": exact(0x1441C8CF5, "c6 87 28 06 00 00 01"),
        "ctor_visible_collision_on": exact(0x1441C8D0B, "c6 87 ac 07 00 00 01"),
        "ctor_visible_collision_max_lod_five": exact(0x1441C8D12, "c7 87 b0 07 00 00 05 00 00 00"),
        "transition_setter": exact(0x143E223D0, "c6 81 b0 05 00 00 01"),
        "collision_setter": exact(0x143E22400, "c6 81 28 06 00 00 01"),
        "visible_collision_setter": exact(0x143E22430, "c6 81 ac 07 00 00 01"),
    }
    descriptors = {
        "RenderType": descriptor(0x14719E410, "RenderType", 0x57C),
        "BoundsExtension": descriptor(0x14719E920, "BoundsExtension", 0x5BC),
        "VisibleChunksCollisionsMaxLOD": descriptor(0x14719EC50, "VisibleChunksCollisionsMaxLOD", 0x7B0),
        "PhysMaterialOverride": descriptor(0x14719EC90, "PhysMaterialOverride", 0x7B8),
    }
    return {
        "mainlevel": str(mainlevel), "zen": str(zen_path), "binary": str(binary),
        "world_export": {"index": 1611, "file_offset": start, "size": 448},
        "selected_indices": sorted(selected), "absent_indices": absent,
        "fields": {
            "BoundsExtension": {"index": 77, "export_offset": 103, "value": bounds},
            "VisibleChunksCollisionsMaxLOD": {"index": 90, "export_offset": 107, "value": visible_lod},
            "PhysMaterialOverride": {"index": 91, "export_offset": 111,
                                     "package_index": physics_material, "import": physics_import},
        },
        "native_anchors": anchors,
        "property_descriptors": descriptors,
        "scope": "Static package values and selected native constructor/setter instruction bytes only",
        "runtime": "Not Run",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mainlevel", type=Path, required=True)
    parser.add_argument("--zen", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    result = probe(args.mainlevel.resolve(strict=True), args.zen.resolve(strict=True),
                   args.binary.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
    print(json.dumps({"visible_collision_max_lod": result["fields"]["VisibleChunksCollisionsMaxLOD"]["value"],
                      "absent": len(result["absent_indices"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
