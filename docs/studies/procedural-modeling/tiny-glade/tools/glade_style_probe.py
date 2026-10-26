"""Read scene-style presets and selected native loading/binding evidence.

Does not run Tiny Glade, decode/export art assets, inspect user mods or saves,
or calculate content digests. Preset values describe the bundled input only.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader
from dof_followup_probe import require


def inspect(root):
    root = root.resolve(strict=True)
    pe = PeReader(root / 'tiny-glade.exe')
    anchors = {
        0x140A9E83A: '0fb68098000000',
        0x140A9E844: '488d0ded8f5a02',
        0x140A9E84F: '488d150a905a02',
        0x140A9E86D: '41b80c000000',
        0x140A9E886: '48c74424200d000000',
        0x140A9EAB7: 'e834f3ffff',
        0x140A9ECF5: 'e8f6f0ffff',
        0x140A9DE37: 'c740106f6c6f72',
        0x140A2EC05: 'e8a636d800',
        0x140C5D272: 'e879609e00',
        0x140C5D2A7: 'e8c42e9f00',
        0x140C5D2B1: '80fb03',
        0x140C5D3D7: '48c70600000000',
        0x140C5DB13: '48c70100000000',
        0x1417CF8CD: '488d8d10020000',
        0x1417CFA33: '488d8d10020000',
        0x1417CFA85: '41b850020000',
        0x1417CFA9A: '81781050020000',
        0x1417CFAF9: 'e8725968ff',
        0x140A4E72A: 'e86110d800',
        0x140C254E2: 'e879eaffff',
        0x140C2550A: 'e8e1efffff',
        0x140C25528: 'e863faffff',
        0x1408F978E: '80b89800000004',
        0x1408F9795: '0f85bf010000',
    }
    for address, expected in anchors.items():
        require(pe, address, expected)
    names = ['summer', 'olden', 'flowery', 'autumn', 'winter']
    for index, expected in enumerate(names):
        size = struct.unpack('<Q', pe.read(0x143047838 + 8*index, 8))[0]
        pointer = struct.unpack('<Q', pe.read(0x143047860 + 8*index, 8))[0]
        if size != len(expected) or pe.read(pointer, size).decode('ascii') != expected:
            raise ValueError('Selected GladeType directory table changed')
    for address, tag in ((0x140A937C0, 1), (0x1408FF990, 2),
                         (0x140901020, 3), (0x140A3D910, 4)):
        require(pe, address, '8039' + f'{tag:02x}' + '0f94c0c3')
    if pe.read(0x143046608, 16) + b'olor' != b'glade:ivy_leaf_color':
        raise ValueError('Selected constructed semantic alias changed')
    for address, expected in ((0x140A9EAB7, 0x140A9DDF0),
                              (0x140A9ECF5, 0x140A9DDF0),
                              (0x140A4E72A, 0x1417CF790),
                              (0x1417CFAF9, 0x140E55470),
                              (0x14164856A, 0x1417CE930),
                              (0x14164874A, 0x1417CE930)):
        if pe.read(address, 1) != b'\xe8':
            raise ValueError('Selected call opcode changed')
        actual = address + 5 + struct.unpack('<i', pe.read(address + 1, 4))[0]
        if actual != expected:
            raise ValueError('Selected direct consumer changed')
    assets = root / 'assets'
    base_rows = json.loads((assets / 'colors.json').read_text(encoding='utf-8'))
    base_colors = {row['name']: row['color'] for row in base_rows}
    if len(base_rows) != 37 or len(base_colors) != 37:
        raise ValueError('Selected common palette changed')
    profiles, overrides = {}, {}
    expected_counts = {'summer': (9, 4), 'olden': (12, 0), 'flowery': (9, 1),
                       'autumn': (9, 0), 'winter': (12, 0)}
    for name in names:
        folder = assets / 'glade' / name
        settings = json.loads((folder / 'settings.json').read_text(encoding='utf-8'))
        textures = json.loads((folder / 'textures.json').read_text(encoding='utf-8'))
        trees = json.loads((folder / 'trees.json').read_text(encoding='utf-8'))
        plants = json.loads((folder / 'plants.json').read_text(encoding='utf-8'))
        grading = json.loads((folder / 'grading.json').read_text(encoding='utf-8'))
        if not isinstance(settings, dict) or len(textures) != 10:
            raise ValueError('Selected preset schema/count changed')
        if (len(trees), len(plants)) != expected_counts[name]:
            raise ValueError('Selected tree/plant configuration counts changed')
        color_file = folder / 'colors.json'
        colors = json.loads(color_file.read_text(encoding='utf-8')) if color_file.exists() else []
        overrides[name] = {row['name']: row['color'] for row in colors}
        if len(overrides[name]) != (4 if name in ('autumn', 'winter') else 0):
            raise ValueError('Selected partial palette changed')
        if not set(overrides[name]) <= set(base_colors):
            raise ValueError('Selected override has an unfamiliar color key')
        profiles[name] = {'settings': settings, 'textures': textures,
                          'tree_configuration_rows': len(trees),
                          'plant_configuration_rows': len(plants),
                          'palette_override_names': list(overrides[name]),
                          'has_tod_file': (folder / 'tod.json').exists(),
                          'grading_lut': grading['current_grading_lut']}
    if overrides['winter'] != overrides['autumn']:
        raise ValueError('Selected winter/autumn partial palette relation changed')
    return {'kind': 'ordinary-file-static-check', 'native_anchors': len(anchors) + 4,
            'direct_calls': 6, 'enum_directories': names, 'profiles': profiles,
            'common_palette_entries': len(base_colors), 'palette_upload_bytes': 0x250,
            'winter_autumn_four_overrides_equal': True,
            'constructed_unchanged_base_entries': 37 - 4,
            'runtime': 'Not Run', 'active_mod_overlay': 'Not Inspected'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.root)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'anchors': result['native_anchors'],
                      'profiles': len(result['profiles']),
                      'palette_bytes': result['palette_upload_bytes']}))


if __name__ == '__main__':
    main()
