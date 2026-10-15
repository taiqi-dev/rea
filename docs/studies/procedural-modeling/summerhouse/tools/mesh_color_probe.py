"""Read selected SUMMERHOUSE Mesh vertex color channels from serialized assets.

The exact Unity 2023.2.22f1 release schema and an existing object index are
required. This reads files only and does not load or execute the game.
"""

import argparse
import importlib.util
import json
import struct
from pathlib import Path


BASE = Path(__file__).resolve().parents[2] / "sandcastle/tools/player_color_space_probe.py"


def load_reader():
    spec = importlib.util.spec_from_file_location("unity_object_reader", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unity object reader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ObjectReader


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-data", required=True, type=Path)
    ap.add_argument("--index", required=True, type=Path)
    ap.add_argument("--schema", required=True, type=Path)
    ap.add_argument("--mesh", required=True, type=int, action="append")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    source = (args.game_data.resolve(strict=True) / "sharedassets0.assets").resolve(strict=True)
    index = json.loads(args.index.read_text(encoding="utf-8"))
    if (Path(index["file"]).resolve(strict=True) != source or index["format"] != 22
            or index["unity"] != "2023.2.22f1" or index["type_trees"]):
        raise ValueError("Unexpected serialized file or index")
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    if schema.get("Version") != "2023.2.22f1":
        raise ValueError("Unexpected schema version")
    classes = [c for c in schema["Classes"] if c["TypeID"] == 43]
    if len(classes) != 1:
        raise ValueError("Expected unique Mesh schema")
    root = classes[0]["ReleaseRootNode"]
    objects = {o["path_id"]: o for o in index["objects"]}
    data = source.read_bytes()
    Reader = load_reader()

    class MeshReader(Reader):
        def parse(self, node, path=""):
            if node.get("TypeName") == "TypelessData":
                start = self.pos
                count = struct.unpack("<i", self.read(4))[0]
                if count < 0 or count > len(self.data) - self.pos:
                    raise ValueError(f"Invalid typeless data length at {path}: {count}")
                result = self.read(count)
                if node.get("MetaFlag", 0) & 0x4000:
                    self.align()
                self.array_counts.append({"path": path, "relative_offset": start, "count": count})
                return result
            return super().parse(node, path)

    rows = []
    for path_id in args.mesh:
        item = objects[path_id]
        if item["class_id"] != 43:
            raise ValueError(f"Object {path_id} is not Mesh")
        blob = data[item["offset"]:item["offset"] + item["bytes"]]
        reader = MeshReader(blob)
        value = reader.parse(root)
        if reader.pos != len(blob):
            raise ValueError(f"Mesh {path_id} not fully consumed: {reader.pos}/{len(blob)}")
        vertex = value["m_VertexData"]
        channels = vertex["m_Channels"]["Array"]
        raw = vertex["m_DataSize"]
        if len(channels) < 4:
            raise ValueError(f"Mesh {path_id} has no color channel slot")
        active = [c for c in channels if c["dimension"]]
        if any(c["stream"] != 0 for c in active):
            raise ValueError(f"Mesh {path_id} uses an unhandled vertex stream")
        format_bytes = {0: 4, 1: 2, 2: 1, 3: 1, 4: 2, 5: 2, 6: 1, 7: 1, 8: 2, 9: 2, 10: 4, 11: 4}
        stride = max(c["offset"] + c["dimension"] * format_bytes[c["format"]] for c in active)
        if len(raw) != stride * vertex["m_VertexCount"]:
            raise ValueError(f"Mesh {path_id} vertex bytes do not fit one stream")
        color = channels[3]
        if color["dimension"] not in (0, 4) or (color["dimension"] and color["format"] != 2):
            raise ValueError(f"Mesh {path_id} has an unhandled COLOR0 layout")
        alpha_counts = {}
        color_samples = []
        if color["dimension"]:
            for i in range(vertex["m_VertexCount"]):
                at = i * stride + color["offset"]
                rgba = list(raw[at:at + 4])
                alpha_counts[rgba[3]] = alpha_counts.get(rgba[3], 0) + 1
                if len(color_samples) < 4:
                    color_samples.append(rgba)
        rows.append({"path_id": path_id, "offset": item["offset"], "bytes": item["bytes"],
                     "name": value["m_Name"], "vertex_count": vertex["m_VertexCount"],
                     "channels": channels, "vertex_stride": stride, "vertex_data_bytes": len(raw),
                     "color_alpha_byte_counts": alpha_counts, "color_samples_rgba_bytes": color_samples,
                     "stream": value["m_StreamData"]})
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        json.dump({"source": str(source), "schema": str(args.schema.resolve(strict=True)),
                   "scope": "offline serialized Mesh fields only", "meshes": rows}, file,
                  ensure_ascii=False, indent=2)
    print(json.dumps({"meshes": len(rows), "output": str(output)}))


if __name__ == "__main__":
    main()
