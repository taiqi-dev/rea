"""Read selected camera depth, active hierarchy, and additional-data prefix.

Static SUMMERHOUSE 2023.2.22f1 only. Custom MonoBehaviour decoding is explicitly
partial. No target execution, rendering, private data, or digest computation.
"""

import argparse
import json
import math
import struct
from pathlib import Path

from mask_target_probe import load, ROOT, VERSION


def probe(scene, schema_path):
    unity = load("camera_order_index", ROOT / "tools/unity22-compute-probe.py")
    Reader = load("camera_order_reader", ROOT / "sandcastle/tools/player_color_space_probe.py").ObjectReader
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("Version") != VERSION:
        raise ValueError("Expected exact 2023.2.22f1 schema")
    classes = {c["TypeID"]: c["ReleaseRootNode"] for c in schema["Classes"]}
    loaded = {}

    def file(path):
        path = path.resolve(strict=True)
        if path.parent != scene.parent:
            raise ValueError("External resource leaves selected game data directory")
        if path not in loaded:
            data, index = unity.resource_index(path, include_externals=True)
            if (index["unity"], index["format"], index["type_trees"]) != (VERSION, 22, False):
                raise ValueError("Unexpected SerializedFile profile")
            loaded[path] = data, index, {x["path_id"]: x for x in index["objects"]}
        return loaded[path]

    def decode(path, path_id, class_id, complete=True):
        data, _, objects = file(path)
        item = objects[path_id]
        if item["class_id"] != class_id:
            raise ValueError("Selected object class changed")
        payload = data[item["offset"]:item["offset"] + item["bytes"]]
        reader = Reader(payload)
        value = reader.parse(classes[class_id])
        if complete and reader.pos != len(payload):
            raise ValueError("Selected native object not completely consumed")
        return value, item, payload, reader.pos

    def local(pointer):
        if pointer["m_FileID"] != 0 or pointer["m_PathID"] == 0:
            raise ValueError("Expected nonnull local PPtr")
        return pointer["m_PathID"]

    def hierarchy(go_id):
        seen, rows = set(), []
        while go_id:
            if go_id in seen:
                raise ValueError("Cyclic selected hierarchy")
            seen.add(go_id)
            go, _, _, _ = decode(scene, go_id, 1)
            _, _, objects = file(scene)
            components = [local(x["component"]) for x in go["m_Component"]["Array"]]
            transforms = [x for x in components if objects[x]["class_id"] == 4]
            if len(transforms) != 1:
                raise ValueError("Expected one selected Transform")
            transform, _, _, _ = decode(scene, transforms[0], 4)
            if local(transform["m_GameObject"]) != go_id:
                raise ValueError("Transform owner differs")
            rows.append({"game_object": go_id, "name": go["m_Name"],
                         "active": go["m_IsActive"], "transform": transforms[0]})
            parent = transform["m_Father"]
            if not parent["m_PathID"]:
                break
            parent_transform, _, _, _ = decode(scene, local(parent), 4)
            go_id = local(parent_transform["m_GameObject"])
        return rows

    rows = []
    for camera_id, additional_id in [(2196, 7384), (2197, 8109)]:
        camera, item, _, _ = decode(scene, camera_id, 20)
        base, additional, payload, consumed = decode(scene, additional_id, 114, complete=False)
        if consumed != 32 or base["m_Name"] or len(payload) < 56:
            raise ValueError("Unexpected selected additional camera prefix")
        go_id = local(camera["m_GameObject"])
        if local(base["m_GameObject"]) != go_id:
            raise ValueError("Additional data has different camera owner")
        script = base["m_Script"]
        _, index, _ = file(scene)
        external = [x["path"] for x in index["externals"] if x["file_id"] == script["m_FileID"]]
        if len(external) != 1 or Path(external[0]).name != external[0]:
            raise ValueError("Unexpected script external path")
        script_value, _, _, _ = decode(scene.parent / external[0], script["m_PathID"], 115)
        if (script_value["m_ClassName"], script_value["m_AssemblyName"]) != (
                "UniversalAdditionalCameraData", "Unity.RenderPipelines.Universal.Runtime"):
            raise ValueError("Selected camera MonoScript identity changed")
        shadows, padding, depth, opaque, mode, stack_count, renderer = struct.unpack_from("<B3siiiii", payload, 32)
        if shadows not in (0, 1) or padding != b"\0\0\0" or stack_count != 0 or mode not in (0, 1):
            raise ValueError("Unsupported selected additional camera prefix")
        depth_value = camera["m_Depth"]
        if not math.isfinite(depth_value) or not -2147483648 <= depth_value <= 2147483647:
            raise ValueError("Depth outside selected CIL comparison conversion range")
        ancestry = hierarchy(go_id)
        rows.append({"camera": item, "enabled": camera["m_Enabled"], "depth": depth_value,
                     "comparison_int_depth": int(depth_value), "target": camera["m_TargetTexture"],
                     "target_display": camera["m_TargetDisplay"], "hierarchy": ancestry,
                     "all_serialized_ancestors_active": all(x["active"] for x in ancestry),
                     "additional_data": {"object": additional, "enabled": base["m_Enabled"],
                                         "prefix_bytes_consumed": 56, "remaining_bytes_unparsed": len(payload) - 56,
                                         "render_shadows": shadows, "depth_option": depth,
                                         "opaque_option": opaque, "camera_type": mode,
                                         "stack_count": stack_count, "renderer_index": renderer}})
    return {"scene": str(scene), "schema": str(schema_path), "cameras": rows,
            "order_if_both_admitted": [x["camera"]["path_id"] for x in sorted(rows, key=lambda x: x["comparison_int_depth"])],
            "scope": "native Camera/GO/Transform/MonoScript complete; AdditionalCameraData selected field-order prefix only",
            "runtime": "Not Run"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    value = probe(args.scene.resolve(strict=True), args.schema.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"cameras": len(value["cameras"]), "conditional_order": value["order_if_both_admitted"]}))


if __name__ == "__main__":
    main()
