"""Trace selected SUMMERHOUSE block MeshFilters to renderers and materials.

Read-only, version-scoped Unity 2023.2.22f1 stripped-type-tree probe. Output is
analysis JSON in an ignored directory. No target code or graphics is executed.
"""

import argparse
import collections
import importlib.util
import json
import re
import struct
from pathlib import Path


def i32(blob, at):
    return struct.unpack_from("<i", blob, at)[0]


def i64(blob, at):
    return struct.unpack_from("<q", blob, at)[0]


def pointer(blob, at):
    return {"file_id": i32(blob, at), "path_id": i64(blob, at + 4)}


def unity_string(blob, at, limit=4096):
    size = i32(blob, at)
    if not 0 <= size <= limit or at + 4 + size > len(blob):
        raise ValueError(f"Invalid Unity string at {at}: {size}")
    value = blob[at + 4:at + 4 + size].decode("utf-8")
    return value, (at + 4 + size + 3) & ~3


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--game-data", required=True, type=Path)
    cli.add_argument("--input", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    data_path = (args.game_data.resolve(strict=True) / "sharedassets0.assets").resolve(strict=True)
    index = json.loads((args.input / "sharedassets0.assets.json").read_text(encoding="utf-8"))
    if (index["format"], index["unity"], index["type_trees"]) != (22, "2023.2.22f1", False):
        raise ValueError("Unexpected Unity serialized profile")
    if Path(index["file"]).resolve(strict=True) != data_path:
        raise ValueError("Index and input file identity differ")
    data = data_path.read_bytes()
    items = {row["path_id"]: row for row in index["objects"]}

    def raw(path_id, expected_class=None):
        item = items[path_id]
        if expected_class is not None and item["class_id"] != expected_class:
            raise ValueError(f"Wrong class {item['class_id']} at pathID {path_id}")
        return data[item["offset"]:item["offset"] + item["bytes"]]

    def game_object(path_id):
        blob = raw(path_id, 1)
        count = i32(blob, 0)
        if not 0 <= count <= 64 or 8 + count * 12 > len(blob):
            raise ValueError(f"Invalid component list in GameObject {path_id}")
        refs = [pointer(blob, 4 + j * 12) for j in range(count)]
        name, _ = unity_string(blob, 8 + count * 12)
        return name, refs

    def material(path_id):
        blob = raw(path_id, 21)
        name, at = unity_string(blob, 0)
        shader = pointer(blob, at)
        if shader["file_id"] == 0 and shader["path_id"]:
            raw(shader["path_id"], 48)
        at += 12

        def count(at, cap=512):
            number = i32(blob, at)
            if not 0 <= number <= cap:
                raise ValueError(f"Invalid Material array at {path_id}:{at}: {number}")
            return number, at + 4

        valid_count, at = count(at)
        keywords = []
        for _ in range(valid_count):
            keyword, at = unity_string(blob, at)
            keywords.append(keyword)
        invalid_count, at = count(at)
        for _ in range(invalid_count):
            _, at = unity_string(blob, at)
        lightmap_flags = i32(blob, at)
        at += 4
        instancing = bool(blob[at])
        double_sided_gi = bool(blob[at + 1])
        at += 4
        custom_queue = i32(blob, at)
        at += 4
        tag_count, at = count(at)
        tags = {}
        for _ in range(tag_count):
            key, at = unity_string(blob, at)
            value, at = unity_string(blob, at)
            tags[key] = value
        pass_count, at = count(at)
        passes = []
        for _ in range(pass_count):
            value, at = unity_string(blob, at)
            passes.append(value)
        texture_count, at = count(at)
        textures = {}
        for _ in range(texture_count):
            key, at = unity_string(blob, at)
            ref = pointer(blob, at)
            at += 12
            scale_offset = struct.unpack_from("<ffff", blob, at)
            at += 16
            textures[key] = {"texture": ref, "scale_offset": scale_offset}
        int_count, at = count(at)
        integers = {}
        for _ in range(int_count):
            key, at = unity_string(blob, at)
            integers[key] = i32(blob, at)
            at += 4
        float_count, at = count(at)
        floats = {}
        for _ in range(float_count):
            key, at = unity_string(blob, at)
            floats[key] = struct.unpack_from("<f", blob, at)[0]
            at += 4
        color_count, at = count(at)
        colors = {}
        for _ in range(color_count):
            key, at = unity_string(blob, at)
            colors[key] = struct.unpack_from("<ffff", blob, at)
            at += 16
        if at + 4 == len(blob) and i32(blob, at) == 0:
            at += 4  # Empty build texture stacks in this Unity profile.
        if at != len(blob):
            raise ValueError(f"Unconsumed Material bytes in {path_id}: {at}/{len(blob)}")
        return {"path_id": path_id, "offset": items[path_id]["offset"], "name": name, "shader": shader,
                "keywords": keywords, "lightmap_flags": lightmap_flags, "instancing": instancing,
                "double_sided_gi": double_sided_gi, "custom_queue": custom_queue, "tags": tags,
                "disabled_passes": passes, "textures": textures, "integers": integers,
                "floats": floats, "colors": colors}

    def renderer(path_id):
        blob = raw(path_id, 23)
        count = i32(blob, 68)
        if not 0 <= count <= 64 or 72 + count * 12 > len(blob):
            raise ValueError(f"Invalid material list in MeshRenderer {path_id}")
        refs = [pointer(blob, 72 + j * 12) for j in range(count)]
        for ref in refs:
            if ref["file_id"] == 0 and ref["path_id"]:
                raw(ref["path_id"], 21)
        return {"path_id": path_id, "offset": items[path_id]["offset"], "materials": refs,
                "enabled": bool(blob[14])}

    block_meshes = json.loads((args.input / "building-block-meshes.json").read_text(encoding="utf-8"))
    selected_ids = {7196, 7632, 7510, 7432}
    selected = []
    all_renderers = []
    used_materials = set()
    for block in block_meshes:
        meshes = []
        for mesh in block["hierarchy_meshes"]:
            filter_blob = raw(mesh["mesh_filter"], 33)
            go_ref = pointer(filter_blob, 0)
            if go_ref["file_id"] != 0:
                raise ValueError(f"External GameObject for MeshFilter {mesh['mesh_filter']}")
            go_name, refs = game_object(go_ref["path_id"])
            go_blob = raw(go_ref["path_id"], 1)
            layer = i32(go_blob, 4 + len(refs) * 12)
            renderer_ids = [r["path_id"] for r in refs if r["file_id"] == 0 and r["path_id"] in items
                            and items[r["path_id"]]["class_id"] == 23]
            if len(renderer_ids) > 1:
                raise ValueError(f"Multiple MeshRenderers for MeshFilter {mesh['mesh_filter']}")
            render = renderer(renderer_ids[0]) if renderer_ids else None
            if render:
                all_renderers.append(render["path_id"])
                used_materials.update(r["path_id"] for r in render["materials"] if r["file_id"] == 0 and r["path_id"])
            meshes.append({"gameobject": go_name, "gameobject_path_id": go_ref["path_id"],
                           "layer": layer, "mesh": mesh, "mesh_renderer": render})
        if block["object_path_id"] in selected_ids:
            selected.append({"block_path_id": block["object_path_id"], "name": block["name"],
                             "save_id": block["save_id"], "meshes": meshes})
    if len(set(all_renderers)) != len(all_renderers):
        raise ValueError("MeshRenderer reused across selected block hierarchies")
    materials = {str(path_id): material(path_id) for path_id in sorted(used_materials)}
    shader_ids = {v["shader"]["path_id"] for v in materials.values()
                  if v["shader"]["file_id"] == 0 and v["shader"]["path_id"]}
    shaders = {}
    for path_id in sorted(shader_ids):
        blob = raw(path_id, 48)
        strings = [m.group().decode("ascii", "replace") for m in re.finditer(rb"[ -~]{5,}", blob)]
        candidates = [s for s in strings if s.startswith(("Shader Graphs/", "Universal Render Pipeline/", "Hidden/"))]
        shaders[str(path_id)] = {"path_id": path_id, "offset": items[path_id]["offset"],
                                 "name_candidates": candidates[:8]}
    texture_ids = {value["texture"]["path_id"] for mat in materials.values()
                   for value in mat["textures"].values()
                   if value["texture"]["file_id"] == 0 and value["texture"]["path_id"]}
    textures = {}
    for path_id in sorted(texture_ids):
        blob = raw(path_id, 28)
        name, _ = unity_string(blob, 0)
        textures[str(path_id)] = {"path_id": path_id, "offset": items[path_id]["offset"],
                                   "name": name}

    global_path = (args.game_data.resolve(strict=True) / "globalgamemanagers.assets").resolve(strict=True)
    global_index = json.loads((args.input / "globalgamemanagers.assets.json").read_text(encoding="utf-8"))
    if Path(global_index["file"]).resolve(strict=True) != global_path:
        raise ValueError("Global index and input file identity differ")
    global_data = global_path.read_bytes()
    global_items = {row["path_id"]: row for row in global_index["objects"]}

    def global_raw(path_id, class_id):
        row = global_items[path_id]
        if row["class_id"] != class_id:
            raise ValueError(f"Global pathID {path_id} has wrong class")
        return global_data[row["offset"]:row["offset"] + row["bytes"]]

    pipeline = global_raw(2355, 114)
    renderer_count = i32(pipeline, 0x48)
    if renderer_count != 2:
        raise ValueError("Unexpected URP renderer list size")
    renderer_refs = [pointer(pipeline, 0x4c + i * 12) for i in range(renderer_count)]
    default_renderer_index = i32(pipeline, 0x64)
    if renderer_refs != [{"file_id": 0, "path_id": 2354}, {"file_id": 0, "path_id": 2353}]:
        raise ValueError("Unexpected URP renderer list")
    renderer_data = global_raw(2354, 114)
    if i32(renderer_data, 0xa8) != 1 or pointer(renderer_data, 0xac) != {"file_id": 0, "path_id": 2360}:
        raise ValueError("Unexpected active URP renderer feature list")
    pixelate = global_raw(2360, 114)
    pixelate_settings = {"active": bool(pixelate[0x30]), "layer_mask": i32(pixelate, 0x34),
                         "final_blit_shader": pointer(pixelate, 0x38),
                         "pixel_scale": i32(pixelate, 0x44), "max_res_height": i32(pixelate, 0x48)}
    if pixelate_settings["final_blit_shader"] != {"file_id": 0, "path_id": 65}:
        raise ValueError("Unexpected final blit shader")
    manager_path = (args.game_data.resolve(strict=True) / "globalgamemanagers").resolve(strict=True)
    indexer_path = Path(__file__).resolve().parents[2] / "tools" / "unity22-compute-probe.py"
    spec = importlib.util.spec_from_file_location("unity22_visual_indexer", indexer_path)
    if spec is None or spec.loader is None:
        raise ValueError("Unity indexer unavailable")
    indexer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(indexer)
    manager_data, manager_index = indexer.resource_index(manager_path)
    manager_refs = []
    for row in manager_index["objects"]:
        if row["class_id"] not in (30, 47):
            continue
        blob = manager_data[row["offset"]:row["offset"] + row["bytes"]]
        for offset in range(0, len(blob) - 11, 4):
            if pointer(blob, offset) == {"file_id": 1, "path_id": 2355}:
                manager_refs.append({"class_id": row["class_id"], "path_id": row["path_id"],
                                     "absolute_offset": row["offset"] + offset})
    if {row["class_id"] for row in manager_refs} != {30, 47}:
        raise ValueError("Pipeline asset is not referenced by GraphicsSettings and QualitySettings")
    scene_path = (args.game_data.resolve(strict=True) / "level0").resolve(strict=True)
    scene_index = json.loads((args.input / "level0.json").read_text(encoding="utf-8"))
    if Path(scene_index["file"]).resolve(strict=True) != scene_path:
        raise ValueError("Scene index and input file identity differ")
    scene_data = scene_path.read_bytes()
    scene_items = {row["path_id"]: row for row in scene_index["objects"]}
    cameras = {}
    for path_id in (7384, 8109):
        row = scene_items[path_id]
        if row["class_id"] != 114:
            raise ValueError("Unexpected camera data class")
        blob = scene_data[row["offset"]:row["offset"] + row["bytes"]]
        cameras[str(path_id)] = {"path_id": path_id, "offset": row["offset"],
                                 "renderer_index": i32(blob, 0x34)}
    output = {"source": str(data_path), "source_sha256": index.get("sha256"),
              "mesh_renderer_count": len(all_renderers), "selected_blocks": selected,
              "materials": materials, "shaders": shaders, "textures": textures,
              "pipeline": {"source": str(global_path), "source_sha256": global_index.get("sha256"),
                           "settings_source": str(manager_path), "settings_references": manager_refs,
                           "renderer_refs": renderer_refs, "default_renderer_index": default_renderer_index,
                           "renderer_feature": {"file_id": 0, "path_id": 2360},
                           "pixelate_settings": pixelate_settings,
                           "shader_name_candidate": "noio/Blit AlphaBlend"},
              "scene_cameras": {"source": str(scene_path), "source_sha256": scene_index.get("sha256"),
                                "additional_camera_data": cameras},
              "material_slot_histogram": dict(collections.Counter(
                  len(renderer(row["path_id"])["materials"]) for row in index["objects"]
                  if row["class_id"] == 23))}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "visual-bindings.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"selected_blocks": len(selected), "mesh_renderers": len(all_renderers),
                      "materials": len(materials), "shaders": len(shaders)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
