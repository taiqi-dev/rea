"""Read the three shipped RoofTile JSON meshes and their default RON order.

This version-bounded probe does not execute the game or export its geometry.
Output is a new metadata-only JSON file; an existing output is never replaced.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re


NAMES = ("roof_tile", "roof_tile_lod1", "roof_tile_backface")


def read_mesh(path):
    raw = path.read_bytes()
    mesh = json.loads(raw)
    if mesh.get("attributes") != ["Vertex_Position"]:
        raise ValueError(f"Unexpected attribute set: {path}")
    positions = mesh["Vertex_Position"]
    indices = mesh["indices"]
    if positions.get("type") != ["float", 3] or indices.get("type") != ["int", 1]:
        raise ValueError(f"Unexpected position/index type: {path}")
    vertices = positions["buffer"]
    faces = indices["buffer"]
    if not vertices or not faces or len(faces) % 3:
        raise ValueError(f"Empty or non-triangle mesh: {path}")
    if any(len(p) != 3 or any(not isinstance(c, (int, float)) for c in p) for p in vertices):
        raise ValueError(f"Malformed position: {path}")
    if any(type(i) is not int or i < 0 or i >= len(vertices) for i in faces):
        raise ValueError(f"Index outside vertex buffer: {path}")
    if len(set(faces)) != len(vertices):
        raise ValueError(f"Unused vertex or incomplete index coverage: {path}")
    bounds = [[min(p[axis] for p in vertices), max(p[axis] for p in vertices)] for axis in range(3)]
    return {
        "path": str(path), "file_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "vertices": len(vertices), "indices": len(faces), "triangles": len(faces) // 3,
        "index_min": min(faces), "index_max": max(faces), "bounds_xyz": bounds,
        "double_sided": mesh.get("double_sided"),
    }


def inspect(assets):
    assets = assets.resolve(strict=True)
    ron_path = assets / "nani_meshes.ron"
    ron_raw = ron_path.read_bytes()
    ron = ron_raw.decode("utf-8")
    matches = list(re.finditer(r"subset:\s*RoofTile\s*,\s*meshes:\s*\[(.*?)\]", ron, re.S))
    if len(matches) != 1:
        raise ValueError("Expected one RoofTile subset in nani_meshes.ron")
    names = re.findall(r'\(\s*name:\s*"([^"\r\n]+)"\s*\)', matches[0].group(1))
    if tuple(names) != NAMES:
        raise ValueError("Unexpected RoofTile mesh order")
    rows = [read_mesh(assets / "meshes" / f"{name}.json") for name in NAMES]
    for row, name in zip(rows, NAMES):
        row["name"] = name
    fine, lod = rows[:2]
    return {
        "assets_root": str(assets),
        "ron": {"path": str(ron_path), "file_bytes": len(ron_raw),
                "sha256": hashlib.sha256(ron_raw).hexdigest(),
                "roof_tile_block_line": ron[:matches[0].start()].count("\n") + 1,
                "mesh_order": names},
        "meshes": rows,
        "lod1_relative_to_fine": {
            "vertex_fraction": [lod["vertices"], fine["vertices"]],
            "index_fraction": [lod["indices"], fine["indices"]],
            "triangle_fraction": [lod["triangles"], fine["triangles"]],
        },
        "limitations": ["Source JSON geometry, not measured GPU traffic or runtime atlas contents.",
                        "No game process, renderer, or asset conversion was run."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.assets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
    print(json.dumps({"meshes": [{k: row[k] for k in ("name", "vertices", "indices", "triangles")}
                                 for row in result["meshes"]],
                      "lod1_relative_to_fine": result["lod1_relative_to_fine"]}))


if __name__ == "__main__":
    main()
