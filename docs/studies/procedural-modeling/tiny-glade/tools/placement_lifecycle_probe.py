"""Read selected Tiny Glade placement-lifecycle instruction anchors.

Version-specific evidence reader. No target execution, emulation, or digest.
Addresses use the preferred image base; matching anchors do not prove runtime
ordering, complete control flow, or applicability to a different release.
"""

import argparse
import json
import math
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


CALLS = {
    "rectangle_ui_wrapper": (0x140AA9080, 0x140ADC7A0),
    "rectangle_submit": (0x140ADD67A, 0x141B75220),
    "rectangle_new_wall": (0x140A4C240, 0x140B0EB60),
    "edit_rectangle_state": (0x140B762F2, 0x14092E8E0),
    "finish_edit_history_add": (0x140ADDBDD, 0x140AE5180),
    "rotation_interpolate": (0x140B3F19C, 0x1419BDC40),
    "history_instant": (0x140B69C80, 0x140B6AE40),
    "timber_wrapper": (0x140FE3AF3, 0x141F4EFC0),
    "timber_clear": (0x141F4F284, 0x14281A140),
    "roof_animation_new": (0x14280E0B7, 0x140A007D0),
    "roof_animation_wrapper": (0x141F46270, 0x142808270),
    "spire_wrapper": (0x141F0FD41, 0x142801B00),
    "spire_collect": (0x142801D86, 0x140FC8440),
    "spire_iterate": (0x140FC846D, 0x140FC7CE0),
    "spire_record_callback": (0x140FC7F62, 0x141F0FF80),
    "spire_upload": (0x142801DFA, 0x140E55470),
    "signifier_despawn": (0x140922642, 0x140F04AA0),
}

ANCHORS = {
    "preview_mode_clear": (0x140ADCDCA, "41c7042400000000"),
    "timber_message_tag": (0x140ADD02C, "c704c801000000"),
    "timber_message_40_byte_index": (0x140ADD028, "488d0c9b"),
    "timber_message_filter": (0x141F4F381, "803a00"),
    "roof_initial_zeroes": (0x140A007D0, "0f57c00f57c9"),
    "roof_progress_write": (0x14280863C, "f3410f110c24"),
    "roof_second_progress_write": (0x14280866C, "f3410f11442404"),
    "spire_reads_second_progress": (0x141F0FF9C, "f3410f107104"),
    "spire_progress_in_option_payload": (0x141F10092, "f30f117620"),
    "spire_upload_32_byte_stride": (0x142801DB1, "48c1e105"),
    "finished_edit_clear": (0x140ADDD01, "41c70700000000"),
    "history_case3_dispatch": (0x140B69B9D, "0fb64709"),
    "history_interrupt_value": (0x140B68600, "b800020002c3"),
    "instant_selected_command_field": (0x140B6AF5C, "c7430800000000"),
    "rotation_zero_current": (0x140B3F173, "48c7453000000000"),
}


def inspect(binary, shader=None):
    pe = PeReader(binary)
    if pe.base != 0x140000000:
        raise ValueError("Unexpected preferred image base")
    calls = {}
    for name, (site, target) in CALLS.items():
        code = pe.read(site, 5)
        actual = site + 5 + struct.unpack_from("<i", code, 1)[0]
        if code[0] != 0xE8 or actual != target:
            raise ValueError(f"Call mismatch: {name} at {site:#x}")
        calls[name] = {"site": hex(site), "target": hex(actual)}
    anchors = {}
    for name, (site, expected) in ANCHORS.items():
        actual = pe.read(site, len(bytes.fromhex(expected)))
        if actual.hex() != expected:
            raise ValueError(f"Anchor mismatch: {name} at {site:#x}")
        anchors[name] = {"site": hex(site), "bytes": actual.hex()}

    # Inspect four selected entries only. This does not establish the complete
    # valid enum domain; case names have not been recovered here.
    table = 0x14305AE2C
    history_cases = [hex(table + struct.unpack("<i", pe.read(table + 4*i, 4))[0])
                     for i in range(4)]
    if history_cases != ["0x140b69bb1", "0x140b69bf0", "0x140b69c85", "0x140b69c70"]:
        raise ValueError("History dispatch mismatch")

    site = 0x1419BDC78
    instruction = pe.read(site, 8)
    if instruction[:4] != bytes.fromhex("f30f1005"):
        raise ValueError("Interpolation scalar-load mismatch")
    scalar_address = site + 8 + struct.unpack_from("<i", instruction, 4)[0]
    scalar = struct.unpack("<f", pe.read(scalar_address, 4))[0]
    if scalar != -20.0:
        raise ValueError("Interpolation exponential coefficient mismatch")

    shader_evidence = None
    if shader is not None:
        data = shader.read_bytes()
        expected = struct.pack("<5I", (5 << 16) | 72, 28, 1, 35, 16)
        if data[1639:1639+len(expected)] != expected:
            raise ValueError("Selected SPIR-V member-offset anchor mismatch")
        shader_evidence = {"path": str(shader.resolve()), "file_offset": 1639,
                           "type_id": 28, "member": 1, "offset": 16,
                           "interpretation": "roof_animation_t; name from retained SPIR-V decoding"}

    examples = []
    for difference in (1.0, 0.01):
        dt = 1/60
        exponential = abs(difference) * (1-math.exp(scalar*dt))
        linear = min(abs(difference), 2*dt)
        examples.append({"difference": difference, "dt": dt,
                         "exponential_step": exponential, "linear_step": linear,
                         "selected_step": max(exponential, linear)})
    return {"binary": str(binary.resolve()), "binary_bytes": len(pe.data),
            "calls": calls, "anchors": anchors, "history_raw_cases": history_cases,
            "interpolation_scalar": {"address": hex(scalar_address), "value": scalar},
            "shader_member_offset": shader_evidence, "constructed_examples": examples,
            "limitations": ["Ordinary file evidence, not REA provider Evidence.",
                            "Selected byte anchors only; semantic interpretation requires the report.",
                            "No target execution or runtime acceptance."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--spire-shader", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.binary, args.spire_shader)
    if args.output is None:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n",
                               encoding="utf-8")
        print(json.dumps({"calls": len(result["calls"]), "anchors": len(result["anchors"]),
                          "shader_checked": result["shader_member_offset"] is not None,
                          "output": str(args.output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
