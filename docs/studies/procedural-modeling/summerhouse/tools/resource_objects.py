"""Index SUMMERHOUSE Unity 2023.2.22f1 MonoScripts and MonoBehaviours.

Read-only; invokes the adjacent format-22 indexer. The optional digest requires
explicit --sha256 because investigations do not generally authorize hashes.
The outputs are analysis records; direct them to the ignored .cache directory.
"""

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path


INDEXER = Path(__file__).resolve().parents[2] / "tools" / "unity22-compute-probe.py"


def aligned_string(data, start, stop):
    if start + 4 > stop:
        raise ValueError("short Unity string prefix")
    size = struct.unpack_from("<i", data, start)[0]
    if not 0 <= size <= 4096 or start + 4 + size > stop:
        raise ValueError(f"invalid Unity string size {size} at {start}")
    return data[start + 4:start + 4 + size].decode("utf-8"), (start + 4 + size + 3) & ~3


def load_indexer():
    spec = importlib.util.spec_from_file_location("unity22_compute_probe", INDEXER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load format-22 indexer: {INDEXER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resource_index


def index_one(indexer, path, output, digest):
    data, index = indexer(path.resolve(strict=True))
    if index["type_trees"] or index["format"] != 22 or index["unity"] != "2023.2.22f1":
        raise ValueError(f"Unsupported Unity serialized profile: {path}")
    if digest:
        index["sha256"] = hashlib.sha256(data).hexdigest()
    (output / f"{path.name}.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return data, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-data", required=True, type=Path, help="Exact SUMMERHOUSE_Data directory")
    parser.add_argument("--output", required=True, type=Path, help="Ignored analysis output directory")
    parser.add_argument("--sha256", action="store_true", help="Compute file digests only when authorized")
    args = parser.parse_args()
    game_data = args.game_data.resolve(strict=True)
    if not game_data.is_dir():
        raise ValueError(f"Not a directory: {game_data}")
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve(strict=True)
    indexer = load_indexer()

    global_data, global_index = index_one(indexer, game_data / "globalgamemanagers.assets", output, args.sha256)
    scripts = {}
    for item in global_index["objects"]:
        if item["class_id"] != 115:
            continue
        start, stop = item["offset"], item["offset"] + item["bytes"]
        name, at = aligned_string(global_data, start, stop)
        at += 20  # execution order and 16-byte script hash
        cls, at = aligned_string(global_data, at, stop)
        namespace, at = aligned_string(global_data, at, stop)
        assembly, at = aligned_string(global_data, at, stop)
        if at != stop:
            raise ValueError(f"Unconsumed MonoScript bytes: pathID {item['path_id']}")
        scripts[item["path_id"]] = {"name": name, "class": cls, "namespace": namespace,
                                     "assembly": assembly, "object_offset": start}
    (output / "monoscripts.json").write_text(json.dumps(scripts, ensure_ascii=False, indent=2), encoding="utf-8")

    shared_data, shared_index = index_one(indexer, game_data / "sharedassets0.assets", output, args.sha256)
    rows = []
    for item in shared_index["objects"]:
        if item["class_id"] != 114:
            continue
        start, stop = item["offset"], item["offset"] + item["bytes"]
        if item["bytes"] < 32:
            raise ValueError(f"Short MonoBehaviour: pathID {item['path_id']}")
        go_file_id, go_path_id = struct.unpack_from("<iq", shared_data, start)
        script_file_id, script_path_id = struct.unpack_from("<iq", shared_data, start + 16)
        name, content_at = aligned_string(shared_data, start + 28, stop)
        rows.append({"path_id": item["path_id"], "offset": start, "bytes": item["bytes"],
                     "gameobject_fileid": go_file_id, "gameobject_pathid": go_path_id,
                     "script_fileid": script_file_id, "script_pathid": script_path_id,
                     "script": scripts.get(script_path_id) if script_file_id == 1 else None,
                     "name": name, "content_offset": content_at})
    (output / "sharedassets0.assets.objects.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    targets = {"BuildingBlock", "BlockCombination", "BuildingBlockLibrary"}
    selected = [row for row in rows if row["script"] and row["script"]["assembly"] == "Assembly-CSharp"
                and row["script"]["class"] in targets]
    print(json.dumps({"mono_scripts": len(scripts), "mono_behaviours": len(rows),
                      "selected": {name: sum(row["script"]["class"] == name for row in selected) for name in sorted(targets)},
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
