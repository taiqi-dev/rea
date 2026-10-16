"""Locate shipped camera-related MonoBehaviours in five SUMMERHOUSE scenes.

Uses the exact Unity 2023.2.22f1 format-22 index and Release type tree. Only
selected native GameObject/Transform/MonoScript records are fully decoded;
MonoBehaviour records are read through their standard 32-byte prefix. This is
static resource evidence and does not execute Unity or compute digests.
"""

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

from mask_target_probe import ROOT, VERSION, load


SELECTED = {"CameraController", "CameraBoundaries", "PlanarReflectionRenderer",
            "PixelPerfectCamera", "ImageRenderer", "UniversalAdditionalCameraData"}


WATER_MVID = "dfe63f36-a582-4939-bd07-a189a923e050"
WATER_FIELDS = ["rotatable", "cullingMask", "rendererIndex", "offset", "includeSkybox",
                "enableFog", "renderShadows", "renderRange", "renderScale", "maximumLODLevel",
                "waterObjects", "moveWithTransform", "bounds"]


def probe(game_data, schema_path, water_metadata_path):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema["Version"] != VERSION:
        raise ValueError("Expected exact 2023.2.22f1 schema")
    classes = {x["TypeID"]: x["ReleaseRootNode"] for x in schema["Classes"]}
    water_metadata = json.loads(water_metadata_path.read_text(encoding="utf-8-sig"))
    if (water_metadata["type"], water_metadata["mvid"]) != ("StylizedWater2.PlanarReflectionRenderer", WATER_MVID):
        raise ValueError("Selected water assembly metadata changed")
    water_fields = [f["name"] for f in water_metadata["declared_fields"]]
    if [name for name in water_fields if name in WATER_FIELDS] != WATER_FIELDS:
        raise ValueError("Selected water field order changed")
    indexer = load("summer_matrix_index", ROOT / "tools/unity22-compute-probe.py")
    Reader = load("summer_matrix_reader", ROOT / "sandcastle/tools/player_color_space_probe.py").ObjectReader
    files = {}

    def resource(name):
        path = (game_data / name).resolve(strict=True)
        if path.parent != game_data:
            raise ValueError("Resource leaves selected game data directory")
        if path not in files:
            raw, index = indexer.resource_index(path, include_externals=True)
            if (index["unity"], index["format"], index["type_trees"]) != (VERSION, 22, False):
                raise ValueError("Unsupported selected resource profile")
            files[path] = raw, index, {x["path_id"]: x for x in index["objects"]}
        return path, files[path]

    def decode(source, pointer, expected):
        name = source.name
        if pointer["m_FileID"]:
            _, (_, index, _) = resource(name)
            refs = [x for x in index["externals"] if x["file_id"] == pointer["m_FileID"]]
            if len(refs) != 1 or Path(refs[0]["path"]).name != refs[0]["path"]:
                raise ValueError("Unresolved external file reference")
            name = refs[0]["path"]
        path, (raw, _, objects) = resource(name)
        obj = objects[pointer["m_PathID"]]
        if obj["class_id"] != expected:
            raise ValueError("Referenced class changed")
        reader = Reader(raw[obj["offset"]:obj["offset"] + obj["bytes"]])
        value = reader.parse(classes[expected])
        if expected != 114 and reader.pos != obj["bytes"]:
            raise ValueError(f"Native object incomplete: {path.name}/{obj['path_id']}")
        if expected == 114 and reader.pos != 32:
            raise ValueError("Unexpected MonoBehaviour prefix length")
        return path, obj, value, reader.pos

    def local(path_id):
        return {"m_FileID": 0, "m_PathID": path_id}

    rows = []
    scope = {}
    for name in ("level0", "level1", "level2", "level3", "level4"):
        scene, (_, index, objects) = resource(name)
        candidates = [o for o in objects.values() if o["class_id"] == 114]
        scope[name] = {"objects": len(objects), "mono_behaviours": len(candidates)}
        for obj in candidates:
            _, _, base, prefix = decode(scene, local(obj["path_id"]), 114)
            script_path, script_obj, script, script_end = decode(scene, base["m_Script"], 115)
            if script["m_ClassName"] not in SELECTED:
                continue
            go_path, go_obj, go, go_end = decode(scene, base["m_GameObject"], 1)
            if go_path != scene:
                raise ValueError("Selected component GameObject is external")
            ancestry = []
            transforms = [ref["component"] for ref in go["m_Component"]["Array"]
                          if ref["component"]["m_FileID"] == 0
                          and objects[ref["component"]["m_PathID"]]["class_id"] == 4]
            if len(transforms) != 1:
                raise ValueError("Selected GameObject must have one local Transform")
            current = transforms[0]
            seen = set()
            while current["m_PathID"]:
                if current["m_FileID"] != 0 or current["m_PathID"] in seen:
                    raise ValueError("Unresolved selected Transform ancestry")
                seen.add(current["m_PathID"])
                _, transform_obj, transform, transform_end = decode(scene, current, 4)
                ancestor_path, ancestor_obj, ancestor_go, ancestor_end = decode(scene, transform["m_GameObject"], 1)
                if ancestor_path != scene:
                    raise ValueError("External selected ancestor")
                ancestry.append({"transform_path_id": transform_obj["path_id"],
                                 "transform_bytes_consumed": transform_end,
                                 "game_object_path_id": ancestor_obj["path_id"],
                                 "game_object_bytes_consumed": ancestor_end,
                                 "name": ancestor_go["m_Name"], "active_self": ancestor_go["m_IsActive"]})
                current = transform["m_Father"]
            selected_data = None
            if script["m_ClassName"] == "PlanarReflectionRenderer":
                raw = files[scene][0][obj["offset"]:obj["offset"] + obj["bytes"]]
                if len(raw) < 76:
                    raise ValueError("Short selected reflection component")
                fields = struct.unpack_from("<iiifiiiffii", raw, 32)
                (rotatable, mask, renderer_index, offset, skybox, fog, shadows,
                 render_range, render_scale, lod, water_count) = fields
                if any(x not in (0, 1) for x in (rotatable, skybox, fog, shadows)):
                    raise ValueError("Invalid selected reflection flags")
                if water_count < 0 or water_count > 1024:
                    raise ValueError("Invalid selected water reference count")
                at = 76
                waters = []
                for _ in range(water_count):
                    file_id, path_id = struct.unpack_from("<iq", raw, at)
                    at += 12
                    if file_id != 0 or not path_id:
                        raise ValueError("Unresolved selected water reference")
                    _, water_obj, water_base, _ = decode(scene, local(path_id), 114)
                    _, _, water_script, _ = decode(scene, water_base["m_Script"], 115)
                    if (water_script["m_ClassName"], water_script["m_AssemblyName"]) != ("WaterObject", "sc.stylizedwater2.runtime"):
                        raise ValueError("Selected water reference changed")
                    waters.append(water_obj["path_id"])
                move, = struct.unpack_from("<i", raw, at)
                if move not in (0, 1):
                    raise ValueError("Invalid selected moveWithTransform")
                at += 4
                bounds = struct.unpack_from("<ffffff", raw, at)
                at += 24
                if at != len(raw):
                    raise ValueError("Selected reflection object not fully consumed")
                selected_data = {"rotatable": rotatable, "culling_mask": mask,
                                 "renderer_index": renderer_index, "offset": offset,
                                 "include_skybox": skybox, "enable_fog": fog,
                                 "render_shadows": shadows, "render_range": render_range,
                                 "render_scale": render_scale, "maximum_lod": lod,
                                 "water_object_path_ids": waters, "move_with_transform": move,
                                 "bounds_center_xyz_extents_xyz": bounds, "bytes_consumed": at}
            rows.append({"scene": name, "component": obj, "prefix_bytes_consumed": prefix,
                         "script": {"resource": script_path.name, "object": script_obj,
                                    "class": script["m_ClassName"], "namespace": script["m_Namespace"],
                                    "assembly": script["m_AssemblyName"], "bytes_consumed": script_end},
                         "enabled": base["m_Enabled"], "game_object": go_obj,
                         "game_object_bytes_consumed": go_end, "game_object_name": go["m_Name"],
                         "active_self": go["m_IsActive"], "ancestry": ancestry,
                         "reflection_fields": selected_data})
    return {"game_data": str(game_data), "schema_version": VERSION,
            "water_mvid": WATER_MVID,
            "scope": scope, "selected": rows,
            "counts": dict(Counter(r["script"]["assembly"] + ":" + r["script"]["class"]
                                   for r in rows)),
            "limits": "Five shipped scenes; selected native records complete, MonoBehaviour prefix only; no runtime additions",
            "runtime": "Not Run", "digests": "Not computed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-data", required=True, type=Path)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--water-metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    result = probe(args.game_data.resolve(strict=True), args.schema.resolve(strict=True),
                   args.water_metadata.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"selected": len(result["selected"]), "scope": result["scope"]}))


if __name__ == "__main__":
    main()
