"""Find bounded PE pointer and RIP-displacement candidates for Unity field names.

Static byte scan only. A RIP hit is a candidate until its instruction is
disassembled; arbitrary four-byte windows are not automatically code xrefs.
"""

import argparse
import array
import json
import struct
import sys
from pathlib import Path


NAMES = (
    "allowedHttpConnections",
    "d3d12DeviceFilterListAsset",
    "androidVulkanDeviceFilterListAsset",
    "m_ActiveColorSpace",
    "qualitySettingsNames",
)


def pe_layout(data):
    if sys.byteorder != "little":
        raise ValueError("This reader requires a little-endian host")
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise ValueError("Not a PE file")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Missing PE header")
    machine, sections, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    if machine != 0x8664 or pe + 24 + optional_size + sections * 40 > len(data):
        raise ValueError("Expected bounded x64 PE section table")
    if struct.unpack_from("<H", data, pe + 24)[0] != 0x20B:
        raise ValueError("Expected PE32+ optional header")
    image_base = struct.unpack_from("<Q", data, pe + 24 + 24)[0]
    layout = []
    for i in range(sections):
        at = pe + 24 + optional_size + i * 40
        name, vsize, rva, size, offset, _, _, _, _, flags = struct.unpack_from(
            "<8sIIIIIIHHI", data, at)
        if offset > len(data) or size > len(data) - offset:
            raise ValueError(f"Section {i} outside file")
        layout.append({"name": name.split(b"\0", 1)[0].decode("ascii"),
                       "rva": rva, "virtual_size": vsize,
                       "size": size, "offset": offset, "executable": bool(flags & 0x20000000)})
    return image_base, layout


def read_names(data, image_base, sections):
    names = {}
    for name in NAMES:
        needle = name.encode("ascii") + b"\0"
        first = data.find(needle)
        if first < 0 or data.find(needle, first + 1) >= 0:
            raise ValueError(f"Expected one NUL-terminated occurrence of {name}")
        sec = next((s for s in sections
                    if s["offset"] <= first < s["offset"] + s["size"]), None)
        if sec is None:
            raise ValueError(f"Field name outside a PE section: {name}")
        rva = sec["rva"] + first - sec["offset"]
        names[name] = {"file_offset": first, "section": sec["name"],
                       "rva": rva, "va": image_base + rva}
    return names


def find_all(data, needle, limit=100):
    offsets = []
    position = 0
    while True:
        position = data.find(needle, position)
        if position < 0:
            break
        offsets.append(position)
        if len(offsets) > limit:
            raise ValueError("Too many pointer candidates")
        position += 1
    return offsets


def rip_candidates(data, sections, names):
    targets = {info["rva"]: name for name, info in names.items()}
    hits = {name: [] for name in names}
    windows = 0
    for sec in sections:
        if not sec["executable"]:
            continue
        body = data[sec["offset"]:sec["offset"] + sec["size"]]
        for alignment in range(4):
            usable = (len(body) - alignment) & ~3
            if usable < 4:
                continue
            words = array.array("I")
            words.frombytes(body[alignment:alignment + usable])
            if words.itemsize != 4:
                raise ValueError("Platform unsigned-int size is not four bytes")
            for ordinal, raw in enumerate(words):
                relative = alignment + ordinal * 4
                displacement = raw if raw < 0x80000000 else raw - 0x100000000
                dest = sec["rva"] + relative + 4 + displacement
                name = targets.get(dest)
                if name is not None:
                    at = sec["offset"] + relative
                    hits[name].append({"displacement_file_offset": at,
                                       "displacement_rva": sec["rva"] + relative,
                                       "before_hex": data[max(sec["offset"], at - 8):at].hex(),
                                       "after_hex": data[at + 4:at + 12].hex()})
            windows += len(words)
    return windows, hits


def probe(binary):
    data = binary.read_bytes()
    image_base, sections = pe_layout(data)
    names = read_names(data, image_base, sections)
    for name, info in names.items():
        info["absolute_pointer_file_offsets"] = find_all(data, struct.pack("<Q", info["va"]))
        info["rva_literal_file_offsets"] = find_all(data, struct.pack("<I", info["rva"]))
    windows, hits = rip_candidates(data, sections, names)
    return {"binary": str(binary), "file_bytes": len(data), "image_base": image_base,
            "executable_sections": [s for s in sections if s["executable"]],
            "candidate_rip_windows_examined": windows, "field_names": names,
            "rip_displacement_candidates": hits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    result = probe(args.binary.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"windows": result["candidate_rip_windows_examined"],
                      "hits": {k: len(v) for k, v in result["rip_displacement_candidates"].items()},
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
