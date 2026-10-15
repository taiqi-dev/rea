"""Compare saved SUMMERHOUSE material properties with shipped shader input names.

Reads the seven selected SerializedFiles and disassembles Shader622 forward
fragment variants. Does not execute target code, render, or compute digests.
"""

import argparse
import collections
import json
import re
import struct
from pathlib import Path

from mask_render_route_probe import ROOT, VERSION, load, program_records, program_dxbc


FILES = ["globalgamemanagers.assets", "resources.assets"] + [f"sharedassets{i}.assets" for i in range(5)]
NAMES = {"_GlobalMaskTexture", "_GlobalMaskTiling", "_GlobalMaskOffset",
         "_MinMaskPosZ", "_MaxMaskPosZ", "_MaskingDepthCutoff",
         "_MinMaskZ", "_MaxMaskZ", "_MaskingTextureOffset"}


def parameter_record(decoded, record):
    """Project the selected shader's observed packed parameter profile, completely.

    Header words are retained without assigning unsupported semantics. This is
    deliberately not a general Unity shader format parser.
    """
    body = decoded[record["offset"]:record["offset"] + record["bytes"]]
    at = 0

    def integers(count):
        nonlocal at
        if count > (len(body) - at) // 4:
            raise ValueError("Truncated parameter record")
        values = struct.unpack_from("<" + "I" * count, body, at)
        at += 4 * count
        return values

    def string():
        nonlocal at
        length = integers(1)[0]
        if not 0 < length <= len(body) - at:
            raise ValueError("Invalid parameter name length")
        raw = body[at:at + length]
        if any(c < 32 or c >= 127 for c in raw):
            raise ValueError("Expected an ASCII parameter name")
        end = at + length
        at = (end + 3) & ~3
        if at > len(body) or any(body[end:at]):
            raise ValueError("Invalid parameter name padding")
        return raw.decode("ascii")

    header = integers(6)
    if header[0] != 202012090 or header[2:] != (0, 0, 0, 0):
        raise ValueError("Unexpected selected parameter record header")
    buffers = []
    while at + 5 <= len(body) and body[at + 4:at + 5] in (b"$", b"U", b"L"):
        buffer = {"name": string(), "bytes": integers(1)[0]}
        for kind in ("vectors", "matrices"):
            count = integers(1)[0]
            if count > (len(body) - at) // 32:
                raise ValueError("Invalid parameter member count")
            members = []
            for _ in range(count):
                name = string()
                fields = integers(6)
                if fields[5] >= buffer["bytes"]:
                    raise ValueError("Parameter offset exceeds its constant buffer")
                members.append({"name": name, "type": fields[0], "rows": fields[1],
                                "dimension": fields[2], "array_size": fields[3],
                                "unresolved_word": fields[4], "byte_offset": fields[5]})
            buffer[kind] = members
        buffers.append(buffer)
    count = integers(1)[0]
    if count > (len(body) - at) // 16:
        raise ValueError("Invalid parameter resource count")
    resources = []
    for _ in range(count):
        name, tag = string(), integers(1)[0]
        if tag == 0:
            index, sampler, dimension = integers(3)
            resources.append({"name": name, "tag": tag, "index": index,
                              "sampler": sampler, "dimension_word": dimension})
        elif tag == 1:
            index, word = integers(2)
            resources.append({"name": name, "tag": tag, "index": index, "unresolved_word": word})
        else:
            raise ValueError("Unsupported selected parameter resource tag")
    if at != len(body):
        raise ValueError("Parameter record not completely consumed")
    return {"record": record, "header_words": header, "constant_buffers": buffers,
            "resources": resources, "consumed_bytes": at}


