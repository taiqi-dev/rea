"""Verify selected render-graph ordering and depth-access evidence from PE bytes.

This is a bounded static reader, not a GPU execution or a timing test. It reads
the supplied Tiny Glade image, calculates no content digest and exports no asset.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader
from dof_followup_probe import require


def batches(count, separate):
    """Independent model of the inspected sequential range construction."""
    if not 0 <= count < 65536:
        raise ValueError('Selected u16 node-count range exceeded')
    if not count:
        return []
    return [[i, i + 1] for i in range(count)] if separate else [[0, count]]


def inspect(root):
    pe = PeReader(root.resolve(strict=True) / 'tiny-glade.exe')
    anchors = {
        0x140E29923: '66894138',
        0x140E29BF3: '48c1e104',
        0x140E29C1A: '48897e70',
        0x140E2D4A4: '41b8a0010000',
        0x140588DFB: '0f108550070000',
        0x1405892BD: '0f2885f00c0000',
        0x1405893BA: '4c8d85800b0000',
        0x140E8A8DB: '48894670',
        0x140E8A8DF: '410f1007',
        0x140E8A8E3: '0f114660',
        0x140E89361: '4584ff',
        0x140E89364: '74e6',
        0x140E8934C: '49ffc4',
        0x140103A00: 'e8db60d800',
        0x140103A2B: 'e8c010d600',
        0x140103F53: 'ffd0',
        0x140E89CAC: '41f7c140550100',
        0x140E89CB3: '0f8542010000',
        0x140564271: '4983c268',
        0x140564292: '410f1101',
        0x140564299: '4983c168',
        0x140357915: 'e896afdaff',
        0x14035632B: 'e800f5d4ff',
        0x140E288B2: 'e899cd0100',
        0x140E45782: 'e94927feff',
        0x140E41A73: 'e8c880feff',
    }
    for address, value in anchors.items():
        require(pe, address, value)
    edges = {
        0x140B38BC9: 0x140E28810,
        0x140E288B2: 0x140E45650,
        0x140E45782: 0x140E27ED0,
        0x140E27F31: 0x140E29B40,
        0x140E41A73: 0x140E29B40,
        0x140103A00: 0x140E89AE0,
        0x140103A2B: 0x140E64AF0,
        0x14035632B: 0x1400A5830,
    }
    for address, expected in edges.items():
        opcode = pe.read(address, 1)
        if opcode not in (b'\xe8', b'\xe9'):
            raise ValueError('Selected branch is no longer direct')
        actual = address + 5 + struct.unpack('<i', pe.read(address + 1, 4))[0]
        if actual != expected:
            raise ValueError('Selected direct branch target changed')
    access = {}
    for tag, expected in ((0x19, [0x800, 0x20, 5]),
                          (0x1A, [0x800, 0x20, 4]),
                          (0x30, [0x300, 0x600, 3])):
        values = [struct.unpack('<I', pe.read(base + tag * 4, 4))[0]
                  for base in (0x143220918, 0x143220A1C, 0x143220B20)]
        if values != expected:
            raise ValueError('Selected access table changed')
        access[hex(tag)] = values
    return {'kind': 'ordinary-file-static-check', 'anchors': len(anchors),
            'direct_edges': len(edges), 'depth_access': access,
            'constructed_ranges': {'combined': batches(3, False),
                                   'separate': batches(3, True)},
            'constructed_write_mask': (0x20 | 0x600) & 0x15540,
            'gpu_timing': 'Not Run', 'active_graph_and_pixels': 'Not Run'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.root)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'anchors': result['anchors'],
                      'direct_edges': result['direct_edges']}))


if __name__ == '__main__':
    main()
