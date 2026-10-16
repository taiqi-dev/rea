"""Read measured RoofTile sparse-pool producers and material dispatch from one PE.

Version-specific instruction anchors and stored constants, not target execution.
No digest is computed. Physical GPU allocation and frame ordering remain unobserved.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


def inspect(binary):
    pe = PeReader(binary)
    anchors = {
        0x141a78824: '48c7465000000100',  # pool initial element capacity
        0x141a78878: '48c7467808000000',  # allocated shadow pages
        0x141a784d4: 'ba8000000031c9',    # fixed page table length
        0x141b0e5af: 'b900004000',        # initial GPU byte request
        0x141f46a2e: '4c8d4378',          # writer aliases pool page count
        0x141f46a54: '4c894528',          # writer base rbp-10, field +38
        0x141f4a11d: '488b4638488945c0488b00',
        0x141f4a128: '488d3c00',          # candidate pages = 2*old
        0x141f4a12c: '4c8b46304939f8490f42f8',
        0x141f4a32c: '488938',            # writes aliased page count
        0x141f488e4: '498b4d784889cf48c1e70d',
        0x141f488f3: '493b7d50',          # candidate capacity > old capacity
        0x141f488fd: '48c1e113',          # byte request = pages << 19
        0x141f48a75: '49894500',          # replaces raw handle
        0x141f48a79: '49897d50',          # capacity field store
        0x14095e13a: '48894808',          # external descriptor callback
        0x14095dc04: '488b00',            # external getter reads current raw
        0x1409e5aa4: '803d3dd22c03007520',
        0x1409e5ab4: '80bd3801000001',
        0x1409e5abb: '7717',              # kind > 1 skips fine
        0x1409e5b40: '48894570',          # callback stored for spawned drawable
        0x1409e5b56: '888580000000',      # kind stored alongside
        0x1409e6b18: '41ff5008',          # material reads external descriptor
        0x1409e75ef: '41b001',            # material binding set index 1
        0x141563b4d: '4c8b00',            # first material field goes to read_buf
        0x141563b8c: '4531c9',            # zero byte offset
        0x140963a96: '488901',            # refreshed binding set replaces component
    }
    for address, expected in anchors.items():
        if pe.read(address, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f'Anchor mismatch at {address:#x}')
    u32 = lambda a: struct.unpack('<I', pe.read(a, 4))[0]
    u64 = lambda a: struct.unpack('<Q', pe.read(a, 8))[0]
    initial_capacity = u32(0x141a78828)
    initial_pages = u32(0x141a7887c)
    page_table_length = u32(0x141a784d5)
    initial_bytes = u32(0x141b0e5b0)
    element_shift = pe.read(0x141f488ee, 1)[0]  # last byte of shl rdi,0Dh
    if (initial_capacity, initial_pages, page_table_length, initial_bytes, element_shift) != (65536, 8, 128, 4194304, 13):
        raise ValueError('Unexpected measured pool geometry')
    keys = {hex(a): pe.read(a, 16).hex() for a in (0x14331c898, 0x143432200)}
    if len(set(keys.values())) != 1:
        raise ValueError('Typed lookup and name lookup have different stored keys')
    constructor = u64(0x143032dc0+6*8)
    branch_table = 0x1430330a0
    material_branch = branch_table+struct.unpack('<i', pe.read(branch_table+6*4, 4))[0]
    name_ptr = u64(0x143032f90+6*8)
    name_length = u64(0x143032ea8+6*8)
    if name_length > 256:
        raise ValueError('Unexpected pipeline name length')
    pipeline = pe.read(name_ptr, name_length).decode('ascii')
    if constructor != 0x14095e130 or material_branch != 0x1409e7561 or pipeline != 'country_core/nani_instanced_roof':
        raise ValueError('Unexpected RoofTile dispatch')
    flags = []
    for site in (0x1409e5aa4, 0x1409e5abd):
        target = site+7+struct.unpack('<i', pe.read(site+2, 4))[0]
        try:
            initializer = pe.read(target, 1)[0]
            status = 'file-backed byte; runtime value unknown'
        except ValueError as error:
            initializer = None
            status = str(error)
        flags.append({'load_va': hex(site), 'flag_va': hex(target),
                      'image_initializer': initializer, 'status': status})
    return {'binary': str(pe.path), 'binary_bytes': len(pe.data), 'image_base': hex(pe.base),
            'initial_capacity_elements': initial_capacity, 'initial_allocated_pages': initial_pages,
            'fixed_page_table_length': page_table_length, 'elements_per_page': 1 << element_shift,
            'bytes_per_element': 64, 'initial_gpu_request_bytes': initial_bytes,
            'writer_candidate': 'min(2*allocated_pages, fixed_page_table_length)',
            'flush_candidate_elements': 'allocated_pages << 13',
            'flush_byte_request': 'allocated_pages << 19',
            'stored_lookup_key_literals': keys, 'roof_constructor_callback': hex(constructor),
            'roof_material_branch': hex(material_branch), 'pipeline_name': pipeline,
            'sorting_flags': flags, 'anchors_checked': {hex(k): v for k, v in anchors.items()},
            'limitations': ['Measured constructors and writer/flush branches only; not every possible store.',
                            'Flag image initializers are not runtime values.',
                            'No physical GPU allocation, graph version freshness, or frame execution observed.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f'Output already exists: {args.output}')
    result = inspect(args.binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('initial_capacity_elements', 'initial_allocated_pages', 'fixed_page_table_length', 'pipeline_name')}))


if __name__ == '__main__':
    main()
