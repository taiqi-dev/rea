"""Read selected Tiny Glade steady-render call/branch anchors from this build.

This is a version-specific static evidence reader, not a renderer or emulator.
It never loads target code or computes a digest. PDB names are corroborated by
the separate address probes; a call does not establish runtime reachability.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


CALLS = {
    "gather_walls": (0x1400FA5F2, 0x1409B8A20),
    "wall_first": (0x1400FA6FB, 0x1409B91B0),
    "generic_first": (0x1400FA7A1, 0x1409B6690),
    "main_first": (0x1400FABCD, 0x1409AC8E0),
    "main_hzb": (0x1400FABEC, 0x1409AD100),
    "wall_second": (0x1400FACAE, 0x1409BA020),
    "generic_second": (0x1400FAD62, 0x1409B6690),
    "main_second": (0x1400FAF8F, 0x1409ABE20),
    "shadow_hzb": (0x1400FB585, 0x1409AD100),
    "wall_shadow": (0x1400FB5F3, 0x1409BA5D0),
    "generic_shadow": (0x1400FB6A1, 0x1409B6690),
    "oc2_gbuffer_raster": (0x1409AC0C1, 0x141758190),
    "oc2_gbuffer_bucket": (0x14175835E, 0x140AF4DC0),
    "first_gbuffer_bucket": (0x1417557A8, 0x140AF4DC0),
    "prebuilt_pipeline": (0x140AF51B9, 0x140E21920),
    "stack_sets": (0x140AF51E4, 0x140E24E00),
    "optional_set": (0x140AF51FA, 0x140E23FA0),
}

ANCHORS = {
    "first_hzb_absent": (0x1400FA79B, "4531c04531c9"),
    "second_mode_one": (0x1400FAD5C, "41b901000000"),
    "freeze_value_test": (0x1400FABF9, "803800"),
    "oc2_bucket_offset": (0x14175833E, "488b90b8000000"),
    "three_stack_sets": (0x140AF51D6, "41b803000000"),
    "entry_stride": (0x140AF509A, "4983c640"),
    "callback_test": (0x140AF523F, "498b46204885c0"),
    "list_mode_test": (0x1409B876D, "83bdd404000000"),
    "second_list_span": (0x1409B8774, "b920020000"),
    "shadow_list_span": (0x1409B8784, "b840040000"),
    "pipeline_handle_write": (0x140E21AA4, "48895048"),
    "pipeline_dirty_bits": (0x140E21AA8, "81888802000001000100"),
    "stack_dirty_bit": (0x140E24F26, "80898802000020"),
}

STRINGS = {
    0x143029436: "G-buffer OC/2",
    0x143029443: "G-buffer emissive OC/2",
    0x143029459: "G-buffer velocity OC/2",
    0x14302946F: "Forward OC/2",
    0x14302947B: "Velocity OC/2",
    0x143029526: "Generate HZB",
}


def inspect(binary):
    pe = PeReader(binary)
    if pe.base != 0x140000000:
        raise ValueError("Unexpected image base")
    calls = []
    for label, (address, expected) in CALLS.items():
        raw = pe.read(address, 5)
        target = address + 5 + struct.unpack_from("<i", raw, 1)[0]
        if raw[0] != 0xE8 or target != expected:
            raise ValueError(f"Call mismatch: {label} at {address:#x}")
        calls.append({"label": label, "address": hex(address), "target": hex(target)})
    anchors = []
    for label, (address, expected) in ANCHORS.items():
        if pe.read(address, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f"Instruction mismatch: {label} at {address:#x}")
        anchors.append({"label": label, "address": hex(address), "bytes": expected})
    branch = pe.read(0x1400FABFC, 6)
    target = 0x1400FABFC + 6 + struct.unpack_from("<i", branch, 2)[0]
    if branch[:2] != b"\x0f\x85" or target != 0x1400FADDA:
        raise ValueError("Unexpected freeze branch")
    strings = []
    for address, expected in STRINGS.items():
        value = pe.read(address, len(expected.encode("utf-8"))).decode("utf-8")
        if value != expected:
            raise ValueError(f"String mismatch at {address:#x}")
        strings.append({"address": hex(address), "value": value})
    return {
        "binary": str(binary.resolve()), "bytes": binary.stat().st_size,
        "image_base": hex(pe.base), "calls": calls, "anchors": anchors,
        "freeze_branch": {"address": "0x1400fabfc", "target": hex(target)},
        "strings": strings,
        "limitations": ["Ordinary local PE evidence, not REA Evidence",
                        "No execution, frame counts or timings observed",
                        "No full control-flow or physical-resource identity proof"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"calls": len(result["calls"]), "anchors": len(result["anchors"]),
                      "strings": len(result["strings"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
