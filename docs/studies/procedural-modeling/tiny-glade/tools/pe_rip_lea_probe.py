"""Find candidate x64 RIP-relative LEA references; verify instruction boundaries.

Reads one file-backed .text section. It does not execute code or calculate digests.
Only REX.W 8D /r with mod=00,r/m=101 is searched; other reference forms are outside coverage.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


def inspect(binary, targets):
    pe = PeReader(binary)
    sections = [s for s in pe.sections if s[0] == '.text']
    if len(sections) != 1:
        raise ValueError('Expected exactly one .text section')
    _, rva, size, raw = sections[0]
    body = pe.data[raw:raw+size]
    matches = {hex(t): [] for t in sorted(targets)}
    for i in range(len(body)-6):
        if body[i] not in (0x48, 0x4c) or body[i+1] != 0x8d or body[i+2] & 0xc7 != 0x05:
            continue
        va = pe.base+rva+i
        target = va+7+struct.unpack_from('<i', body, i+3)[0]
        if target in targets:
            matches[hex(target)].append(hex(va))
    return {'binary': str(pe.path), 'binary_bytes': len(pe.data),
            'text_va': hex(pe.base+rva), 'text_bytes_examined': len(body),
            'coverage': 'candidate REX.W RIP-relative LEA bytes; disassembly boundary check required',
            'matches': matches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('va', nargs='+', type=lambda s: int(s, 0))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f'Output already exists: {args.output}')
    result = inspect(args.binary, set(args.va))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: len(v) for k, v in result['matches'].items()}))


if __name__ == '__main__':
    main()
