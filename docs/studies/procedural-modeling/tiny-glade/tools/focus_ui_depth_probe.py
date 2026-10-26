"""Read selected UI writers, depth access declarations and tree material bindings.

Version-specific, execution-free PE/SPIR-V checks. Does not calculate digests,
load target DLLs, read personal settings/saves or export game assets.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader
from dof_tree_probe import modules
from dof_followup_probe import require


def inspect(root, grammar_path):
    root = root.resolve(strict=True)
    pe = PeReader(root / 'tiny-glade.exe')
    anchors = {
        0x142B58708: 'c6000e',  # tree button tag
        0x142B58106: 'c645680f',  # focus overlay button tag
        0x142B58054: 'c60010',  # pin button tag
        0x1429906AA: '80703d01',  # profile tree_see_thru toggle
        0x142990690: '4883c040',  # next 64-byte profile
        0x142990669: 'e8129c01fe',
        0x14299039C: '80700d01',  # focus overlay toggle
        0x1429903DD: 'e8ee640afe',  # MainCamera::focus
        0x14298F684: 'f30f117704',
        0x14298F689: 'f3440f114f08',
        0x14298F6D5: 'f30f117710',
        0x14298F6DA: 'f3440f114f14',
        0x14298F6E0: 'c70700000000',
        0x14298F51C: 'c74004ffffffff',
        0x14298F6D2: '897004',
        0x140B02994: '48c784249001000000000000',
        0x140B029A0: '4c89b42498010000',
        0x140B0130D: '4c898db8010000',
        0x140B01A3D: '4c898d90030000',
        0x14174C225: 'c644244830',
        0x14174F2A3: 'c644244830',
        0x14174C0C1: '4885db0f8489000000',
        0x140BDCD0F: 'b019',
        0x140BDCDA3: 'e8d872b800',
        0x140BDCE24: '4489740818',
        0x141B04286: '66c74424481933',
        0x1409E6C44: 'e857a5b800',
        0x1409E732B: 'e88085b600',
        0x141572121: 'ff9680020000',
        0x1415507F1: 'ff9680020000',
    }
    for address, expected in anchors.items():
        require(pe, address, expected)
    strings = {
        0x14367E855: 'toolbar/photomode_tree_seethrough',
        0x14367E755: 'toolbar/photomode_focus',
        0x14367E740: 'toolbar/photomode_pin',
        0x1430316B6: 'canopy_flowers_color',
        0x1430316CA: 'glade:canopy_flowers_depth',
        0x1430316E4: 'country_core/clearing/tree_canopy/material_data',
        0x143031737: 'country_core/clearing/tree_trunk/material_data',
    }
    for address, value in strings.items():
        if pe.read(address, len(value)) != value.encode('ascii'):
            raise ValueError(f'Changed literal at {address:#x}')
    dispatch = {}
    for tag, expected in ((14, 0x14299064C), (15, 0x142990389),
                          (16, 0x1429903CA)):
        base = 0x1436095D8
        target = base + struct.unpack('<i', pe.read(base + 4*(tag-4), 4))[0]
        if target != expected:
            raise ValueError('Changed selected button dispatch')
        dispatch[tag] = hex(target)
    access = {}
    for tag, expected in ((0x17, [0x300, 0x200, 4]),
                          (0x30, [0x300, 0x600, 3]),
                          (0x19, [0x800, 0x20, 5]),
                          (0x1A, [0x800, 0x20, 4])):
        values = [struct.unpack('<I', pe.read(base + 4*tag, 4))[0]
                  for base in (0x143220918, 0x143220A1C, 0x143220B20)]
        if values != expected:
            raise ValueError('Changed selected vk_sync access table')
        access[hex(tag)] = values
    source = json.loads(grammar_path.read_text(encoding='utf-8'))
    grammar = {row['opcode']: row for row in source['instructions']}
    bindings = {}
    for part, expected in (
            ('canopy', {'canopy_alpha_texture': 1, 'canopy_flowers_color': 2,
                        'canopy_flowers_depth': 3, 'canopy_color': 4}),
            ('trunk', {'bark_color': 1, 'bark_color_naked': 2, 'bark_lines': 3})):
        path = root / f'compiled-shaders/country-core/compiled/clearing/tree_{part}.precomp'
        module = modules(path, grammar)[1]
        names = module['names']
        found, sets = {}, {}
        for row in module['instructions']:
            args = row['operands']
            if row['op'] != 'OpDecorate' or args[1] not in (33, 34):
                continue
            name = names.get(str(args[0]), '')
            if not name.startswith('material_data.'):
                continue
            name = name[len('material_data.'):]
            (found if args[1] == 33 else sets)[name] = args[2]
        if found != expected or sets != {name: 0 for name in expected}:
            raise ValueError('Changed selected material shader bindings')
        bindings[part] = found
    # Constructed inverse mapping, not an observed cursor or UI interaction.
    width, height, px, py = 1920., 1080., 1440., 270.
    point = [(2*px/width-1)*width/height, 1-2*py/height]
    uv = [.5 + .5*point[0]/(width/height), .5-.5*point[1]]
    return {'kind': 'ordinary-file-static-check', 'instruction_anchors': len(anchors),
            'literal_count': len(strings), 'button_dispatch': dispatch,
            'access_table': access, 'shader_material_bindings': bindings,
            'constructed_point': point, 'constructed_uv': uv,
            'runtime': 'Not Run', 'graph_execution_order': 'Unresolved',
            'instance_to_final_draw': 'Unresolved'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--grammar', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.root, args.grammar)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'anchors': result['instruction_anchors'],
                      'material_textures': sum(map(len, result['shader_material_bindings'].values()))}))


if __name__ == '__main__':
    main()
