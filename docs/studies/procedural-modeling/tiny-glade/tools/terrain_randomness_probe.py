"""Read selected Tiny Glade terrain randomness evidence without execution.

Checks a version-specific PE and one packaged SPIR-V module, and summarizes
three public starting-build histories. No hashes, private saves, target code
execution, asset copying or provider Evidence claims. Refuses output overwrite.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader
from dof_tree_probe import modules


def inspect(root, grammar_path, symbol_path=None):
    root = root.resolve(strict=True)
    pe = PeReader(root / 'tiny-glade.exe')
    if pe.base != 0x140000000 or len(pe.data) != 65612184:
        raise ValueError('Selected PE identity facts changed')
    pdb = root / 'tiny_glade.pdb'
    if pdb.stat().st_size != 310513664:
        raise ValueError('Selected PDB size changed')
    grammar_data = json.loads(grammar_path.read_text(encoding='utf-8'))
    grammar = {r['opcode']: r for r in grammar_data['instructions']}
    shader_path = root / 'compiled-shaders/country-core/compiled/terrain_editing/rasterize_terrain_stroke.precomp'
    decoded = modules(shader_path, grammar)
    if len(decoded) != 1 or decoded[0]['offset'] != 152 or decoded[0]['word_count'] != 16190:
        raise ValueError('Selected terrain module extent changed')
    module = decoded[0]
    definitions = {r['result_id']: r for r in module['instructions'] if 'result_id' in r}
    by_word = {r['word_offset']: r for r in module['instructions']}

    def constant(identifier):
        scalar = module['constants'].get(str(identifier))
        if scalar is not None:
            return scalar['value']
        row = definitions[identifier]
        if row['op'] != 'OpConstantComposite':
            raise ValueError(f'Not a constant: {identifier}')
        return [constant(i) for i in row['operands'][2:]]

    def anchor(word, op, operands):
        row = by_word[word]
        if row['op'] != op or row['operands'] != operands:
            raise ValueError(f'Changed shader anchor: {word}')
        return {'word': word, 'file_offset': hex(row['file_offset']),
                'operation': op, 'operands': operands}

    proofs = [anchor(*args) for args in (
        (1682, 'OpPhi', [5, 6204, 186, 4, 7353, 75]),
        (1735, 'OpFOrdEqual', [35, 1255, 118, 155]),
        (1743, 'OpBranchConditional', [1255, 78, 79]),
        (1883, 'OpUDiv', [17, 1589, 1580, 343]),
        (1888, 'OpBitcast', [11, 1590, 1589]),
        (4127, 'OpVectorTimesScalar', [14, 756, 1801, 757]),
        (4132, 'OpConvertSToF', [5, 758, 1590]),
        (4136, 'OpFMul', [5, 759, 758, 140]),
        (4146, 'OpFAdd', [14, 761, 756, 760]),
        (4219, 'OpSLessThan', [35, 2552, 6387, 207]),
        (4241, 'OpFMul', [5, 1042, 1041, 1043]),
        (4246, 'OpFSub', [5, 1044, 754, 1042]),
        (4251, 'OpVectorTimesScalar', [14, 1045, 1801, 140]),
        (4256, 'OpFAdd', [14, 1047, 1045, 760]),
        (5550, 'OpSLessThan', [35, 2966, 6389, 207]),
        (5572, 'OpFSub', [5, 1050, 1044, 1049]),
        (5679, 'OpIAdd', [11, 1093, 1590, 1590]),
        (5836, 'OpFAdd', [14, 1112, 1092, 3376]),
        (8229, 'OpIMul', [11, 1129, 1590, 1590]),
        (8234, 'OpIMul', [11, 1130, 1129, 1590]),
        (8391, 'OpFAdd', [14, 1133, 1112, 3810]),
        (9673, 'OpFOrdGreaterThan', [35, 1155, 1153, 6204]),
        (13139, 'OpVectorShuffle', [14, 1257, 1476, 1476, 0, 2]),
        (13146, 'OpVectorTimesScalar', [14, 1258, 1257, 1259]),
        (13151, 'OpFMul', [14, 1261, 1258, 8499]),
        (13156, 'OpFAdd', [14, 1262, 1261, 1263]),
        (13165, 'OpPhi', [5, 6349, 140, 78, 5136, 5144]),
        (13207, 'OpPhi', [5, 6206, 155, 78, 5134, 5144]),
        (13229, 'OpSLessThan', [35, 5126, 6205, 197]),
        (13243, 'OpFAdd', [5, 1267, 6206, 140]),
        (13248, 'OpFMul', [5, 1271, 1267, 8521]),
        (13253, 'OpExtInst', [5, 1273, 185, 40, 6204, 1271]),
        (13264, 'OpExtInst', [14, 5166, 185, 8, 6322]),
        (13274, 'OpExtInst', [14, 5168, 185, 10, 6322]),
        (14265, 'OpFMul', [14, 5522, 5168, 5168]),
        (14280, 'OpFMul', [14, 5525, 5522, 5524]),
        (14355, 'OpFMul', [5, 5150, 145, 5215]),
        (14360, 'OpFAdd', [5, 5151, 1016, 5150]),
        (14365, 'OpFMul', [5, 5132, 6349, 5151]),
        (14370, 'OpFAdd', [5, 5134, 6206, 5132]),
        (14375, 'OpFMul', [5, 5136, 6349, 1024]),
        (14380, 'OpVectorTimesScalar', [14, 5138, 6322, 1027]),
        (14385, 'OpVectorTimesMatrix', [14, 5139, 5138, 8509]),
        (16103, 'OpFMul', [5, 1392, 6219, 1055]),
    )]
    native = []
    for va, expected in (
        (0x140B14289, '488b7138'), (0x140B142A7, '48ffc6'),
        (0x140B142AA, '498936'), (0x140B142C6, 'ffce'),
        (0x140B142F3, '89742444'), (0x140B14310, '4189f0'),
        (0x140B142EB, 'c7442440cdcccc3e'),
        (0x140B142F7, 'c744244800002040'),
    ):
        if pe.read(va, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f'Changed native anchor at {va:#x}')
        native.append({'va': hex(va), 'bytes': expected})
    presets = []
    for name in ('intro', '05-rocky-lake', '17-two-islands'):
        path = root / 'assets/starting-builds/full' / name / 'history.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        tags, terrain = Counter(), []
        for item in data['History']['edit_chain']:
            for edit in item.get('edits', []):
                tags.update(edit.keys())
                if 'Terrain' in edit:
                    for operation, payload in edit['Terrain'].items():
                        terrain.append({'operation': operation,
                            'fields': {key: len(value) if key == 'stroke_pts' else value
                                       for key, value in payload.items()}})
        presets.append({'name': name, 'relative_path': str(path.relative_to(root)),
                        'file_bytes': path.stat().st_size, 'version': data['Version'],
                        'root_keys': list(data), 'edit_tags': dict(tags),
                        'terrain_operations': terrain})
    symbols = None
    if symbol_path:
        data = json.loads(symbol_path.read_text(encoding='utf-8'))
        symbols = {'source': str(symbol_path), 'queries': data['queries'],
                   'symbols': [{**s, 'name': s['name'].split('\0', 1)[0]}
                               for s in data['symbols']]}
    examples = {
        'chosen_noise_inputs_not_original_samples': {'N0': 0.2, 'N1': -0.4},
        'interior_no_stroke_height_before_blur': 20 * max(.01, .035 * (.5 + .5 * .2 + .275 * -.4)),
        'baseline_possible_upper_world_height': 20 * .035 * (.5 + .5 + .275),
        'q0_at_world_origin': [34, 436],
        'q1_at_world_origin': [1.9 * (.8 * 34 - .6 * 436), 1.9 * (.6 * 34 + .8 * 436)],
        'distance_coordinates_at_XZ_10_20_ID_7': [[.2 * 10 + .5 * 7, .2 * 20 + .5 * 7],
                                                 [.5 * 10 + .5 * 7, .5 * 20 + .5 * 7]],
    }
    if abs(examples['interior_no_stroke_height_before_blur'] - .343) > 1e-12:
        raise ValueError('Constructed arithmetic failed')
    return {'target': str(root), 'exe_bytes': len(pe.data), 'pdb_bytes': pdb.stat().st_size,
            'image_base': hex(pe.base), 'shader': str(shader_path.relative_to(root)),
            'module_offset': 152, 'words': 16190, 'instructions': module['instruction_count'],
            'shader_anchors': proofs, 'native_anchors': native,
            'constants': {str(k): constant(k) for k in
                          (140, 145, 155, 186, 197, 207, 343, 757, 1043,
                           1024, 1027, 1055, 1108, 1259, 1263, 8499, 8509, 8521)},
            'global_fields': [r for r in module['member_names'] if r['type_id'] == 92],
            'named_resources': module['names'], 'public_presets': presets,
            'symbols': symbols, 'constructive_examples': examples,
            'limitations': ['Selected static data flow, not complete shader semantics',
                            'No game/GPU execution or runtime binding observation',
                            'History records do not establish final active stroke count',
                            'No REA Evidence was produced']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--grammar', required=True, type=Path)
    parser.add_argument('--symbols', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.root, args.grammar, args.symbols)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': str(args.output), 'shader_anchors': len(result['shader_anchors']),
                      'native_anchors': len(result['native_anchors']),
                      'public_presets': len(result['public_presets'])}))


if __name__ == '__main__':
    main()
