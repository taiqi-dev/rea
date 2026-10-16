"""Bounded, read-only check of the selected serialized Shader property prefixes.

The offsets below are assertions for the two already indexed Unity 6000.4.10f1
Shader objects, not a general Unity Shader parser.  A failed assertion stops the
probe rather than silently treating a changed layout as the same property list.
"""

import argparse
import json
import struct
from pathlib import Path


PROFILES = {
    605: {"prefix_end": 0x90, "names": [(0x08, "sandMap"), (0x48, "causticsMap")],
          "colors": ["sandColor", "sandColor2", "wetSandColor", "sedimentColor"]},
    587: {"prefix_end": 0xA8, "names": [(0x08, "refractionFactor"), (0x58, "waterNormalMap")],
          "colors": ["waterColor", "waterScatteringColor"]},
}


def read_u32(data, offset):
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"u32 outside object at {offset:#x}")
    return struct.unpack_from("<I", data, offset)[0]


def read_string(data, offset):
    length = read_u32(data, offset)
    if length > 256 or offset + 4 + length > len(data):
        raise ValueError(f"invalid string at {offset:#x}")
    return data[offset + 4:offset + 4 + length].decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    results = []
    for path_id, profile in PROFILES.items():
        index_path = args.index_dir / f"shader-{path_id}-index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        obj = index["object"]
        if obj["path_id"] != path_id or obj["class_id"] != 48:
            raise ValueError(f"unexpected object identity in {index_path}")
        with Path(index["resource"]).open("rb") as source:
            source.seek(obj["offset"])
            data = source.read(obj["bytes"])
        if len(data) != obj["bytes"]:
            raise ValueError(f"short Shader object {path_id}")
        if read_u32(data, 0) != 0 or read_u32(data, 4) != len(profile["names"]):
            raise ValueError(f"unexpected property prefix header in Shader {path_id}")
        names = []
        for offset, expected in profile["names"]:
            name = read_string(data, offset)
            if name != expected or offset >= profile["prefix_end"]:
                raise ValueError(f"unexpected Shader {path_id} property at {offset:#x}: {name}")
            names.append({"object_offset": hex(offset), "name": name})
        if read_u32(data, profile["prefix_end"]) != 1:
            raise ValueError(f"unexpected post-property boundary in Shader {path_id}")
        prefix = data[:profile["prefix_end"]]
        colors = []
        for name in profile["colors"]:
            encoded = name.encode("utf-8")
            positions = [hex(i) for i in range(len(data)) if data.startswith(encoded, i)]
            colors.append({"name": name, "in_property_prefix": encoded in prefix,
                           "object_byte_offsets": positions})
        results.append({"shader_path_id": path_id, "class_id": obj["class_id"],
                        "resource": index["resource"], "object_file_offset": hex(obj["offset"]),
                        "object_bytes": obj["bytes"], "property_count_at_object_offset_4": len(names),
                        "property_prefix_end": hex(profile["prefix_end"]),
                        "post_prefix_u32": 1, "property_names": names, "color_name_occurrences": colors,
                        "index": str(index_path)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"scope": "fixed-profile property-prefix byte check, not GPU binding proof",
                   "shaders": results}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"checked {len(results)} Shader property prefixes: {args.output}")


if __name__ == "__main__":
    main()
