"""Check GAIT traversal boundaries and selected recorded configuration facts."""
import json
from pathlib import Path
import struct
import unittest

from read_selected_ability_properties import FormatError
from read_selected_movement_resources import read_gait


def gait_blob(path=False, opaque_tail=0, groups=1):
    payload = struct.pack('<ff', 0, .7)
    if groups:
        payload += struct.pack('<ffi', 0, 1, 1) + struct.pack('<26f', *([0] * 26))
        payload += struct.pack('<IIff', 1, int(path), 0, .5)
        if path:
            payload += struct.pack('<III', 1, 0, 0)
            payload += struct.pack('<IIfff', 0, 0, 0, 0, 0)
            payload += (struct.pack('<ffBBHI', 0, 0, 0, 0, 0, opaque_tail)) * 3
    return struct.pack('<IIIIII', 0x54494147, 24 + len(payload), 11, 1, 1, groups) + payload


class MovementReaderChecks(unittest.TestCase):
    def test_gait_header_step_key_and_foot_parameters(self):
        result = read_gait(gait_blob())
        self.assertAlmostEqual(result['stepLengthKeys'][0]['stepLength'], .7)
        self.assertEqual(result['gaitGroupKeys'][0]['dutyFactors'], [.5])
        self.assertEqual(result['gaitGroupKeys'][0]['path_count'], 0)

    def test_path_traversal_keeps_opaque_word_variants(self):
        for tail in (0, 0xFFFFFFFF, 0xCDCDCDCD, 0x12345678):
            result = read_gait(gait_blob(True, tail))
            self.assertEqual(result['opaque_spline_tail_counts'], {f'0x{tail:08x}': 3})
            self.assertEqual(result['validated_path_counts']['position_keys'], 1)

    def test_bad_magic_version_size_counts_truncation_rejected(self):
        cases = []
        for offset, value in [(0, 0), (4, 0), (8, 10), (20, 1000)]:
            b = bytearray(gait_blob())
            struct.pack_into('<I', b, offset, value)
            cases.append(b)
        b = bytearray(gait_blob(True)[:-1])
        struct.pack_into('<I', b, 4, len(b))
        cases.append(b)
        for data in cases:
            with self.assertRaises(FormatError):
                read_gait(data)

    def test_nonfinite_fields_and_trailing_bytes_rejected(self):
        data = bytearray(gait_blob())
        struct.pack_into('<f', data, 24, float('nan'))
        with self.assertRaises(FormatError):
            read_gait(data)
        data = bytearray(gait_blob() + b'X')
        struct.pack_into('<I', data, 4, len(data))
        with self.assertRaises(FormatError):
            read_gait(data)

    def test_recorded_local_resources_have_complete_coverage(self):
        path = Path(__file__).resolve().parent.parent / 'evidence/local-selected-movement-resources.json'
        self.report = report = json.loads(path.read_text(encoding='utf-8'))
        props = [r for r in report['records'] if 'selected_properties' in r]
        gaits = [r for r in report['records'] if 'gait_summary' in r]
        self.assertEqual((len(props), len(gaits)), (8, 14))
        for r in gaits:
            self.assertEqual(r['memory_bytes'], r['gait_summary']['fully_consumed_bytes'])
            self.assertIn('unknown', r['gait_summary']['spline_tail_semantics'])
        central = [r for r in props if r['key']['group'] == '0xad56080c']
        self.assertEqual(len(central), 2)
        self.assertEqual(central[0]['selected_properties'], central[1]['selected_properties'])
        fields = central[0]['selected_properties']
        self.assertAlmostEqual(fields['creatureAvatarGoalStopDistance']['values'][0], .4)
        self.assertEqual(fields['creatureBaseDeceleration']['values'], [0])

    def test_six_slot_gait_and_two_slot_patch_difference_are_preserved(self):
        path = Path(__file__).resolve().parent.parent / 'evidence/local-selected-movement-resources.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        records = {(r['package'], r['name']): r for r in report['records'] if 'gait_summary' in r}
        for package in ('Spore_Game.package', 'PatchData.package'):
            key = records[(package, 'gait6')]['gait_summary']['gaitGroupKeys'][0]
            self.assertEqual(key['taxon_count'], 6)
            self.assertEqual(key['triggers'], [0, .5, .33329999446868896, .833299994468689,
                                               .6665999889373779, .16660000383853912])
            self.assertEqual(key['dutyFactors'], [.5] * 6)
            high = records[(package, 'gait6')]['gait_summary']['gaitGroupKeys'][-1]
            self.assertEqual(high['triggers'], [.6499999761581421, .6000000238418579,
                                               .550000011920929, .5, 0, .05000000074505806])
            for duty in high['dutyFactors']:
                self.assertAlmostEqual(duty, .4)
        base = records[('Spore_Game.package', 'gait2')]['gait_summary']
        patch = records[('PatchData.package', 'gait2')]['gait_summary']
        self.assertEqual(len(base['stepLengthKeys']), 8)
        self.assertEqual(len(patch['stepLengthKeys']), 10)
        self.assertEqual([k['speedi'] for k in patch['stepLengthKeys'][-2:]], [11.5, 12])


if __name__ == '__main__':
    unittest.main(verbosity=2)
