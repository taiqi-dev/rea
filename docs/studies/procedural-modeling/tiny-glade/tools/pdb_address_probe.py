"""Resolve exact PE RVAs against an adjacent local PDB without target execution."""

import argparse
import ctypes
from ctypes import wintypes
import json
import struct
from pathlib import Path


class SymbolInfo(ctypes.Structure):
    _fields_ = [
        ("SizeOfStruct", wintypes.ULONG), ("TypeIndex", wintypes.ULONG),
        ("Reserved", ctypes.c_uint64 * 2), ("Index", wintypes.ULONG),
        ("Size", wintypes.ULONG), ("ModBase", ctypes.c_uint64),
        ("Flags", wintypes.ULONG), ("Value", ctypes.c_uint64),
        ("Address", ctypes.c_uint64), ("Register", wintypes.ULONG),
        ("Scope", wintypes.ULONG), ("Tag", wintypes.ULONG),
        ("NameLen", wintypes.ULONG), ("MaxNameLen", wintypes.ULONG),
        ("Name", wintypes.WCHAR * 1),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("rva", nargs="+", type=lambda value: int(value, 0))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    with binary.open("rb") as stream:
        header = stream.read(4096)
    if header[:2] != b"MZ":
        raise ValueError("Not a PE image")
    pe = struct.unpack_from("<I", header, 0x3C)[0]
    if header[pe:pe + 4] != b"PE\0\0" or struct.unpack_from("<H", header, pe + 24)[0] != 0x20B:
        raise ValueError("Expected PE32+ in the 4 KiB header window")
    image_base = struct.unpack_from("<Q", header, pe + 48)[0]
    dll = ctypes.WinDLL("dbghelp.dll", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    process = kernel.GetCurrentProcess()
    dll.SymSetOptions.argtypes = [wintypes.DWORD]
    dll.SymSetOptions.restype = wintypes.DWORD
    dll.SymSetOptions(0x2 | 0x4 | 0x200 | 0x1000 | 0x80000 | 0x02000000)
    dll.SymInitializeW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.BOOL]
    dll.SymInitializeW.restype = wintypes.BOOL
    dll.SymLoadModuleExW.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPCWSTR,
                                    wintypes.LPCWSTR, ctypes.c_uint64, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.DWORD]
    dll.SymLoadModuleExW.restype = ctypes.c_uint64
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.POINTER(SymbolInfo),
                                      wintypes.ULONG, ctypes.c_void_p)
    dll.SymEnumSymbolsW.argtypes = [wintypes.HANDLE, ctypes.c_uint64, wintypes.LPCWSTR,
                                    callback_type, ctypes.c_void_p]
    dll.SymEnumSymbolsW.restype = wintypes.BOOL
    dll.SymCleanup.argtypes = [wintypes.HANDLE]
    dll.SymCleanup.restype = wintypes.BOOL
    if not dll.SymInitializeW(process, str(binary.parent), False):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        module = dll.SymLoadModuleExW(process, None, str(binary), None, image_base, 0, None, 0)
        if not module:
            raise ctypes.WinError(ctypes.get_last_error())
        if any(rva < 0 for rva in args.rva):
            raise ValueError("RVA must be nonnegative")
        best = {rva: None for rva in args.rva}

        @callback_type
        def callback(pointer, _size, _context):
            record = pointer.contents
            symbol_rva = int(record.Address) - module
            for rva in best:
                if symbol_rva <= rva and (best[rva] is None or symbol_rva > best[rva][0]):
                    name = ctypes.wstring_at(ctypes.addressof(record) + SymbolInfo.Name.offset,
                                             record.NameLen).split("\0", 1)[0]
                    best[rva] = (symbol_rva, int(record.Size), name)
            return True

        if not dll.SymEnumSymbolsW(process, module, "*", callback, None):
            raise ctypes.WinError(ctypes.get_last_error())
        results = []
        for rva, match in best.items():
            if match is None:
                results.append({"rva": hex(rva), "symbol": None})
            else:
                symbol_rva, size, name = match
                results.append({"rva": hex(rva), "symbol_rva": hex(symbol_rva),
                                "displacement": hex(rva - symbol_rva), "size": size,
                                "contains_address": size > 0 and rva < symbol_rva + size,
                                "name": name})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"binary": str(binary), "image_base": hex(module),
                                           "results": results}, ensure_ascii=True, indent=2),
                               encoding="utf-8")
        print(json.dumps({"resolved": sum("name" in item for item in results),
                          "output": str(args.output)}))
    finally:
        dll.SymCleanup(process)


if __name__ == "__main__":
    main()
