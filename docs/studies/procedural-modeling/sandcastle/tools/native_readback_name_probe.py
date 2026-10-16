"""Bounded static name and PE reference inventory for Sandcastle readback.

This reads shipped DLL bytes only. String and four-byte displacement hits are
candidates; instruction boundaries and semantic calls require disassembly.
"""

import argparse
import array
import json
import struct
from pathlib import Path

from unity_player_xref_probe import pe_layout


NAMES = (
    "Request_Internal_ComputeBuffer_1_Injected",
    "AsyncGPUReadbackRequest::SetScriptingCallback",
    "ComputeBuffer::Release",
    "ComputeBuffer::DestroyBuffer",
    "ComputeBuffer::DestroyBuffer_Injected",
    "ComputeBuffer::DestroyBuffer_Injected(System.IntPtr)",
    "UnsafeUtility::FreeTracked(System.Void*,Unity.Collections.Allocator)",
    "DestroyBuffer",
    "WaitAllRequests",
    "WaitForCompletion",
    "NativeArray",
    "AsyncGPUReadback",
)

NAME_TABLE_FILE_START = 0x1EB5D80
FUNCTION_TABLE_FILE_START = 0x1EBDA60


def containing(sections, offset):
    return next((s for s in sections if s["offset"] <= offset < s["offset"] + s["size"]), None)


def locations(data, base, sections, needle):
    result = []
    at = 0
    while (at := data.find(needle, at)) >= 0:
        sec = containing(sections, at)
        result.append({"file_offset": at, "section": sec["name"] if sec else None,
                       "va": base + sec["rva"] + at - sec["offset"] if sec else None})
        at += 1
        if len(result) > 500:
            raise ValueError("Unbounded result for selected literal")
    return result


def code_displacements(data, base, sections, targets):
    """Find candidate four-byte RIP displacements in executable sections."""
    by_rva = {va - base: name for name, va in targets.items()}
    hits = {name: [] for name in targets}
    windows = 0
    for sec in sections:
        if not sec["executable"]:
            continue
        body = data[sec["offset"]:sec["offset"] + sec["size"]]
        for alignment in range(4):
            usable = (len(body) - alignment) & ~3
            words = array.array("I")
            words.frombytes(body[alignment:alignment + usable])
            for i, raw in enumerate(words):
                relative = alignment + i * 4
                signed = raw if raw < 0x80000000 else raw - 0x100000000
                name = by_rva.get(sec["rva"] + relative + 4 + signed)
                if name:
                    hits[name].append({"displacement_va": base + sec["rva"] + relative,
                                       "displacement_file_offset": sec["offset"] + relative,
                                       "preceding_hex": body[max(0, relative - 8):relative].hex()})
            windows += len(words)
    return windows, hits


def probe(binary):
    data = binary.read_bytes()
    base, sections = pe_layout(data)
    results = {}
    targets = {}
    for name in NAMES:
        variants = {}
        for label, needle in (("ascii", name.encode() + b"\0"),
                              ("utf16le", name.encode("utf-16le") + b"\0\0")):
            hits = locations(data, base, sections, needle)
            for hit in hits:
                if hit["va"] is not None:
                    start = data.rfind(b"\0", max(0, hit["file_offset"] - 256), hit["file_offset"]) + 1
                    if label == "ascii" and start < hit["file_offset"]:
                        sec = containing(sections, start)
                        hit["full_ascii_literal"] = data[start:hit["file_offset"] + len(needle) - 1].decode("ascii", "replace")
                        hit["literal_start_va"] = base + sec["rva"] + start - sec["offset"] if sec else None
                    reference_va = hit.get("literal_start_va") or hit["va"]
                    hit["reference_va"] = reference_va
                    hit["absolute_pointer_file_offsets"] = [x["file_offset"] for x in
                        locations(data, base, sections, struct.pack("<Q", reference_va))]
                    hit["rva_literal_file_offsets"] = [x["file_offset"] for x in
                        locations(data, base, sections, struct.pack("<I", reference_va - base))]
                    if label == "ascii" and hit.get("literal_start_va"):
                        targets[name] = hit["literal_start_va"]
            variants[label] = hits
        results[name] = variants
    windows, xrefs = code_displacements(data, base, sections, targets)
    icall_table = {}
    if binary.name.lower() == "unityplayer.dll":
        count = (FUNCTION_TABLE_FILE_START - NAME_TABLE_FILE_START) // 8
        if count != 3996:
            raise ValueError("Unexpected table layout")
        name_ptrs = struct.unpack_from(f"<{count}Q", data, NAME_TABLE_FILE_START)
        function_ptrs = struct.unpack_from(f"<{count}Q", data, FUNCTION_TABLE_FILE_START)
        def in_section(va, executable):
            rva = va - base
            return any(s["executable"] == executable and
                       s["rva"] <= rva < s["rva"] + s["virtual_size"] for s in sections)
        if not all(in_section(ptr, False) for ptr in name_ptrs):
            raise ValueError("Name table has a pointer outside data sections")
        if not all(in_section(ptr, True) for ptr in function_ptrs):
            raise ValueError("Function table has a pointer outside executable sections")
        for name, enc in results.items():
            if not enc["ascii"]:
                continue
            start_va = enc["ascii"][0].get("literal_start_va")
            indices = [i for i, ptr in enumerate(name_ptrs) if ptr == start_va]
            if len(indices) == 1:
                i = indices[0]
                icall_table[name] = {"index": i,
                    "name_pointer_file_offset": NAME_TABLE_FILE_START + 8 * i,
                    "function_pointer_file_offset": FUNCTION_TABLE_FILE_START + 8 * i,
                    "candidate_function_va": function_ptrs[i]}
        icall_table = {"name_table_start_file_offset": NAME_TABLE_FILE_START,
                       "function_table_start_file_offset": FUNCTION_TABLE_FILE_START,
                       "entries": count, "mapped_names": icall_table,
                       "parallel_mapping_is_inferred": True}
    return {"binary": str(binary), "file_bytes": len(data), "image_base": base,
            "search_mode": "exact substring followed by NUL; ASCII or UTF-16LE; entire file",
            "names": results, "code_windows_scanned": windows,
            "literal_start_rip_displacement_candidates": xrefs,
            "icall_parallel_tables": icall_table,
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output exists: {args.output}")
    result = probe(args.binary.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"names": {k: {e: len(v) for e, v in enc.items()}
                                for k, enc in result["names"].items()},
                      "rip_candidates": {k: len(v) for k, v in
                                         result["literal_start_rip_displacement_candidates"].items()}}))


if __name__ == "__main__":
    main()