def probe(game_data, schema_path, output):
    unity = load("unity_input_index", ROOT / "tools/unity22-compute-probe.py")
    obj = load("input_object_reader", ROOT / "sandcastle/tools/player_color_space_probe.py")
    shader = load("input_lz4", ROOT / "tools/unity22-shader-probe.py")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("Version") != VERSION:
        raise ValueError("Expected the exact 2023.2.22f1 schema")
    classes = {c["TypeID"]: c["ReleaseRootNode"] for c in schema["Classes"]}
    shader_rows, material_rows, files = [], [], []
    selected = None
    for name in FILES:
        data, index = unity.resource_index(game_data / name, include_externals=True)
        if (index["unity"], index["format"], index["type_trees"]) != (VERSION, 22, False):
            raise ValueError(f"Unexpected SerializedFile profile: {name}")
        counts = collections.Counter()
        for item in index["objects"]:
            if item["class_id"] not in (21, 48):
                continue
            reader = obj.ObjectReader(data[item["offset"]:item["offset"] + item["bytes"]])
            value = reader.parse(classes[item["class_id"]])
            if reader.pos != item["bytes"]:
                raise ValueError(f"Object not fully consumed: {name}, {item['path_id']}")
            counts[item["class_id"]] += 1
            if item["class_id"] == 21:
                saved = {kind: [p for p in group["Array"] if p["first"] in NAMES]
                         for kind, group in value["m_SavedProperties"].items()}
                ref = value["m_Shader"]
                external = None
                if ref["m_FileID"]:
                    matches = [x["path"] for x in index["externals"] if x["file_id"] == ref["m_FileID"]]
                    if len(matches) != 1:
                        raise ValueError("Material Shader external fileID does not resolve")
                    external = matches[0]
                material_rows.append({"resource": name, "object": item, "name": value["m_Name"],
                                      "shader": ref, "shader_resource": external or name,
                                      "keywords": value["m_ValidKeywords"]["Array"],
                                      "mask_saved_properties": saved})
            else:
                parsed = value["m_ParsedForm"]
                passes = []
                for si, sub in enumerate(parsed["m_SubShaders"]["Array"]):
                    for pi, p in enumerate(sub["m_Passes"]["Array"]):
                        names = [x["first"] for x in p["m_NameIndices"]["Array"]]
                        passes.append({"subshader": si, "pass": pi, "name": p["m_State"]["m_Name"],
                                       "common_name_indices": names, "common_mask_names": sorted(set(names) & NAMES)})
                shader_rows.append({"resource": name, "object": item, "name": parsed["m_Name"],
                                    "passes": passes})
                if name == "sharedassets0.assets" and item["path_id"] == 622:
                    if selected is not None:
                        raise ValueError("Duplicate selected Shader622")
                    selected = value
        files.append({"name": name, "bytes": len(data), "objects": index["object_count"],
                      "materials_complete": counts[21], "shaders_complete": counts[48]})
    if selected is None:
        raise ValueError("Missing selected Shader622")
    parsed = selected["m_ParsedForm"]
    if parsed["m_Name"] != "Shader Graphs/LitColorTriplanarNormalAnimatedShimmer":
        raise ValueError("Unexpected selected shader identity")
    decoded, records = program_records(selected, shader)
    forward = parsed["m_SubShaders"]["Array"][0]["m_Passes"]["Array"][0]
    keywords = parsed["m_KeywordNames"]["Array"]
    fragment = forward["progFragment"]
    programs = []
    for group, parameters in zip(fragment["m_PlayerSubPrograms"]["Array"],
                                 fragment["m_ParameterBlobIndices"]["Array"], strict=True):
        programs.extend(zip(group["Array"], parameters["Array"], strict=True))
    fragments = []
    for p, parameter_index in programs:
        blob = p["m_BlobIndex"]
        if not 0 <= blob < len(records):
            raise ValueError("Program blob index exceeds section table")
        if not 0 <= parameter_index < len(records):
            raise ValueError("Parameter blob index exceeds section table")
        parameters = parameter_record(decoded, records[parameter_index])
        at, code = program_dxbc(decoded, records[blob])
        text = unity.disassemble(code)
        if "ps_4_0" not in text:
            raise ValueError("Expected the selected pixel shader model")
        filename = f"shader622-fragment-{blob}.asm.txt"
        with (output / filename).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        fragments.append({"blob_index": blob, "keywords": [keywords[i] for i in p["m_KeywordIndices"]["Array"]],
                          "record": records[blob], "parameters": parameters,
                          "dxbc_record_offset": at, "dxbc_bytes": len(code),
                          "resource_declarations": [line.strip() for line in text.splitlines() if "dcl_resource_" in line],
                          "sample_instructions": len(re.findall(r"\bsample(?:_\w+)?\s", text)),
                          "discard_instructions": len(re.findall(r"\bdiscard_\w+\s", text)),
                          "disassembly": filename})
    shader_map = {(s["resource"], s["object"]["path_id"]): s for s in shader_rows}
    vertices = []
    vertex = forward["progVertex"]
    for group, parameters in zip(vertex["m_PlayerSubPrograms"]["Array"],
                                 vertex["m_ParameterBlobIndices"]["Array"], strict=True):
        for p, parameter_index in zip(group["Array"], parameters["Array"], strict=True):
            blob = p["m_BlobIndex"]
            if not (0 <= blob < len(records) and 0 <= parameter_index < len(records)):
                raise ValueError("Vertex blob index exceeds section table")
            at, code = program_dxbc(decoded, records[blob])
            text = unity.disassemble(code)
            if "vs_4_0" not in text:
                raise ValueError("Expected the selected vertex shader model")
            filename = f"shader622-vertex-{blob}.asm.txt"
            with (output / filename).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
            vertices.append({"blob_index": blob, "record": records[blob],
                             "keywords": [keywords[i] for i in p["m_KeywordIndices"]["Array"]],
                             "parameters": parameter_record(decoded, records[parameter_index]),
                             "dxbc_record_offset": at, "dxbc_bytes": len(code), "disassembly": filename})
    for material in material_rows:
        ref = material["shader"]
        match = shader_map.get((material["shader_resource"], ref["m_PathID"]))
        material["resolved_shader_name"] = match["name"] if match else None
        material["shader_common_mask_names"] = sorted({n for p in match["passes"] for n in p["common_mask_names"]}) if match else None
    return {"game_data": str(game_data), "schema": str(schema_path), "version": VERSION,
            "files": files, "mask_names_examined": sorted(NAMES),
            "materials": material_rows, "shaders": shader_rows,
            "selected_shader": {"name": parsed["m_Name"], "program_records": len(records),
                                "decoded_bytes": len(decoded), "fragment_variants": fragments,
                                "vertex_variants": vertices,
                                "forward_common_name_indices": forward["m_NameIndices"]["Array"]},
            "scope": "seven resource common name tables plus Shader622 forward parameter records and fragments; no runtime observation"}


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
    with (args.output / "material-inputs.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"files": len(result["files"]), "materials": len(result["materials"]),
                      "shaders": len(result["shaders"]),
                      "fragment_variants": len(result["selected_shader"]["fragment_variants"]),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
