"""Read SUMMERHOUSE's selected pipeline texture-option prefix and settings refs.

Static 2023.2.22f1 data only. Custom URP asset consumption is explicitly partial.
"""
import argparse
import json
import struct
from pathlib import Path

from mask_target_probe import load, ROOT, VERSION


FIELDS = [("k_AssetVersion", "Int32"), ("k_AssetPreviousVersion", "Int32"),
          ("m_RendererType", "UnityEngine.Rendering.Universal.RendererType"),
          ("m_RendererData", "UnityEngine.Rendering.Universal.ScriptableRendererData"),
          ("m_RendererDataList", "UnityEngine.Rendering.Universal.ScriptableRendererData[]"),
          ("m_DefaultRendererIndex", "Int32"), ("m_RequireDepthTexture", "Boolean"),
          ("m_RequireOpaqueTexture", "Boolean"),
          ("m_OpaqueDownsampling", "UnityEngine.Rendering.Universal.Downsampling")]


def probe(game_data, schema_path, metadata_path):
    indexer = load("pipeline_prefix_index", ROOT / "tools/unity22-compute-probe.py")
    Reader = load("pipeline_prefix_reader", ROOT / "sandcastle/tools/player_color_space_probe.py").ObjectReader
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("Version") != VERSION:
        raise ValueError("Expected exact 2023.2.22f1 schema")
    classes = {x["TypeID"]: x["ReleaseRootNode"] for x in schema["Classes"]}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if (metadata["type"], metadata["mvid"]) != (
            "UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset", "441516f4-c7ab-401e-840b-a71a7013b536"):
        raise ValueError("Unexpected selected URP metadata")
    serial = [f for f in metadata["declared_fields"] if not f["flags"] & (0x10 | 0x80)
              and any(a["constructor"] == "UnityEngine.SerializeField::.ctor" for a in f["custom_attributes"])]
    if [(f["name"], f["field_type"]) for f in serial[:len(FIELDS)]] != FIELDS:
        raise ValueError("Selected pipeline field/type order changed")

    def resource(name):
        path = (game_data / name).resolve(strict=True)
        if path.parent != game_data:
            raise ValueError("Resource leaves selected data directory")
        raw, index = indexer.resource_index(path, include_externals=True)
        if (index["unity"], index["format"], index["type_trees"]) != (VERSION, 22, False):
            raise ValueError("Unexpected selected resource profile")
        return path, raw, index, {x["path_id"]: x for x in index["objects"]}

    path, raw, index, objects = resource("globalgamemanagers.assets")
    item = objects[2355]
    if item["class_id"] != 114:
        raise ValueError("Selected pipeline object class changed")
    payload = raw[item["offset"]:item["offset"] + item["bytes"]]
    base_reader = Reader(payload)
    base = base_reader.parse(classes[114])
    if base["m_Name"] != "URP-HighFidelity":
        raise ValueError("Selected pipeline name changed")
    script_ref = base["m_Script"]
    if script_ref["m_FileID"] != 0:
        raise ValueError("Selected pipeline script is no longer local")
    script_item = objects[script_ref["m_PathID"]]
    if script_item["class_id"] != 115:
        raise ValueError("Selected pipeline script class changed")
    script_reader = Reader(raw[script_item["offset"]:script_item["offset"] + script_item["bytes"]])
    script = script_reader.parse(classes[115])
    if script_reader.pos != script_item["bytes"] or (script["m_ClassName"], script["m_AssemblyName"]) != (
            "UniversalRenderPipelineAsset", "Unity.RenderPipelines.Universal.Runtime"):
        raise ValueError("Selected pipeline MonoScript identity differs")
    pos = base_reader.pos
    fields = []

    def pptr():
        nonlocal pos
        file_id, path_id = struct.unpack_from("<iq", payload, pos)
        pos += 12
        return {"m_FileID": file_id, "m_PathID": path_id}

    for name, kind in FIELDS:
        start = pos
        if kind.endswith("[]"):
            count = struct.unpack_from("<i", payload, pos)[0]
            pos += 4
            if count != 2:
                raise ValueError("Expected two selected renderer data references")
            value = [pptr() for _ in range(count)]
        elif kind.endswith("ScriptableRendererData"):
            value = pptr()
        elif kind == "Boolean":
            value = payload[pos]
            if value not in (0, 1) or any(payload[pos + 1:pos + 4]):
                raise ValueError("Unexpected selected bool/padding")
            pos += 4
        else:
            value = struct.unpack_from("<i", payload, pos)[0]
            pos += 4
        fields.append({"name": name, "field_type": kind, "offset": start, "end": pos, "value": value})
    values = {x["name"]: x["value"] for x in fields}
    if values["m_RendererDataList"] != [{"m_FileID": 0, "m_PathID": 2354}, {"m_FileID": 0, "m_PathID": 2353}]:
        raise ValueError("Selected renderer list changed")
    settings_path, settings_raw, settings_index, settings_objects = resource("globalgamemanagers")
    settings = []
    for class_id, path_id in [(30, 7), (47, 12)]:
        obj = settings_objects[path_id]
        if obj["class_id"] != class_id:
            raise ValueError("Selected settings object class changed")
        reader = Reader(settings_raw[obj["offset"]:obj["offset"] + obj["bytes"]])
        value = reader.parse(classes[class_id])
        if reader.pos != obj["bytes"]:
            raise ValueError("Selected native settings not completely consumed")
        settings.append({"object": obj, "value": value, "end": reader.pos})
    return {"resource": str(path), "pipeline_object": item, "name": base["m_Name"],
            "base_bytes": base_reader.pos, "fields": fields, "prefix_end": pos,
            "remaining_bytes_unparsed": len(payload) - pos, "metadata": str(metadata_path),
            "settings_resource": str(settings_path), "settings_externals": settings_index["externals"],
            "native_settings": settings, "scope": "selected custom prefix only; native settings and MonoScript complete",
            "runtime": "Not Run"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["game-data", "schema", "metadata", "output"]:
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    result = probe(args.game_data.resolve(strict=True), args.schema.resolve(strict=True), args.metadata.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"prefix_end": result["prefix_end"], "remaining_bytes": result["remaining_bytes_unparsed"]}))


if __name__ == "__main__":
    main()
