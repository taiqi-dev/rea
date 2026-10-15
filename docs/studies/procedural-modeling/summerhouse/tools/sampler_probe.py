"""Read Shader 65's observed inline-sampler table without executing the game.

The raw record is an observation; bit meanings are a format interpretation from
the pinned ShaderRecoveryPlugin source cited in the report, not a driver probe.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import struct


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    unity = module_at("unity_compute", root / "tools/unity22-compute-probe.py")
    params = module_at("shader_params", root / "sandcastle/tools/surface_probe.py")
    data, index = unity.resource_index(args.resource.resolve(strict=True))
    if (index["format"], index["unity"], index["type_trees"]) != (22, "2023.2.22f1", False):
        raise ValueError("Unsupported serialized-file profile")
    objects = [o for o in index["objects"] if o["path_id"] == 65 and o["class_id"] == 48]
    if len(objects) != 1:
        raise ValueError("Expected exactly one Shader 65")
    item = objects[0]
    raw = data[item["offset"]:item["offset"] + item["bytes"]]
    tables = params.read_tables(raw, 0x10, 0x8a8, 0x880)
    pos = tables["table_end"]
    if pos + 8 > len(raw) or struct.unpack_from("<I", raw, pos)[0] != 0:
        raise ValueError("Expected observed zero UAV-parameter count")
    pos += 4
    count = struct.unpack_from("<I", raw, pos)[0]
    pos += 4
    if count != 1 or count > (len(raw) - pos) // 8:
        raise ValueError("Unexpected inline sampler table")
    records = []
    for _ in range(count):
        bits, slot = struct.unpack_from("<II", raw, pos)
        fields = {"filter": bits & 3, "wrap_u": (bits >> 2) & 3,
                  "wrap_v": (bits >> 4) & 3, "wrap_w": (bits >> 6) & 3,
                  "comparison": bool(bits & 0x100)}
        if bits & ~0x1ff or fields["filter"] > 2:
            raise ValueError("Sampler has bits outside selected interpretation")
        records.append({"object_offset": pos, "encoded": bits, "slot": slot,
                        "interpreted_fields": fields})
        pos += 8
    result = {"resource": str(args.resource.resolve()), "object": item,
              "parameters": tables, "samplers": records, "end": pos,
              "scope": "raw sampler record plus explicit format-derived fields; no runtime validation"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"samplers": records, "output": str(args.output)}))


if __name__ == "__main__":
    main()
