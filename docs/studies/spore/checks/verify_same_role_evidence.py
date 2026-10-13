"""Consistency checks on selected static records; no native/runtime validation."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import unittest


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EVIDENCE = HERE.parent / 'evidence'


def read(name):
    return json.loads((EVIDENCE / name).read_text(encoding='utf-8'))


class StaticEvidenceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local = read('local-same-role-selector-observations.json')
        cls.prior = read('local-selected-action-channels.json')
        cls.public = read('public-same-role-binding-contracts.json')
        cls.animations = [r for r in cls.prior['records'] if 'anim' in r]

    def test_input_and_reader_identities(self):
        for identity in (self.local['prior_evidence'], self.local['reader']):
            path = REPO / identity['path'].replace('\\', '/')
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), identity['sha256'])
        self.assertEqual(self.local['format_commit'], self.prior['format_commit'])

    def test_resource_summary_matches_prior(self):
        self.assertEqual(len(self.local['resources']),46)
        by_key={(r['package'],tuple(r['key'].items())):r for r in self.animations}
        for row in self.local['resources']:
            prior=by_key[(row['package'],tuple(row['key'].items()))]
            for key in ('key','offset','stored_bytes','memory_bytes','compression','stored_sha256','decoded_sha256'):
                self.assertEqual(row[key],prior[key])
            self.assertEqual(row['channel_count'],len(prior['anim']['channels']))
            self.assertEqual(row['version'],prior['anim']['version'])
        self.assertEqual(sum(r['channel_count'] for r in self.local['resources']),612)

    def test_all_context_pattern_counts(self):
        expected=Counter()
        for row in self.animations:
            for channel in row['anim']['channels']:
                for role in ('primaryContext','secondaryContext'):
                    c=channel[role]
                    expected[(role,c['flags'],c['capability_bytes'],c['field_8'],c['field_C'])]+=1
        actual=Counter()
        for c in self.local['statistics']['unique_context_patterns']:
            key=(c['context_role'],c['flags'],c['capability_bytes'],c['field_8'],c['field_C'])
            self.assertNotIn(key,actual)
            actual[key]=c['occurrences']
        self.assertEqual(actual,expected)
        self.assertEqual(sum(actual.values()),1224)
        self.assertEqual(len(actual),32)
        self.assertTrue(all(k[3:] == ('0x00000000','0x00000000') for k in actual))

    def test_example_raw_words_and_offsets(self):
        self.assertEqual(len(self.local['examples']),26)
        for e in self.local['examples']:
            c=e['context']; raw=bytes.fromhex(c['raw_16_bytes'])
            self.assertEqual(len(raw),16)
            flags,payload,u8,uc=struct.unpack('<4I',raw)
            self.assertEqual(flags,int(c['flags'],16))
            self.assertEqual(raw[4:8].hex(),c['capability_bytes'])
            self.assertEqual(payload,int(c['capability_or_id_le_u32'],16))
            self.assertEqual((u8,uc),(int(c['field_8'],16),int(c['field_C'],16)))
            relative=0x8c if e['context_role']=='primaryContext' else 0x9c
            self.assertEqual(c['decoded_resource_offset'],e['channel_decoded_offset']+relative)
            self.assertLessEqual(c['decoded_resource_offset']+16,
                                 self.local['resources'][e['resource_record_index']]['memory_bytes'])
            self.assertIsNone(c['package_file_offset'])

    def test_decoder_masks_and_unsigned_groups(self):
        schema=self.local['selector_format']
        known=int(schema['type_mask'],16)|int(schema['limb_mask'],16)|int(schema['extent']['mask'],16)
        for axis in schema['axes'].values():
            known |= int(axis['mask'],16)
        for e in self.local['examples']:
            flags=int(e['context']['flags'],16); decoded=e['selector_decoded']
            self.assertEqual(int(decoded['type_masked_value'],16),flags&int(schema['type_mask'],16))
            for axis,spec in schema['axes'].items():
                self.assertEqual(int(decoded['select'+axis]['masked_value'],16),flags&int(spec['mask'],16))
            self.assertEqual(int(decoded['extent']['masked_value'],16),flags&int(schema['extent']['mask'],16))
            self.assertEqual(int(decoded['unknown_select_flags'],16),flags&(~known&0xffffffff))
            bind=int(e['bindFlags'],16)
            self.assertEqual(e['community_blendGroup'],(bind>>16)&255)
            self.assertEqual(e['community_variantGroup'],(bind>>24)&255)

    def test_secondary_field_not_enabled_and_no_extents(self):
        stats=self.local['statistics']
        self.assertEqual((stats['secondary_none_count'],stats['secondary_other_count']),(611,1))
        self.assertEqual(stats['raw_extent_mask_nonzero_count'],0)
        other=[(r,c) for r in self.animations for c in r['anim']['channels']
               if c['secondaryContext']['flags'] != '0x00000002']
        self.assertEqual(len(other),1)
        resource,channel=other[0]
        self.assertEqual(resource['key']['instance'],'0x9a1bf2ca')
        self.assertEqual(channel['name'],'L hand')
        self.assertEqual(channel['secondaryContext']['capability_ascii'],'mout')
        self.assertEqual(int(channel['movementFlags'],16)&1,0)

    def test_fixed_public_sources_and_recorded_coverage(self):
        p=self.public
        self.assertEqual(len(p['files']),10)
        self.assertEqual(len(p['contracts']),16)
        self.assertEqual(p['verification']['status'],'pass')
        self.assertEqual(p['verification']['reused_source_matches'],9)
        identities=[r['path'] for r in p['files']]
        self.assertEqual(len(set(identities)),10)
        for row in p['files']:
            self.assertEqual(len(row['sha256']),64)
            self.assertIn(row['commit'],row['url'])
            for start,end in row['read_ranges']:
                self.assertTrue(1<=start<=end<=row['lines'])

    def test_scope_and_absent_native_claims(self):
        self.assertIsNone(self.local['rea_evidence_id'])
        self.assertFalse(self.local['coverage']['curves_events_predicates_relocations_decoded'])
        self.assertFalse(self.local['coverage']['old_version_fixups_applied'])
        self.assertFalse(self.public['scope']['game_executed'])
        self.assertFalse(self.public['scope']['game_modified'])
        self.assertFalse(self.public['scope']['private_data_read'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
