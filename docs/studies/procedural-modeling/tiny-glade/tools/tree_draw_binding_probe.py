"""Check the selected Tiny Glade tree instance/buffer/draw static chain.

Version-specific ordinary-file evidence; no target execution, DLL loading,
private settings/saves, asset export, digest calculation or provider claim.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader
from dof_tree_probe import modules, anchor


ANCHORS = {
    'subset_constructor_index': (0x1409E52B6, '89d8c1e003'),
    'subset_constructor_dispatch': (0x1409E52D5, '42ff1410'),
    'subset_output_stride': (0x1409E52DC, '488d049bc1e005'),
    'placement_vtable_store': (0x14095A197, '48894678'),
    'flush_trait_slot': (0x14257D585, '488b4e28488b46304889faff5030'),
    'placement_flush_adjust': (0x140958E10, '4883c118'),
    'buffer_getter': (0x1408FFDC0, '488d4118c3'),
    'material_buffer_trait_slot': (0x1409E6B33, '498b4870498b4078ff5040'),
    'material_buffer_handle_read': (0x1409E6B3E, '488b00'),
    'placement_dense_stride': (0x140955273, '4b8d0c7648c1e104'),
    'placement_copy_last_block': (0x140955286, '410f105424200f11540820'),
    'placement_dirty_min': (0x1409552AA, 'f0490fb14f30'),
    'placement_dirty_max': (0x1409552CA, 'f0490fb14f38'),
    'flush_inclusive_end': (0x141A8588D, '48ffc3'),
    'flush_source_stride': (0x141A858B6, '4c8d3c7f49c1e7044c037e08'),
    'flush_destination_stride': (0x141A858EB, '48c1e704488d0c7f'),
    'flush_reset_min': (0x141A85939, '48c74618ffffffff'),
    'flush_reset_max': (0x141A85941, '48c7462000000000'),
    'default_tree_fine_gate': (0x1409E5AB4, '80bd3801000001'),
    'spawn_binding_set': (0x1409E5B3C, '4c896d68'),
    'spawn_draw_callback': (0x1409E5B40, '48894570'),
    'spawn_subset_payload': (0x1409E5B4B, '48894578'),
    'fine_command_index_load': (0x1409E6289, '448b2498'),
    'fine_command_byte_stride': (0x1409E6431, '49c1e4024f8d04a4'),
    'fine_count_byte_offset': (0x1409E6439, '48c1e302'),
    'record_command_offset': (0x140E2505D, '4489bedc000000'),
    'record_max_commands': (0x140E2509B, '8986e0000000'),
    'record_count_offset': (0x140E2512A, '8986ec000000'),
    'upload_cpu_copy': (0x140E55702, 'e859d0fd01'),
    'upload_region_triple': (0x140E55A91, '4c8978f04d01d74c8948f84c8910'),
    'upload_backend_slot': (0x140E55B56, 'ff9088030000'),
}

CALLS = {
    'prefab_update_to_placement': (0x14090FC72, 0x140954F80),
    'placement_flush_to_byte_update': (0x141A85925, 0x140E55470),
    'byte_update_to_setup': (0x140E55759, 0x140E57120),
    'setup_to_copy_closure': (0x140E57285, 0x140E559A0),
    'scene_to_material_update': (0x1409E5A9E, 0x1409E6AB0),
    'canopy_material_update': (0x1409E6C44, 0x1415711A0),
    'canopy_material_read_buf': (0x141571408, 0x140E27260),
    'trunk_material_update': (0x1409E732B, 0x14154F8B0),
    'trunk_material_read_buf': (0x14154FB0C, 0x140E27260),
    'spawn_drawable_bundle': (0x1409E5B79, 0x141620010),
    'fine_draw_indirect_count': (0x1409E6454, 0x140E24FA0),
}


def shader_trace(module, part):
    names = module['names']
    rows = module['instructions']
    values = {r['result_id']: r for r in rows if 'result_id' in r}
    decorations = {}
    for row in rows:
        if row['op'] == 'OpDecorate':
            args = row['operands']
            decorations.setdefault(args[0], {})[args[1]] = args[2:]

    def named(value):
        ids = [int(key) for key, name in names.items() if name == value]
        if len(ids) != 1:
            raise ValueError(f'Expected unique shader name {value}')
        return ids[0]

    instance = named('material_data.nani_instance_data')
    indirect = named('nani_instance_indirection.buffer')
    placement = named('PlacementData_natural')
    variable = values[instance]['operands']
    pointer = values[variable[0]]['operands']
    block = pointer[2]
    array = values[block]['operands'][1]
    if variable[2] != 2 or pointer[1] != 2 or decorations[block].get(3) != []:
        raise ValueError('Expected Uniform storage class plus BufferBlock SSBO encoding')
    if decorations[array].get(6) != [48]:
        raise ValueError('Changed placement array stride')
    if decorations[instance].get(33) != [0] or decorations[instance].get(34) != [0]:
        raise ValueError('Changed placement binding')
    expected_indirect_set = {'canopy': 8, 'trunk': 5}[part]
    if decorations[indirect].get(33) != [0] or decorations[indirect].get(34) != [expected_indirect_set]:
        raise ValueError('Changed indirection binding')
    offsets = {r['operands'][1]: r['operands'][3] for r in rows
               if r['op'] == 'OpMemberDecorate' and r['operands'][0] == placement
               and r['operands'][2] == 35}
    if offsets != {0: 0, 1: 12, 2: 16, 3: 20, 4: 24, 5: 28, 6: 32, 7: 36, 8: 44}:
        raise ValueError('Changed placement member offsets')
    selected = ([(2342, 'OpLoad', [8, 47, 49]),
                 (2350, 'OpAccessChain', [52, 53, 57, 51, 50]),
                 (2356, 'OpLoad', [9, 58, 53]),
                 (2375, 'OpAccessChain', [52, 151, 65, 51, 58, 100]),
                 (2382, 'OpLoad', [9, 153, 151]),
                 (2386, 'OpExtInst', [10, 1429, 171, 62, 153])]
                if part == 'canopy' else
                [(1878, 'OpLoad', [9, 24, 26]),
                 (1886, 'OpAccessChain', [29, 30, 34, 28, 27]),
                 (1892, 'OpLoad', [10, 35, 30]),
                 (1896, 'OpAccessChain', [29, 85, 48, 28, 35, 84]),
                 (1903, 'OpLoad', [10, 87, 85]),
                 (1907, 'OpExtInst', [14, 641, 109, 62, 87])])
    vertex_input = selected[0][2][2]
    if decorations[vertex_input].get(11) != [43]:
        raise ValueError('Expected BuiltIn InstanceIndex')
    anim_member = selected[3][2][-1]
    if module['constants'][str(anim_member)]['value'] != 6:
        raise ValueError('Expected anim_t_packed member index')
    return {'module_file_offset': hex(module['offset']),
            'indirection': {'descriptor_set': expected_indirect_set, 'binding': 0, 'stride': 4},
            'placement': {'descriptor_set': 0, 'binding': 0, 'stride': 48,
                          'storage_class': 2, 'block_decoration': 'BufferBlock',
                          'member_offsets': offsets},
            'anchors': [anchor(module, word, op, args) for word, op, args in selected]}


def inspect(root, grammar_path):
    root = root.resolve(strict=True)
    pe = PeReader(root / 'tiny-glade.exe')
    if pe.base != 0x140000000 or len(pe.data) != 65612184:
        raise ValueError('Unexpected PE identity')
    if (root / 'tiny_glade.pdb').stat().st_size != 310513664:
        raise ValueError('Unexpected adjacent PDB length')
    anchors = []
    for name, (address, expected) in ANCHORS.items():
        raw = pe.read(address, len(bytes.fromhex(expected)))
        if raw.hex() != expected:
            raise ValueError(f'Changed native anchor {name} at {address:#x}')
        offset, section = pe.locate(address, len(raw))
        anchors.append({'name': name, 'va': hex(address), 'file_offset': hex(offset),
                        'section': section, 'bytes': expected})
    calls = []
    for name, (address, expected) in CALLS.items():
        raw = pe.read(address, 5)
        target = address + 5 + struct.unpack_from('<i', raw, 1)[0]
        if raw[0] != 0xE8 or target != expected:
            raise ValueError(f'Changed direct call {name}: {target:#x}')
        calls.append({'name': name, 'va': hex(address), 'target': hex(target)})
    table = struct.unpack('<13Q', pe.read(0x143025A60, 104))
    if table[3] != 0x140958F30 or table[6] != 0x140958E10 or table[8] != 0x1408FFDC0:
        raise ValueError('Changed PlacementData trait identity/flush/buffer slots')
    subsets = []
    for index, part, length, branch in ((0, 'canopy', 33, 0x1409E6B69),
                                       (1, 'trunk', 32, 0x1409E7275)):
        constructor = struct.unpack('<Q', pe.read(0x143032DC0+index*8, 8))[0]
        name_va = struct.unpack('<Q', pe.read(0x143032F90+index*8, 8))[0]
        actual_length = struct.unpack('<Q', pe.read(0x143032EA8+index*8, 8))[0]
        name = pe.read(name_va, actual_length).decode('ascii')
        material_branch = 0x1430330A0 + struct.unpack('<i', pe.read(0x1430330A0+index*4, 4))[0]
        if constructor != 0x140959DC0 or actual_length != length or name != f'country_core/clearing/tree_{part}' or material_branch != branch:
            raise ValueError('Changed selected subset tables')
        subsets.append({'subset': index, 'shader': name, 'constructor': hex(constructor),
                        'material_branch': hex(material_branch)})
    source = json.loads(grammar_path.read_text(encoding='utf-8'))
    grammar = {row['opcode']: row for row in source['instructions']}
    shaders = {}
    for part in ('canopy', 'trunk'):
        path = root / f'compiled-shaders/country-core/compiled/clearing/tree_{part}.precomp'
        decoded = modules(path, grammar)
        if len(decoded) != 4:
            raise ValueError('Changed selected shader module count')
        shaders[part] = shader_trace(decoded[0], part)
        shaders[part]['package_module_count'] = len(decoded)
        shaders[part]['scope'] = 'first vertex module; other variants not semantically traced'
    dirty_min, dirty_max, indirect_value = 10, 12, 11
    return {'kind': 'ordinary-file-static-check', 'binary': str(pe.path),
            'binary_bytes': len(pe.data), 'image_base': hex(pe.base),
            'anchors': anchors, 'calls': calls, 'subsets': subsets,
            'placement_trait_vtable': {'va': '0x143025a60',
                                      'type_name': hex(table[3]), 'gpu_flush': hex(table[6]),
                                      'buffer': hex(table[8])},
            'vertex_shaders': shaders,
            'constructed': {'dirty_min': dirty_min, 'dirty_max_inclusive': dirty_max,
                            'byte_offset': 48*dirty_min, 'byte_count': 48*(dirty_max+1-dirty_min),
                            'instance_index': 23, 'indirection_value': indirect_value,
                            'placement_anim_byte_offset': 48*indirect_value+32},
            'limits': ['No target execution or REA Evidence ID',
                       'No final physical indirection backing identity proof',
                       'No live tree entity, visible slot or actual draw count',
                       'Backend +0x388/+0x280 device embedding still not proven'],
            'runtime': 'Not Run'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--grammar', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.root, args.grammar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'native_anchors': len(result['anchors']), 'calls': len(result['calls']),
                      'subsets': len(result['subsets']), 'vertex_shaders': len(result['vertex_shaders'])}))


if __name__ == '__main__':
    main()
