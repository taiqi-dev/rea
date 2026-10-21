"""Validate selected static idle-frame branches in the matched shipping PE.

This reads the executable and prior, local PDB/dumpbin receipts only. It does
not start the game or treat those receipts as REA Evidence.
"""

import argparse
import json
import struct
from pathlib import Path


ANCHORS = {
    # LOD Tick: interval gate, invoker poll, and secondary work gate.
    "lod_tick_interval_skip": (0x143E941BC, "7611"),
    "lod_tick_update_invokers": (0x143E941CA, "e8e13b0000"),
    "lod_tick_work_gate": (0x143E941CF, "80bfb000000000"),
    # Invoker poll: unchanged fast path, pending flag, delayed LOD rebuild.
    "invoker_unchanged": (0x143E983CE, "4084ff"),
    "invoker_unchanged_skip": (0x143E983D1, "0f8415040000"),
    "invoker_pending": (0x143E983DE, "41c6862901000001"),
    "invoker_update_pending_gate": (0x143E987FA, "4180be2901000000"),
    "invoker_update_lods": (0x143E98868, "e833150000"),
    # Renderer completion and submission gates.
    "mesh_deadline": (0x143EED089, "660f2fc7"),
    "mesh_empty_queue": (0x143EED0DA, "4885d2"),
    "show_empty": (0x143EEC599, "4439a368020000"),
    "remove_empty": (0x143EEC7B3, "4439a358020000"),
    "flush_queue_zero": (0x143EDFEEA, "85c0"),
    "flush_queue_one": (0x143EDFF2F, "85c0"),
    "flush_queue_two": (0x143EDFF74, "85c0"),
    "flush_queue_three": (0x143EDFFB9, "85c0"),
}

SYMBOLS = {
    "FVoxelDefaultLODManager::Tick": (0x143E94160, 1142),
    "FVoxelDefaultLODManager::UpdateInvokers": (0x143E97DB0, 2875),
    "FVoxelDefaultLODManager::UpdateLODs": (0x143E99DA0, 913),
    "FVoxelDefaultRenderer::Tick": (0x143EF3890, 588),
    "FVoxelDefaultRenderer::ProcessChunksToRemoveOrShow": (0x143EEC550, 980),
    "FVoxelDefaultRenderer::ProcessMeshUpdates": (0x143EED040, 1398),
    "FVoxelDefaultRenderer::FlushQueuedTasks": (0x143EDFED0, 312),
}


def read_pe(binary: Path):
    data = binary.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[:2] != b"MZ" or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Expected PE image")
    coff = pe + 4
    section_count = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    if struct.unpack_from("<H", data, optional)[0] != 0x20B:
        raise ValueError("Expected PE32+ image")
    image_base = struct.unpack_from("<Q", data, optional + 24)[0]
    sections = []
    for index in range(section_count):
        start = optional + optional_size + index * 40
        virtual_size, rva, raw_size, raw_start = struct.unpack_from("<IIII", data, start + 8)
        sections.append((rva, min(virtual_size, raw_size), raw_start))
    return data, image_base, sections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--symbols", required=True, type=Path)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    data, base, sections = read_pe(args.binary)
    checks = []

    def check(name, passed, detail):
        checks.append({"name": name, "status": "Passed" if passed else "Failed", "detail": detail})

    check("pe_identity", len(data) == 145180160 and base == 0x140000000,
          {"bytes": len(data), "image_base": hex(base)})
    for name, (va, expected_hex) in ANCHORS.items():
        wanted = bytes.fromhex(expected_hex)
        rva = va - base
        matches = [(raw + rva - start, size) for start, size, raw in sections
                   if start <= rva and rva + len(wanted) <= start + size]
        actual = data[matches[0][0]:matches[0][0] + len(wanted)] if len(matches) == 1 else b""
        check(name, actual == wanted, {"va": hex(va), "expected": expected_hex,
                                      "actual": actual.hex(), "section_matches": len(matches)})

    receipt = json.loads(args.symbols.read_text(encoding="utf-8"))
    check("pdb_queries_complete", all(q["exhausted"] for q in receipt["queries"]),
          receipt["queries"])
    found = {row["name"]: row for row in receipt["symbols"]}
    for name, (va, size) in SYMBOLS.items():
        row = found.get(name)
        check(f"symbol:{name}", row is not None and int(row["address"], 16) == va
              and row["size"] == size,
              {"expected_va": hex(va), "expected_size": size,
               "actual": row and {"address": row["address"], "size": row["size"]}})

    for file, label in (("process-chunks-to-remove-or-show.disasm.txt",
                         "FVoxelDefaultRenderer::ProcessChunksToRemoveOrShow"),
                        ("flush-queued-tasks.disasm.txt", "FVoxelDefaultRenderer::FlushQueuedTasks")):
        content = (args.raw / file).read_text(encoding="utf-8")
        function = label.split("::", 1)[1]
        check(f"dumpbin:{file}", f"?{function}@FVoxelDefaultRenderer@@" in content
              and "fatal error" not in content,
              {"file": str(args.raw / file), "label": label})

    result = {"kind": "static-validation", "evidence_class": "PE/PDB/dumpbin; not REA Evidence",
              "target": str(args.binary), "passed": sum(c["status"] == "Passed" for c in checks),
              "failed": sum(c["status"] == "Failed" for c in checks),
              "not_run": ["game execution", "runtime timing/FPS", "Ghidra retry", "private saves"],
              "checks": checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "failed": result["failed"],
                      "output": str(args.output)}, ensure_ascii=False))
    raise SystemExit(1 if result["failed"] else 0)


if __name__ == "__main__":
    main()
