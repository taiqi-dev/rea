"""Read selected Tiny Glade UI motion anchors from the inspected PE version.

Uses the existing bounded PE reader. Does not execute target code, read saves,
calculate digests, or infer runtime scheduling from static call sites.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


ANCHORS = {
    'cubic_out_arithmetic': (0x140DEDE9C,
                             '0f28d0f30f5cd10f28caf30f59caf30f59caf30f5cc1'),
    'appearance_flag_and_speed': (0x14297C514, '803900418916f30f59ea'),
    'appearance_clamp_store': (0x14297C2C2,
                               'f30f582b0f57f6f30f5ff50f28e9f30f5deef30f112b'),
    'focus_flag': (0x14297C48F, '80790100'),
    'focus_forward_step': (0x14297C4A2,
                            'f3410f106b58418916f30f5ee8f30f586b04f30f116b04'),
    'focus_tag_store': (0x14297C4F3, '4488530c'),
    'focus_clamp': (0x14297C4F7, '0f57edf30f5f6b040f28f1f30f5df5'),
    'appear_scale_read_write': (0x14297B40C, 'f3420f594cad10f3420f114cad10'),
    'focus_scale_read_write': (0x14297ADA1, 'f3410f597d10f3410f117d10'),
    'select_pulse_arithmetic': (0x14297BF1A,
                                '0f28cef30f5cc8f30f59cff30f58c80f28c6f30f5cc1'
                                'f3410f59c8f30f59c8f30f59c9f30f590bf30f58ce'),
    'layout_size_multiply': (0x142981AC1, '0f59c1f30f12ca0f59c8'),
    'layout_scale_reset': (0x1429816C7, 'c745100000803f'),
    'layout_result_center': (0x1429813BD,
                              '0f28d00f59d60f58d10f13540500'),
    'parent_focus_read': (0x14297EA11, '450fb65c0a01'),
    'child_appearance_write': (0x14297EA63, '45881c31'),
    'drag_started_tag': (0x140901020, '8039030f94c0c3'),
    'feedback_command_payload': (0x14297D456,
                                  'f2440f11643010c744301800000000c644301c00'),
}


def inspect(binary, esc_ron):
    pe = PeReader(binary)
    if pe.base != 0x140000000:
        raise ValueError('Unexpected preferred image base')
    checked = []
    for label, (va, expected_hex) in ANCHORS.items():
        expected = bytes.fromhex(expected_hex)
        actual = pe.read(va, len(expected))
        if actual != expected:
            raise ValueError(f'Anchor mismatch: {label} at {va:#x}: {actual.hex()}')
        offset, section = pe.locate(va, len(expected))
        checked.append({'label': label, 'va': hex(va), 'file_offset': hex(offset),
                        'section': section, 'bytes': actual.hex()})

    calls = []
    for va, expected in (
        (0x14297AD86, 0x140DEDCD0),
        (0x14297B3EC, 0x140DEDCD0),
        (0x14297B479, 0x140DEDCD0),
        (0x1429816BC, 0x1423909C0),
    ):
        raw = pe.read(va, 5)
        if raw[0] != 0xE8:
            raise ValueError(f'Expected direct call at {va:#x}')
        target = va + 5 + struct.unpack_from('<i', raw, 1)[0]
        if target != expected:
            raise ValueError(f'Unexpected call target at {va:#x}')
        calls.append({'va': hex(va), 'target_va': hex(target)})

    for va in (0x14297AD7F, 0x14297B3E5):
        raw = pe.read(va, 7)
        if raw[:3] != bytes.fromhex('488d0d'):
            raise ValueError('Expected selected easing preset address')
        if va + 7 + struct.unpack_from('<i', raw, 3)[0] != 0x143607840:
            raise ValueError('Unexpected easing preset')
    preset = struct.unpack('<I', pe.read(0x143607840, 4))[0]
    table = 0x1431FF458
    branch = table + struct.unpack('<i', pe.read(table + preset * 4, 4))[0] if preset == 6 else None
    if branch != 0x140DEDE94:
        raise ValueError('Selected easing branch changed')

    constants = {}
    for label, va, expected in (
        ('focus_forward_denominator', 0x14297C28C, 0.2),
        ('unit', 0x14297C294, 1.0),
        ('appearance_speed', 0x14297C29C, 4.0),
        ('focus_reverse_denominator', 0x14297C2AB, -0.2),
    ):
        raw = pe.read(va, 8)
        if raw[:3] != bytes.fromhex('f30f10') or raw[3] & 0xC7 != 0x05:
            raise ValueError(f'Expected RIP-relative scalar load at {va:#x}')
        target = va + 8 + struct.unpack_from('<i', raw, 4)[0]
        data = pe.read(target, 4)
        if data != struct.pack('<f', expected):
            raise ValueError(f'Unexpected constant: {label}')
        constants[label] = {'load_va': hex(va), 'constant_va': hex(target),
                            'value': struct.unpack('<f', data)[0]}
    raw = pe.read(0x14297AD69, 7)
    if raw[:3] != bytes.fromhex('488d15'):
        raise ValueError('Expected focus factor table reference')
    target = 0x14297AD69 + 7 + struct.unpack_from('<i', raw, 3)[0]
    pair = pe.read(target, 8)
    if pair != struct.pack('<ff', 1.2, 1.5):
        raise ValueError('Unexpected focus factor table')
    constants['focus_target_pair'] = {'constant_va': hex(target),
                                      'values': list(struct.unpack('<ff', pair))}

    ron = esc_ron.resolve(strict=True)
    text = ron.read_text(encoding='utf-8')
    lines = text.splitlines()
    layout_lines = {token: [i for i, line in enumerate(lines, 1) if token in line]
                    for token in ('Horizontal', 'Vertical', 'Gap(20)', 'slot: "buttons"')}
    # This is bounded presence evidence, not a complete RON parser or a negative
    # proof that all shipped menus lack motion configuration.
    if any(not positions for positions in layout_lines.values()):
        raise ValueError('Expected selected menu layout directions, gap, and slot')
    return {
        'binary': str(pe.path), 'binary_bytes': len(pe.data), 'image_base': hex(pe.base),
        'anchors_checked': checked, 'direct_calls_checked': calls,
        'selected_easing': {'preset_va': '0x143607840', 'tag': preset,
                            'jump_table_va': hex(table), 'branch_va': hex(branch),
                            'structural_formula': '1-(1-t)^3'},
        'constants': constants,
        'menu_layout': {'path': str(ron), 'bytes': ron.stat().st_size,
                        'matching_lines': layout_lines},
        'limitations': [
            'Static anchors and manually interpreted arithmetic, not target execution.',
            'No proof of complete scheduler order, actual frame durations, or stagger.',
            'Toolbar animation constants do not establish Mei menu animation constants.',
            'Feedback producer command payload is not a fully recovered component insertion chain.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('esc_ron', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.binary, args.esc_ron)
    # Refuse to overwrite an earlier evidence receipt.
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'output': str(args.output), 'anchors': len(ANCHORS),
                      'direct_calls': len(result['direct_calls_checked']),
                      'target_execution': 'Not Run'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
