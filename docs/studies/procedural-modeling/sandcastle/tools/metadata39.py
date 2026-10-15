"""Read a narrow, validated subset of Unity IL2CPP metadata version 39.

This is an offline name/index reader, not an IL2CPP code decompiler. It does not
calculate a digest or execute the target. Its section and record layouts follow
the v39 metadata structures in Il2CppDumper's Unity 6 work; each decoded index
is checked against the source file before it is reported.
"""

import argparse
import json
import re
import struct
from pathlib import Path


SECTIONS = (
    "string_lit", "string_lit_data", "strings", "events", "properties",
    "methods", "parameter_defaults", "field_defaults", "default_data",
    "field_marshaled", "parameters", "fields", "generic_parameters",
    "generic_constraints", "generic_containers", "nested_types", "interfaces",
    "vtable", "interface_offsets", "types", "images", "assemblies",
    "field_refs", "referenced_assemblies", "attribute_data", "attribute_ranges",
    "unresolved_parameter_types", "unresolved_parameter_ranges",
    "windows_runtime_type_names", "windows_runtime_strings", "exported_types",
)


class Metadata39:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        magic, version = struct.unpack_from("<II", self.data)
        if (magic, version) != (0xFAB11BAF, 39):
            raise ValueError(f"expected IL2CPP metadata v39, got {magic:#x}, {version}")
        self.sections = {}
        for i, name in enumerate(SECTIONS):
            offset, size, count = struct.unpack_from("<III", self.data, 8 + 12 * i)
            if offset + size > len(self.data):
                raise ValueError(f"out-of-file section {name}: {offset:#x}+{size}")
            self.sections[name] = (offset, size, count)
        if self.sections["string_lit"][0] != 380:
            raise ValueError("unexpected v39 header length")
        self._check_stride("types", 76)
        self._check_stride("methods", 30)
        self._check_stride("fields", 10)
        self._check_stride("images", 36)

    def _check_stride(self, name, stride):
        _, size, count = self.sections[name]
        if size != count * stride:
            raise ValueError(f"unexpected {name} stride: {size}/{count}")

    def name(self, index):
        offset, size, _ = self.sections["strings"]
        if index >= size:
            raise ValueError(f"string index {index:#x} outside string heap")
        start = offset + index
        end = self.data.find(b"\0", start, offset + size)
        if end < 0:
            raise ValueError(f"unterminated string index {index:#x}")
        return self.data[start:end].decode("utf-8", errors="replace")

    def images(self):
        offset, _, count = self.sections["images"]
        for i in range(count):
            pos = offset + 36 * i
            name_index, assembly_index = struct.unpack_from("<Ii", self.data, pos)
            # Metadata v39 uses compact 16-bit image type ranges here.
            type_start, type_count = struct.unpack_from("<HH", self.data, pos + 8)
            if type_start < 0 or type_start + type_count > self.sections["types"][2]:
                raise ValueError(f"image {i} has invalid type range")
            yield {"index": i, "name": self.name(name_index), "assembly": assembly_index,
                   "type_start": type_start, "type_count": type_count, "offset": pos}

    def types(self, image):
        offset, _, _ = self.sections["types"]
        for i in range(image["type_start"], image["type_start"] + image["type_count"]):
            pos = offset + 76 * i
            name_index, namespace_index = struct.unpack_from("<II", self.data, pos)
            starts = struct.unpack_from("<8i", self.data, pos + 20)
            counts = struct.unpack_from("<8H", self.data, pos + 52)
            field_start, method_start = starts[:2]
            method_count, _, field_count = counts[:3]
            if ((field_count and (field_start < 0 or field_start + field_count > self.sections["fields"][2]))
                    or (method_count and (method_start < 0 or method_start + method_count > self.sections["methods"][2]))):
                raise ValueError(f"type {i} has invalid member range")
            yield {"index": i, "name": self.name(name_index), "namespace": self.name(namespace_index),
                   "offset": pos, "field_start": field_start, "field_count": field_count,
                   "method_start": method_start, "method_count": method_count,
                   "token": struct.unpack_from("<I", self.data, pos + 72)[0]}

    def fields(self, type_info):
        offset, _, _ = self.sections["fields"]
        for i in range(type_info["field_start"], type_info["field_start"] + type_info["field_count"]):
            pos = offset + 10 * i
            name_index, type_index, token = struct.unpack_from("<IHI", self.data, pos)
            yield {"index": i, "name": self.name(name_index), "type_index": type_index,
                   "token": token, "offset": pos}

    def methods(self, type_info):
        offset, _, _ = self.sections["methods"]
        for i in range(type_info["method_start"], type_info["method_start"] + type_info["method_count"]):
            pos = offset + 30 * i
            name_index = struct.unpack_from("<I", self.data, pos)[0]
            declaring_type, return_type = struct.unpack_from("<HH", self.data, pos + 4)
            if declaring_type != type_info["index"]:
                raise ValueError(f"method {i} declares unexpected type {declaring_type}")
            parameter_start = struct.unpack_from("<i", self.data, pos + 12)[0]
            token = struct.unpack_from("<I", self.data, pos + 18)[0]
            parameter_count = struct.unpack_from("<H", self.data, pos + 28)[0]
            parameter_offset, _, total_parameters = self.sections["parameters"]
            if parameter_count and (parameter_start < 0 or parameter_start + parameter_count > total_parameters):
                raise ValueError(f"method {i} has invalid parameter range")
            parameters = []
            for index in range(parameter_start, parameter_start + parameter_count):
                param_pos = parameter_offset + 10 * index
                param_name, param_token, param_type = struct.unpack_from("<IIH", self.data, param_pos)
                parameters.append({"index": index, "name": self.name(param_name),
                                   "token": param_token, "type_index": param_type, "offset": param_pos})
            yield {"index": i, "name": self.name(name_index), "token": token,
                   "parameter_count": parameter_count, "parameters": parameters,
                   "return_type_index": return_type, "offset": pos}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--image", default="Assembly-CSharp.dll")
    parser.add_argument("--pattern", default="water|sand|dig|excavat|terrain|voxel|mesh|fluid|height|sculpt|erosion|tide|wave|build|castle|shore|wet|moist|stamp|paint|deposit|sediment|surface", help="case-insensitive type name pattern")
    parser.add_argument("--all-types", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    metadata = Metadata39(args.metadata)
    image = next((i for i in metadata.images() if i["name"] == args.image), None)
    if image is None:
        raise ValueError(f"image {args.image!r} not found")
    pattern = re.compile(args.pattern, re.I)
    types = []
    for type_info in metadata.types(image):
        if args.all_types or pattern.search(type_info["name"]):
            type_info["fields"] = list(metadata.fields(type_info))
            type_info["methods"] = list(metadata.methods(type_info))
            types.append(type_info)
    result = {"source": str(args.metadata), "metadata_version": 39,
              "source_bytes": len(metadata.data), "image": image,
              "matched_type_count": len(types), "types": types}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {len(types)} types to {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
