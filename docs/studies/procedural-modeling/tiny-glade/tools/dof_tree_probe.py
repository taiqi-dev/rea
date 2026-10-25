"""Check selected Tiny Glade depth-of-field and tree see-through evidence.

Reads this study's PE and word-count-prefixed SPIR-V only. No target execution,
asset export, private configuration, digest, Unity access or provider claim.
This is a version-specific evidence reader, not a renderer implementation.
"""

import argparse
import json
from pathlib import Path
import struct
import sys

from atlas_budget_probe import PeReader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from spirv_probe import decode_module


def modules(path, grammar):
    blob = path.read_bytes()
    result, position = [], 0
    while True:
        offset = blob.find(b'\x03\x02\x23\x07', position)
        if offset < 0:
            break
        if offset < 4:
            raise ValueError('No preceding module length')
        count = struct.unpack_from('<I', blob, offset - 4)[0]
        if count < 5 or offset + count * 4 > len(blob):
            raise ValueError('Module exceeds selected file')
        result.append(decode_module(blob, offset, count, grammar))
        position = offset + count * 4
    if not result:
        raise ValueError('No supported module')
    return result


def anchor(module, word, operation, operands=None):
    rows = [r for r in module['instructions'] if r['word_offset'] == word]
    if len(rows) != 1 or rows[0]['op'] != operation:
        raise ValueError(f'Changed operation at word {word}')
    row = rows[0]
    if operands is not None and row['operands'] != operands:
        raise ValueError(f'Changed operands at word {word}')
    return {'word': word, 'file_offset': hex(row['file_offset']),
            'operation': operation, 'operands': row['operands']}


def frame_accesses(module):
    roots = {int(k) for k, v in module['names'].items() if v == 'frame_constants'}
    indices = set()
    for row in module['instructions']:
        if row['op'] in ('OpAccessChain', 'OpInBoundsAccessChain'):
            args = row['operands']
            if args[2] in roots:
                scalar = module['constants'].get(str(args[3]))
                if scalar:
                    indices.add(scalar['value'])
    fields = {}
    for row in module['member_names']:
        if row['member'] in indices and row['name'] in (
                'render_overrides', 'is_firstperson_mode',
                'tree_canopy_cone_angle_mult', 'tree_canopy_max_cone_cull_dist_range'):
            fields[row['member']] = row['name']
    return fields


def inspect(root, grammar_path):
    root = root.resolve(strict=True)
    pe = PeReader(root / 'tiny-glade.exe')
    grammar_data = json.loads(grammar_path.read_text(encoding='utf-8'))
    grammar = {row['opcode']: row for row in grammar_data['instructions']}
    inputs = {
        'focus': 'country-core/compiled/dof/calc_autofocus.precomp',
        'coc': 'country-core/compiled/dof/prepare.precomp',
        'canopy': 'country-core/compiled/clearing/tree_canopy.precomp',
        'trunk': 'country-core/compiled/clearing/tree_trunk.precomp',
        'brick': 'country-core/compiled/wall/wall_brick_lod0.precomp',
    }
    decoded = {name: modules(root / 'compiled-shaders' / path, grammar)
               for name, path in inputs.items()}
    coc = decoded['coc'][0]
    proofs = {
        'coc_transition_min': anchor(coc, 2226, 'OpExtInst',
                                     [6, 569, 72, 37, 379, 568]),
        'coc_sign_negation': anchor(coc, 2385, 'OpFNegate', [6, 597, 717]),
        'canopy_conical_demote': anchor(decoded['canopy'][1], 3230,
                                        'OpDemoteToHelperInvocation'),
        'canopy_texture_demote': anchor(decoded['canopy'][1], 3550,
                                        'OpDemoteToHelperInvocation'),
        'trunk_conical_demote': anchor(decoded['trunk'][1], 5052,
                                       'OpDemoteToHelperInvocation'),
        'trunk_height_smoothstep': anchor(decoded['trunk'][1], 2131,
                                          'OpExtInst', [10, 126, 127, 49, 128, 129, 124]),
        'canopy_unpack_half': anchor(decoded['canopy'][0], 2386,
                                     'OpExtInst', [10, 1429, 171, 62, 153]),
        'trunk_unpack_half': anchor(decoded['trunk'][0], 1907,
                                    'OpExtInst', [14, 641, 109, 62, 87]),
    }
    for identifier, expected in ((379, .01), (377, .05)):
        value = coc['constants'][str(identifier)]['value']
        if abs(value - expected) > 1e-8:
            raise ValueError('Changed CoC transition constant')
    calls = []
    for address, target in ((0x1400FBC1B, 0x140B38410),
                             (0x1400FC598, 0x140B04C70),
                             (0x1400FC6F5, 0x140CD3700)):
        raw = pe.read(address, 5)
        if raw[0] != 0xE8 or address + 5 + struct.unpack_from('<i', raw, 1)[0] != target:
            raise ValueError('Changed selected render-world call')
        calls.append({'call': hex(address), 'target': hex(target)})
    for address, expected in ((0x14288EAEA, '894720'),
                              (0x1409263CA, 'f3440f118938010000'),
                              (0x1409263DB, 'f30f11813c010000')):
        if pe.read(address, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f'Changed selected write at {address:#x}')
    mode_table = 0x1435AB888
    selected_modes = {}
    for tag, expected in ((4, 0x14288E467), (12, 0x14288E478)):
        target = mode_table + struct.unpack('<i', pe.read(mode_table + tag * 4, 4))[0]
        if target != expected:
            raise ValueError('Changed selected handplaced-tree mode branch')
        selected_modes[tag] = hex(target)
    if pe.read(0x14288E467, 4).hex() != '80780106':
        raise ValueError('Changed selected tree-layer check')
    return {
        'root': str(root), 'binary_bytes': len(pe.data),
        'evidence_kind': 'ordinary file/SSA reads, not runtime or REA Evidence',
        'module_extents': {name: [{'offset': m['offset'], 'words': m['word_count']}
                                  for m in ms] for name, ms in decoded.items()},
        'anchors': proofs, 'selected_render_world_calls': calls,
        'selected_handplaced_mode_targets': selected_modes,
        'actual_selected_frame_accesses': {
            name: frame_accesses(decoded[name][1]) for name in ('canopy', 'trunk', 'brick')},
        'constructed_fade_example': {'s': .2, 'increment': .1,
                                     'advanced': .3, 'ease_out_quad': 1 - (1 - .3) ** 2},
        'limitations': ['Not SPIR-V semantic validation or GPU execution',
                        'No complete schedule, all-material or all-mode coverage',
                        'No visibility hysteresis or runtime latency proven'],
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
    print(json.dumps({'inputs': 5, 'modules': sum(len(x) for x in result['module_extents'].values()),
                      'anchors': len(result['anchors']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
