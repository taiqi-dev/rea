"""Check selected menu rendering and toolbar click publication anchors.

Reads only the inspected PE and a retained DbgHelp query receipt. No target
execution, save access, digest computation, or runtime timing is performed.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


ANCHORS = {
    'menu_next_request_consumed': (0x1411D8DDB, '4c8b2a48c7020c0000004983fd0c'),
    'menu_current_state_store': (0x1411D8E6D, '4c892b4883c308'),
    'menu_close_tag': (0x14033E84E, '48c784248000000002000000'),
    'mei_new_node_scalar': (0x14072C5F3, 'c74411b40000803f'),
    'mei_new_node_local_scalar': (0x14072C62A, 'c74411f40000803f'),
    'mei_value_pointer': (0x14072C64C, '480530ffffff'),
    'mei_local_scalar_to_render_scalar': (0x14072FE9B,
                                         '450f28faf3440f59b8c4000000f3440f11b884000000'),
    'mei_render_scalar_read': (0x140730F3D, '660f6e8384000000'),
    'mei_render_args_geometry_scalar': (0x140730F68,
                                        '440f114d78660f7e8588000000f30f11b58c000000'),
    'mei_render_dispatch': (0x140730F86, 'ff5068'),
    'mei_mouse_activation_bit': (0x14072DDBC, '41804dfa10'),
    'menu_hotkey_activation_bit': (0x140729564, '800820'),
    'mei_used_bitmask': (0x14072CE1E, 'f641fa30'),
    'menu_text_scalar_argument': (0x1407295AE, 'f30f104f18'),
    'toolbar_drag_start_gate': (0x14297D411, '3c030f8547010000'),
    'toolbar_feedback_payload': (0x14297D456,
                                  'f2440f11643010c744301800000000c644301c00'),
    'select_completion_gate': (0x14297BF5A, 'f30f1043080f2ec675447a42'),
    'select_completion_entity_payload': (0x14297BF88, '4a8914304e896c3008'),
    'parent_focus_read': (0x14297EA11, '450fb65c0a01'),
    'child_show_write': (0x14297EA63, '45881c31'),
}


INTERACTION_ANCHORS = {
    'zero_size_reference': (0x14297CA99, '450f57c0'),
    'focus_clear_and_show_gate': (0x14297D165, 'c64101008039010f8567faffff'),
    'nonpositive_size_gate': (0x14297D17E, 'f30f5dc8440f2ec10f834dfaffff'),
    'hit_padding_scale': (0x14297D196,
                           'f30f1081e8000000f3410f59c1488b8dc8010000f30f5901'),
    'hit_dimensions_expansion': (0x14297D1AE, 'f30f12c00f58f0'),
    'exclusion_intersection_skip': (0x14297D21D, '0f85aff9ffff'),
    'focus_from_matching_entity': (0x14297D260, 'c6400101'),
    'active_focus_show_gate': (0x14297D570, '803801756b'),
    'focus_from_active_widget': (0x14297D598, 'c6400101'),
    'world_occlusion_argument_false': (0x14297D312, '4531c0'),
    'negative_distance_argument_true': (0x14297D328, '41b001'),
}


def inspect_interaction(pe):
    anchors = []
    for label, (va, expected_hex) in INTERACTION_ANCHORS.items():
        expected = bytes.fromhex(expected_hex)
        actual = pe.read(va, len(expected))
        if actual != expected:
            raise ValueError(f'Interaction anchor changed: {label} at {va:#x}')
        offset, section = pe.locate(va, len(expected))
        anchors.append({'label': label, 'va': hex(va), 'file_offset': hex(offset),
                         'section': section, 'bytes': actual.hex()})
    calls = []
    for va, expected in (
        (0x14297D1D4, 0x140DEEAD0),
        (0x14297D2EC, 0x140C9DCB0),
        (0x14297D315, 0x140C9DBE0),
        (0x14297D373, 0x1409008D0),
    ):
        raw = pe.read(va, 5)
        if raw[0] != 0xE8 or va + 5 + struct.unpack_from('<i', raw, 1)[0] != expected:
            raise ValueError(f'Interaction call changed at {va:#x}')
        calls.append({'va': hex(va), 'target_va': hex(expected)})
    raw = pe.read(0x14297CA9D, 9)
    if raw[:5] != bytes.fromhex('f3440f100d'):
        raise ValueError('Expected selected hit-padding scalar load')
    constant_va = 0x14297CA9D + 9 + struct.unpack_from('<i', raw, 5)[0]
    if pe.read(constant_va, 4) != struct.pack('<f', 10.0):
        raise ValueError('Selected hit-padding scalar changed')
    return {'anchors_checked': anchors, 'direct_calls_checked': calls,
            'hit_dimension_addition': {'constant_va': hex(constant_va),
                                       'scalar_before_user_scales': 10.0},
            'limitations': [
                'Finite ordinary dimensions only; this is not invalid-input verification.',
                'Widget registration gates do not prove cancellation of an older capture.',
                'No overlap arbitration, full scheduling order, or runtime timing is established.',
            ]}


def inspect(binary, symbols):
    pe = PeReader(binary)
    if pe.base != 0x140000000:
        raise ValueError('Unexpected image base')
    checked = []
    for label, (va, expected_hex) in ANCHORS.items():
        expected = bytes.fromhex(expected_hex)
        actual = pe.read(va, len(expected))
        if actual != expected:
            raise ValueError(f'Anchor mismatch: {label} at {va:#x}: {actual.hex()}')
        offset, section = pe.locate(va, len(expected))
        checked.append({'label': label, 'va': hex(va), 'file_offset': hex(offset),
                        'section': section, 'bytes': actual.hex()})

    direct_calls = []
    for va, expected in (
        (0x14033E862, 0x140A003A0),
        (0x1411AEA07, 0x142351070),
        (0x1423510E2, 0x142355C60),
        (0x1411AF089, 0x142363DE0),
    ):
        data = pe.read(va, 5)
        if data[0] != 0xE8:
            raise ValueError(f'Expected direct call at {va:#x}')
        actual = va + 5 + struct.unpack_from('<i', data, 1)[0]
        if actual != expected:
            raise ValueError(f'Call target changed at {va:#x}')
        direct_calls.append({'va': hex(va), 'target_va': hex(actual)})
    queued_callbacks = []
    for va, expected in ((0x14297D43F, 0x1411AE9E0), (0x14297BF81, 0x1411AF020)):
        data = pe.read(va, 7)
        if data[:3] != bytes.fromhex('488d15'):
            raise ValueError('Expected callback address load')
        actual = va + 7 + struct.unpack_from('<i', data, 3)[0]
        if actual != expected:
            raise ValueError('Queued callback changed')
        queued_callbacks.append({'va': hex(va), 'callback_va': hex(actual)})

    table = 0x14329C948
    expected_slots = {0x30: 0x1422F64A0, 0x58: 0x140729540,
                      0x60: 0x140728A60, 0x68: 0x140729570}
    for slot, expected in expected_slots.items():
        if struct.unpack('<Q', pe.read(table + slot, 8))[0] != expected:
            raise ValueError(f'MenuButtonContent vtable slot changed: {slot:#x}')

    pair_load = 0x14297CAB7
    raw = pe.read(pair_load, 9)
    if raw[:5] != bytes.fromhex('f2440f1025'):
        raise ValueError('Expected selected feedback parameter load')
    pair_va = pair_load + 9 + struct.unpack_from('<i', raw, 5)[0]
    pair = pe.read(pair_va, 8)
    if pair != struct.pack('<ff', 0.2, 0.2):
        raise ValueError('Selected feedback parameter pair changed')

    receipt = json.loads(symbols.read_text(encoding='utf-8-sig'))
    if Path(receipt['binary']).resolve() != pe.path or receipt['binary_bytes'] != len(pe.data):
        raise ValueError('DbgHelp receipt names a different PE input')
    symbol_matches = []
    for va, operation in ((0x1411AE9E0, 'insert'), (0x142355C60, 'insert'),
                          (0x1411AF020, 'remove'), (0x142363DE0, 'remove')):
        candidates = [s['name'].split('\0')[0] for s in receipt['symbols']
                      if int(s['address'], 16) == va]
        names = [n for n in candidates
                 if 'UiPlaySelectAnimation' in n
                 and f'entity_command::{operation}::' in n]
        if not names:
            raise ValueError(f'Missing typed callback evidence at {va:#x}')
        symbol_matches.append({'va': hex(va), 'operation': operation, 'name': names[0]})

    return {
        'binary': str(pe.path), 'binary_bytes': len(pe.data), 'image_base': hex(pe.base),
        'anchors_checked': checked, 'direct_calls_checked': direct_calls,
        'queued_callbacks_checked': queued_callbacks,
        'menu_button_vtable': {'va': hex(table),
                               'slots': {hex(k): hex(v) for k, v in expected_slots.items()}},
        'selected_feedback_parameters': {'constant_va': hex(pair_va),
                                         'values': list(struct.unpack('<ff', pair))},
        'symbol_receipt': str(symbols.resolve()), 'typed_commands': symbol_matches,
        'interaction_gate': inspect_interaction(pe),
        'limitations': [
            'Selected static branches only; no game execution or elapsed-time observation.',
            'No final ECS scheduler/deferred-barrier order or stale-remove race is established.',
            'No complete upstream menu scalar writer or per-child delay inventory is established.',
            'Typed names are from the supplied DbgHelp receipt, not PE bytes alone.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--symbols', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.binary, args.symbols)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'output': str(args.output), 'anchors': len(ANCHORS),
                      'interaction_anchors': len(INTERACTION_ANCHORS),
                      'direct_calls': len(result['direct_calls_checked']),
                      'typed_commands': len(result['typed_commands']),
                      'runtime': 'Not Run'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
