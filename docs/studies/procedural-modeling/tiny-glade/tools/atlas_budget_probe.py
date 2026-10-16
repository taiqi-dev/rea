"""Decode this study's measured Tiny Glade subset budget jump table from PE bytes.

This is a version-specific, read-only extractor, not an emulator. It requires
the inspected dispatch/store/enum anchors and rejects unfamiliar branch shapes.
No target code runs, and no digest is calculated.
"""

import argparse
import json
from pathlib import Path
import re
import struct


class PeReader:
    def __init__(self, path):
        self.path = path.resolve(strict=True)
        self.data = self.path.read_bytes()
        if self.data[:2] != b'MZ':
            raise ValueError('Expected PE')
        pe = struct.unpack_from('<I', self.data, 0x3c)[0]
        if self.data[pe:pe+4] != b'PE\0\0' or struct.unpack_from('<H', self.data, pe+24)[0] != 0x20b:
            raise ValueError('Expected PE32+')
        self.base = struct.unpack_from('<Q', self.data, pe+48)[0]
        count = struct.unpack_from('<H', self.data, pe+6)[0]
        section = pe+24+struct.unpack_from('<H', self.data, pe+20)[0]
        self.sections = []
        for index in range(count):
            start = section+index*40
            name = self.data[start:start+8].rstrip(b'\0').decode('ascii')
            virtual, rva, size, raw = struct.unpack_from('<IIII', self.data, start+8)
            if raw+size > len(self.data):
                raise ValueError('Section exceeds file')
            self.sections.append((name, rva, min(virtual, size), raw))

    def locate(self, va, size):
        for name, rva, length, raw in self.sections:
            offset = va-self.base-rva
            if 0 <= offset and offset+size <= length:
                return raw+offset, name
        raise ValueError(f'VA range not file-backed: {va:#x}+{size}')

    def read(self, va, size):
        offset, _ = self.locate(va, size)
        return self.data[offset:offset+size]


def inspect(binary, ron):
    pe = PeReader(binary)
    anchors = {
        0x1409d3a40: '488954c5a0',       # indexed stack table write
        0x1409d2d73: '488b84c158120000', # subset_capacity getter
        0x1409d2fec: '4c898cc658120000', # apply_grown_capacity writer
        0x1409d2faf: 'b900001000',       # default limit
        0x1409d2fb4: 'babfd1ff0f',       # per-kind table mask
        0x1409d3046: 'ba40280000',       # kinds using the default limit
        0x1409d2fe2: '41f6c13f',         # alignment check
        0x140958ff5: '498d40fc',         # visit_str length dispatch
        0x14095942a: '48b8526f6f6654696c65',
        0x140959439: '66c7013206',       # success payload RoofTile=6
        0x1409d0e19: '488b4050',         # external SSBO field read
        0x1409d0e69: '488984cf58120000', # external-capacity table writer
        0x14195312e: 'b106',             # maintenance passes RoofTile kind
        0x14195302e: '41b858130000',     # typed resource scope copies GpuWorld
    }
    for address, expected in anchors.items():
        if pe.read(address, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f'Anchor mismatch at {address:#x}')
    resource_keys = []
    for instruction in (0x1409e618e, 0x141952f2f):
        raw = pe.read(instruction, 8)
        if raw[:3] != bytes.fromhex('660f6f'):
            raise ValueError('Expected measured RIP-relative resource-key load')
        target = instruction+8+struct.unpack_from('<i', raw, 4)[0]
        resource_keys.append({'instruction_va': hex(instruction), 'constant_va': hex(target),
                              'literal_bytes': pe.read(target, 16).hex()})
    if resource_keys[0]['literal_bytes'] != resource_keys[1]['literal_bytes']:
        raise ValueError('Draw callback and typed GpuWorld resource scope use different keys')
    table = 0x14302dd0c
    records = []
    for index in range(30):
        target = table+struct.unpack('<i', pe.read(table+index*4, 4))[0]
        item = {'subset': index, 'branch_va': hex(target)}
        if index == 29:
            if target != 0x1409d3a5a:
                raise ValueError('Expected termination branch at index 29')
            item['termination'] = True
        elif target == 0x1409d3a40:
            item['initial_capacity'] = 0x800
        else:
            body = pe.read(target, 7)
            if body[0] != 0xba:
                raise ValueError(f'Expected mov edx,imm32 at {target:#x}')
            item['initial_capacity'] = struct.unpack_from('<I', body, 1)[0]
            if body[5] == 0xeb:
                if target+7+struct.unpack_from('<b', body, 6)[0] != 0x1409d3a40:
                    raise ValueError('Unexpected tail branch')
            elif not (target+5 == 0x1409d3a3f and body[5] == 0x90):
                raise ValueError('Unrecognized budget branch shape')
        records.append(item)
    roof = records[6]
    # apply_grown_capacity: first mask selects per-kind table; the second mask
    # selects the already initialized 0x100000 limit when the first bit is clear.
    first_mask, second_mask = 0x0fffd1bf, 0x2840
    if first_mask & (1 << 6) or not second_mask & (1 << 6):
        raise ValueError('Unexpected RoofTile limit branch')
    source = ron.resolve(strict=True).read_text(encoding='utf-8')
    blocks = list(re.finditer(r'subset:\s*RoofTile\s*,\s*meshes:\s*\[(.*?)\]', source, re.S))
    if len(blocks) != 1:
        raise ValueError('Expected exactly one bounded RoofTile RON mesh block')
    block = blocks[0]
    names = re.findall(r'\(\s*name:\s*"([^"\r\n]+)"\s*\)', block.group(1))
    if names != ['roof_tile', 'roof_tile_lod1', 'roof_tile_backface']:
        raise ValueError('Unexpected RoofTile reference inputs')
    offset, section = pe.locate(table, 120)
    return {'binary': str(pe.path), 'binary_bytes': len(pe.data), 'image_base': hex(pe.base),
            'jump_table': {'va': hex(table), 'file_offset': hex(offset), 'section': section,
                           'entry_bytes': 4, 'entries': records},
            'roof_tile': {'subset': 6, 'initial_capacity': roof['initial_capacity'],
                          'apply_grown_capacity_limit': 0x100000, 'required_alignment': 64,
                          'ordinary_kind_ge_2_max_draw_count': 1024,
                          'force_fine_max_draw_count_initial': (roof['initial_capacity']+31)&~31},
            'ron': {'path': str(ron.resolve(strict=True)), 'bytes': ron.stat().st_size,
                    'block_start_line': source[:block.start()].count('\n')+1, 'mesh_names': names},
            'anchors_checked': {hex(k):v for k,v in anchors.items()},
            'recorded_resource_keys': resource_keys,
            'limitations': ['Initialization and selected setter constraints only; no live capacity.',
                            'RON order alone does not prove all runtime atlas indices.',
                            'No graph backing identity or GPU execution observed.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('ron', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.binary, args.ron)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2)
        stream.write('\n')
    print(json.dumps(result['roof_tile']))


if __name__ == '__main__':
    main()
