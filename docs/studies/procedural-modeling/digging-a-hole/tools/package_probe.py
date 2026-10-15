"""Inventory this study's unencrypted IoStore v8 / PAK v11 containers.

Optional extraction selects exact logical names, never executes game code, and
uses an explicitly supplied ooz executable for Oodle blocks. Other layouts fail.
Output is research data; this is not a general Unreal package deserializer.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import subprocess
import tempfile


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError(f"Range outside record: {self.pos}+{count}")
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result

    def number(self, fmt="I"):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def string(self):
        size = self.number("i")
        raw = self.take(abs(size) * (2 if size < 0 else 1))
        if not size:
            return ""
        encoding = "utf-16-le" if size < 0 else "utf-8"
        text = raw.decode(encoding)
        if not text.endswith("\0"):
            raise ValueError("Missing FString terminator")
        return text[:-1]


def read_at(path, offset, count):
    if offset < 0 or count < 0 or offset + count > path.stat().st_size:
        raise ValueError(f"Outside source file: {path}: {offset}+{count}")
    with path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(count)
    if len(data) != count:
        raise ValueError("Short read")
    return data


def decode(data, method, size, decoder, scratch):
    if method == "None":
        if len(data) != size:
            raise ValueError("Uncompressed block size mismatch")
        return data
    if method != "Oodle" or decoder is None:
        raise ValueError(f"Explicit decoder needed for {method}")
    with tempfile.TemporaryDirectory(dir=scratch) as root:
        source, output = Path(root) / "input.ooz", Path(root) / "decoded.bin"
        source.write_bytes(struct.pack("<Q", size) + data)
        run = subprocess.run([str(decoder), "-d", str(source), str(output)],
                             capture_output=True, timeout=30, check=False)
        if run.returncode:
            raise RuntimeError(f"ooz failed ({run.returncode}): {run.stderr.decode(errors='replace')}")
        result = output.read_bytes()
    if len(result) != size:
        raise ValueError("Decoder output length mismatch")
    return result


def iostore(path):
    data = path.read_bytes()
    if data[:16] != b"-==-" * 4 or data[16] != 8:
        raise ValueError("Expected IoStore v8")
    header, entries, count, entry_size, methods, method_width, block_size, directory_size, partitions = struct.unpack_from("<9I", data, 20)
    flags, seeds = struct.unpack_from("<II", data, 80)
    if header != 144 or entry_size != 12 or partitions != 1 or flags & 2:
        raise ValueError("Unsupported/encrypted IoStore layout")
    overflow_count = struct.unpack_from("<I", data, 96)[0]
    offsets = header + entries * 12
    blocks_at = offsets + entries * 10 + seeds * 4 + overflow_count * 4
    blocks = []
    for i in range(count):
        record = data[blocks_at + i * 12:blocks_at + (i + 1) * 12]
        if len(record) != 12:
            raise ValueError("Truncated block table")
        blocks.append((int.from_bytes(record[:5], "little"),
                       int.from_bytes(record[5:8], "little"),
                       int.from_bytes(record[8:11], "little"), record[11]))
    names_at = blocks_at + count * entry_size
    names = ["None"] + [data[names_at + i * method_width:names_at + (i + 1) * method_width].split(b"\0")[0].decode("ascii") for i in range(methods)]
    # Signed containers have signature records before the directory index.
    if flags & 4:
        raise ValueError("Signed directory layout not supported by this probe")
    reader = Reader(data[names_at + methods * method_width:names_at + methods * method_width + directory_size])
    mount = reader.string() if directory_size else ""
    directories = [tuple(reader.number() for _ in range(4)) for _ in range(reader.number())] if directory_size else []
    files = [tuple(reader.number() for _ in range(3)) for _ in range(reader.number())] if directory_size else []
    strings = [reader.string() for _ in range(reader.number())] if directory_size else []
    if reader.pos != directory_size:
        raise ValueError("Unconsumed directory bytes")
    rows, visited = [], set()

    def walk(index, prefix):
        if index == 0xFFFFFFFF:
            return
        if index in visited:
            raise ValueError("Directory cycle or repeated directory")
        visited.add(index)
        name, child, sibling, file_index = directories[index]
        current = prefix + (strings[name] + "/" if name != 0xFFFFFFFF else "")
        seen_files = set()
        while file_index != 0xFFFFFFFF:
            if file_index in seen_files:
                raise ValueError("File list cycle")
            seen_files.add(file_index)
            filename, next_file, entry = files[file_index]
            if entry >= entries:
                raise ValueError("Invalid chunk entry")
            record = data[offsets + entry * 10:offsets + (entry + 1) * 10]
            offset, length = int.from_bytes(record[:5], "big"), int.from_bytes(record[5:], "big")
            first, last = offset // block_size, (offset + length - 1) // block_size
            rows.append({"path": mount + current + strings[filename], "entry": entry,
                         "offset": offset, "length": length,
                         "methods": sorted({names[blocks[j][3]] for j in range(first, last + 1)}) if length else []})
            file_index = next_file
        walk(child, current)
        walk(sibling, prefix)

    if directory_size:
        walk(0, "")
    elif entries == 1 and data[header:header + 12] == b"\0" * 11 + b"\x05":
        record = data[offsets:offsets + 10]
        offset, length = int.from_bytes(record[:5], "big"), int.from_bytes(record[5:], "big")
        rows.append({"path": "ScriptObjects", "entry": 0, "offset": offset, "length": length,
                     "methods": sorted({names[b[3]] for b in blocks})})
    else:
        raise ValueError("Unindexed container is not the single ScriptObjects layout")
    if directory_size and len(rows) != len(files):
        raise ValueError("Directory did not cover all file entries")
    result = {"container": str(path), "kind": "iostore-v8", "mount": mount,
              "entries": entries, "blocks": count, "block_size": block_size,
              "directory_bytes": directory_size, "flags": flags,
              "block_methods": dict(Counter(names[b[3]] for b in blocks)), "rows": rows}

    def extract(row, decoder, scratch):
        parts = []
        start, end = row["offset"], row["offset"] + row["length"]
        for index in range(start // block_size, (end - 1) // block_size + 1):
            offset, size, raw_size, method = blocks[index]
            block = decode(read_at(path.with_suffix(".ucas"), offset, size), names[method], raw_size, decoder, scratch)
            local_start = max(start - index * block_size, 0)
            local_end = min(end - index * block_size, raw_size)
            parts.append(block[local_start:local_end])
        return b"".join(parts)

    return result, extract


def pak(path):
    tail = read_at(path, path.stat().st_size - 512, 512)
    position = tail.rfind(struct.pack("<I", 0x5A6F12E1))
    if position < 17 or tail[position - 1] != 0:
        raise ValueError("No supported unencrypted PAK footer")
    version, offset, size = struct.unpack_from("<Iqq", tail, position + 4)
    if version != 11:
        raise ValueError("Expected PAK v11")
    reader = Reader(read_at(path, offset, size))
    mount, count, seed = reader.string(), reader.number(), reader.number("Q")
    indexes = []
    for _ in range(2):
        if not reader.number():
            raise ValueError("PAK needs both indexes")
        indexes.append((reader.number("q"), reader.number("q")))
        reader.take(20)  # stored index identity, not recomputed
    encoded = reader.take(reader.number())
    remainder = reader.number()
    if remainder or reader.pos != size:
        raise ValueError("Unsupported residual index entries")
    directory = Reader(read_at(path, *indexes[1]))
    rows = []
    for _ in range(directory.number()):
        dirname = directory.string()
        for _ in range(directory.number()):
            filename, encoded_at = directory.string(), directory.number("i")
            er = Reader(encoded)
            er.pos = encoded_at
            bits = er.number()
            block_size = er.number() if bits & 63 == 63 else (bits & 63) << 11
            method, encrypted, blocks = (bits >> 23) & 63, bool(bits & (1 << 22)), (bits >> 6) & 65535
            file_offset = er.number("I" if bits & (1 << 31) else "q")
            raw_size = er.number("I" if bits & (1 << 30) else "q")
            packed_size = er.number("I" if bits & (1 << 29) else "q") if method else raw_size
            header_size = 53 + (4 + blocks * 16 if method else 0)
            lengths = [packed_size] if blocks == 1 and not encrypted else [er.number() for _ in range(blocks)]
            rows.append({"path": mount + dirname + filename, "offset": file_offset,
                         "length": raw_size, "packed_bytes": packed_size, "method": method,
                         "encrypted": encrypted, "block_size": raw_size if blocks == 1 else block_size,
                         "header_size": header_size, "block_lengths": lengths})
    if len(rows) != count or directory.pos != len(directory.data):
        raise ValueError("PAK directory count/length mismatch")
    # This file declares Oodle at compression method index 1 in its footer.
    method_bytes = tail[position + 44:position + 76]
    if method_bytes.split(b"\0")[0] != b"Oodle":
        raise ValueError("Unexpected PAK compression methods")
    result = {"container": str(path), "kind": "pak-v11", "mount": mount,
              "files": count, "index_offset": offset, "index_bytes": size,
              "directory_index": indexes[1], "rows": rows}

    def extract(row, decoder, scratch):
        if row["encrypted"] or row["method"] not in (0, 1):
            raise ValueError("Unsupported encrypted/compressed entry")
        position = row["offset"] + row["header_size"]
        if not row["method"]:
            return read_at(path, position, row["length"])
        parts, remaining = [], row["length"]
        for length in row["block_lengths"]:
            size = min(remaining, row["block_size"])
            parts.append(decode(read_at(path, position, length), "Oodle", size, decoder, scratch))
            remaining -= size
            position += length
        if remaining:
            raise ValueError("PAK block coverage mismatch")
        return b"".join(parts)

    return result, extract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("container", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--select", action="append", default=[], help="Exact logical name from inventory")
    parser.add_argument("--extract-to", type=Path)
    parser.add_argument("--ooz", type=Path)
    args = parser.parse_args()
    path = args.container.resolve(strict=True)
    result, extractor = iostore(path) if path.suffix.lower() == ".utoc" else pak(path)
    result["extractions"] = []
    if args.select:
        if args.extract_to is None:
            raise ValueError("Extraction needs an explicit output directory")
        args.extract_to.mkdir(parents=True, exist_ok=True)
        for selected in args.select:
            matches = [r for r in result["rows"] if r["path"] == selected]
            if len(matches) != 1:
                raise ValueError(f"Selection must match exactly one entry: {selected}")
            output = args.extract_to / Path(selected).name
            data = extractor(matches[0], args.ooz.resolve(strict=True) if args.ooz else None, args.extract_to)
            if len(data) != matches[0]["length"]:
                raise ValueError("Selected entry output size mismatch")
            with output.open("xb") as stream:
                stream.write(data)
            result["extractions"].append({"path": selected, "output": str(output.resolve()), "bytes": len(data)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"kind": result["kind"], "files": len(result["rows"]), "extracted": len(result["extractions"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
