"""PCTP research-reader format/boundary checks, not Spore animation execution."""
import json
from pathlib import Path
import struct
import unittest

from read_selected_capability_mappings import read_pctp_v4, select_roles, FormatError
from read_selected_ability_properties import fnv


def role(value):
    return value[::-1]


def fixture(index=8, role_bytes=b'grsp'):
    data = bytearray(struct.pack('>Iif', 0x70637470, 4, 2.0))
    name = b'grasper'
    data += struct.pack('>ii', 1, len(name)) + name + role(role_bytes)
    data += struct.pack('>iI', 1, fnv('grasper')) + role(role_bytes) + struct.pack('>i', index)
    data += struct.pack('>i', 1) + role(role_bytes) + struct.pack('>i', 1) + role(b'gest')
    data += struct.pack('>i', 1) + role(role_bytes) + struct.pack('>i', 1)
    data += struct.pack('>IffI', 0x89e06a31, .5, 1, 0)
    return data


class ReaderChecks(unittest.TestCase):
    def test_mixed_layout_and_exact_end(self):
        data = fixture(); result = read_pctp_v4(data)
        self.assertEqual(result['exact_end'], len(data))
        self.assertEqual(result['names'][0]['name'], 'grasper')
        self.assertEqual(result['remaps'][0]['index_raw'], 8)
        self.assertEqual(result['deforms'][0]['entries'][0]['raw_float_0'], .5)

    def test_reversed_tag_bytes(self):
        tag = read_pctp_v4(fixture())['names'][0]['role']
        self.assertEqual(tag['stored_hex'], '70737267')
        self.assertEqual(tag['logical_hex'], '67727370')

    def test_nul_identity_not_display_identity(self):
        a = read_pctp_v4(fixture(role_bytes=b'a\0bc'))['names'][0]['role']
        b = read_pctp_v4(fixture(role_bytes=b'a bc'))['names'][0]['role']
        self.assertEqual(a['display'], b['display'])
        self.assertNotEqual(a['logical_hex'], b['logical_hex'])

    def test_signed_remap_index_preserved(self):
        self.assertEqual(read_pctp_v4(fixture(-3))['remaps'][0]['index_raw'], -3)

    def test_magic_and_version(self):
        data = fixture(); struct.pack_into('>I', data, 0, 0)
        with self.assertRaisesRegex(FormatError, 'magic'):
            read_pctp_v4(data)
        data = fixture(); struct.pack_into('>i', data, 4, 3)
        with self.assertRaisesRegex(FormatError, 'version3'):
            read_pctp_v4(data)

    def test_negative_or_impossible_count(self):
        for count in (-1, 0x7fffffff):
            data = fixture(); struct.pack_into('>i', data, 12, count)
            with self.assertRaisesRegex(FormatError, 'count'):
                read_pctp_v4(data)

    def test_name_length_guard(self):
        data = fixture(); struct.pack_into('>i', data, 16, 10000)
        with self.assertRaisesRegex(FormatError, 'name length'):
            read_pctp_v4(data)

    def test_non_ascii_name(self):
        data = fixture(); data[20] = 255
        with self.assertRaisesRegex(FormatError, 'non-ASCII'):
            read_pctp_v4(data)

    def test_non_finite_numbers(self):
        data = fixture(); struct.pack_into('>f', data, 8, float('nan'))
        with self.assertRaisesRegex(FormatError, 'priority'):
            read_pctp_v4(data)
        data = fixture(); struct.pack_into('>f', data, len(data) - 12, float('inf'))
        with self.assertRaisesRegex(FormatError, 'deform'):
            read_pctp_v4(data)

    def test_truncated_or_trailing_data(self):
        with self.assertRaisesRegex(FormatError, 'truncated|count'):
            read_pctp_v4(fixture()[:-1])
        with self.assertRaisesRegex(FormatError, 'trailing'):
            read_pctp_v4(fixture() + b'!')

    def test_hash_candidate_matches_stored_record(self):
        selected = [x for x in select_roles(read_pctp_v4(fixture())) if x['role']=='grsp'][0]
        self.assertEqual(len(selected['name_fnv1_to_stored_hash_matches']), 1)

    def test_actual_selected_roles(self):
        p = Path(__file__).resolve().parents[1] / 'evidence/local-selected-capability-mappings.json'
        records = json.loads(p.read_text(encoding='utf-8'))['records']
        self.assertEqual(records[0]['status'], 'unsupported-profile-header-only')
        self.assertEqual(records[1]['counts'], {'names':88,'remaps':168,'aggregates':8,'deforms':20})
        m, g = records[1]['selected_roles']
        self.assertEqual(m['role'], 'mout'); self.assertEqual(g['role'], 'grsp')
        self.assertEqual(g['names'][0]['name'], 'grasper')
        self.assertEqual(g['name_fnv1_to_stored_hash_matches'][0]['index_raw'], 8)

    def test_actual_same_id_distinct_role_defaults(self):
        p = Path(__file__).resolve().parents[1] / 'evidence/local-selected-capability-mappings.json'
        selected = json.loads(p.read_text(encoding='utf-8'))['records'][1]['selected_roles']
        mouth, hand = (r['deforms'][0]['entries'][0] for r in selected)
        self.assertEqual(mouth['deform_id'], hand['deform_id'])
        self.assertEqual((mouth['raw_float_0'],hand['raw_float_0']), (0, .5))


if __name__ == '__main__':
    unittest.main(verbosity=2)
