"""Verify selected autofocus producers, tree settings and depth-record evidence.

Version-specific ordinary-file reader. Resource keys below are existing program
TypeId literals, not content digests. No target code executes and no game asset,
private save/configuration or Unity project is exported or modified.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader
from dof_tree_probe import modules


def require(pe, address, expected):
    raw = bytes.fromhex(expected)
    if pe.read(address, len(raw)) != raw:
        raise ValueError(f'Changed instruction at {address:#x}')


def key_literal(pe, address):
    raw = pe.read(address, 8)
    if raw[:3] != bytes.fromhex('660f6f') or raw[3] & 0xC7 != 5:
        raise ValueError('Expected selected RIP-relative MOVDQA')
    target = address + 8 + struct.unpack_from('<i', raw, 4)[0]
    return target, pe.read(target, 16)


def string_literal(pe, address, length):
    raw = pe.read(address, 7)
    if raw[:3] != bytes.fromhex('488d15'):
        raise ValueError('Expected selected RIP-relative LEA RDX')
    target = address + 7 + struct.unpack_from('<i', raw, 3)[0]
    return pe.read(target, length).decode('ascii')


def float_literal(pe, address, opcode):
    prefix = bytes.fromhex(opcode)
    raw = pe.read(address, len(prefix) + 4)
    if raw[:len(prefix)] != prefix:
        raise ValueError('Changed selected scalar RIP instruction')
    target = address + len(raw) + struct.unpack_from('<i', raw, len(prefix))[0]
    return struct.unpack('<f', pe.read(target, 4))[0]


def inspect(root, grammar_path):
    root = root.resolve(strict=True)
    pe = PeReader(root / 'tiny-glade.exe')
    identities = []
    for name, insertion, lookup in (
        ('MainCamera', 0x14028762A, 0x140B3861E),
        ('AppMode', 0x141901338, 0x140B38470),
        ('WindowSize', 0x14028FD3D, 0x140B38555),
        ('CursorPositionSS', 0x141905C6C, 0x140B388B9),
        ('PhotomodeState', 0x1402970C8, 0x140B38749),
    ):
        left_address, left = key_literal(pe, insertion)
        right_address, right = key_literal(pe, lookup)
        if left != right:
            raise ValueError(f'Resource identity mismatch: {name}')
        identities.append({'type': name, 'typed_insert_instruction': hex(insertion),
                           'lookup_instruction': hex(lookup),
                           'insert_literal_va': hex(left_address),
                           'lookup_literal_va': hex(right_address),
                           'stored_type_id_bytes': left.hex()})
    require(pe, 0x140A36620, '0fb681d0040000c3')
    lens = struct.unpack('<6Q', pe.read(0x14303B4D0, 48))
    focus = struct.unpack('<6Q', pe.read(0x14303B500, 48))
    focus_used = struct.unpack('<6Q', pe.read(0x143058CA8, 48))
    lens_used = struct.unpack('<6Q', pe.read(0x143058CD8, 48))
    if tuple(x + 0x100 for x in focus) != focus_used or lens != lens_used:
        raise ValueError('Getter and autofocus selection tables differ')
    if struct.unpack('<6Q', pe.read(0x143021840, 48)) != lens:
        raise ValueError('Frame FOV and camera lens selection tables differ')
    require(pe, 0x140A36615, '480500010000')
    require(pe, 0x140A368E5, '480500010000')

    fields = [
        (0x14052CD75, 7, 'grading'),
        (0x14052CDB3, 11, 'camera_lens'),
        (0x14052CDDA, 8, 'artistic'),
        (0x14052CB35, 13, 'lighting_only'),
        (0x14052CB72, 13, 'tree_see_thru'),
    ]
    for address, length, expected in fields:
        if string_literal(pe, address, length) != expected:
            raise ValueError('Changed serializer field')
    require(pe, 0x14052CB6F, '48ffc6')
    require(pe, 0x140925DE9, '4183cf02')
    require(pe, 0x140925DF7, '80bdd811000010')
    require(pe, 0x140925E11, '3c03')
    require(pe, 0x141A2E5B0, 'f30f114908f30f114904c3')
    range_constants = {
        'distance_multiplier': float_literal(pe, 0x140925D4C, 'f3440f5915'),
        'degrees_to_radians': float_literal(pe, 0x1409260EE, 'f3440f590d'),
        'half_angle': float_literal(pe, 0x1409260F7, 'f30f1005'),
        'minimum_half_angle': float_literal(pe, 0x1409263A8, 'f3440f5f0d'),
        'cone_multiplier': float_literal(pe, 0x1409263B1, 'f3440f590d'),
    }
    for key, expected in (('distance_multiplier', 30), ('degrees_to_radians', .0174532925),
                          ('half_angle', .5), ('minimum_half_angle', .07), ('cone_multiplier', .8)):
        if abs(range_constants[key] - expected) > 1e-6:
            raise ValueError('Changed selected tree cone constant')

    anchors = {
        0x1409ACB0A: '4d8d7818',          # depth pointer = G-buffer struct + 24
        0x1409ACB5B: '4c897d78',          # depth attachment parameter
        0x1400FA9EA: 'f30f7f85c8070000',  # copied input D into struct + 24
        0x140B3843C: '4c89442440',        # preserve autofocus depth pointer
        0x140BDCCE2: '488b39',            # autofocus binder input depth
        0x140B04C99: '4c89cb',            # preserve CoC depth pointer
        0x140B04FFD: '48899c2428010000',  # put it at shader argument + 8
        0x141B041AC: '488b7908',          # CoC binder reads that + 8
    }
    for address, expected in anchors.items():
        require(pe, address, expected)
    grammar_data = json.loads(grammar_path.read_text(encoding='utf-8'))
    grammar = {row['opcode']: row for row in grammar_data['instructions']}
    bindings = []
    for relative in ('dof/calc_autofocus.precomp', 'dof/prepare.precomp'):
        path = root / 'compiled-shaders/country-core/compiled' / relative
        module = modules(path, grammar)[0]
        ids = [int(k) for k, v in module['names'].items() if v == 'depth_tex']
        if len(ids) != 1:
            raise ValueError('Expected a unique depth_tex')
        rows = [r['operands'] for r in module['instructions']
                if r['op'] == 'OpDecorate' and r['operands'][0] == ids[0]]
        if [ids[0], 33, 1] not in rows or [ids[0], 34, 0] not in rows:
            raise ValueError('Changed depth binding')
        bindings.append({'shader': relative, 'offset': module['offset'],
                         'words': module['word_count'], 'depth_set': 0, 'depth_binding': 1})
    return {
        'root': str(root), 'binary_bytes': len(pe.data),
        'evidence_kind': 'ordinary static file evidence, not REA Evidence or runtime',
        'resource_type_literal_matches': identities,
        'camera_offsets_measured_tags_0_through_5': [
            {'tag': i, 'focus_base': focus_used[i], 'lens_base': lens[i] + 0x100,
             'aperture': lens_used[i] + 0x118, 'tilt_shift': lens_used[i] + 0x128}
            for i in range(6)],
        'serializer_keys': [row[2] for row in fields],
        'tree_cone_constants': range_constants,
        'depth_instruction_anchors': [hex(a) for a in anchors],
        'shader_bindings': bindings,
        'constructed_examples_not_runtime': {
            'configured_point_uv': [.5 + .5 * .8 / (1920 / 1080), .5 - .5 * .4],
            'cursor_point_uv': [(399.5 + .5) / 800, (299.5 + .5) / 600],
        },
        'limitations': ['PDB names supply typed-insert identity; this reader checks its bytes',
                        'Not a proof that intervening passes preserve resource versions',
                        'No live settings, shader execution, GPU binding or frame timing'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--grammar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.root, args.grammar)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'resource_pairs': len(result['resource_type_literal_matches']),
                      'bindings': len(result['shader_bindings']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
