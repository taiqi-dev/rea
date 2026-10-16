"""Read bounded local PDB type children with Windows DbgHelp; no target loading.

Symbol names and raw constant VARIANT bytes remain escaped JSON. Unsupported
DbgHelp queries are recorded individually, never interpreted as absent fields.
"""

import argparse
import ctypes as c
from ctypes import wintypes as w
import importlib.util
import json
from pathlib import Path
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--mask', action='append', required=True)
    parser.add_argument('--limit', type=int, default=64)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.limit < 1 or args.output.exists():
        raise ValueError('Positive limit and fresh output required')
    source = Path(__file__).resolve().parents[2] / 'digging-a-hole/tools/pdb_probe.py'
    spec = importlib.util.spec_from_file_location('local_pdb_symbols', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SymbolInfo = module.SymbolInfo
    binary = args.binary.resolve(strict=True)
    with binary.open('rb') as stream:
        header = stream.read(4096)
    if header[:2] != b'MZ':
        raise ValueError('Expected PE')
    pe = struct.unpack_from('<I', header, 0x3c)[0]
    if header[pe:pe+4] != b'PE\0\0' or struct.unpack_from('<H', header, pe+24)[0] != 0x20b:
        raise ValueError('Expected PE32+')
    base = struct.unpack_from('<Q', header, pe+48)[0]
    api = c.WinDLL('dbghelp.dll', use_last_error=True)
    kernel = c.WinDLL('kernel32.dll', use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    process = kernel.GetCurrentProcess()
    api.SymSetOptions.argtypes = [w.DWORD]
    api.SymSetOptions.restype = w.DWORD
    options = 0x2 | 0x4 | 0x200 | 0x1000 | 0x80000 | 0x02000000
    api.SymSetOptions(options)
    api.SymInitializeW.argtypes = [w.HANDLE, w.LPCWSTR, w.BOOL]
    api.SymInitializeW.restype = w.BOOL
    api.SymLoadModuleExW.argtypes = [w.HANDLE, w.HANDLE, w.LPCWSTR, w.LPCWSTR,
                                   c.c_uint64, w.DWORD, c.c_void_p, w.DWORD]
    api.SymLoadModuleExW.restype = c.c_uint64
    api.SymGetTypeInfo.argtypes = [w.HANDLE, c.c_uint64, w.ULONG, c.c_int, c.c_void_p]
    api.SymGetTypeInfo.restype = w.BOOL
    api.SymCleanup.argtypes = [w.HANDLE]
    api.SymCleanup.restype = w.BOOL
    callback_type = c.WINFUNCTYPE(w.BOOL, c.POINTER(SymbolInfo), w.ULONG, c.c_void_p)
    api.SymEnumTypesByNameW.argtypes = [w.HANDLE, c.c_uint64, w.LPCWSTR, callback_type, c.c_void_p]
    api.SymEnumTypesByNameW.restype = w.BOOL
    if not api.SymInitializeW(process, str(binary.parent), False):
        raise c.WinError(c.get_last_error())
    records, queries = [], []
    try:
        loaded = api.SymLoadModuleExW(process, None, str(binary), None, base, 0, None, 0)
        if not loaded:
            raise c.WinError(c.get_last_error())

        def scalar(type_id, selector, wide=False):
            value = c.c_uint64() if wide else w.ULONG()
            if api.SymGetTypeInfo(process, loaded, type_id, selector, c.byref(value)):
                return value.value
            return {'error': c.get_last_error()}

        def describe(type_id):
            name = c.c_void_p()
            if api.SymGetTypeInfo(process, loaded, type_id, 1, c.byref(name)):
                try:
                    text = c.wstring_at(name.value)
                finally:
                    kernel.LocalFree(name)
            else:
                text = {'error': c.get_last_error()}
            result = {'type_id': type_id, 'name': text}
            for label, selector, wide in [('tag', 0, False), ('length', 2, True),
                                           ('type', 3, False), ('type_id_ref', 4, False),
                                           ('offset', 10, False), ('data_kind', 8, False)]:
                result[label] = scalar(type_id, selector, wide)
            raw = (c.c_ubyte * 32)()
            if api.SymGetTypeInfo(process, loaded, type_id, 11, c.byref(raw)):
                data = bytes(raw)
                vt = struct.unpack_from('<H', data)[0]
                result['constant'] = {'variant_type': vt, 'raw_hex': data.hex()}
                fmt = {2:'h', 3:'i', 16:'b', 17:'B', 18:'H', 19:'I', 20:'q', 21:'Q', 22:'i', 23:'I'}.get(vt)
                if fmt:
                    result['constant']['integer'] = struct.unpack_from('<'+fmt, data, 8)[0]
            return result

        for mask in args.mask:
            ids, errors = [], []
            limited = False

            @callback_type
            def callback(pointer, _size, _context):
                nonlocal limited
                try:
                    record = pointer.contents
                    ids.append(int(record.TypeIndex))
                    if len(ids) >= args.limit:
                        limited = True
                        return False
                    return True
                except Exception as error:
                    errors.append(repr(error))
                    return False

            ok = api.SymEnumTypesByNameW(process, loaded, mask, callback, None)
            if errors or (not ok and not limited):
                raise RuntimeError({'mask': mask, 'errors': errors, 'winerror': c.get_last_error()})
            queries.append({'mask': mask, 'returned': len(ids), 'exhausted': not limited})
            for type_id in ids:
                item = describe(type_id)
                count = scalar(type_id, 13)
                item['children_count'] = count
                if isinstance(count, int) and count:
                    # Bound children by the caller's same explicit result limit.
                    selected = min(count, args.limit)
                    params = (w.ULONG * (selected+2))()
                    params[0], params[1] = selected, 0
                    if api.SymGetTypeInfo(process, loaded, type_id, 7, c.byref(params)):
                        item['children'] = [describe(int(value)) for value in params[2:]]
                        item['children_exhausted'] = selected == count
                    else:
                        item['children_error'] = c.get_last_error()
                records.append(item)
    finally:
        if not api.SymCleanup(process):
            raise c.WinError(c.get_last_error())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump({'binary': str(binary), 'binary_bytes': binary.stat().st_size,
                   'image_base': hex(base), 'options': hex(options),
                   'queries': queries, 'types': records}, stream, ensure_ascii=True, indent=2)
        stream.write('\n')
    print(json.dumps({'queries': queries, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
