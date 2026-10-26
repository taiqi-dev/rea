"""Check selected Tiny Glade focus readback PE and SPIR-V evidence.

Version-specific ordinary-file inspection only; no target execution, private
configuration, digest calculation, provider access, or asset export.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader
from dof_tree_probe import modules, anchor


def inspect(root, grammar_path):
    root = root.resolve(strict=True)
    pe = PeReader(root / 'tiny-glade.exe')
    checks = {
        0x14298F552: '4883781000',  # mapped element count
        0x14298F560: '488b7808',  # mapped data pointer
        0x14298F564: '8b5f0c',  # response
        0x14298F584: '83f902',  # selector < 2
        0x14298F589: '39f3',  # response vs current mode
        0x14298F58E: '85db',  # reject zero response
        0x14298F5A4: '897004',  # request mode
        0x14298F5C3: 'c70001000000',
        0x14298F5D0: '48894804',
        0x14298F5DA: '89480c',
        0x141543B60: '4531c0',  # no initial data
        0x141B1A5B9: 'bb10000000',
        0x141B1A5C3: 'ba04000000',
        0x141B1A5E4: 'b910000000',  # 16-byte GPU buffer
        0x141B1A67F: '488b5848',  # mapped pointer from Buffer cold
        0x141B1A6BE: '48893e',
        0x141B1A6C1: '48895e08',
        0x141B1A6C5: '4c897610',
        0x140B38A9C: 'e83f1e9f00',
        0x140B38BDF: 'e81ce69f00',
        0x140B7F795: 'e8a6439c00',
        0x140BDCF2C: '4c8b7610',
        0x140BDCFE4: 'c7040803000000',
    }
    for va, expected in checks.items():
        if pe.read(va, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f'Changed instruction at {va:#x}')

    def rip(va):
        raw = pe.read(va, 7)
        if raw[0] not in (0x48, 0x4c) or raw[1] != 0x8d:
            raise ValueError(f'Expected selected RIP lea at {va:#x}')
        return va + 7 + struct.unpack_from('<i', raw, 3)[0]

    keys = {}
    for label, va in [('ui_lookup_key', 0x14298F523), ('rg_lookup_key', 0x14152A902)]:
        address = rip(va)
        keys[label] = {'va': hex(address), 'existing_u64_literal': hex(struct.unpack('<Q', pe.read(address, 8))[0])}
    if {row['existing_u64_literal'] for row in keys.values()} != {'0x29faa4608bf58d67'}:
        raise ValueError('UI and typed RG paths use different selected SsboId')
    strings = {}
    for label, va, size in [('registered_type_name', 0x141543B94, 0x57),
                            ('gpu_buffer_label', 0x141B1A623, 0x14)]:
        address = rip(va)
        strings[label] = {'va': hex(address),
                          'bytes': pe.read(address, size).decode('ascii')}
    tables = {}
    for label, va, size in [('storage_dyn', rip(0x141543BAB), 56),
                            ('mapped_any', 0x14338EA58, 32)]:
        tables[label] = {'va': hex(va), 'slots': [hex(x) for x in
                          struct.unpack('<' + 'Q'*(size//8), pe.read(va, size))]}
    if tables['storage_dyn']['slots'][3] != '0x141b1d960' or tables['mapped_any']['slots'][3] != '0x141b1dc80':
        raise ValueError('Changed typed mapped-storage vtables')
    callers = []
    for name, rva, length, raw in pe.sections:
        if name != '.text':
            continue
        for index in range(length - 4):
            if pe.data[raw + index] == 0xe8:
                address = pe.base + rva + index
                target = address + 5 + struct.unpack_from('<i', pe.data, raw + index + 1)[0]
                if target == 0x141543B40:
                    callers.append(hex(address))
    grammar_data = json.loads(grammar_path.read_text(encoding='utf-8'))
    grammar = {row['opcode']: row for row in grammar_data['instructions']}
    shader = modules(root / 'compiled-shaders/country-core/compiled/dof/calc_autofocus.precomp', grammar)[0]
    if shader['offset'] != 108 or shader['word_count'] != 4387:
        raise ValueError('Changed selected module extent')
    proofs = [anchor(shader, w, op, args) for w, op, args in [
        (1943, 'OpTypeStruct', [859, 7, 8]),
        (1529, 'OpMemberDecorate', [859, 0, 35, 0]),
        (1534, 'OpMemberDecorate', [859, 1, 35, 12]),
        (1551, 'OpDecorate', [865, 33, 3]),
        (2072, 'OpAccessChain', [113, 124, 122, 123]),
        (3592, 'OpAccessChain', [113, 617, 242, 148]),
        (3601, 'OpIEqual', [90, 619, 618, 125]),
        (3609, 'OpBranchConditional', [619, 45, 46]),
        (3805, 'OpPhi', [7, 1725, 157, 44, 1338, 45]),
        (4361, 'OpAccessChain', [154, 1504, 865, 112, 112, 112]),
        (4368, 'OpStore', [1504, 1725]),
        (4371, 'OpAccessChain', [113, 1506, 865, 112, 112, 138]),
        (4378, 'OpStore', [1506, 618]),
    ]]
    examples = []
    for selector, mode, response in [(0, 3, 0), (0, 3, 2), (0, 3, 3),
                                      (1, 3, 2), (3, 3, 3)]:
        accepts = selector < 2 and response != 0 and response == mode
        requests = selector == 0 and not (response != 0 and response == mode)
        examples.append({'selector': selector, 'mode': mode, 'response': response,
                         'accepts_in_selected_branch': accepts,
                         'requests_in_selected_branch': requests})
    return {'binary': str(pe.path), 'binary_bytes': len(pe.data),
            'evidence_kind': 'ordinary-file PE/SPIR-V; not REA Evidence or runtime',
            'pe_instruction_checks': len(checks), 'keys': keys, 'strings': strings,
            'unvalidated_direct_call_candidates_to_add_new': callers,
            'vtables': tables, 'shader_proofs': proofs,
            'shader_member_names': [row for row in shader['member_names']
                                    if row['type_id'] == 859 or
                                    (row['type_id'] == 119 and row['member'] == 18)],
            'examples': examples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('grammar', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.root, args.grammar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'checks': result['pe_instruction_checks'],
                      'shader_proofs': len(result['shader_proofs'])}))


if __name__ == '__main__':
    main()
