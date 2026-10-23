"""Read selected UI capture, arbitration, selection and focus anchors.

Version-specific static evidence only. Does not execute game code, simulate
input, inspect the Unity project, read saves, or calculate digests.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


GROUPS = {
    'capture': {
        'clicked_outer_gate': (0x1408FFA93, '807818027512'),
        'clicked_finished_gate': (0x1408FFA99, '80781901750c'),
        'clicked_id_gate': (0x1408FFAA3, '483948380f94c0'),
        'finish_hit_and_id': (0x140BF08F1, '4183ff020f95c14839c70f94c020c8'),
        'finished_state_store': (0x140BF095D, '41c64118020fb6451041884119'),
        'capture_params_fallback': (0x140BF0DE2,
                                    '498d43f84d85db490f44c34885c0480f44c3488b00f048ff00'),
        'ongoing_state_and_params': (0x140BF0EB1, '6641c741180204488b457049894120'),
        'registration_table_clear_address': (0x140BF134C, '4881c198000000'),
    },
    'arbitration': {
        'widget_record_stride': (0x14151B966, '486bc2384801c8'),
        'widget_scalar_comparison': (0x14151B9B8,
                                      'f30f1042e8f30f105a200f2ed80f8ab10000000f2ec376db'),
        'layer_byte_comparison': (0x14151BEED, '4c8b08450fb619453a1a73e3'),
        'layer_append_after_widget_count': (0x140BEF9C1, '4c6bc2384901c0'),
    },
    'selection_focus_sound': {
        'mode_selection_store': (0x1429850DF, '88442902'),
        'category_selection_from_current': (0x142986262,
                                             '410fb640183a0419488b4424688914980f944702'),
        'focus_timer_decrement': (0x142985667,
                                  'f30f1014bb488b4de8f30f5c5158f30f5fd1'),
        'positive_timer_restores_focus': (0x142985B51,
                                          'f3410f100c930f2ec80f865affffff488d0c5244893496c6440f0101'),
        'sound_tag_18': (0x1429808CC, 'c7040812000000'),
        'sound_tag_12': (0x142980A14, 'c704080c000000'),
    },
    'focus_edge': {
        'focus_state_gate': (0x14297E28D, '80780100746d'),
        'existing_focus_skips_event': (0x14297E2A0, '84c00f856cfeffff'),
        'new_focus_event_entity': (0x14297E2E0, '4c8924084c8b45f04c89440808'),
    },
}


def inspect(binary, signatures, focus_signatures):
    pe = PeReader(binary)
    if pe.base != 0x140000000:
        raise ValueError('Unexpected image base')
    groups = {}
    for group, anchors in GROUPS.items():
        checked = []
        for label, (va, expected_hex) in anchors.items():
            expected = bytes.fromhex(expected_hex)
            raw = pe.read(va, len(expected))
            if raw != expected:
                raise ValueError(f'Anchor mismatch: {label} at {va:#x}: {raw.hex()}')
            offset, section = pe.locate(va, len(raw))
            checked.append({'label': label, 'va': hex(va), 'file_offset': hex(offset),
                            'section': section, 'bytes': raw.hex()})
        groups[group] = checked
    calls = []
    for va, expected in ((0x140BEF966, 0x14151BE80), (0x140BEF985, 0x14151B930),
                          (0x1429850C8, 0x142986F30), (0x140BF1353, 0x140CAC1D0),
                          (0x14297E29A, 0x1403B05D0), (0x14297E319, 0x140CA9AC0)):
        raw = pe.read(va, 5)
        if raw[0] != 0xE8 or va + 5 + struct.unpack_from('<i', raw, 1)[0] != expected:
            raise ValueError(f'Direct call changed at {va:#x}')
        calls.append({'va': hex(va), 'target_va': hex(expected)})
    va = 0x142985596
    raw = pe.read(va, 8)
    if raw[:4] != bytes.fromhex('f30f1005'):
        raise ValueError('Expected focus timer scalar load')
    timer_va = va + 8 + struct.unpack_from('<i', raw, 4)[0]
    if pe.read(timer_va, 4) != struct.pack('<f', 0.3):
        raise ValueError('Focus timer scalar changed')

    receipt = json.loads(signatures.read_text(encoding='utf-8-sig'))
    if Path(receipt['binary']).resolve() != pe.path or receipt['binary_bytes'] != len(pe.data):
        raise ValueError('Signature receipt names a different PE input')
    requirements = {
        'toolbar_button_keep_focus': ['ToolbarButtonCooldown', 'UiToolbarButtonResetAllCooldowns', 'bevy_time'],
        'switch_app_mode_button': ['SwitchAppModeButton', 'UiInteractionState', 'RequestAppModeChange', 'AppMode'],
        'switch_toolbar_category_button': ['SwitchToolbarCategoryButton', 'RequestToolbarCategoryChange', 'Toolbar'],
        'ui_sounds': ['UiJustBecameInFocusEvent', 'UiClickEvent', 'UiDragEvent', 'PlayUiSound'],
    }
    typed = []
    for function, tokens in requirements.items():
        matches = [s['name'].split('\0')[0] for s in receipt['symbols']
                   if function in s['name'] and all(t in s['name'] for t in tokens)]
        if not matches:
            raise ValueError(f'Missing typed signature: {function}')
        typed.append({'function': function, 'name': matches[0]})
    focus_receipt = json.loads(focus_signatures.read_text(encoding='utf-8-sig'))
    if (Path(focus_receipt['binary']).resolve() != pe.path
            or focus_receipt['binary_bytes'] != len(pe.data)):
        raise ValueError('Focus signature receipt names a different PE input')
    focus_matches = [s['name'].split('\0')[0] for s in focus_receipt['symbols']
                     if 'ui_send_focus_begin_events' in s['name']
                     and all(t in s['name'] for t in ('HashSet', 'UiJustBecameInFocusEvent'))]
    if not focus_matches:
        raise ValueError('Missing typed signature: ui_send_focus_begin_events')
    typed.append({'function': 'ui_send_focus_begin_events', 'name': focus_matches[0]})
    return {
        'binary': str(pe.path), 'binary_bytes': len(pe.data), 'image_base': hex(pe.base),
        'groups': groups, 'direct_calls_checked': calls,
        'focus_timer': {'constant_va': hex(timer_va),
                        'float_value': struct.unpack('<f', pe.read(timer_va, 4))[0]},
        'signature_receipt': str(signatures.resolve()), 'typed_signatures': typed,
        'focus_signature_receipt': str(focus_signatures.resolve()),
        'limitations': [
            'No proof of real frame order, capture cancellation latency, or user-visible behavior.',
            'Missing live registry entry can use captured parameters; not a runtime bug claim.',
            'Sort checks cover selected small-sort branches; upstream tie order is not established.',
            'Sound branch tags do not identify audio clips or prove downstream deduplication.',
            'The inspected focus edge uses an entity set; disposal pruning and cross-input deduplication remain unknown.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--signatures', required=True, type=Path)
    parser.add_argument('--focus-signatures', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.binary, args.signatures, args.focus_signatures)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'output': str(args.output),
                      'anchors': sum(map(len, GROUPS.values())),
                      'direct_calls': len(result['direct_calls_checked']),
                      'typed_signatures': len(result['typed_signatures']),
                      'runtime': 'Not Run'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
