"""Resolve selected SUMMERHOUSE camera PPtrs and read their shipped target settings.

Static format-22/2023.2.22f1 only. Never loads game assemblies or computes digests.
Custom MonoBehaviour fields below follow the selected assembly's metadata order.
"""

import argparse
import copy
import importlib.util
import json
from pathlib import Path


VERSION = "2023.2.22f1"
ROOT = Path(__file__).resolve().parents[2]


def load(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe(scene, schema_path):
    unity = load("unity22_index", ROOT / "tools/unity22-compute-probe.py")
    reader_type = load("player_object_reader", ROOT / "sandcastle/tools/player_color_space_probe.py").ObjectReader
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("Version") != VERSION:
        raise ValueError("Expected the exact 2023.2.22f1 reference schema")
    classes = {item["TypeID"]: item for item in schema["Classes"]}
    loaded = {}

    def get_file(path):
        path = path.resolve(strict=True)
        if path.parent != scene.parent:
            raise ValueError("External path leaves the selected data directory")
        if path not in loaded:
            raw, index = unity.resource_index(path, include_externals=True)
            if (index["unity"], index["format"], index["type_trees"]) != (VERSION, 22, False):
                raise ValueError("Unexpected SerializedFile profile")
            loaded[path] = (raw, index)
        return loaded[path]

    def resolve(path, pointer, class_id):
        file_id, path_id = pointer["m_FileID"], pointer["m_PathID"]
        if path_id == 0:
            raise ValueError("Expected a nonnull PPtr")
        if file_id:
            _, index = get_file(path)
            external = [x for x in index["externals"] if x["file_id"] == file_id]
            if len(external) != 1 or Path(external[0]["path"]).name != external[0]["path"]:
                raise ValueError("Unsupported external PPtr path")
            path = path.parent / external[0]["path"]
        raw, index = get_file(path)
        matches = [x for x in index["objects"] if x["path_id"] == path_id and x["class_id"] == class_id]
        if len(matches) != 1:
            raise ValueError(f"Missing unique class {class_id}, pathID {path_id}")
        return path, raw, matches[0]

    def decode(path, pointer, class_id, node=None):
        path, raw, obj = resolve(path, pointer, class_id)
        reader = reader_type(raw[obj["offset"]:obj["offset"] + obj["bytes"]])
        value = reader.parse(node or classes[class_id]["ReleaseRootNode"])
        if reader.pos != obj["bytes"]:
            raise ValueError(f"Object not fully consumed: {reader.pos}/{obj['bytes']}")
        return path, {"object": obj, "bytes_consumed": reader.pos,
                      "values": value, "fields": reader.fields}

    def local(path_id):
        return {"m_FileID": 0, "m_PathID": path_id}

    cameras = []
    for path_id in (2196, 2197):
        _, camera = decode(scene, local(path_id), 20)
        target = camera["values"]["m_TargetTexture"]
        if target["m_PathID"]:
            target_path, texture = decode(scene, target, 84)
            camera["resolved_target"] = {"resource": str(target_path), **texture}
        cameras.append(camera)

    # The three public fields of each selected script are serialized in metadata
    # order. Private screenshot Texture2D is not part of the 52-byte object.
    behaviors = []
    for path_id, class_name, fields in (
        (6578, "ScreenshotTaker", [("gameCamera", "pointer"), ("screenshotWidth", "int"),
                                  ("screenshotHeight", "int")]),
        (7819, "MaskingManager", [("maskingCamera", "pointer"), ("minMaskZ", "float"),
                                 ("maxMaskZ", "float")]),
    ):
        node = copy.deepcopy(classes[114]["ReleaseRootNode"])
        for name, kind in fields:
            if kind == "pointer":
                field = copy.deepcopy(next(x for x in node["SubNodes"] if x["Name"] == "m_Script"))
                field["Name"] = name
                field["TypeName"] = "PPtr<Camera>"
            else:
                field = {"Name": name, "TypeName": kind, "ByteSize": 4, "MetaFlag": 0, "SubNodes": []}
            node["SubNodes"].append(field)
        path, behavior = decode(scene, local(path_id), 114, node)
        _, script = decode(path, behavior["values"]["m_Script"], 115)
        values = script["values"]
        if values["m_ClassName"] != class_name or values["m_AssemblyName"] != "Assembly-CSharp":
            raise ValueError(f"MonoScript identity does not match selected behavior: "
                             f"{values['m_ClassName']} / {values['m_AssemblyName']}")
        behavior["script_identity"] = {key: values[key] for key in
                                       ("m_Name", "m_ClassName", "m_Namespace", "m_AssemblyName")}
        behaviors.append(behavior)
    return {"scene": str(scene), "schema": str(schema_path), "schema_version": VERSION,
            "files": [{"file": str(path), "externals": index["externals"],
                       "metadata_consumed_end": index["metadata_consumed_end"]}
                      for path, (_, index) in loaded.items()],
            "cameras": cameras, "behaviors": behaviors,
            "scope": "selected shipped resources and reference layout; no runtime validation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    result = probe(args.scene.resolve(strict=True), args.schema.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps({"cameras": len(result["cameras"]), "behaviors": len(result["behaviors"]),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
