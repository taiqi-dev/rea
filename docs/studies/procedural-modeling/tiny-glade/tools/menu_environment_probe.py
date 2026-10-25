"""Read selected menu/environment evidence from this study's Tiny Glade PE.

Version-specific file reader; no target execution, assets export or digest.
It checks instruction shapes before following measured tables or literals.
It does not reconstruct the renderer or establish runtime behavior.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


def require(pe, address, expected):
    raw = bytes.fromhex(expected)
    if pe.read(address, len(raw)) != raw:
        raise ValueError(f'Unexpected instruction anchor at {address:#x}')


def rip_address(pe, address, opcode):
    raw = pe.read(address, 7)
    if raw[:3] != bytes.fromhex(opcode):
        raise ValueError(f'Unexpected RIP instruction at {address:#x}')
    return address + 7 + struct.unpack_from('<i', raw, 3)[0]


def display_records(pe, start):
    require(pe, start + 8, '0fb601')
    table = rip_address(pe, start + 11, '488d0d')
    require(pe, start + 18, '486304814801c8ffe0')
    records = []
    # Five measured records, not a generic search for a table terminator.
    for index in range(5):
        branch = table + struct.unpack('<i', pe.read(table + index * 4, 4))[0]
        literal = rip_address(pe, branch, '488d0d')
        require(pe, branch + 7, 'ba')
        length = struct.unpack('<I', pe.read(branch + 8, 4))[0]
        if not 1 <= length <= 64:
            raise ValueError('Unexpected localization-key length')
        key = pe.read(literal, length).decode('ascii')
        if not key.startswith('Quality.'):
            raise ValueError('Unexpected localization-key family')
        records.append({'index': index, 'branch_va': hex(branch), 'key': key})
    return records


def eraser_records(pe):
    require(pe, 0x141B6ED86, '0fb609c1e103')
    require(pe, 0x141B6EA1F, '41b907000000')  # unknown_variant advertises seven
    lengths = rip_address(pe, 0x141B6ED8C, '488d15')
    pointers = rip_address(pe, 0x141B6ED97, '488d15')
    names = []
    for index in range(7):
        length = struct.unpack('<Q', pe.read(lengths + index * 8, 8))[0]
        address = struct.unpack('<Q', pe.read(pointers + index * 8, 8))[0]
        if not 1 <= length <= 32:
            raise ValueError('Unexpected eraser name length')
        names.append(pe.read(address, length).decode('ascii'))
    if names != ['All', 'Wall', 'Path', 'Bulldoze', 'Water', 'Garden', 'Tree']:
        raise ValueError('Unexpected EraserLayer variants')
    require(pe, 0x140A3B010, '0fb60980c1feb00780f90c')
    table = rip_address(pe, 0x140A3B020, '488d0d')
    layers = list(pe.read(table, 13))
    if any(layer > 7 for layer in layers):
        raise ValueError('Unexpected temp eraser layer')
    require(pe, 0x140A3B042, '41b9031e0000')
    return {
        'variants': [{'tag': i, 'name': name} for i, name in enumerate(names)],
        'temp_mode_tags_2_through_14': [
            {'input_tag': i + 2, 'result_tag': tag,
             'layer': names[tag] if tag < 7 else 'no layer (raw 7)'}
            for i, tag in enumerate(layers)],
        'effective_mode_eligible_input_tags': [i + 2 for i in range(13)
                                               if 0x1E03 & (1 << i)],
        'scope': 'selected helper tables; not final consumers or UI selection',
    }


def inspect(binary):
    pe = PeReader(binary)
    require(pe, 0x140A92210, '0fb601488d0d96345b02f30f100481c3')
    scales_va = rip_address(pe, 0x140A92213, '488d0d')
    scales = struct.unpack('<5f', pe.read(scales_va, 20))
    upscale = display_records(pe, 0x140A94560)
    for record, scale in zip(upscale, scales):
        if not 0 < scale <= 1:
            raise ValueError('Unexpected resolution scale')
        record['tgsr_linear_scale'] = scale
        record['relative_pixel_count_arithmetic'] = scale * scale
    require(pe, 0x140B86CC0,
            '4889c8f30f1042080fb64a14f20f100af20f1108f30f11400888480cc3')
    require(pe, 0x140B86CE0, 'f30f1041100fb64115c3')
    fog_keys = []
    for address, length in ((0x140676FE2, 9), (0x140677009, 6),
                            (0x14067702D, 9), (0x140677051, 6)):
        target = rip_address(pe, address, '488d15')
        fog_keys.append(pe.read(target, length).decode('ascii'))
    if fog_keys != ['thickness', 'height', 'steepness', 'locked']:
        raise ValueError('Unexpected fog serializer keys')
    require(pe, 0x1400B2D61, '4084f60f8496000000')
    return {
        'binary': str(pe.path), 'bytes': len(pe.data), 'preferred_base': hex(pe.base),
        'evidence_kind': 'ordinary PE file reads, not REA Evidence or runtime',
        'upscaling_measured_records': upscale,
        'image_quality_measured_records': display_records(pe, 0x140A946D0),
        'fog_serializer_keys': fog_keys,
        'fog_save_fields': {'floats': ['0x0', '0x4', '0x8'], 'locked': '0x14'},
        'precipitation_save_fields': {'strength': '0x10', 'locked': '0x15'},
        'eraser': eraser_records(pe),
        'selected_menu_request_gate': {'va': '0x1400b2d61',
                                       'false_target': '0x1400b2e00'},
        'constructed_arithmetic_only': {
            'fog_t_0_05_1': [1 / (20 * (1 - t) + 2 * t) for t in (0, .5, 1)],
            'precipitation_positive_example': .4 + .1 * .1,
        },
        'not_established': ['whole preset mapping', 'default or selected settings',
                            'capture GPU completion', 'runtime cost or appearance'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = json.dumps(inspect(args.binary), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        # Do not overwrite an earlier receipt.
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(data)
    else:
        print(data, end='')


if __name__ == '__main__':
    main()
