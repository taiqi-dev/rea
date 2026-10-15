"""Read selected name/constant-buffer tables in the studied Unity 6 shaders.

Offsets are caller-selected object-relative boundaries, not a complete Shader
schema parser. The observed tables use aligned strings and 16-byte numeric
parameters. Unknown structs or malformed bounds stop the read explicitly.
No target code is executed and no digests are computed.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import struct


class Reader:
    def __init__(self, data, pos):
        self.data, self.pos = data, pos

    def read(self, count):
        if self.pos < 0 or count < 0 or count > len(self.data) - self.pos:
            raise ValueError("Selected shader table exceeds object")
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result

    def uint(self):
        return struct.unpack("<I", self.read(4))[0]

    def count(self, minimum_bytes):
        count = self.uint()
        if count > (len(self.data) - self.pos) // minimum_bytes:
            raise ValueError("Table count exceeds remaining object bytes")
        return count

    def align(self):
        self.read((-self.pos) % 4)

    def string(self):
        size = self.uint()
        text = self.read(size).decode("utf-8")
        self.align()
        return text


def read_tables(raw, names_offset, buffers_offset, textures_offset=None):
    names_reader = Reader(raw, names_offset)
    names = {}
    for _ in range(names_reader.count(8)):
        name = names_reader.string()
        index = names_reader.uint()
        if index in names:
            raise ValueError("Duplicate name index")
        names[index] = name

    reader = Reader(raw, buffers_offset)

    def name_index():
        index = reader.uint()
        if index not in names:
            raise ValueError(f"Unknown name index {index}")
        return names[index]

    def parameter():
        offset = reader.pos
        name = name_index()
        byte_offset, array_size = reader.uint(), reader.uint()
        data_type, dimension = struct.unpack("<BB", reader.read(2))
        reader.align()
        if data_type > 4 or not 1 <= dimension <= 4 or byte_offset % 4:
            raise ValueError("Unsupported numeric parameter record")
        return {"object_offset": offset, "name": name,
                "byte_offset": byte_offset, "register": byte_offset // 16,
                "component": (byte_offset % 16) // 4,
                "array_size": array_size, "type": data_type,
                "dimension": dimension}

    textures = []
    if textures_offset is not None:
        buffers_reader = reader
        reader = Reader(raw, textures_offset)
        for _ in range(reader.count(16)):
            offset = reader.pos
            name = name_index()
            slot, sampler = reader.uint(), reader.uint()
            multisampled, dimension = struct.unpack("<BB", reader.read(2))
            reader.align()
            if multisampled not in (0, 1) or not 1 <= dimension <= 6:
                raise ValueError("Unsupported texture parameter record")
            textures.append({"object_offset": offset, "name": name,
                             "slot": slot, "sampler": sampler,
                             "multisampled": bool(multisampled),
                             "dimension": dimension})
        reader = buffers_reader

    buffers = []
    for _ in range(reader.count(20)):
        offset = reader.pos
        name = name_index()
        matrices = [parameter() for _ in range(reader.count(16))]
        vectors = [parameter() for _ in range(reader.count(16))]
        if reader.uint() != 0:
            raise ValueError("Struct parameters are outside this reader's scope")
        size = reader.uint()
        partial = reader.uint()
        if partial not in (0, 1):
            raise ValueError("Unexpected partial-CB/alignment value")
        if any(p["byte_offset"] >= size for p in matrices + vectors):
            raise ValueError("Parameter offset exceeds declared constant buffer")
        buffers.append({"object_offset": offset, "name": name, "bytes": size,
                        "partial": bool(partial), "matrices": matrices,
                        "vectors": vectors})
    bindings = []
    for _ in range(reader.count(12)):
        bindings.append({"name": name_index(), "slot": reader.uint(),
                         "array_size": reader.uint()})
    if set(b["name"] for b in buffers) != set(b["name"] for b in bindings):
        raise ValueError("Selected constant-buffer names and bindings differ")
    return {"names_offset": names_offset, "names_end": names_reader.pos,
            "names": names, "buffers_offset": buffers_offset,
            "buffers": buffers, "bindings": bindings, "table_end": reader.pos,
            "textures_offset": textures_offset, "textures": textures,
            "scope": "selected tables only; not a full Shader or runtime parser"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource", type=Path)
    parser.add_argument("--object-id", required=True, type=int)
    parser.add_argument("--names-offset", required=True, type=lambda x: int(x, 0))
    parser.add_argument("--buffers-offset", required=True, type=lambda x: int(x, 0))
    parser.add_argument("--textures-offset", type=lambda x: int(x, 0))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[2] / "tools/unity22-compute-probe.py"
    spec = importlib.util.spec_from_file_location("unity_compute_probe", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    data, index = helper.resource_index(args.resource.resolve(strict=True))
    matches = [x for x in index["objects"]
               if x["path_id"] == args.object_id and x["class_id"] == 48]
    if len(matches) != 1:
        raise ValueError("Expected exactly one selected Shader object")
    item = matches[0]
    raw = data[item["offset"]:item["offset"] + item["bytes"]]
    result = read_tables(raw, args.names_offset, args.buffers_offset,
                         args.textures_offset)
    result.update({"resource": str(args.resource.resolve()), "object": item})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"object": args.object_id, "buffers": len(result["buffers"]),
                      "table_end": result["table_end"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
