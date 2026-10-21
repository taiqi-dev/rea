"""Check the measured coarse indirect-submission chain in one Tiny Glade PE.

This is a bounded, version-specific static reader. It never executes target
code, calculates a digest, or claims a live draw count.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


ANCHORS = {
    "sublist_kind_gate": (0x1409E677C, "4180f91d"),
    "kind_stride_160_a": (0x1409E6799, "83e01f"),
    "kind_stride_160_b": (0x1409E679C, "488d0480c1e005"),
    "per_kind_lock_state": (0x1409E67AB, "498b440438"),
    "guarded_data_selection": (0x1409E6826, "488d8f88000000488d571048f7d8480f40ca"),
    "count_saved": (0x1409E6838, "488b4108488945f0"),
    "sublist_index_bounds": (0x1409E6887, "4839d60f83ca010000"),
    "start_command_load": (0x1409E6894, "448b24b0"),
    "start_to_bytes_a": (0x1409E69C4, "49c1e402"),
    "start_to_bytes_b": (0x1409E69C8, "4f8d04a4"),
    "call_args": (0x1409E69C0, "4c8b4df049c1e4024f8d04a4488d55d44889f9"),
    "recorder_view_offset": (0x140E24D41, "418b47084901c6"),
    "recorder_byte_offset_store": (0x140E24D5D, "4489b6dc000000"),
    "recorder_command_count_store": (0x140E24D91, "89bee0000000"),
}

CALLS = {
    "read_draw_list_view": (0x1409E68AA, 0x141525A40),
    "record_indirect": (0x1409E69D3, 0x140E24CB0),
}


def inspect(path):
    pe = PeReader(path)
    if pe.base != 0x140000000 or len(pe.data) != 65612184:
        raise ValueError("Unexpected target image base or size")
    anchors = []
    for label, (va, expected) in ANCHORS.items():
        raw = pe.read(va, len(bytes.fromhex(expected)))
        if raw.hex() != expected:
            raise ValueError(f"Anchor mismatch: {label} at {va:#x}")
        offset, section = pe.locate(va, len(raw))
        anchors.append({"label": label, "va": hex(va), "file_offset": hex(offset),
                        "section": section, "bytes": raw.hex()})
    calls = []
    for label, (va, expected) in CALLS.items():
        raw = pe.read(va, 5)
        target = va + 5 + struct.unpack_from("<i", raw, 1)[0]
        if raw[0] != 0xE8 or target != expected:
            raise ValueError(f"Call mismatch: {label} at {va:#x}")
        calls.append({"label": label, "va": hex(va), "target": hex(target)})
    return {"binary": str(pe.path), "bytes": len(pe.data),
            "image_base": hex(pe.base), "anchors": anchors, "calls": calls,
            "interpretation": {
                "start_command": "u32 table element selected by bounded composite index",
                "byte_offset": "20 * start_command, plus resource view offset",
                "command_count": "qword from selected read-guard data +8, narrowed to u32 in recorder",
            },
            "limits": ["Ordinary PE file evidence, not REA Evidence",
                       "No target execution or live command count",
                       "No proof of backing identity across graph resources"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"anchors": len(result["anchors"]), "calls": len(result["calls"]),
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
