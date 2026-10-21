"""Verify selected shadow-budget anchors in this Tiny Glade build.

Static PE and previously decoded SPIR-V only. No target code runs, and this
ordinary local record is not REA Evidence.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


EXPECTED_BYTES = {
    "three_cascades_argument": (0x1400FB11F, "41b803000000"),
    "shadow_resolution_argument": (0x1400FB128, "6641b90004"),
    "maximum_depth_argument": (0x1400FB110, "c74424280000fa44"),
    "maximum_depth_sixth_argument_read": (0x140CAD8F1, "f30f10b42468020000"),
    "setup_buffer_resolution_shift": (0x140CAD94D, "48c1e10a"),
    "return_binding_set_at_34": (0x140CADCFF, "66896834"),
    "return_resolution_at_36": (0x140CADD03, "6644896836"),
    "cascade_loop_bound": (0x1400FB483, "4983fe03"),
    "shadow_hzb_loop_bound": (0x1400FB562, "4983fe03"),
    "shadow_pass_dimension_read": (0x140B00837, "410fb75e36"),
    "square_texture_dimension_pair": (0x140B008CF, "89c1c1e11009c1"),
    "shadow_pass_layer_read": (0x140B00A48, "418b7e28"),
    "shadow_pass_layer_view": (0x140B00D07, "31c9"),
    "shadow_list_mode": (0x1400FB68C, "c744242001000000"),
}

EXPECTED_CALLS = {
    "cascade_setup": (0x1400FB12D, 0x140CAD8C0),
    "shadow_hzb": (0x1400FB585, 0x1409AD100),
    "wall_shadow_lists": (0x1400FB5F3, 0x1409BA5D0),
    "shadow_iterator": (0x1400FB67E, 0x1409D1290),
    "generic_shadow_lists": (0x1400FB6A1, 0x1409B6690),
    "shadow_pass": (0x1400FBAE3, 0x140B00540),
}


def inspect(binary: Path, setup_json: Path, wall_json: Path):
    pe = PeReader(binary)
    if binary.stat().st_size != 65612184 or pe.base != 0x140000000:
        raise ValueError("Unexpected Tiny Glade PE identity/size")
    anchors = []
    for label, (address, expected) in EXPECTED_BYTES.items():
        actual = pe.read(address, len(bytes.fromhex(expected))).hex()
        if actual != expected:
            raise ValueError(f"{label} mismatch at {address:#x}: {actual}")
        anchors.append({"label": label, "va": hex(address), "bytes": actual})
    calls = []
    for label, (address, target) in EXPECTED_CALLS.items():
        raw = pe.read(address, 5)
        actual = address + 5 + struct.unpack_from("<i", raw, 1)[0]
        if raw[0] != 0xE8 or actual != target:
            raise ValueError(f"{label} mismatch at {address:#x}")
        calls.append({"label": label, "va": hex(address), "target": hex(actual)})
    shaders = []
    for label, path, expected_fetches in (
        ("setup_shadows", setup_json, 1),
        ("wall_shadow", wall_json, 12),
    ):
        decoded = json.loads(path.read_text(encoding="utf-8"))
        if decoded["candidates"] != 1 or decoded["rejected"] or len(decoded["modules"]) != 1:
            raise ValueError(f"{label}: incomplete SPIR-V structural decode")
        module = decoded["modules"][0]
        fetches = sum(row["op"] == "OpImageFetch" for row in module["instructions"])
        if fetches != expected_fetches:
            raise ValueError(f"{label}: unexpected ImageFetch instruction count {fetches}")
        shaders.append({"label": label, "path": decoded["input"],
                        "module_offset": module["offset"], "instructions": module["instruction_count"],
                        "image_fetch_instructions": fetches})
    return {"binary": str(binary), "binary_bytes": binary.stat().st_size,
            "preferred_base": hex(pe.base), "anchors": anchors, "calls": calls,
            "shader_structure": shaders,
            "limitations": ["Static PE/SPIR-V checks, not REA Evidence",
                            "No execution, scheduling frequency, GPU time or allocation readback"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--setup-spv", required=True, type=Path)
    parser.add_argument("--wall-spv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = inspect(args.binary.resolve(strict=True), args.setup_spv, args.wall_spv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"anchors": len(output["anchors"]), "calls": len(output["calls"]),
                      "shaders": len(output["shader_structure"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
