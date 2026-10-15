"""Read small IL2CPP v39 enum constants from the field-default table.

Only the single-byte signed form is accepted. Larger encodings remain unknown
instead of silently interpreting them as a fixed-width integer.
"""

import argparse
import struct
from pathlib import Path

from metadata39 import Metadata39


def main():
    args = argparse.ArgumentParser()
    args.add_argument("metadata", type=Path)
    args.add_argument("type_name")
    args.add_argument("--image", default="Assembly-CSharp.dll")
    args.add_argument("--type-index", type=int, help="select a duplicate nested type name")
    parsed = args.parse_args()

    metadata = Metadata39(parsed.metadata)
    image = next(i for i in metadata.images() if i["name"] == parsed.image)
    matches = [
        t for t in metadata.types(image)
        if t["name"] == parsed.type_name
        and (parsed.type_index is None or t["index"] == parsed.type_index)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one {parsed.type_name!r} type, got indices "
            f"{[t['index'] for t in matches]}; pass --type-index"
        )

    table_offset, table_size, table_count = metadata.sections["field_defaults"]
    if table_size != table_count * 10:
        raise ValueError("unexpected field-default record size")
    data_offset, data_size, _ = metadata.sections["default_data"]
    defaults = {}
    for i in range(table_count):
        field_index, type_index, relative_data = struct.unpack_from(
            "<IHi", metadata.data, table_offset + i * 10
        )
        if not (0 <= relative_data < data_size):
            raise ValueError(f"field {field_index} default points outside data")
        defaults[field_index] = (type_index, relative_data)

    for field in metadata.fields(matches[0]):
        if field["name"] == "value__":
            continue
        if field["index"] not in defaults:
            print(f"{field['name']}: unknown (no field default)")
            continue
        _, position = defaults[field["index"]]
        first = metadata.data[data_offset + position]
        # Values 0..63 have the one-byte signed encoding n -> n*2.
        value = str(first // 2) if first < 0x80 and first % 2 == 0 else "unknown (multi-byte)"
        print(f"{field['name']}: {value}")


if __name__ == "__main__":
    main()
