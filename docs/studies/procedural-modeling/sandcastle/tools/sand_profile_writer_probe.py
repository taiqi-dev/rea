"""Bound direct E8 calls to the shipped IL2CPP color setter methods.

This scans file-backed il2cpp bytes for relative-call encodings. A byte match
is a candidate until the selected call neighborhood is disassembled; indirect
calls, engine-native writes, and loaded-frame ordering remain out of scope.
"""

import argparse
import bisect
import importlib.util
import json
import struct
from pathlib import Path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("binary", type=Path)
    ap.add_argument("metadata", type=Path)
    ap.add_argument("game_codegen_map", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    tools = Path(__file__).resolve().parent
    m39 = module("sand_m39", tools / "metadata39.py")
    cg = module("sand_cg", tools / "map_codegen.py")
    pe = cg.PE(args.binary.resolve(strict=True))
    md = m39.Metadata39(args.metadata.resolve(strict=True))
    modules = cg.locate_modules(pe, "UnityEngine.CoreModule.dll")
    if len(modules) != 1:
        raise ValueError("CoreModule codegen table is not unique")
    core = modules[0]
    image = next(x for x in md.images() if x["name"] == "UnityEngine.CoreModule.dll")
    wanted = {("Shader", "SetGlobalColor", "name"),
              ("MaterialPropertyBlock", "SetColor", "name"),
              ("MaterialPropertyBlock", "SetColor", "nameID")}
    setters = []
    for typ in md.types(image):
        if typ["name"] not in ("Shader", "MaterialPropertyBlock"):
            continue
        for method in md.methods(typ):
            if not method["parameters"]:
                continue
            key = (typ["name"], method["name"], method["parameters"][0]["name"])
            if key not in wanted:
                continue
            rid = method["token"] & 0xFFFFFF
            if not 1 <= rid <= core["pointer_count"]:
                raise ValueError("setter RID outside CoreModule pointer table")
            va = struct.unpack_from("<Q", pe.data, core["pointers_file"] + 8 * (rid - 1))[0]
            if pe.va_to_file(va) is None:
                raise ValueError("setter pointer is not file-backed")
            setters.append({"type": key[0], "method": key[1], "first_parameter": key[2],
                            "token": hex(method["token"]), "va": hex(va)})
    if len(setters) != len(wanted):
        raise ValueError("expected three selected color setter overloads")
    targets = {int(item["va"], 16): item for item in setters}
    game = json.loads(args.game_codegen_map.resolve(strict=True).read_text(encoding="utf-8"))
    if Path(game["source"]).resolve() != args.binary.resolve() or not game["selected_methods"]:
        raise ValueError("game codegen map does not match binary")
    entries = sorted(((int(item["pointer_va"], 16), item) for item in game["selected_methods"]
                      if int(item["pointer_va"], 16) != 0), key=lambda pair: pair[0])
    starts = [entry[0] for entry in entries]
    game_lo, game_hi = starts[0], starts[-1]
    calls = []
    for section, rva, _, raw, size in pe.sections:
        if section != "il2cpp":
            continue
        cursor, end = raw, raw + size
        while (cursor := pe.data.find(b"\xe8", cursor, end)) >= 0:
            if cursor + 5 <= end:
                va = pe.base + rva + cursor - raw
                dest = va + 5 + struct.unpack_from("<i", pe.data, cursor + 1)[0]
                if dest in targets:
                    index = bisect.bisect_right(starts, va) - 1
                    hint = entries[index][1] if index >= 0 else None
                    calls.append({"call_va": hex(va), "file_offset": hex(cursor),
                                  "target": targets[dest]["type"] + "." + targets[dest]["method"]
                                  + "(" + targets[dest]["first_parameter"] + ")",
                                  "unwind_range": pe.unwind_bounds(va),
                                  "inside_game_method_pointer_span": game_lo <= va <= game_hi,
                                  "nearest_game_entry_hint": None if hint is None else
                                  {"type": hint["type"], "method": hint["method"],
                                   "pointer_va": hint["pointer_va"]}})
            cursor += 1
    result = {"binary": str(args.binary.resolve()), "binary_bytes": len(pe.data),
              "metadata": str(args.metadata.resolve()),
              "coverage": "direct E8 rel32 candidates in file-backed il2cpp section only",
              "game_pointer_span": [hex(game_lo), hex(game_hi)], "setters": setters,
              "calls": calls}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"mapped {len(setters)} setters and {len(calls)} direct calls -> {args.output}")


if __name__ == "__main__":
    main()
