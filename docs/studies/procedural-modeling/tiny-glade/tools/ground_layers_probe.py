"""Read Tiny Glade ground startup, SPIR-V and public preset evidence.

Version-specific static inspection. No game code or shader executes; no digest,
private save, target mutation, asset export or Unity project access occurs.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

from atlas_budget_probe import PeReader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from spirv_probe import decode_module


CALLS = {
    0x140A5D6B1: 0x140A5C690,
    0x140A5DCA4: 0x140B0B280,
    0x140A5DCEC: 0x140B0B460,
    0x140B0B683: 0x140B09020,
    0x140B0BA03: 0x140B09020,
    0x140B0C2E0: 0x140B0A710,
    0x140B0C32C: 0x140B0A710,
}

STRINGS = {
    0x140A5D740: 'floor',
    0x140A5D776: 'country_core/terrain_editing/floor',
    0x140A5D86A: 'glade:grass_world_albedo_tint',
    0x140A5D899: 'mud',
    0x140A5DB5E: 'assets/meshes/terrain.json',
    0x140A5DBEB: 'assets/meshes/water_plane.json',
    0x140A5DDB5: 'country_core/distant_terrain',
    0x140A5DDE3: 'glade:terrain_texture',
    0x140916432: 'assets/starting-builds/full',
    0x140916439: 'assets/starting-builds/demo',
}


def inspect(root, grammar_path):
    root = root.resolve(strict=True)
    pe = PeReader(root / 'tiny-glade.exe')
    if pe.base != 0x140000000 or len(pe.data) != 65612184:
        raise ValueError('Unexpected PE identity facts')
    calls, strings = [], []
    for va, target in CALLS.items():
        raw = pe.read(va, 5)
        if raw[0] != 0xE8 or va + 5 + struct.unpack_from('<i', raw, 1)[0] != target:
            raise ValueError(f'Changed call at {va:#x}')
        calls.append({'va': hex(va), 'target': hex(target), 'bytes': raw.hex()})
    for va, expected in STRINGS.items():
        raw = pe.read(va, 7)
        if raw[0] not in (0x48, 0x4C) or raw[1] != 0x8D or raw[2] & 0xC7 != 5:
            raise ValueError(f'Expected RIP-relative LEA at {va:#x}')
        target = va + 7 + struct.unpack_from('<i', raw, 3)[0]
        if pe.read(target, len(expected)) != expected.encode('ascii'):
            raise ValueError(f'Changed literal at {va:#x}')
        strings.append({'va': hex(va), 'literal_va': hex(target), 'literal': expected})

    grammar_data = json.loads(grammar_path.read_text(encoding='utf-8'))
    grammar = {r['opcode']: r for r in grammar_data['instructions']}
    path = root / 'compiled-shaders/country-core/compiled/terrain_editing/floor.precomp'
    blob = path.read_bytes()
    modules = []
    for offset, count in ((161, 2372), (9662, 12233), (66568, 2372), (76069, 41)):
        if struct.unpack_from('<I', blob, offset - 4)[0] != count:
            raise ValueError('Floor module extent changed')
        modules.append(decode_module(blob, offset, count, grammar))
    vertex, fragment = modules[:2]

    def constant(module, identifier):
        scalar = module['constants'].get(str(identifier))
        if scalar is not None:
            return scalar['value']
        definitions = [r for r in module['instructions'] if r.get('result_id') == identifier]
        if len(definitions) != 1 or definitions[0]['op'] != 'OpConstantComposite':
            raise ValueError(f'Expected scalar/vector constant {identifier}')
        return [constant(module, i) for i in definitions[0]['operands'][2:]]

    def row(module, word, operation):
        matches = [r for r in module['instructions'] if r['word_offset'] == word]
        if len(matches) != 1 or matches[0]['op'] != operation:
            raise ValueError(f'Changed shader operation: {word} {operation}')
        r = matches[0]
        return {'word': word, 'file_offset': hex(r['file_offset']),
                'op': operation, 'operands': r['operands']}

    anchors = [row(vertex, w, op) for w, op in (
        (1173, 'OpUMod'), (1178, 'OpUDiv'),
        (1299, 'OpImageSampleExplicitLod'), (1311, 'OpExtInst'),
        (1354, 'OpULessThanEqual'), (1498, 'OpExtInst'), (1592, 'OpExtInst'),
        (1981, 'OpImageGather'), (2101, 'OpExtInst'),
        (2302, 'OpExtInst'), (2310, 'OpExtInst'), (2328, 'OpExtInst'),
        (2364, 'OpStore'), (2367, 'OpStore'))]
    anchors += [row(fragment, w, op) for w, op in (
        (3342, 'OpAccessChain'), (3359, 'OpAccessChain'),
        (3859, 'OpExtInst'), (3873, 'OpExtInst'),
        (8003, 'OpImageSampleExplicitLod'), (8033, 'OpImageSampleExplicitLod'),
        (8048, 'OpExtInst'), (8062, 'OpExtInst'))]
    expected_vertex_scalars = {52: 93, 159: 92, 154: -2.5, 155: 24,
                               406: 26.5, 824: 67.16666412353516,
                               830: 0.01075268816202879, 464: -0.800000011920929}
    for identifier, value in expected_vertex_scalars.items():
        if vertex['constants'].get(str(identifier), {}).get('value') != value:
            raise ValueError(f'Changed vertex constant {identifier}')
    # ExtInst code 40 is FMax, not FMin; retain this material distinction.
    for word, opcode in ((1311, 46), (1498, 40), (1592, 40), (2101, 68),
                          (2302, 49), (2310, 49), (2328, 46)):
        if row(vertex, word, 'OpExtInst')['operands'][3] != opcode:
            raise ValueError(f'Changed vertex GLSL operation {word}')
    for word, opcode in ((3859, 43), (3873, 46), (8048, 49), (8062, 46)):
        if row(fragment, word, 'OpExtInst')['operands'][3] != opcode:
            raise ValueError(f'Changed fragment GLSL operation {word}')
    for member, name in ((18, 'grass_1'), (19, 'grass_2')):
        if {'type_id': 119, 'member': member, 'name': name} not in fragment['member_names']:
            raise ValueError('Changed grass palette members')
    if constant(vertex, 63) != [130.0, 130.0]:
        raise ValueError('Changed world-space gradient span')
    for word, member in ((3342, 18), (3359, 19)):
        access = row(fragment, word, 'OpAccessChain')['operands']
        if access[2] != 121 or constant(fragment, access[3]) != member:
            raise ValueError('Grass palette producer changed')
    smooth = row(fragment, 8048, 'OpExtInst')['operands']
    f32 = lambda value: struct.unpack('<f', struct.pack('<f', value))[0]
    if [constant(fragment, i) for i in smooth[4:6]] != [f32(0.4), 0.5]:
        raise ValueError('Wet color transition thresholds changed')

    mesh_path = root / 'assets/meshes/terrain.json'
    mesh = json.loads(mesh_path.read_text(encoding='utf-8'))
    positions = mesh['Vertex_Position']['buffer']
    if len(positions) != 1078 or len(mesh['indices']['buffer']) != 6099:
        raise ValueError('Unexpected packaged terrain mesh schema/count')
    mesh_summary = {'path': str(mesh_path), 'vertices': len(positions),
                    'indices': len(mesh['indices']['buffer']),
                    'raw_min': [min(p[i] for p in positions) for i in range(3)],
                    'raw_max': [max(p[i] for p in positions) for i in range(3)]}
    presets = []
    for name in ('intro', '05-rocky-lake', '17-two-islands'):
        path = root / 'assets/starting-builds/full' / name / 'history.json'
        history = json.loads(path.read_text(encoding='utf-8'))
        tags = Counter()
        for item in history['History']['edit_chain']:
            for edit in item['edits']:
                if not isinstance(edit, dict):
                    raise ValueError('Unexpected public history edit schema')
                tags.update(edit.keys())
        presets.append({'public_preset': name, 'history_bytes': path.stat().st_size,
                        'edit_tag_counts': dict(tags)})
    theme_path = root / 'assets/glade/summer/textures.json'
    theme = json.loads(theme_path.read_text(encoding='utf-8'))
    if theme.get('terrain_texture') != 'terrain_summer':
        raise ValueError('Summer distant terrain mapping changed')
    plants_path = root / 'assets/glade/summer/plants.json'
    plants = json.loads(plants_path.read_text(encoding='utf-8'))
    if sorted(set(p['mesh'] for p in plants)) != ['plant_leafy', 'plant_thistle']:
        raise ValueError('Summer public plant references changed')
    return {'target_root': str(root), 'binary_bytes': len(pe.data),
            'native_calls': calls, 'native_literals': strings,
            'floor_modules': [{'offset': m['offset'], 'words': m['word_count'],
                               'instructions': m['instruction_count']} for m in modules],
            'shader_anchors': anchors, 'vertex_constants': expected_vertex_scalars,
            'terrain_mesh': mesh_summary, 'public_presets': presets,
            'summer_textures': theme, 'summer_plant_references': plants,
            'limitations': ['No game, GPU or Unity execution.',
                            'Initial preset selection policy and complete scheduler remain unproved.',
                            'Raw mesh bounds are not a measured world/camera footprint.',
                            'No proprietary mesh/image data is exported.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--grammar', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.root, args.grammar)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'native_calls': len(result['native_calls']),
                      'native_literals': len(result['native_literals']),
                      'modules': len(result['floor_modules']),
                      'shader_anchors': len(result['shader_anchors']),
                      'public_presets': len(result['public_presets']),
                      'runtime': 'Not Run'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
