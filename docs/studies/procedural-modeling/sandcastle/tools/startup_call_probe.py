"""Find file-backed direct calls to selected Sandcastle IL2CPP game methods.

E8 byte matches are candidates until their instruction boundaries are checked
with a disassembler. The codegen map supplies method entry hints, not proof of
dispatch or runtime execution.
"""

import argparse
import bisect
import importlib.util
import json
import struct
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("binary", type=Path)
    ap.add_argument("codegen_map", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    spec = importlib.util.spec_from_file_location("sand_map", Path(__file__).with_name("map_codegen.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    binary = args.binary.resolve(strict=True)
    pe = module.PE(binary)
    mapping = json.loads(args.codegen_map.resolve(strict=True).read_text(encoding="utf-8"))
    if Path(mapping["source"]).resolve() != binary or mapping["size"] != len(pe.data):
        raise ValueError("codegen map does not match input binary")
    methods = [m for m in mapping["selected_methods"] if int(m["pointer_va"], 16)]
    entries = sorted(((int(m["pointer_va"], 16), m) for m in methods), key=lambda entry: entry[0])
    starts = [va for va, _ in entries]
    targets = {("Game", "New"), ("Game", "Prepare"), ("Game", "ResetConfiguration"),
               ("Game", "Load"), ("Beach", "Setup"), ("Ground", "Setup"),
               ("Water", "Setup")}
    selected = {int(m["pointer_va"], 16): {"type": m["type"], "method": m["method"]}
                for m in methods if (m["type"], m["method"]) in targets}
    if len(selected) != len(targets):
        raise ValueError("selected method entries are missing or non-unique")
    calls = []
    for name, rva, _, raw, size in pe.sections:
        if name != "il2cpp":
            continue
        cursor, end = raw, raw + size
        while (cursor := pe.data.find(b"\xe8", cursor, end)) >= 0:
            if cursor + 5 <= end:
                va = pe.base + rva + cursor - raw
                destination = va + 5 + struct.unpack_from("<i", pe.data, cursor + 1)[0]
                if destination in selected:
                    nearest = bisect.bisect_right(starts, va) - 1
                    hint = entries[nearest][1] if nearest >= 0 else None
                    calls.append({"call_va": hex(va), "file_offset": hex(cursor),
                                  "target_va": hex(destination), "target": selected[destination],
                                  "unwind_range": pe.unwind_bounds(va),
                                  "nearest_entry_hint": None if hint is None else
                                  {"type": hint["type"], "method": hint["method"],
                                   "pointer_va": hint["pointer_va"]}})
            cursor += 1
    result = {"binary": str(binary), "size": len(pe.data),
              "coverage": "E8 rel32 byte candidates in file-backed il2cpp only; disassemble before use",
              "targets": [{"va": hex(va), **method} for va, method in sorted(selected.items())],
              "calls": calls}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(f"{len(calls)} candidate calls -> {args.output}")


if __name__ == "__main__":
    main()
