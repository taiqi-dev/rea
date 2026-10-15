"""Read a caller-located serialized Unity Shader state prefix.

Observed Unity 2023.2 / 6000.4 layout only: state name, eight blend targets,
separate-blend flag and eight depth/raster fields. Not a full pass parser.
Does not execute shaders, infer active passes or compute content digests.
"""

import argparse
import importlib.util
import json
import math
from pathlib import Path
import struct


class Reader:
    def __init__(self, raw, offset):
        self.raw, self.pos = raw, offset

    def read(self, count):
        if self.pos < 0 or count < 0 or count > len(self.raw) - self.pos:
            raise ValueError("Shader state exceeds selected object")
        value = self.raw[self.pos:self.pos + count]
        self.pos += count
        return value

    def string(self):
        size = struct.unpack("<I", self.read(4))[0]
        value = self.read(size).decode("utf-8")
        self.read((-self.pos) % 4)
        return value

    def scalar(self):
        offset = self.pos
        value = struct.unpack("<f", self.read(4))[0]
        if not math.isfinite(value):
            raise ValueError("Non-finite shader state")
        return {"object_offset": offset, "value": value,
                "name": self.string()}


def read_prefix(raw, offset):
    reader = Reader(raw, offset)
    name = reader.string()
    targets = []
    for _ in range(8):
        targets.append({key: reader.scalar() for key in
                        ("src", "dst", "src_alpha", "dst_alpha",
                         "op", "op_alpha", "color_mask")})
    separate = reader.read(1)[0]
    if separate not in (0, 1):
        raise ValueError("Invalid separate-blend flag")
    reader.read((-reader.pos) % 4)
    fields = {key: reader.scalar() for key in
              ("z_clip", "z_test", "z_write", "cull", "conservative",
               "offset_factor", "offset_units", "alpha_to_mask")}
    return {"object_offset": offset, "name": name, "targets": targets,
            "separate_blend": bool(separate), "fields": fields,
            "prefix_end": reader.pos,
            "scope": "state prefix only; stencil, tags and program tables omitted"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", type=Path)
    parser.add_argument("--object-id", required=True, type=int)
    parser.add_argument("--state-offset", required=True, type=lambda x: int(x, 0))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    path = Path(__file__).with_name("unity22-compute-probe.py")
    spec = importlib.util.spec_from_file_location("unity_compute", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    data, index = helper.resource_index(args.resource.resolve(strict=True))
    if (index["format"] != 22 or index["type_trees"] or
            index["unity"] not in ("2023.2.22f1", "6000.4.10f1")):
        raise ValueError("Unsupported serialized-file profile for this state reader")
    matches = [x for x in index["objects"]
               if x["path_id"] == args.object_id and x["class_id"] == 48]
    if len(matches) != 1:
        raise ValueError("Expected one selected Shader object")
    item = matches[0]
    raw = data[item["offset"]:item["offset"] + item["bytes"]]
    result = read_prefix(raw, args.state_offset)
    result.update({"resource": str(args.resource.resolve()), "object": item})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"object": args.object_id, "prefix_end": result["prefix_end"],
                      "target0": result["targets"][0], "fields": result["fields"]}))


if __name__ == "__main__":
    main()
