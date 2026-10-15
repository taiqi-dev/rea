"""Locate one IL2CPP code-generation module and selected method pointer slots.

Reads PE sections and file-backed pointers only. It neither executes the target
nor assumes that a name match alone identifies a method body: the module name,
table count, pointer validity, and metadata token range are all checked.
"""

import argparse
import bisect
import json
import struct
from pathlib import Path


def u16(data, pos):
    return struct.unpack_from("<H", data, pos)[0]


def u32(data, pos):
    return struct.unpack_from("<I", data, pos)[0]


def u64(data, pos):
    return struct.unpack_from("<Q", data, pos)[0]


class PE:
    def __init__(self, path):
        self.path = path
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ValueError("not a PE image")
        pe = u32(self.data, 0x3C)
        if self.data[pe:pe + 4] != b"PE\0\0":
            raise ValueError("invalid PE signature")
        section_count = u16(self.data, pe + 6)
        optional = pe + 24
        if u16(self.data, optional) != 0x20B:
            raise ValueError("expected PE32+")
        self.base = u64(self.data, optional + 24)
        first_section = optional + u16(self.data, pe + 20)
        self.sections = []
        self._pdata_starts = None
        self._pdata_raw = None
        for i in range(section_count):
            pos = first_section + 40 * i
            name = self.data[pos:pos + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from("<IIII", self.data, pos + 8)
            if raw_offset + raw_size > len(self.data):
                raise ValueError(f"section {name} exceeds file")
            self.sections.append((name, rva, virtual_size, raw_offset, raw_size))

    def file_to_va(self, pos):
        for _, rva, _, raw, size in self.sections:
            if raw <= pos < raw + size:
                return self.base + rva + pos - raw
        return None

    def va_to_file(self, va):
        rva = va - self.base
        for _, section_rva, _, raw, size in self.sections:
            if section_rva <= rva < section_rva + size:
                return raw + rva - section_rva
        return None

    def section_at(self, pos):
        for name, _, _, raw, size in self.sections:
            if raw <= pos < raw + size:
                return name
        return None

    def unwind_bounds(self, va):
        section = next((s for s in self.sections if s[0] == ".pdata"), None)
        if section is None:
            return None
        _, _, virtual_size, raw, _ = section
        if self._pdata_starts is None:
            self._pdata_raw = raw
            self._pdata_starts = [u32(self.data, pos) for pos in range(raw, raw + virtual_size - 11, 12)]
        starts = self._pdata_starts
        rva = va - self.base
        idx = bisect.bisect_right(starts, rva) - 1
        if idx < 0:
            return None
        start, end, _ = struct.unpack_from("<III", self.data, raw + idx * 12)
        if not start <= rva < end:
            return None
        return [hex(self.base + start), hex(self.base + end)]


def locate_modules(pe, image_name):
    name_bytes = image_name.encode("ascii") + b"\0"
    names = []
    pos = 0
    while (pos := pe.data.find(name_bytes, pos)) >= 0:
        names.append(pos)
        pos += 1
    candidates = []
    for name_file in names:
        name_va = pe.file_to_va(name_file)
        if name_va is None:
            continue
        needle = struct.pack("<Q", name_va)
        pos = 0
        while (pos := pe.data.find(needle, pos)) >= 0:
            ptr_count, ptr_va = struct.unpack_from("<QQ", pe.data, pos + 8)
            ptr_file = pe.va_to_file(ptr_va)
            if 1 <= ptr_count <= 100_000 and ptr_file is not None and ptr_file + ptr_count * 8 <= len(pe.data):
                first_ptr = u64(pe.data, ptr_file)
                candidates.append({"module_file": pos, "module_va": pe.file_to_va(pos),
                                   "module_section": pe.section_at(pos), "name_file": name_file,
                                   "name_va": name_va, "pointer_count": ptr_count,
                                   "pointers_file": ptr_file, "pointers_va": ptr_va,
                                   "first_pointer_va": first_ptr,
                                   "first_pointer_file": pe.va_to_file(first_ptr)})
            pos += 1
    return candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binary", type=Path)
    ap.add_argument("--image", default="Assembly-CSharp.dll")
    ap.add_argument("--metadata-types", type=Path)
    ap.add_argument("--type-pattern", default="Beach|Ground|Water|Shovel|Brush|Compute|Readback")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    pe = PE(args.binary)
    modules = locate_modules(pe, args.image)
    result = {"source": str(args.binary), "size": len(pe.data), "image_base": hex(pe.base),
              "sections": [{"name": s[0], "rva": hex(s[1]), "raw_offset": hex(s[3]),
                            "raw_size": s[4]} for s in pe.sections], "modules": modules}
    if args.metadata_types:
        import re
        types = json.loads(args.metadata_types.read_text(encoding="utf-8"))["types"]
        selection = re.compile(args.type_pattern, re.I)
        if len(modules) == 1:
            module = modules[0]
            table = module["pointers_file"]
            methods = []
            for typ in types:
                if not selection.search(typ["name"]):
                    continue
                for method in typ["methods"]:
                    rid = method["token"] & 0xFFFFFF
                    if method["token"] >> 24 != 6 or rid < 1 or rid > module["pointer_count"]:
                        continue
                    pointer_va = u64(pe.data, table + (rid - 1) * 8)
                    methods.append({"type": typ["name"], "method": method["name"],
                                    "token": hex(method["token"]), "rid": rid,
                                    "pointer_va": hex(pointer_va),
                                    "pointer_file": pe.va_to_file(pointer_va),
                                    "pointer_section": pe.section_at(pe.va_to_file(pointer_va)) if pe.va_to_file(pointer_va) is not None else None,
                                    "unwind_entry_range": pe.unwind_bounds(pointer_va) if pointer_va else None})
            result["selected_methods"] = methods
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {len(modules)} module candidates to {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
