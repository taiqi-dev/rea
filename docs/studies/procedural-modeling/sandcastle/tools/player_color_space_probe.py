"""Bounded Unity 6000.4.10f1 PlayerSettings Release type-tree reader.

Reads one shipped SerializedFile object. This does not load or run game code.
The public TypeTreeDumps JSON supplies field layout, not target values.
"""

import argparse
import importlib.util
import json
import struct
from pathlib import Path


VERSION = "6000.4.10f1"
CLASS_ID = 129
PATH_ID = 1
REFERENCE_COMMIT = "20ba06e00e0625de0e49a502c6868d6cc86d0f0b"
ALIGN_FLAG = 0x4000
PRIMITIVES = {
    "bool": ("B", 1),
    "char": ("B", 1),
    "UInt8": ("B", 1),
    "SInt8": ("b", 1),
    "UInt16": ("H", 2),
    "SInt16": ("h", 2),
    "int": ("i", 4),
    "unsigned int": ("I", 4),
    "SInt64": ("q", 8),
    "UInt64": ("Q", 8),
    "float": ("f", 4),
}


def resource_index(resource):
    source = Path(__file__).resolve().parents[2] / "tools" / "unity22-compute-probe.py"
    spec = importlib.util.spec_from_file_location("unity22_compute_probe", source)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load the shared SerializedFile index reader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resource_index(resource)


def release_node(schema):
    doc = json.loads(schema.read_text(encoding="utf-8"))
    if doc.get("Version") != VERSION or not isinstance(doc.get("Classes"), list):
        raise ValueError("Type tree version or Classes does not match 6000.4.10f1")
    classes = [item for item in doc["Classes"]
               if item.get("TypeID") == CLASS_ID and item.get("Name") == "PlayerSettings"]
    if len(classes) != 1:
        raise ValueError("Expected exactly one PlayerSettings class 129")
    node = classes[0].get("ReleaseRootNode")
    if not isinstance(node, dict) or node.get("TypeName") != "PlayerSettings":
        raise ValueError("Missing PlayerSettings ReleaseRootNode")
    children = node.get("SubNodes")
    if not isinstance(children, list) or len(children) < 36:
        raise ValueError("Incomplete PlayerSettings ReleaseRootNode")
    color = [x for x in children if x.get("Name") == "m_ActiveColorSpace"]
    if len(color) != 1 or color[0].get("TypeName") != "int" or color[0].get("ByteSize") != 4:
        raise ValueError("Missing unique int m_ActiveColorSpace field")
    return node


