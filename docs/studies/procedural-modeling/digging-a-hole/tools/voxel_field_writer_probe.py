"""Inventory x64 instructions that may directly store at selected VoxelWorld offsets.

This is a candidate scan of PE .text, not a disassembler or receiver-type proof.
It reads the Shipping EXE as data and computes no content digest.
"""

import argparse
import bisect
import ctypes
import json
import struct
from pathlib import Path
from ctypes import wintypes


TARGETS = {0x47C, 0x47D, 0x57C}


class SymbolInfo(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wintypes.ULONG), ("TypeIndex", wintypes.ULONG),
                ("Reserved", ctypes.c_uint64 * 2), ("Index", wintypes.ULONG),
                ("Size", wintypes.ULONG), ("ModBase", ctypes.c_uint64),
                ("Flags", wintypes.ULONG), ("Value", ctypes.c_uint64),
                ("Address", ctypes.c_uint64), ("Register", wintypes.ULONG),
                ("Scope", wintypes.ULONG), ("Tag", wintypes.ULONG),
                ("NameLen", wintypes.ULONG), ("MaxNameLen", wintypes.ULONG),
                ("Name", wintypes.WCHAR * 1)]


def resolve_symbols(binary, base, rows):
    dll = ctypes.WinDLL("dbghelp.dll", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    process = kernel.GetCurrentProcess()
    dll.SymSetOptions.argtypes = [wintypes.DWORD]
    dll.SymSetOptions.restype = wintypes.DWORD
    dll.SymSetOptions(0x2 | 0x4 | 0x200 | 0x1000 | 0x80000 | 0x02000000)
    dll.SymInitializeW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.BOOL]
    dll.SymInitializeW.restype = wintypes.BOOL
    dll.SymCleanup.argtypes = [wintypes.HANDLE]
    dll.SymCleanup.restype = wintypes.BOOL
    dll.SymLoadModuleExW.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPCWSTR,
                                    wintypes.LPCWSTR, ctypes.c_uint64, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.DWORD]
    dll.SymLoadModuleExW.restype = ctypes.c_uint64
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.POINTER(SymbolInfo),
                                       wintypes.ULONG, ctypes.c_void_p)
    dll.SymEnumSymbolsW.argtypes = [wintypes.HANDLE, ctypes.c_uint64, wintypes.LPCWSTR,
                                   callback_type, ctypes.c_void_p]
    dll.SymEnumSymbolsW.restype = wintypes.BOOL
    if not dll.SymInitializeW(process, str(binary.parent), False):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        module = dll.SymLoadModuleExW(process, None, str(binary), None, base, 0, None, 0)
        if not module:
            raise ctypes.WinError(ctypes.get_last_error())
        by_start = {}
        for row in rows:
            if row["function_start"] is not None:
                by_start.setdefault(int(row["function_start"], 16), []).append(row)
        count = 0
        matched = 0

        @callback_type
        def callback(pointer, _size, _context):
            nonlocal count, matched
            count += 1
            info = pointer.contents
            targets = by_start.get(int(info.Address))
            if targets and int(info.Tag) == 5:
                name = ctypes.wstring_at(
                    ctypes.addressof(info) + SymbolInfo.Name.offset, info.NameLen).rstrip("\0")
                for row in targets:
                    row["function_symbol"] = name
                    row["symbol_size"] = int(info.Size)
                matched += 1
            return True

        if not dll.SymEnumSymbolsW(process, module, "*", callback, None):
            raise ctypes.WinError(ctypes.get_last_error())
        for row in rows:
            row.setdefault("function_symbol", None)
        return {"pdb_symbols_enumerated": count, "candidate_function_starts_matched": matched}
    finally:
        if not dll.SymCleanup(process):
            raise ctypes.WinError(ctypes.get_last_error())


