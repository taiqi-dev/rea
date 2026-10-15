"""Check selected VoxelWorld property descriptors against native config gates.

Reads PE bytes and six already decoded Zen name tables. Does not load target
code, invoke Unreal, inspect user saves, or compute content digests.
"""

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sandcastle/tools"))
from player_callback_table_probe import va_to_file
from unity_player_xref_probe import pe_layout


PROPERTIES = {"MaterialConfig": (0x14719DC40, 0x47D),
              "RenderType": (0x14719E410, 0x57C)}
PACKAGES = ["mainlevel-zen.json", "character-zen.json", "saveexample-zen.json",
            "orespawner-zen.json", "explosion-zen.json", "digging/dynamite-zen.json"]


def probe(binary, metadata_root):
    data = binary.read_bytes()
    base, sections = pe_layout(data)
    if base != 0x140000000 or len(data) != 145180160:
        raise ValueError("Unexpected selected Shipping PE profile")

    def read(va, count):
        at = va_to_file(base, sections, va)
        end = va_to_file(base, sections, va + count - 1)
        if end != at + count - 1 or at + count > len(data):
            raise ValueError("Non-contiguous/out-of-file selected PE range")
        return data[at:at + count]

    anchors = {
        0x14131DDAA: "49 0b 76 10",       # OR constructor flags with params+0x10.
        0x14131DDB1: "48 89 77 38",       # Property flags stored at FProperty+0x38.
        0x14131DDD0: "41 0f b7 4e 32",    # Params+0x32 -> property member offset.
        0x141309470: "49 8b 7d 38",       # Load property flags.
        0x141309474: "48 0f ba e7 0e",    # Test bit14, mask0x4000.
        0x141309479: "0f 83 c3 06 00 00", # Clear bit -> skip to next property.
        0x141309B42: "4d 8b 6d 48",       # Next linked property.
        0x141309B57: "0f 85 13 f9 ff ff", # Continue at flag test.
    }
    for va, expected in anchors.items():
        encoded = bytes.fromhex(expected)
        if read(va, len(encoded)) != encoded:
            raise ValueError(f"Native gate changed at {va:#x}")
    enum_flags = read(0x14127DA55, 10)
    if enum_flags[:2] != b"\x49\xb9":
        raise ValueError("Enum property constructor flag source changed")
    extra = struct.unpack_from("<Q", enum_flags, 2)[0]
    if extra != 0x8000000000000:
        raise ValueError("Unexpected enum constructor extra flags")
    rows = []
    for name, (va, member_offset) in PROPERTIES.items():
        raw = read(va, 64)
        name_va, _, flags = struct.unpack_from("<QQQ", raw)
        expected_name = name.encode("ascii") + b"\0"
        if read(name_va, len(expected_name)) != expected_name:
            raise ValueError("Selected descriptor name changed")
        array_dim, offset = struct.unpack_from("<HH", raw, 48)
        if flags != 0x10000000000005 or array_dim != 1 or offset != member_offset:
            raise ValueError("Selected descriptor flags/member offset changed")
        constructed = flags | extra
        rows.append({"name": name, "descriptor_va": hex(va),
                     "descriptor_file_offset": va_to_file(base, sections, va),
                     "property_flags": hex(flags), "enum_extra_flags": hex(extra),
                     "flags_at_constructor_store": hex(constructed),
                     "array_dim": array_dim, "member_offset": hex(offset),
                     "config_bit14": bool(constructed & 0x4000),
                     "global_config_bit18": bool(constructed & 0x40000),
                     "blueprint_readonly_bit4": bool(constructed & 0x10)})
    packages = []
    needles = ["MaterialConfig", "RenderType", "RecreateRender"]
    for relative in PACKAGES:
        path = metadata_root / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        names = value["names"]
        if not isinstance(names, list) or not all(isinstance(x, str) for x in names):
            raise ValueError("Invalid decoded Zen names")
        packages.append({"metadata": str(path), "package": value["package_name"],
                         "name_count": len(names),
                         "substring_hits": [x for x in names if any(n.casefold() in x.casefold() for n in needles)]})
    return {"binary": str(binary), "binary_bytes": len(data), "properties": rows,
            "verified_instruction_bytes": {hex(va): value for va, value in anchors.items()},
            "packages_examined": packages,
            "scope": "selected constructor flags and ordinary LoadConfig property loop; later flag mutation/custom writers are not excluded",
            "runtime": "Not Run"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--metadata-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    result = probe(args.binary.resolve(strict=True), args.metadata_root.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"properties": len(result["properties"]),
                      "packages": len(result["packages_examined"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
