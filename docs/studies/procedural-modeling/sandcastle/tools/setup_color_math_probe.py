"""Resolve exact Unity color/random helpers and float literals in this IL2CPP image."""

import argparse
import importlib.util
import json
import struct
from pathlib import Path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("binary", type=Path)
    ap.add_argument("metadata", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    tools = Path(__file__).resolve().parent
    cg = load("setup_cg", tools / "map_codegen.py")
    m39 = load("setup_md", tools / "metadata39.py")
    pe = cg.PE(args.binary.resolve(strict=True))
    md = m39.Metadata39(args.metadata.resolve(strict=True))
    core = cg.locate_modules(pe, "UnityEngine.CoreModule.dll")
    if len(core) != 1:
        raise ValueError("CoreModule table is not unique")
    core = core[0]
    image = next(x for x in md.images() if x["name"] == "UnityEngine.CoreModule.dll")
    targets = {0x181C521E0, 0x181C52260, 0x181C20BF0, 0x181C20810, 0x181C4A140}
    methods = []
    for typ in md.types(image):
        for method in md.methods(typ):
            rid = method["token"] & 0xFFFFFF
            if not 1 <= rid <= core["pointer_count"]:
                continue
            va = struct.unpack_from("<Q", pe.data, core["pointers_file"] + 8 * (rid - 1))[0]
            if va in targets:
                methods.append({"va": hex(va), "type": typ["name"], "method": method["name"],
                                "token": hex(method["token"]),
                                "parameters": [p["name"] for p in method["parameters"]]})
    if {int(m["va"], 16) for m in methods} != targets:
        raise ValueError("selected helper identities are incomplete")
    literals = {}
    for va in (0x182035AFC, 0x182035BBC, 0x182035B54, 0x182035AF0, 0x182035CDC):
        pos = pe.va_to_file(va)
        if pos is None:
            raise ValueError(f"literal {va:#x} is not file backed")
        literals[hex(va)] = {"file_offset": hex(pos), "f32": struct.unpack_from("<f", pe.data, pos)[0]}
    result = {"binary": str(args.binary.resolve()), "bytes": len(pe.data),
              "metadata": str(args.metadata.resolve()), "helpers": methods,
              "literals": literals,
              "coverage": "selected CoreModule method pointers and file-backed f32 values; no execution"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(f"{len(methods)} helpers and {len(literals)} literals -> {args.output}")


if __name__ == "__main__":
    main()
