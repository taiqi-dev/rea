"""Read names, imports and export ranges in this study's UE5 Zen packages.

This indexes serialized objects, not Blueprint execution. The caller supplies
the exact uncompressed ScriptObjects chunk and a package decoded separately.
"""

import argparse
import json
from pathlib import Path
import struct


def name_batch(data, start):
    count = struct.unpack_from("<I", data, start)[0]
    if not count:
        return [], start + 4
    size = struct.unpack_from("<I", data, start + 4)[0]
    headers = start + 16 + count * 8
    position = headers + count * 2
    end = position + size
    if end > len(data):
        raise ValueError("Name batch outside input")
    names = []
    for index in range(count):
        a, b = data[headers + 2 * index:headers + 2 * index + 2]
        length = ((a & 127) << 8) | b
        width = 2 if a & 128 else 1
        raw = data[position:position + length * width]
        position += length * width
        names.append(raw.decode("utf-16-le" if width == 2 else "utf-8"))
    if position != end:
        raise ValueError("Name byte count mismatch")
    return names, end


def scripts(data):
    names, position = name_batch(data, 0)
    count = struct.unpack_from("<I", data, position)[0]
    position += 4
    if position + count * 32 != len(data):
        raise ValueError("Unexpected ScriptObjects chunk length")
    entries = {}
    for index in range(count):
        name, number, key, outer, cdo = struct.unpack_from("<IIQQQ", data, position + index * 32)
        entries[key] = {"name": names[name & 0x3FFFFFFF], "number": number,
                        "outer": outer, "cdo_class": cdo}

    def full_name(key, visited=None):
        if key == 0xFFFFFFFFFFFFFFFF:
            return ""
        if key not in entries:
            return f"unresolved:{key:#x}"
        visited = set() if visited is None else visited
        if key in visited:
            raise ValueError("Script object outer cycle")
        visited.add(key)
        row = entries[key]
        outer = full_name(row["outer"], visited)
        return (outer + "." if outer else "") + row["name"]

    return {key: full_name(key) for key in entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--script-objects", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = args.package.read_bytes()
    versioning, header_size, package_name, package_number, flags, cooked_header, hashes_at, imports_at, exports_at, bundles_at, dependencies_at, dependency_entries_at, imported_names_at = struct.unpack_from("<13I", data)
    if versioning or not (52 <= hashes_at <= imports_at <= exports_at <= bundles_at <= header_size <= len(data)):
        raise ValueError("Expected unversioned UE5.3+ Zen summary")
    names, names_end = name_batch(data, 52)
    imported_names, imported_names_end = name_batch(data, imported_names_at)
    if imported_names_end + len(imported_names) * 4 != header_size:
        raise ValueError("Unexpected imported package name number table")
    imported_numbers = struct.unpack_from("<" + "I" * len(imported_names), data, imported_names_end)
    if (imports_at - hashes_at) % 8:
        raise ValueError("Invalid imported public export identifier table")
    imported_hashes = struct.unpack_from("<" + "Q" * ((imports_at - hashes_at) // 8), data, hashes_at)
    global_scripts = scripts(args.script_objects.read_bytes())
    imports = []
    for offset in range(imports_at, exports_at, 8):
        value = struct.unpack_from("<Q", data, offset)[0]
        row = {"index": len(imports), "package_index": -len(imports) - 1,
               "value": hex(value), "kind": value >> 62,
               "script_object": global_scripts.get(value)}
        if value >> 62 == 2:
            package_index, hash_index = (value & ((1 << 62) - 1)) >> 32, value & 0xFFFFFFFF
            row.update({"imported_package_index": package_index,
                        "external_package": imported_names[package_index],
                        "external_package_number": imported_numbers[package_index],
                        "public_export_hash_index": hash_index,
                        "stored_public_export_hash": hex(imported_hashes[hash_index])})
        imports.append(row)
    exports = []
    if (bundles_at - exports_at) % 72:
        raise ValueError("Invalid export map size")
    for offset in range(exports_at, bundles_at, 72):
        serial, size, name, number, outer, cls, parent, template, public_hash, object_flags, filter_flags = struct.unpack_from("<QQIIQQQQQIB", data, offset)
        start, end = header_size + serial, header_size + serial + size
        if end > len(data) or name >> 30:
            raise ValueError("Unexpected export data range/name scope")
        exports.append({"index": len(exports), "package_index": len(exports) + 1,
                        "name": names[name], "number": number, "data_offset": start,
                        "size": size, "outer": hex(outer), "class_index": hex(cls),
                        "class_script": global_scripts.get(cls), "super": hex(parent),
                        "template": hex(template), "flags": hex(object_flags),
                        "stored_public_export_hash": hex(public_hash)})
    result = {"package": str(args.package.resolve()), "bytes": len(data),
              "package_name": names[package_name & 0x3FFFFFFF], "header_size": header_size,
              "cooked_header_size": cooked_header, "names_end": names_end,
              "names": names, "imports": imports, "exports": exports,
              "limitations": ["No property or bytecode deserialization", "External package identity and stored export identifier exposed; member resolution still requires matching that package export table", "Name hashes and public export hashes not recomputed"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"names": len(names), "imports": len(imports), "exports": len(exports), "output": str(args.output)}))


if __name__ == "__main__":
    main()
