"""Read the selected SUMMERHOUSE Camera layout using an explicit release schema.

No target code is loaded and no digests are computed. The schema is evidence,
not an instruction source; only this fixed version/class and scalar types apply.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import struct


def read_camera(raw, node):
    position = 0
    offsets = {}
    formats = {"int": "i", "unsigned int": "I", "UInt8": "B",
               "bool": "B", "float": "f", "SInt64": "q"}

    def read(current, prefix):
        nonlocal position
        name = prefix + current["Name"]
        offsets[name] = position
        children = current["SubNodes"]
        if children:
            value = {child["Name"]: read(child, name + ".") for child in children}
        else:
            kind = current["TypeName"]
            if kind not in formats:
                raise ValueError(f"Unsupported schema scalar {kind}")
            fmt = "<" + formats[kind]
            size = struct.calcsize(fmt)
            if current["ByteSize"] != size or position + size > len(raw):
                raise ValueError(f"Truncated or incompatible field {name}")
            value = struct.unpack_from(fmt, raw, position)[0]
            position += size
            if kind == "bool" and value not in (0, 1):
                raise ValueError(f"Invalid bool at {name}")
        if current["MetaFlag"] & 0x4000:
            position = (position + 3) & ~3
            if position > len(raw):
                raise ValueError("Alignment exceeds object")
        return value

    value = read(node, "")
    if position != len(raw):
        raise ValueError(f"Camera not fully consumed: {position}/{len(raw)}")
    return value, offsets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    if schema["Version"] != "2023.2.22f1":
        raise ValueError("Only the selected 2023.2.22f1 schema is accepted")
    classes = [c for c in schema["Classes"] if c["TypeID"] == 20 and c["Name"] == "Camera"]
    if len(classes) != 1:
        raise ValueError("Expected one Camera schema")
    node = classes[0]["ReleaseRootNode"]
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("unity_index", root / "tools/unity22-compute-probe.py")
    unity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(unity)
    data, index = unity.resource_index(args.scene.resolve(strict=True))
    if (index["format"], index["unity"], index["type_trees"]) != (22, "2023.2.22f1", False):
        raise ValueError("Unexpected serialized file profile")
    objects = {o["path_id"]: o for o in index["objects"]}
    cameras = []
    for item in index["objects"]:
        if item["class_id"] != 20:
            continue
        raw = data[item["offset"]:item["offset"] + item["bytes"]]
        values, offsets = read_camera(raw, node)
        ref = values["m_GameObject"]
        game_object = objects[ref["m_PathID"]]
        if ref["m_FileID"] != 0 or game_object["class_id"] != 1:
            raise ValueError("Camera does not reference a local GameObject")
        go = data[game_object["offset"]:game_object["offset"] + game_object["bytes"]]
        count = struct.unpack_from("<i", go)[0]
        if not 0 <= count <= 64:
            raise ValueError("Invalid GameObject component count")
        at = 8 + count * 12
        if at + 4 > len(go):
            raise ValueError("Truncated GameObject name")
        length = struct.unpack_from("<i", go, at)[0]
        if length < 0 or length > len(go) - at - 4:
            raise ValueError("Invalid GameObject name length")
        name = go[at + 4:at + 4 + length].decode("utf-8", "strict")
        cameras.append({"object": item, "game_object_name": name,
                        "values": values, "field_offsets": offsets})
    if not cameras:
        raise ValueError("No Cameras found in selected scene")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump({"scene": str(args.scene.resolve()), "schema": str(args.schema.resolve()),
                   "schema_version": schema["Version"], "cameras": cameras,
                   "scope": "release schema interpretation of current scene bytes; no runtime"}, output,
                  ensure_ascii=False, indent=2)
    print(json.dumps([{"path_id": c["object"]["path_id"], "name": c["game_object_name"],
                       "target": c["values"]["m_TargetTexture"]} for c in cameras]))


if __name__ == "__main__":
    main()
