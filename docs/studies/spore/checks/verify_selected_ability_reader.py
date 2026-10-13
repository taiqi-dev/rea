"""Synthetic format-boundary checks plus checks of the recorded local findings."""
import json
from pathlib import Path
import struct
import unittest

from read_selected_ability_properties import FormatError, fnv, read_index, read_prop, refpack


def packed(payload, size):
    return b'\x10\xfb' + size.to_bytes(3, 'big') + payload


class ReaderChecks(unittest.TestCase):
    def test_registered_names_use_fnv1_not_fnv1a(self):
        self.assertEqual(fnv('CreatureAbilities'), 0xDD91AC58)
        self.assertEqual(fnv('CreatureAbilityTemplate'), 0x7C330EE2)
        self.assertEqual(fnv('STRIKETEMPLATE'), 0xAD00CD69)

    def test_refpack_literal_and_terminal_forms(self):
        self.assertEqual(refpack(packed(b'\xe0ABCD\xffXYZ', 7), 7), b'ABCDXYZ')
        self.assertEqual(refpack(packed(b'\xfc', 0), 0), b'')

    def test_refpack_three_copy_forms_and_overlap(self):
        self.assertEqual(refpack(packed(b'\xe0ABCD\x00\x03\xfc', 7), 7), b'ABCDABC')
        self.assertEqual(refpack(packed(b'\xe0ABCD\x80\x00\x03\xfc', 8), 8), b'ABCDABCD')
        self.assertEqual(refpack(packed(b'\xe0ABCD\xc0\x00\x03\x00\xfc', 9), 9), b'ABCDABCDA')
        self.assertEqual(refpack(packed(b'\xe0ABCD\x00\x00\xfc', 7), 7), b'ABCDDDD')

    def test_refpack_rejects_corrupt_length_backref_and_tail(self):
        cases = [(packed(b'\xfc', 1), 1), (packed(b'\x00\x00\xfc', 3), 3),
                 (packed(b'\xe0AB', 4), 4), (packed(b'\xfcX', 0), 0),
                 (packed(b'\xe0ABCD', 4), 4), (packed(b'\xfc', 0), 1)]
        for data, size in cases:
            with self.subTest(data=data), self.assertRaises(FormatError):
                refpack(data, size)

    def test_prop_mixed_endianness_scalar_key_and_vector_padding(self):
        data = struct.pack('>I', 3)
        data += struct.pack('>IHHf', 1, 13, 0, 30.0)
        data += struct.pack('>IHH', 2, 0x20, 0) + struct.pack('<IIII', 9, 0, 11, 0)
        data += struct.pack('>IHH', 3, 0x30, 0) + struct.pack('<ffff', 2, 5, 0, 0)
        props = read_prop(data)
        self.assertEqual(props[1]['values'], [30.0])
        self.assertEqual(props[2]['values'][0]['group'], '0x0000000b')
        self.assertEqual(props[3]['values'], [[2.0, 5.0]])

    def test_prop_rejects_duplicate_type_truncation_and_trailing_data(self):
        header = struct.pack('>IHH', 1, 13, 0)
        cases = [struct.pack('>I', 1) + header,
                 struct.pack('>I', 2) + (header + struct.pack('>f', 1)) * 2,
                 struct.pack('>IIHH', 1, 1, 0x99, 0),
                 struct.pack('>I', 0) + b'x',
                 struct.pack('>IIHHII', 1, 1, 13, 0x30, 1, 8) + b'12345678']
        for data in cases:
            with self.subTest(data=data), self.assertRaises(FormatError):
                read_prop(data)

    def test_index_common_fields_count_and_resource_bounds(self):
        data = bytearray(100)
        data[:12] = b'DBPF' + struct.pack('<II', 3, 0)
        for offset, value in [(36, 1), (44, 28), (64, 100)]:
            struct.pack_into('<I', data, offset, value)
        # Common type/group/high-ID prefix(16) plus one entry(20).
        data += struct.pack('<IIIIIIIIHBB', 7, 0xB1B104, 4, 0, 5, 96, 4, 4, 0, 0, 0)
        struct.pack_into('<I', data, 44, 36)
        entries, info = read_index(data)
        self.assertEqual(info['examined_entries'], 1)
        self.assertEqual(entries[(0xB1B104, 4, 5)]['offset'], 96)
        struct.pack_into('<I', data, 36, 2)
        with self.assertRaises(FormatError):
            read_index(data)
        struct.pack_into('<I', data, 36, 1)
        struct.pack_into('<I', data, 120, 500)
        with self.assertRaises(FormatError):
            read_index(data)

    def test_recorded_local_config_preserves_both_packages_and_raw_parents(self):
        path = Path(__file__).resolve().parent.parent / 'evidence/local-selected-attack-properties.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(report['records']), 50)
        self.assertEqual(report['missing_keys'], [])
        self.assertIn('unknown', report['package_load_order'])
        groups = {}
        for record in report['records']:
            groups.setdefault(record['name'], []).append(record)
            if 'parent_lookup_candidate' in record:
                self.assertEqual(record['selected_properties']['parent']['values'][0]['type'], '0x00000000')
        self.assertEqual(len(groups), 25)
        for name, records in groups.items():
            self.assertEqual({r['package'] for r in records}, {'Spore_Game.package', 'PatchData.package'})
            self.assertEqual(records[0]['selected_properties'], records[1]['selected_properties'], name)
        for name, value in [('BiteTemplate', 1), ('StrikeTemplate', 1), ('SpitTemplate', 30)]:
            self.assertEqual(groups[name][0]['selected_properties']['creatureAbilityRange']['values'], [value])


if __name__ == '__main__':
    unittest.main(verbosity=2)
