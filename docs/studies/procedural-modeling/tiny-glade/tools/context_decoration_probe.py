"""Read selected Tiny Glade contextual-decoration PE/SPIR-V anchors.

Ordinary static-file evidence only. No execution of target code, game assets
export, private data, digest calculation, process attachment or provider claim.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader
from dof_tree_probe import modules, anchor


ANCHORS = {
    'bush_grid_90': (0x140B32B2E, '49be5a0000005a000000'),
    'flower_grid_150': (0x140B32BF2, '49bf9600000096000000'),
    'lilypad_grid_225': (0x140B31A5D, '49bee1000000e1000000'),
    'reed_grid_150': (0x140B31B44, '49be9600000096000000'),
    'candidate_stride_152': (0x1428EA1D2, '4869572898000000'),
    'candidate_raw6_overlap_exception': (0x1428EA311, '42807c363006'),
    'accepted_stride_104': (0x1428EA4B0, '486bce68'),
    'accepted_length_write': (0x1428EA504, '48897758'),
    'manager_same_request_pointer': (0x1428EAF22, '488b5150'),
    'manager_same_request_stride': (0x1428EAF26, '4c6b415868'),
    'old_candidate_swap_length': (0x1410D0801, '4c896e28'),
    'pending_removal_clear': (0x1410D0939, '48c7464000000000'),
    'sort_u64_descending': (0x14219EF25, '4c3948f0'),
    'sort_u32_descending': (0x14219EF32, '4439d6'),
    'gate_two_regions': (0x1428E8B23, '4983ff02'),
    'lantern_five_attempts': (0x1428EFF13, '4983fd05'),
    'lantern_kind_4_or_5': (0x1428EFDEC, '8b48a083e1fe83f904'),
    'lantern_reject_zero_sample': (0x1428EFFEC, '410f2ec6'),
    'lantern_request_append': (0x1428EFEFF, '49895858'),
    'cpu_non_grass_reject': (0x1428DECB4, '84c0751c'),
}

CALLS = {
    'render_water_raster': (0x1400FA145, 0x140B31C80),
    'render_water_vegetation': (0x1400FA244, 0x140B31710),
    'render_building_vegetation': (0x1400FA24F, 0x140B32850),
    'render_bush_readback': (0x1400FA25A, 0x140B325D0),
    'gate_register_region': (0x1428E8B17, 0x1410CFF30),
    'region_old_cells': (0x1410D01F7, 0x1421A65F0),
    'region_new_cells': (0x1410D02D0, 0x1421A6BD0),
    'populate_take_dirty': (0x1428DC0A7, 0x14147FE80),
    'populate_extend_dirty': (0x1428DC0DD, 0x140A83F50),
    'populate_iter_dirty': (0x1428DC169, 0x1421A63D0),
    'process_overlap': (0x1428EA33B, 0x140DF3F80),
    'manager_reserve_entity': (0x1428EC251, 0x140ED5970),
    'cpu_non_grass_query': (0x1428DECAE, 0x140A85320),
    'lantern_transform': (0x1428EFE4A, 0x140C45EC0),
    'lantern_owner_seed': (0x1428EFE77, 0x140DEDFE0),
    'lantern_circle_position': (0x1428EFF87, 0x140DEF2C0),
    'lantern_mask_sample': (0x1428EFFE7, 0x140A7D8D0),
}

LEAS = {
    'old_entity_delete_marker': (0x1428EB877, 0x1428D9330),
    'spawn_autoclutter': (0x1428EC283, 0x1428D96C0),
    'insert_plant_bundle': (0x1428EC70A, 0x1428D9720),
    'insert_uber_bundle': (0x1428EC7BA, 0x1428D9200),
}


def inspect(root, grammar_path):
    pe = PeReader(root / 'tiny-glade.exe')
    if pe.base != 0x140000000 or len(pe.data) != 65612184:
        raise ValueError('Unexpected PE identity')
    if (root / 'tiny_glade.pdb').stat().st_size != 310513664:
        raise ValueError('Unexpected PDB length')
    anchors, calls, leas = [], [], []
    for name, (va, expected) in ANCHORS.items():
        if pe.read(va, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f'Changed native anchor {name} at {va:#x}')
        offset, section = pe.locate(va, len(bytes.fromhex(expected)))
        anchors.append({'name': name, 'va': hex(va), 'file_offset': hex(offset), 'section': section})
    for name, (va, expected) in CALLS.items():
        raw = pe.read(va, 5)
        target = va+5+struct.unpack_from('<i', raw, 1)[0]
        if raw[0] != 0xE8 or target != expected:
            raise ValueError(f'Changed call {name}: {target:#x}')
        calls.append({'name': name, 'va': hex(va), 'target': hex(target)})
    for name, (va, expected) in LEAS.items():
        raw = pe.read(va, 7)
        target = va+7+struct.unpack_from('<i', raw, 3)[0]
        if raw[:2] != b'\x48\x8d' or target != expected:
            raise ValueError(f'Changed command callback {name}')
        leas.append({'name': name, 'va': hex(va), 'target': hex(target)})
    literals = {0x1435B22C0: 'gate_right', 0x1435B22CA: 'gate_left', 0x1435B2F00: 'lantern',
                0x143331D33: 'country_core/garden/spawn_bushes_buildings:main',
                0x143331B42: 'country_core/garden/spawn_flowers_buildings:main',
                0x143331B1C: 'country_core/water/spawn_lilypads:main'}
    for va, literal in literals.items():
        if pe.read(va, len(literal)) != literal.encode('ascii'):
            raise ValueError(f'Changed literal at {va:#x}')
    grammar = {r['opcode']: r for r in json.loads(grammar_path.read_text(encoding='utf-8'))['instructions']}
    selected = {
        'water/spawn_reeds.precomp': [(3204, [6, 659, 658, 361, 357, 361])],
        'water/spawn_lilypads.precomp': [(7068, [6, 793, 792, 409, 405, 409]),
                                         (7340, [6, 884, 883, 409, 405, 409])],
        'garden/spawn_bushes_buildings.precomp': [(4949, [9, 952, 951, 552, 392, 552]),
                                                 (5226, [9, 1044, 1043, 552, 392, 552])],
        'garden/spawn_flowers_buildings.precomp': [(4261, [17, 1322, 1321, 600, 410, 600]),
                                                  (7115, [17, 2285, 2284, 600, 410, 600])],
    }
    shaders = {}
    for name, atomics in selected.items():
        module = modules(root / 'compiled-shaders/country-core/compiled' / name, grammar)[0]
        shaders[name] = [anchor(module, word, 'OpAtomicIAdd', args) for word, args in atomics]
        if name == 'water/spawn_reeds.precomp':
            by_offset = {r['file_offset']: r for r in module['instructions']}
            expected = {0x298A: ('OpFOrdGreaterThan', [10, 454, 927, 248]),
                        0x299E: ('OpFOrdGreaterThan', [10, 455, 1525, 456]),
                        0x29C6: ('OpFOrdLessThan', [10, 458, 264, 459])}
            for offset, (op, args) in expected.items():
                row = by_offset[offset]
                if row['op'] != op or row['operands'] != args:
                    raise ValueError('Changed selected reed acceptance predicates')
    # Constructed arithmetic only, independent inputs; never target invocation.
    weights, u = [1.0, 2.0, 1.0], 0.6
    cumulative, chosen = 0.0, None
    for index, weight in enumerate(weights):
        cumulative += weight/sum(weights)
        if cumulative > u:
            chosen = index
            break
    return {'kind': 'ordinary-static-file-evidence', 'binary_bytes': len(pe.data),
            'native_anchors': anchors, 'calls': calls, 'command_callbacks': leas,
            'literal_count': len(literals), 'shader_atomic_anchors': shaders,
            'constructed_weighted_choice': {'weights': weights, 'u': u, 'chosen_index': chosen},
            'runtime': 'Not Run', 'limits': ['No complete environmental filter recovered',
                'No observed ECS schedule, graph execution, visible object count or pixel',
                'No final despawn after ClutterMarkedForDeletion proven',
                'Lantern input-grid identity not named from shared deref alias']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--grammar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.root.resolve(strict=True), args.grammar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'native_anchors': len(result['native_anchors']), 'calls': len(result['calls']),
                      'command_callbacks': len(result['command_callbacks']),
                      'shader_atomic_anchors': sum(map(len, result['shader_atomic_anchors'].values()))}))


if __name__ == '__main__':
    main()
