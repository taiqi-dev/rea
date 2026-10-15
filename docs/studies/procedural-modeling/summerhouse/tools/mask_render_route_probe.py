"""Read SUMMERHOUSE camera/layer filters and the exact Mask shader pass records.

Only the observed 2023.2.22f1 stripped SerializedFile profile is accepted.
Output is research metadata and selected DXBC disassembly, never target execution.
"""

import argparse
import collections
import importlib.util
import json
import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERSION = "2023.2.22f1"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe(game_data, schema_path, output):
    unity = load("unity_index", ROOT / "tools/unity22-compute-probe.py")
    objects = load("object_reader", ROOT / "sandcastle/tools/player_color_space_probe.py")
    shader = load("shader_lz4", ROOT / "tools/unity22-shader-probe.py")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("Version") != VERSION:
        raise ValueError("Expected the exact 2023.2.22f1 schema")
    classes = {c["TypeID"]: c["ReleaseRootNode"] for c in schema["Classes"]}
    loaded = {}

    def file(name):
        if name not in loaded:
            raw, index = unity.resource_index(game_data / name)
            if (index["unity"], index["format"], index["type_trees"]) != (VERSION, 22, False):
                raise ValueError("Unexpected SerializedFile profile")
            loaded[name] = (raw, index)
        return loaded[name]

    def decode(name, item):
        raw, _ = file(name)
        reader = objects.ObjectReader(raw[item["offset"]:item["offset"] + item["bytes"]])
        value = reader.parse(classes[item["class_id"]])
        if reader.pos != item["bytes"]:
            raise ValueError(f"Object not fully consumed: {name}, {item['path_id']}")
        return value, reader.fields

    def selected(name, path_id, class_id):
        _, index = file(name)
        matches = [o for o in index["objects"] if o["path_id"] == path_id and o["class_id"] == class_id]
        if len(matches) != 1:
            raise ValueError("Missing unique selected object")
        return matches[0]

    cameras = []
    _, index = file("level0")
    for obj in index["objects"]:
        if obj["class_id"] != 20:
            continue
        value, fields = decode("level0", obj)
        cameras.append({"object": obj, "values": value, "fields": fields})

    renderers = []
    raw, index = file("sharedassets0.assets")
    for obj in index["objects"]:
        if obj["class_id"] != 23:
            continue
        value, fields = decode("sharedassets0.assets", obj)
        go = value["m_GameObject"]
        if go["m_FileID"] != 0:
            raise ValueError("Expected a local Renderer GameObject")
        go_obj = selected("sharedassets0.assets", go["m_PathID"], 1)
        go_value, _ = decode("sharedassets0.assets", go_obj)
        renderers.append({"object": obj, "game_object": go_obj,
                          "name": go_value["m_Name"], "layer": go_value["m_Layer"],
                          "local_active": go_value["m_IsActive"], "enabled": value["m_Enabled"],
                          "enabled_offset": next(x["relative_offset"] for x in fields if x["name"] == "m_Enabled"),
                          "previous_probe_byte14": raw[obj["offset"] + 14],
                          "materials": value["m_Materials"]["Array"]})

    obj = selected("sharedassets0.assets", 621, 48)
    value, fields = decode("sharedassets0.assets", obj)
    parsed = value["m_ParsedForm"]
    if parsed["m_Name"] != "Shader Graphs/Mask" or value["platforms"]["Array"] != [4]:
        raise ValueError("Unexpected Mask shader identity/platform")
    passes = []
    for sub_index, subshader in enumerate(parsed["m_SubShaders"]["Array"]):
        for pass_index, item in enumerate(subshader["m_Passes"]["Array"]):
            state = item["m_State"]
            passes.append({"subshader": sub_index, "pass": pass_index, "name": state["m_Name"],
                           "tags": state["m_Tags"]["tags"]["Array"], "state": state,
                           "name_indices": item["m_NameIndices"]["Array"],
                           "vertex": item["progVertex"], "fragment": item["progFragment"]})
    source = bytes(value["compressedBlob"]["Array"])
    offsets, sizes, decoded_sizes = [value[key]["Array"][0]["Array"] for key in
                                   ("offsets", "compressedLengths", "decompressedLengths")]
    if offsets != [0] or len(sizes) != 1 or len(decoded_sizes) != 1 or sizes[0] != len(source):
        raise ValueError("Expected one complete compressed shader section")
    if not 0 < decoded_sizes[0] <= 16 * 1024 * 1024:
        raise ValueError("Shader section exceeds the decoder allocation bound")
    decoded = shader.decode_lz4(source, decoded_sizes[0])
    count = struct.unpack_from("<I", decoded)[0]
    if not 0 < count <= (len(decoded) - 4) // 12:
        raise ValueError("Invalid subprogram record count")
    records = []
    for i in range(count):
        start, length, segment = struct.unpack_from("<III", decoded, 4 + 12 * i)
        if segment != 0 or start < 4 + 12 * count or start > len(decoded) or length > len(decoded) - start:
            raise ValueError("Invalid subprogram record range/segment")
        records.append({"index": i, "offset": start, "bytes": length, "segment": segment})
    first = passes[0]
    disassembly = []
    for stage in ("vertex", "fragment"):
        variants = first[stage]["m_PlayerSubPrograms"]["Array"]
        programs = [p for group in variants for p in group["Array"]]
        if len(programs) != 1:
            raise ValueError("Expected exactly one selected forward-stage program")
        blob_index = programs[0]["m_BlobIndex"]
        if not 0 <= blob_index < len(records):
            raise ValueError("Forward program index exceeds section table")
        record = records[blob_index]
        body = decoded[record["offset"]:record["offset"] + record["bytes"]]
        hits = list(re.finditer(b"DXBC", body))
        if len(hits) != 1:
            raise ValueError("Expected one DXBC container in the selected program record")
        at = hits[0].start()
        if len(body) - at < 32:
            raise ValueError("Truncated DXBC header")
        marker, size, chunks = struct.unpack_from("<III", body, at + 20)
        if marker != 1 or not 1 <= chunks <= 64 or not 32 + 4 * chunks <= size <= len(body) - at:
            raise ValueError("Invalid DXBC header/range")
        for chunk in struct.unpack_from("<" + "I" * chunks, body, at + 32):
            if not 32 + 4 * chunks <= chunk <= size - 8:
                raise ValueError("Invalid DXBC chunk offset")
            chunk_size = struct.unpack_from("<I", body, at + chunk + 4)[0]
            if chunk_size > size - chunk - 8:
                raise ValueError("Invalid DXBC chunk length")
        filename = f"mask-forward-{stage}.asm.txt"
        with (output / filename).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(unity.disassemble(body[at:at + size]))
        disassembly.append({"stage": stage, "blob_index": blob_index,
                            "record": record, "dxbc_record_offset": at,
                            "dxbc_bytes": size, "disassembly": filename})
    return {"game_data": str(game_data), "schema": str(schema_path), "version": VERSION,
            "cameras": cameras, "renderer_count": len(renderers), "renderers": renderers,
            "layer_histogram": dict(collections.Counter(x["layer"] for x in renderers)),
            "enabled_byte14_mismatches": [x["object"]["path_id"] for x in renderers
                                           if x["enabled"] != x["previous_probe_byte14"]],
            "shader": {"object": obj, "fields": fields, "name": parsed["m_Name"],
                       "passes": passes, "records": records, "forward_programs": disassembly},
            "scope": "serialized configuration, shader records and offline disassembly; no frame observation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-data", required=True, type=Path)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output directory must not already exist")
    args.output.mkdir(parents=True)
    result = probe(args.game_data.resolve(strict=True), args.schema.resolve(strict=True), args.output)
    with (args.output / "mask-route.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"renderers": result["renderer_count"], "passes": len(result["shader"]["passes"]),
                      "byte14_mismatches": len(result["enabled_byte14_mismatches"]),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
