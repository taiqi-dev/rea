"""Read local matching Windows PDB symbols without launching a target.

Uses the host's Microsoft DbgHelp with an explicit local symbol search path.
No target DLL loading, remote symbol servers, or game process attachment.
"""

import argparse
import ctypes
from ctypes import wintypes
import json
import re
import struct
from pathlib import Path


class SymbolInfo(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wintypes.ULONG), ("TypeIndex", wintypes.ULONG),
                ("Reserved", ctypes.c_uint64 * 2), ("Index", wintypes.ULONG),
                ("Size", wintypes.ULONG), ("ModBase", ctypes.c_uint64),
                ("Flags", wintypes.ULONG), ("Value", ctypes.c_uint64),
                ("Address", ctypes.c_uint64), ("Register", wintypes.ULONG),
                ("Scope", wintypes.ULONG), ("Tag", wintypes.ULONG),
                ("NameLen", wintypes.ULONG), ("MaxNameLen", wintypes.ULONG),
                ("Name", wintypes.WCHAR * 1)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("binary", type=Path)
    ap.add_argument("--mask", action="append", required=True)
    ap.add_argument("--regex", help="Optional filter on returned names")
    ap.add_argument("--limit", type=int, help="Explicit output bound; reports incomplete enumeration when reached")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    binary = args.binary.resolve(strict=True)
    if args.limit is not None and args.limit < 1:
        raise ValueError("Symbol limit must be positive")
    with binary.open("rb") as stream:
        header = stream.read(4096)
    if header[:2] != b"MZ":
        raise ValueError("Not a PE image")
    pe = struct.unpack_from("<I", header, 0x3c)[0]
    if header[pe:pe + 4] != b"PE\0\0" or struct.unpack_from("<H", header, pe + 24)[0] != 0x20b:
        raise ValueError("Expected PE32+")
    image_base = struct.unpack_from("<Q", header, pe + 48)[0]
    dll = ctypes.WinDLL("dbghelp.dll", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    process = kernel.GetCurrentProcess()
    dll.SymSetOptions.argtypes = [wintypes.DWORD]
    dll.SymSetOptions.restype = wintypes.DWORD
    # Exact constants from the installed Windows SDK DbgHelp.h.
    options = 0x2 | 0x4 | 0x200 | 0x1000 | 0x80000 | 0x02000000
    dll.SymSetOptions(options)
    dll.SymInitializeW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.BOOL]
    dll.SymInitializeW.restype = wintypes.BOOL
    dll.SymCleanup.argtypes = [wintypes.HANDLE]
    dll.SymCleanup.restype = wintypes.BOOL
    dll.SymLoadModuleExW.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPCWSTR,
                                    wintypes.LPCWSTR, ctypes.c_uint64, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.DWORD]
    dll.SymLoadModuleExW.restype = ctypes.c_uint64
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.POINTER(SymbolInfo), wintypes.ULONG, ctypes.c_void_p)
    dll.SymEnumSymbolsW.argtypes = [wintypes.HANDLE, ctypes.c_uint64, wintypes.LPCWSTR,
                                   callback_type, ctypes.c_void_p]
    dll.SymEnumSymbolsW.restype = wintypes.BOOL
    if not dll.SymInitializeW(process, str(binary.parent), False):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        module = dll.SymLoadModuleExW(process, None, str(binary), None, image_base, 0, None, 0)
        if not module:
            raise ctypes.WinError(ctypes.get_last_error())
        pattern = re.compile(args.regex) if args.regex else None
        symbols = {}
        queries = []
        for mask in args.mask:
            seen = 0
            accepted = 0
            limited = False
            callback_errors = []

            @callback_type
            def callback(pointer, _size, _context):
                nonlocal seen, accepted, limited
                try:
                    record = pointer.contents
                    name = ctypes.wstring_at(ctypes.addressof(record) + SymbolInfo.Name.offset, record.NameLen).rstrip("\0")
                    seen += 1
                    if pattern is not None and not pattern.search(name):
                        return True
                    address = int(record.Address)
                    symbols[(address, name)] = {"name": name, "address": hex(address),
                                                "rva": hex(address - module), "size": int(record.Size),
                                                "tag": int(record.Tag), "type_index": int(record.TypeIndex)}
                    accepted += 1
                    if args.limit is not None and accepted >= args.limit:
                        limited = True
                        return False
                    return True
                except Exception as error:
                    callback_errors.append(repr(error))
                    return False

            success = dll.SymEnumSymbolsW(process, module, mask, callback, None)
            if callback_errors:
                raise RuntimeError(callback_errors)
            if not success and not limited:
                raise ctypes.WinError(ctypes.get_last_error())
            queries.append({"mask": mask, "seen": seen, "accepted": accepted,
                            "exhausted": not limited, "limited": limited})
        result = {"binary": str(binary), "binary_bytes": binary.stat().st_size,
                  "image_base": hex(image_base), "loaded_base": hex(module),
                  "local_symbol_path": str(binary.parent), "dbghelp_options": hex(options),
                  "query_regex": args.regex, "queries": queries,
                  "symbols": sorted(symbols.values(), key=lambda x: (int(x["address"], 16), x["name"]))}
    finally:
        if not dll.SymCleanup(process):
            raise ctypes.WinError(ctypes.get_last_error())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"symbols": len(result["symbols"]), "queries": queries, "output": str(args.output)}))


if __name__ == "__main__":
    main()
