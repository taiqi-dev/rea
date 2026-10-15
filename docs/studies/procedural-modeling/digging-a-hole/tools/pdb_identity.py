"""Compare a PE CodeView RSDS identity with a PDB MSF7 information stream.

Reads bounded header/directory pages. Does not compute content fingerprints or
execute/load the supplied image. GUID and age are producer-assigned identifiers.
"""

import argparse
import json
from pathlib import Path
import struct
import uuid


def read_at(stream, offset, count, size):
    if offset < 0 or count < 0 or offset + count > size:
        raise ValueError(f"File range outside input: {offset}+{count}")
    stream.seek(offset)
    data = stream.read(count)
    if len(data) != count:
        raise ValueError("Short read")
    return data


def pe_identity(path):
    size = path.stat().st_size
    with path.open("rb") as stream:
        dos = read_at(stream, 0, 64, size)
        if dos[:2] != b"MZ":
            raise ValueError("Expected PE")
        pe = struct.unpack_from("<I", dos, 60)[0]
        coff = read_at(stream, pe, 24, size)
        if coff[:4] != b"PE\0\0":
            raise ValueError("Invalid PE signature")
        section_count = struct.unpack_from("<H", coff, 6)[0]
        optional_size = struct.unpack_from("<H", coff, 20)[0]
        optional = read_at(stream, pe + 24, optional_size, size)
        if struct.unpack_from("<H", optional)[0] != 0x20B:
            raise ValueError("Expected PE32+")
        sections = read_at(stream, pe + 24 + optional_size, section_count * 40, size)

        def rva_to_offset(rva):
            for index in range(section_count):
                virtual_size, start, raw_size, raw_start = struct.unpack_from("<4I", sections, index * 40 + 8)
                if start <= rva < start + max(virtual_size, raw_size):
                    if rva - start >= raw_size:
                        raise ValueError("RVA has no file bytes")
                    return raw_start + rva - start
            raise ValueError("Unmapped RVA")

        debug_rva, debug_size = struct.unpack_from("<II", optional, 112 + 6 * 8)
        debug = read_at(stream, rva_to_offset(debug_rva), debug_size, size)
        for offset in range(0, debug_size, 28):
            kind, length, address, pointer = struct.unpack_from("<4I", debug, offset + 12)
            if kind != 2:
                continue
            data = read_at(stream, pointer, length, size)
            if data[:4] == b"RSDS":
                return {"guid": str(uuid.UUID(bytes_le=data[4:20])),
                        "age": struct.unpack_from("<I", data, 20)[0],
                        "recorded_pdb_path": data[24:].split(b"\0")[0].decode("utf-8"),
                        "codeview_file_offset": pointer}
    raise ValueError("No RSDS record")


def pdb_identity(path):
    size = path.stat().st_size
    with path.open("rb") as stream:
        header = read_at(stream, 0, 56, size)
        if header[:32] != b"Microsoft C/C++ MSF 7.00\r\n\x1aDS\0\0\0":
            raise ValueError("Expected MSF7")
        block_size, _, block_count, directory_size, _, map_block = struct.unpack_from("<6I", header, 32)
        if block_size not in (512, 1024, 2048, 4096) or block_count * block_size != size:
            raise ValueError("Unexpected MSF allocation")
        directory_blocks = (directory_size + block_size - 1) // block_size
        block_map = read_at(stream, map_block * block_size, directory_blocks * 4, size)
        directory = b"".join(read_at(stream, number * block_size, block_size, size)
                              for number in struct.unpack("<" + "I" * directory_blocks, block_map))[:directory_size]
        streams = struct.unpack_from("<I", directory)[0]
        lengths = struct.unpack_from("<" + "I" * streams, directory, 4)
        position = 4 + streams * 4
        information = None
        for index, length in enumerate(lengths):
            blocks = 0 if length == 0xFFFFFFFF else (length + block_size - 1) // block_size
            pages = struct.unpack_from("<" + "I" * blocks, directory, position)
            position += blocks * 4
            if index == 1:
                if length < 28:
                    raise ValueError("PDB information stream too short")
                information = read_at(stream, pages[0] * block_size, 28, size)
        if information is None:
            raise ValueError("Missing PDB information stream")
        version, signature, age = struct.unpack_from("<3I", information)
        return {"guid": str(uuid.UUID(bytes_le=information[12:28])), "age": age,
                "information_version": version, "signature": signature, "block_size": block_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("pdb", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    pe, pdb = pe_identity(args.binary), pdb_identity(args.pdb)
    matches = pe["guid"] == pdb["guid"] and pe["age"] == pdb["age"]
    result = {"binary": str(args.binary.resolve()), "pdb": str(args.pdb.resolve()),
              "pe_codeview": pe, "pdb_information": pdb, "guid_and_age_match": matches}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if not matches:
        raise SystemExit("EXE/PDB identity mismatch")


if __name__ == "__main__":
    main()