class ObjectReader:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.fields = []
        self.array_counts = []

    def read(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError(f"Object truncated at +0x{self.pos:x}, need {size} bytes")
        start = self.pos
        self.pos += size
        return self.data[start:self.pos]

    def align(self):
        aligned = (self.pos + 3) & ~3
        padding = self.read(aligned - self.pos)
        if any(padding):
            raise ValueError(f"Nonzero alignment padding before +0x{self.pos:x}")

    def parse(self, node, path=""):
        name = node.get("Name")
        kind = node.get("TypeName")
        children = node.get("SubNodes", [])
        if not isinstance(name, str) or not isinstance(kind, str) or not isinstance(children, list):
            raise ValueError("Malformed type tree node")
        here = f"{path}.{name}" if path else name
        start = self.pos
        if kind == "string":
            if len(children) != 1 or children[0].get("TypeName") != "Array":
                raise ValueError(f"Unexpected string schema: {here}")
            length = struct.unpack("<i", self.read(4))[0]
            if length < 0 or length > len(self.data) - self.pos:
                raise ValueError(f"Invalid string length at {here}")
            value = self.read(length).decode("utf-8", errors="strict")
            if children[0].get("MetaFlag", 0) & ALIGN_FLAG:
                self.align()
        elif kind == "Array":
            if len(children) != 2 or children[0].get("Name") != "size":
                raise ValueError(f"Unexpected array schema: {here}")
            count = struct.unpack("<i", self.read(4))[0]
            if count < 0 or count > (len(self.data) - self.pos):
                raise ValueError(f"Invalid array count at {here}: {count}")
            self.array_counts.append({"path": here, "relative_offset": start, "count": count})
            value = [self.parse(children[1], f"{here}[{i}]") for i in range(count)]
        elif kind in PRIMITIVES:
            fmt, size = PRIMITIVES[kind]
            if node.get("ByteSize") != size or children:
                raise ValueError(f"Unexpected primitive schema: {here}")
            value = struct.unpack("<" + fmt, self.read(size))[0]
            if kind == "bool" and value not in (0, 1):
                raise ValueError(f"Invalid boolean at {here}: {value}")
        elif children:
            value = {child["Name"]: self.parse(child, here) for child in children}
        else:
            raise ValueError(f"Unsupported type tree leaf: {here} ({kind})")
        if node.get("MetaFlag", 0) & ALIGN_FLAG and kind != "string":
            self.align()
        if len(path.split(".")) <= 1 and path == "Base":
            self.fields.append({"name": name, "type": kind,
                                "relative_offset": start, "bytes": self.pos - start,
                                "value": value if isinstance(value, (str, int, float)) else None})
        return value


def probe(resource, schema):
    data, index = resource_index(resource)
    if index["unity"] != VERSION or index["format"] != 22 or index["type_trees"]:
        raise ValueError("Resource is not the expected stripped Unity 6000.4.10f1 format-22 file")
    objects = [x for x in index["objects"]
               if x["class_id"] == CLASS_ID and x["path_id"] == PATH_ID]
    if len(objects) != 1:
        raise ValueError("Expected exactly one PlayerSettings object with pathID 1")
    obj = objects[0]
    node = release_node(schema)
    reader = ObjectReader(data[obj["offset"]:obj["offset"] + obj["bytes"]])
    values = reader.parse(node)
    schema_consumed = reader.pos
    # This exact shipped object has one extra final int32 beyond the public
    # ReleaseRootNode. Report Partial and preserve it; do not assign a field.
    trailing = reader.read(obj["bytes"] - reader.pos)
    if len(trailing) != 4:
        raise ValueError(f"Release type tree consumed {schema_consumed} of {obj['bytes']} bytes; "
                         f"expected the observed 4-byte unmapped tail")
    if values.get("companyName") != "BubblebirdStudio" or values.get("productName") != "Sandcastle":
        raise ValueError("PlayerSettings identity fields do not match target")
    color = values.get("m_ActiveColorSpace")
    if color not in (0, 1):
        raise ValueError(f"Unexpected ColorSpace enum value: {color}")
    wanted = ["companyName", "productName", "defaultScreenWidth", "defaultScreenHeight",
              "defaultScreenWidthWeb", "defaultScreenHeightWeb", "m_StereoRenderingPath",
              "m_ActiveColorSpace", "unsupportedMSAAFallback", "m_SpriteBatchMaxVertexCount",
              "m_SpriteBatchVertexThreshold", "allowedHttpConnections"]
    selected = [field for field in reader.fields if field["name"] in wanted]
    return {
        "resource": str(resource), "schema": str(schema),
        "schema_commit": REFERENCE_COMMIT, "unity": index["unity"],
        "object": obj, "release_tree_top_field_count": len(node["SubNodes"]),
        "schema_status": "Partial: four bytes remain unmapped by ReleaseRootNode",
        "schema_consumed_bytes": schema_consumed,
        "unmapped_tail": {"relative_offset": schema_consumed,
                          "bytes": len(trailing), "hex": trailing.hex(),
                          "uint32": struct.unpack("<I", trailing)[0]},
        "object_bytes_read": reader.pos, "array_counts": reader.array_counts,
        "selected_fields": selected,
        "configured_color_space": {"field": "m_ActiveColorSpace", "value": color,
                                   "name": "Linear" if color == 1 else "Gamma"},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", required=True, type=Path)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    result = probe(args.resource.resolve(strict=True), args.schema.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"color_space": result["configured_color_space"],
                      "schema_consumed_bytes": result["schema_consumed_bytes"],
                      "object_bytes_read": result["object_bytes_read"],
                      "schema_status": result["schema_status"],
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
