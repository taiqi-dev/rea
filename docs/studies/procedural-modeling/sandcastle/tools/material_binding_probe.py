"""Read selected Unity 6 Material bindings from a stripped format-22 file.

The reader accepts only the observed Material layout and requires all selected
PPtrs to resolve inside the same serialized file. It does not load the game.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import struct


class Reader:
    def __init__(self, blob):
        self.blob, self.pos = blob, 0

    def take(self, size):
        if size < 0 or size > len(self.blob) - self.pos:
            raise ValueError("Material field exceeds object")
        start = self.pos
        self.pos += size
        return self.blob[start:self.pos]

    def uint(self):
        return struct.unpack("<I", self.take(4))[0]

    def sint(self):
        return struct.unpack("<i", self.take(4))[0]

    def align4(self):
        self.take((-self.pos) % 4)

    def string(self):
        length = self.uint()
        if length > 1024:
            raise ValueError("Unbounded Material string")
        result = self.take(length).decode("utf-8")
        self.align4()
        return result

    def pptr(self):
        return {"file_id": self.sint(), "path_id": struct.unpack("<q", self.take(8))[0]}

    def count(self, minimum_size):
        count = self.uint()
        if count > (len(self.blob) - self.pos) // minimum_size:
            raise ValueError("Material array count exceeds object")
        return count


def parse_material(blob):
    r = Reader(blob)
    name = r.string()
    shader = r.pptr()
    valid_keywords = [r.string() for _ in range(r.count(4))]
    invalid_keywords = [r.string() for _ in range(r.count(4))]
    flags = r.uint()
    instancing, double_sided = struct.unpack("<BB", r.take(2))
    if r.take(2) != b"\0\0" or instancing > 1 or double_sided > 1:
        raise ValueError("Unsupported Material flags/padding")
    queue = r.sint()
    tags = [(r.string(), r.string()) for _ in range(r.count(8))]
    disabled_passes = [r.string() for _ in range(r.count(4))]

    texenvs = []
    for _ in range(r.count(32)):
        entry_offset = r.pos
        key = r.string()
        pointer = r.pptr()
        transform = struct.unpack("<4f", r.take(16))
        texenvs.append({"object_offset": entry_offset, "name": key,
                        "texture": pointer, "scale": transform[:2], "offset": transform[2:]})
    ints = []
    for _ in range(r.count(8)):
        ints.append({"name": r.string(), "value": r.sint()})
    floats = []
    for _ in range(r.count(8)):
        entry_offset = r.pos
        floats.append({"object_offset": entry_offset, "name": r.string(),
                       "value": struct.unpack("<f", r.take(4))[0]})
    colors = []
    for _ in range(r.count(24)):
        entry_offset = r.pos
        colors.append({"object_offset": entry_offset, "name": r.string(),
                       "rgba": struct.unpack("<4f", r.take(16))})
    trailing = r.take(len(blob) - r.pos)
    if trailing not in (b"", b"\0\0\0\0"):
        raise ValueError("Unsupported Material trailing fields")
    for table in (texenvs, ints, floats, colors):
        names = [entry["name"] for entry in table]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate Material property key")
    return {"name": name, "shader": shader, "valid_keywords": valid_keywords,
            "invalid_keywords": invalid_keywords, "lightmap_flags": flags,
            "instancing": bool(instancing), "double_sided_gi": bool(double_sided),
            "custom_render_queue": queue, "tags": tags,
            "disabled_passes": disabled_passes, "textures": texenvs,
            "ints": ints, "floats": floats, "colors": colors,
            "parsed_bytes": r.pos, "trailing_bytes": len(trailing)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", type=Path)
    parser.add_argument("--material-ids", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    helper_path = Path(__file__).resolve().parents[2] / "tools/unity22-compute-probe.py"
    spec = importlib.util.spec_from_file_location("unity22_index", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    data, index = helper.resource_index(args.resource.resolve(strict=True))
    if (index["format"], index["unity"], index["type_trees"]) != (22, "6000.4.10f1", False):
        raise ValueError("Unsupported serialized-file profile for this Material reader")
    by_id = {item["path_id"]: item for item in index["objects"]}
    if len(by_id) != len(index["objects"]):
        raise ValueError("Duplicate pathID in file")
    results = []
    for material_id in args.material_ids:
        item = by_id.get(material_id)
        if item is None or item["class_id"] != 21:
            raise ValueError(f"Selected ID {material_id} is not a Material")
        blob = data[item["offset"]:item["offset"] + item["bytes"]]
        result = parse_material(blob)
        if result["shader"]["file_id"] != 0:
            raise ValueError("Selected Material shader is external")
        shader = by_id.get(result["shader"]["path_id"])
        if shader is None or shader["class_id"] != 48:
            raise ValueError("Selected shader reference does not resolve")
        result.update({"object": item, "shader_object": shader})
        for texture in result["textures"]:
            pointer = texture["texture"]
            if pointer["file_id"] != 0 or pointer["path_id"] == 0:
                raise ValueError("Selected texture is external or null")
            target = by_id.get(pointer["path_id"])
            if target is None or target["class_id"] not in (28, 89, 117):
                raise ValueError("Selected texture reference does not resolve")
            target_blob = data[target["offset"]:target["offset"] + target["bytes"]]
            target_name = Reader(target_blob).string()
            texture["target"] = {**target, "name": target_name}
        results.append(result)
    output = {"resource": str(args.resource.resolve()), "unity": index["unity"],
              "format": index["format"], "type_trees": index["type_trees"],
              "materials": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, ensure_ascii=False)
    print(json.dumps({"selected": len(results), "output": str(args.output)}))


if __name__ == "__main__":
    main()
