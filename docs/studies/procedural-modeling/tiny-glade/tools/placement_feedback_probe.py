"""Read selected Tiny Glade preview/animation anchors from the studied PE.

This version-specific reader never loads target code or computes a digest.
Its direct-call and scalar observations are ordinary-file evidence, not REA
Evidence. Complete source identity is recorded separately by the study.
"""

import argparse
import json
import struct
from pathlib import Path

from atlas_budget_probe import PeReader


CALLS = {
    "rectangle_writer_clear": (0x141F4F284, 0x14281A140),
    "rectangle_plank_default": (0x141F4F6F6, 0x140A77410),
    "rectangle_plank_push": (0x141F4F749, 0x1428199B0),
    "circle_plank_default": (0x14281A90F, 0x140A77410),
    "circle_plank_push": (0x14281A95F, 0x1428199B0),
}

ANCHORS = {
    "rectangle_requires_two_subdivisions": (0x141F4F91C, "4883fe02"),
    "rectangle_first_interior_index": (0x141F4F968, "41bf01000000"),
    "circle_minimum_comparison": (0x14281A7A3, "4983f807"),
    "circle_minimum_six": (0x14281A7A7, "b806000000"),
    "roof_first_channel_write": (0x14280863C, "f3410f110c24"),
    "roof_second_channel_write": (0x14280866C, "f3410f11442404"),
}


def inspect(binary):
    pe = PeReader(binary)
    if pe.base != 0x140000000 or len(pe.data) != 65612184:
        raise ValueError("Unexpected study build layout")
    calls = []
    for label, (address, expected) in CALLS.items():
        raw = pe.read(address, 5)
        target = address + 5 + struct.unpack_from("<i", raw, 1)[0]
        if raw[0] != 0xE8 or target != expected:
            raise ValueError(f"Direct call mismatch: {label} at {address:#x}")
        calls.append({"label": label, "va": hex(address), "target": hex(target)})
    anchors = []
    for label, (address, expected) in ANCHORS.items():
        if pe.read(address, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f"Instruction mismatch: {label} at {address:#x}")
        anchors.append({"label": label, "va": hex(address), "bytes": expected})
    scalars = []
    for label, address, expected in [
        ("rectangle_spacing", 0x141F4F8CE, 0x3FC147AE),
        ("circle_spacing", 0x14281A759, 0x3FC00000),
    ]:
        raw = pe.read(address, 8)
        if raw[:4] != bytes.fromhex("f30f5e05"):
            raise ValueError(f"Unexpected RIP-relative division: {label}")
        constant_va = address + 8 + struct.unpack_from("<i", raw, 4)[0]
        value_bytes = pe.read(constant_va, 4)
        if struct.unpack("<I", value_bytes)[0] != expected:
            raise ValueError(f"Scalar mismatch: {label}")
        scalars.append({"label": label, "va": hex(address),
                        "constant_va": hex(constant_va),
                        "value": struct.unpack("<f", value_bytes)[0]})
    return {"binary": str(pe.path), "bytes": len(pe.data), "image_base": hex(pe.base),
            "calls": calls, "anchors": anchors, "scalars": scalars,
            "limitations": ["Version-specific ordinary PE observations, not REA Evidence",
                            "No complete creation/removal or final draw-binding proof",
                            "No target execution, timings, frame counts or FPS measurement"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    result = inspect(args.binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"calls": len(result["calls"]), "anchors": len(result["anchors"]),
                      "scalars": len(result["scalars"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
