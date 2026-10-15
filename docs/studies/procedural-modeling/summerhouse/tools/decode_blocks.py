"""Decode selected SUMMERHOUSE block prefabs and combination records.

This is a bounded, read-only decoder for the observed stripped-type-tree Unity
profile. It depends on resource_objects.py output and Assembly-CSharp metadata
for the selected field order; it is not a general Unity asset parser. Outputs
must go to an ignored analysis directory, not into the study documentation.
"""

import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path


def i32(data, at):
    return struct.unpack_from("<i", data, at)[0]


def i64(data, at):
    return struct.unpack_from("<q", data, at)[0]


def pptr(data, at):
    return {"file_id": i32(data, at), "path_id": i64(data, at + 4)}


class Reader:
    def __init__(self, data, path_id, start):
        self.data = data
        self.path_id = path_id
        self.at = start

    def take(self, fmt):
        size = struct.calcsize("<" + fmt)
        if self.at + size > len(self.data):
            raise ValueError(f"Truncated object pathID {self.path_id} at {self.at}")
        value = struct.unpack_from("<" + fmt, self.data, self.at)
        self.at += size
        return value[0] if len(value) == 1 else value

    def pointer(self):
        return {"file_id": self.take("i"), "path_id": self.take("q")}

    def boolean(self):
        value = self.take("B")
        if value not in (0, 1):
            raise ValueError(f"Invalid bool {value} in pathID {self.path_id}")
        self.at = (self.at + 3) & ~3
        return bool(value)

    def count(self, limit):
        value = self.take("i")
        if not 0 <= value <= limit:
            raise ValueError(f"Invalid list length {value} in pathID {self.path_id}")
        return value

    def finish(self):
        if self.at != len(self.data):
            raise ValueError(f"Unconsumed bytes in pathID {self.path_id}: {self.at}/{len(self.data)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-data", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path, help="Output directory from resource_objects.py")
    parser.add_argument("--output", required=True, type=Path, help="Ignored analysis output directory")
    args = parser.parse_args()
    game_data = args.game_data.resolve(strict=True)
    input_dir = args.input.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve(strict=True)
    source = game_data / "sharedassets0.assets"
    data = source.read_bytes()
    index = json.loads((input_dir / "sharedassets0.assets.json").read_text(encoding="utf-8"))
    if Path(index["file"]).resolve(strict=True) != source.resolve(strict=True) or index["format"] != 22 or index["type_trees"]:
        raise ValueError("Index identity or Unity profile does not match resource")
    if index["unity"] != "2023.2.22f1" or index["object_count"] != len(index["objects"]):
        raise ValueError("Unsupported or incomplete resource index")
    if "sha256" in index and hashlib.sha256(data).hexdigest() != index["sha256"]:
        raise ValueError("Resource bytes changed since the indexed digest")
    if len(data) < max((x["offset"] + x["bytes"] for x in index["objects"]), default=0):
        raise ValueError("Indexed object exceeds source length")
    items = {x["path_id"]: x for x in index["objects"]}
    if len(items) != len(index["objects"]):
        raise ValueError("Duplicate Unity pathID")
    behaviours = json.loads((input_dir / "sharedassets0.assets.objects.json").read_text(encoding="utf-8"))
    selected = {"BuildingBlock", "BlockCombination", "BuildingBlockLibrary"}
    targets = [x for x in behaviours if x["script"] and x["script"]["assembly"] == "Assembly-CSharp"
               and x["script"]["class"] in selected]

    def raw(path_id, class_id=None):
        item = items[path_id]
        if class_id is not None and item["class_id"] != class_id:
            raise ValueError(f"Wrong class for pathID {path_id}: {item['class_id']} != {class_id}")
        return data[item["offset"]:item["offset"] + item["bytes"]]

    def go(path_id):
        blob = raw(path_id, 1)
        count = i32(blob, 0)
        if not 0 <= count <= 64 or 8 + count * 12 > len(blob):
            raise ValueError(f"Invalid GameObject component count: pathID {path_id}")
        components = [pptr(blob, 4 + j * 12) for j in range(count)]
        at = 8 + count * 12  # component list followed by layer and name
        size = i32(blob, at)
        if not 0 <= size <= 512 or at + 4 + size > len(blob):
            raise ValueError(f"Invalid GameObject name: pathID {path_id}")
        return {"path_id": path_id, "name": blob[at + 4:at + 4 + size].decode("utf-8"),
                "components": components}

    def local(ref, class_id):
        if ref["file_id"] != 0 or ref["path_id"] not in items:
            raise ValueError(f"Unresolved local reference: {ref}")
        raw(ref["path_id"], class_id)
        return ref["path_id"]

    blocks = []
    combinations = []
    libraries = []
    for item in targets:
        path_id = item["path_id"]
        blob = raw(path_id, 114)
        if item["offset"] != items[path_id]["offset"] or item["bytes"] != len(blob):
            raise ValueError(f"MonoBehaviour index mismatch: pathID {path_id}")
        cls = item["script"]["class"]
        gameobject = (None if cls == "BuildingBlockLibrary" and item["gameobject_fileid"] == 0
                      and item["gameobject_pathid"] == 0 else
                      go(local({"file_id": item["gameobject_fileid"],
                                "path_id": item["gameobject_pathid"]}, 1)))
        reader = Reader(blob, path_id, item["content_offset"] - item["offset"])
        if cls == "BuildingBlock":
            categories = [reader.take("i") for _ in range(reader.count(32))]
            cells = [list(reader.take("ii")) for _ in range(reader.count(64))]
            punch = reader.take("f")
            flipped = reader.boolean()
            save_id = reader.take("i")
            preview = reader.pointer()
            priority = reader.take("i")
            renderer = reader.pointer()
            z_offset = reader.take("f")
            raycast = reader.boolean()
            depth_mode = reader.take("i")
            depth_steps = reader.take("i")
            ray_positions = [list(reader.take("fff")) for _ in range(reader.count(64))]
            unlock = reader.take("i")
            preview_time = reader.take("f")
            placement_time = reader.take("f")
            preview_ease = reader.take("i")
            placement_ease = reader.take("i")
            overwrite_sound = reader.boolean()
            sound = reader.pointer()
            intensity = reader.take("i")
            reader.finish()
            blocks.append({"object_path_id": path_id, "object_offset": item["offset"], "gameobject": gameobject,
                           "save_id": save_id, "category_tags": categories, "cells": cells,
                           "punch_strength": punch, "flipped": flipped, "preview_image": preview,
                           "priority_in_picker": priority, "main_renderer": renderer,
                           "z_offset": z_offset, "raycast_for_z_depth": raycast,
                           "depth_sample_mode": depth_mode, "additional_depth_steps": depth_steps,
                           "raycast_positions": ray_positions, "unlock_state": unlock,
                           "preview_anim_length": preview_time, "placement_anim_length": placement_time,
                           "preview_ease": preview_ease, "placement_ease": placement_ease,
                           "overwrite_placement_sound": overwrite_sound,
                           "custom_placement_sound": sound, "sound_intensity": intensity})
        elif cls == "BlockCombination":
            requirements = []
            for _ in range(reader.count(32)):
                prefab = reader.pointer()
                position = list(reader.take("ii"))
                replace = reader.boolean()
                requirements.append({"block_prefab": prefab, "relative_position": position,
                                     "replace_on_success": replace})
            reward = reader.pointer()
            recipe_id = reader.take("i")
            unlocked = reader.boolean()
            reader.finish()
            combinations.append({"object_path_id": path_id, "object_offset": item["offset"],
                                 "gameobject": gameobject, "requirements": requirements,
                                 "block_to_unlock": reward, "recipe_id": recipe_id,
                                 "has_been_unlocked": unlocked})
        elif cls == "BuildingBlockLibrary":
            folder_size = reader.count(4096)
            folder = reader.take(f"{folder_size}s").decode("utf-8")
            reader.at = (reader.at + 3) & ~3
            entries = []
            for _ in range(reader.count(4096)):
                entries.append({"block": reader.pointer(), "id": reader.take("i")})
            max_id = reader.take("i")
            reader.finish()
            libraries.append({"object_path_id": path_id, "gameobject": gameobject,
                              "target_folder": folder, "entries": entries, "max_id": max_id})

    if len(libraries) != 1:
        raise ValueError(f"Expected one block library in this file, found {len(libraries)}")
    blocks_by_id = {x["object_path_id"]: x for x in blocks}
    for recipe in combinations:
        for requirement in recipe["requirements"]:
            path_id = local(requirement["block_prefab"], 114)
            if path_id not in blocks_by_id:
                raise ValueError(f"Requirement is not a decoded BuildingBlock: {path_id}")
            block = blocks_by_id[path_id]
            requirement["resolved_block"] = {"object_path_id": path_id, "save_id": block["save_id"],
                                             "name": block["gameobject"]["name"]}
        path_id = local(recipe["block_to_unlock"], 114)
        if path_id not in blocks_by_id:
            raise ValueError(f"Reward is not a decoded BuildingBlock: {path_id}")
        reward = blocks_by_id[path_id]
        recipe["resolved_reward"] = {"object_path_id": path_id, "save_id": reward["save_id"],
                                     "name": reward["gameobject"]["name"]}
    if len({x["recipe_id"] for x in combinations}) != len(combinations):
        raise ValueError("Duplicate combination ID")
    library = libraries[0]
    for entry in library["entries"]:
        path_id = local(entry["block"], 114)
        if path_id not in blocks_by_id or blocks_by_id[path_id]["save_id"] != entry["id"]:
            raise ValueError(f"Block library ID mismatch: {entry}")
        entry["name"] = blocks_by_id[path_id]["gameobject"]["name"]
    if len({x["id"] for x in library["entries"]}) != len(library["entries"]):
        raise ValueError("Duplicate block library ID")

    def mesh_hierarchy(transform_id, visited):
        if transform_id in visited:
            raise ValueError(f"Repeated Transform within hierarchy: {transform_id}")
        visited.add(transform_id)
        blob = raw(transform_id, 4)
        if len(blob) < 68:
            raise ValueError(f"Short Transform: {transform_id}")
        gameobject = go(local(pptr(blob, 0), 1))
        meshes = []
        for component in gameobject["components"]:
            component_id = local(component, items[component["path_id"]]["class_id"])
            if items[component_id]["class_id"] == 33:
                mesh_filter = raw(component_id, 33)
                if len(mesh_filter) != 24:
                    raise ValueError(f"Unexpected MeshFilter size: {component_id}")
                ref = pptr(mesh_filter, 12)
                if ref["file_id"] == 0 and ref["path_id"] != 0:
                    raw(ref["path_id"], 43)
                meshes.append({"mesh_filter": component_id, "mesh_file_id": ref["file_id"],
                               "mesh_path_id": ref["path_id"]})
        children = i32(blob, 52)
        if not 0 <= children <= 256 or 68 + children * 12 != len(blob):
            raise ValueError(f"Unexpected Transform children/size: {transform_id}")
        for j in range(children):
            meshes.extend(mesh_hierarchy(local(pptr(blob, 56 + j * 12), 4), visited))
        return meshes

    mesh_rows = []
    for block in blocks:
        transforms = [local(ref, 4) for ref in block["gameobject"]["components"]
                      if ref["file_id"] == 0 and ref["path_id"] in items and items[ref["path_id"]]["class_id"] == 4]
        if len(transforms) != 1:
            raise ValueError(f"Expected one root Transform for block {block['object_path_id']}")
        mesh_rows.append({"object_path_id": block["object_path_id"], "name": block["gameobject"]["name"],
                          "save_id": block["save_id"], "hierarchy_meshes": mesh_hierarchy(transforms[0], set())})
    mesh_refs = [mesh for row in mesh_rows for mesh in row["hierarchy_meshes"]]
    if len({mesh["mesh_filter"] for mesh in mesh_refs}) != len(mesh_refs):
        raise ValueError("MeshFilter belongs to multiple decoded block hierarchies")

    def write(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {"blocks": len(blocks), "distinct_save_ids": len({x["save_id"] for x in blocks}),
               "combinations": len(combinations),
               "requirements": sum(len(x["requirements"]) for x in combinations),
               "library_entries": len(library["entries"]), "library_max_id": library["max_id"],
               "mesh_filters_in_block_hierarchies": len(mesh_refs),
               "mesh_filters_in_file": index["classes"].get("33"),
               "mesh_references": dict(collections.Counter(
                   "null" if x["mesh_file_id"] == 0 and x["mesh_path_id"] == 0
                   else "local" if x["mesh_file_id"] == 0 else "external" for x in mesh_refs))}
    if summary["mesh_filters_in_block_hierarchies"] != summary["mesh_filters_in_file"]:
        raise ValueError("Block hierarchies do not cover all MeshFilters in this file")
    write("building-blocks.json", blocks)
    write("block-combinations.json", combinations)
    write("block-library.json", library)
    write("building-block-meshes.json", mesh_rows)
    write("summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