def scan(binary):
    data = binary.read_bytes()
    if len(data) != 145180160 or data[:2] != b"MZ":
        raise ValueError("Unexpected selected Shipping PE")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Missing PE header")
    sections = struct.unpack_from("<H", data, pe + 6)[0]
    optional = pe + 24
    if struct.unpack_from("<H", data, optional)[0] != 0x20B:
        raise ValueError("Expected PE32+")
    image_base = struct.unpack_from("<Q", data, optional + 24)[0]
    section_table = optional + struct.unpack_from("<H", data, pe + 20)[0]
    text = None
    pdata = None
    for index in range(sections):
        at = section_table + index * 40
        name = data[at:at + 8].split(b"\0", 1)[0]
        virtual_size, virtual_address, raw_size, raw_address = struct.unpack_from("<IIII", data, at + 8)
        if name == b".text":
            text = (virtual_address, virtual_size, raw_address, raw_size)
        if name == b".pdata":
            pdata = (virtual_address, virtual_size, raw_address, raw_size)
    if text is None or pdata is None:
        raise ValueError("Missing .text or .pdata section")
    rva, virtual_size, raw, raw_size = text
    if raw + raw_size > len(data):
        raise ValueError(".text outside file")
    code = data[raw:raw + min(virtual_size, raw_size)]
    rows = []
    # The displacement can occur in data or the middle of an instruction. The
    # preceding bytes are only a conservative encoding-shaped filter.
    for displacement in sorted(TARGETS):
        needle = struct.pack("<I", displacement)
        start = 0
        while True:
            at = code.find(needle, start)
            if at < 0:
                break
            start = at + 1
            forms = []
            if at >= 2:
                forms.append((code[at - 1], code[at - 2], at - 2, False))
            if at >= 3:
                forms.append((code[at - 2], code[at - 3], at - 3, True))
            for modrm, opcode, instruction_at, sib in forms:
                if modrm & 0xC0 != 0x80 or ((modrm & 7 == 4) != sib):
                    continue
                group = (modrm >> 3) & 7
                if opcode in (0xC6, 0xC7) and group != 0:
                    continue
                if opcode in (0x80, 0x81, 0x83) and group == 7:
                    continue
                if opcode in (0xFE, 0xFF) and group not in (0, 1):
                    continue
                if opcode not in (0x88, 0x89, 0xC6, 0xC7, 0x80, 0x81, 0x83, 0xFE, 0xFF):
                    continue
                break
            else:
                continue
            prefix = code[instruction_at - 1] if instruction_at else 0
            va = image_base + rva + instruction_at
            rows.append({"displacement": hex(displacement), "candidate_va": hex(va),
                         "candidate_file_offset": raw + instruction_at,
                         "opcode": hex(opcode), "modrm": hex(modrm), "prefix": hex(prefix),
                         "sib": sib,
                         "surrounding_bytes": code[max(0, at - 10):at + 12].hex(" ")})
    _, pdata_size, pdata_raw, pdata_raw_size = pdata
    if pdata_raw + pdata_raw_size > len(data) or pdata_size % 12:
        raise ValueError("Unexpected .pdata bounds")
    functions = [struct.unpack_from("<III", data, pdata_raw + i)
                 for i in range(0, min(pdata_size, pdata_raw_size), 12)]
    starts = [entry[0] for entry in functions]
    if starts != sorted(starts):
        raise ValueError("Unsorted .pdata runtime functions")
    for row in rows:
        candidate_rva = int(row["candidate_va"], 16) - image_base
        index = bisect.bisect_right(starts, candidate_rva) - 1
        if index >= 0 and candidate_rva < functions[index][1]:
            row["function_start"] = hex(image_base + functions[index][0])
            row["function_end"] = hex(image_base + functions[index][1])
        else:
            row["function_start"] = None
            row["function_end"] = None
    symbol_coverage = resolve_symbols(binary, image_base, rows)
    return {"binary": str(binary), "binary_bytes": len(data), "image_base": hex(image_base),
            "text_rva": hex(rva), "text_virtual_size": virtual_size,
            "text_raw_size": raw_size, "candidate_count": len(rows),
            "symbol_coverage": symbol_coverage, "candidates": rows,
            "limitation": "Encoding-shaped byte candidates only; disassemble and establish receiver type before claiming a VoxelWorld write."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    result = scan(args.binary.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"candidate_count": result["candidate_count"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
