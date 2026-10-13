"""Selected event record consistency only; no Spore consumers or runtime."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import unittest


EVIDENCE=Path(__file__).resolve().parent.parent/'evidence'


def read(name):
    return json.loads((EVIDENCE/name).read_text(encoding='utf-8'))


class EventEvidenceConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current=read('local-selected-action-events.json')
        cls.prior=read('local-selected-action-channels.json')
        cls.public=read('public-action-event-format-contracts.json')

    def test_reader_and_prior_identity(self):
        for row in (self.current['reader'],self.current['prior_evidence']):
            self.assertEqual(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest(),row['sha256'])
        for package in self.current['packages']:
            self.assertIn(package['sha256'],[r['sha256'] for r in self.prior['packages']])
        json.dumps(self.current,allow_nan=False)

    def test_exact_eight_records_are_existing_selected_resources(self):
        old={(r['package'],r['key']['instance']):r for r in self.prior['records'] if 'anim' in r}
        records=self.current['records']
        self.assertEqual(len(records),8)
        self.assertEqual(len({(r['package'],r['key']['instance']) for r in records}),8)
        for r in records:
            prior=old[(r['package'],r['key']['instance'])]
            for key in ('key','offset','stored_bytes','memory_bytes','compression','stored_sha256','decoded_sha256'):
                self.assertEqual(r[key],prior[key])
            self.assertEqual(r['status'],'decoded-event-metadata')
            self.assertIn('\\creature\\',r['anim_events']['embedded_path'].lower())

    def test_aggregate_counts_and_nonzero_ranges(self):
        coverages=[r['anim_events']['coverage'] for r in self.current['records']]
        for key,total in (('event_records',60),('INFO_rows_examined',770),
                          ('nonzero_INFO_rows',48),('zero_count_INFO_rows',722),
                          ('event_reference_occurrences',60)):
            self.assertEqual(sum(c[key] for c in coverages),total)
        self.assertTrue(all(c['all_nonzero_INFO_ranges_legal'] for c in coverages))
        self.assertEqual(sum(c['repeated_event_index_count'] for c in coverages),0)

    def test_event_raw_layout_and_selector_words(self):
        types=Counter()
        for row in self.current['records']:
            a=row['anim_events']; self.assertEqual(a['header']['eventCount'],len(a['events']))
            for event in a['events']:
                raw=bytes.fromhex(event['raw_96_bytes']); self.assertEqual(len(raw),96)
                self.assertEqual(event['decoded_offset'],a['header']['eventPointer']+96*event['event_index'])
                self.assertLessEqual(event['decoded_offset']+96,row['memory_bytes'])
                flags=struct.unpack_from('<I',raw)[0]
                self.assertEqual(flags,int(event['flags'],16))
                self.assertEqual(flags&0x20007,event['community_event_type_value'])
                types[event['community_event_type']]+=1
                for i,selector in enumerate(event['selectors']):
                    block=raw[4+12*i:16+12*i]
                    self.assertEqual(block.hex(),selector['raw_12_bytes'])
                    self.assertEqual(struct.unpack_from('<I',block)[0],int(selector['flags'],16))
                    self.assertEqual(block[8:12].hex(),selector['capability_bytes'])
                self.assertEqual(event['selectors'][3]['role'],'source4')
                self.assertEqual(struct.unpack_from('<I',raw,0x3c)[0],int(event['id'],16))
        self.assertEqual(types,Counter(effect=26,sound=18,eventControl=10,unk3=6))

    def test_INFO_raw_words_and_indexes(self):
        for resource in self.current['records']:
            a=resource['anim_events']
            for row in a['info_event_references']:
                raw=bytes.fromhex(row['raw_20_bytes']); self.assertEqual(len(raw),20)
                self.assertEqual(struct.unpack_from('<i',raw)[0],row['time_raw'])
                start,count=struct.unpack_from('<HB',raw,8)
                self.assertEqual((start,count),(row['eventStartIndex'],row['eventCount']))
                self.assertEqual(row['event_indices'],list(range(start,start+count)))
                self.assertLessEqual(start+count,len(a['events']))
                self.assertLessEqual(row['decoded_offset']+20,resource['memory_bytes'])
            for row in a['zero_count_INFO_examples']:
                self.assertEqual(row['eventCount'],0)
                self.assertEqual(bytes.fromhex(row['raw_20_bytes'])[10],0)

    def test_spit_same_ID_is_different_event_index(self):
        r=next(r for r in self.current['records'] if r['package']=='PatchData.package' and r['key']['instance']=='0x38ed1075')
        a=r['anim_events']; hits=[e for e in a['events'] if e['name'] and e['name']['name']=='hit']
        self.assertEqual([e['event_index'] for e in hits],[1,3])
        self.assertEqual({e['id'] for e in hits},{'0x428ae400'})
        links={r['channel_name']:r for r in a['info_event_references']}
        self.assertEqual(links['shoot_rng']['event_indices'],[1,2])
        self.assertEqual(links['poison_cell']['event_indices'],[3,4])
        self.assertEqual(links['shoot_rng']['time_raw'],links['poison_cell']['time_raw'])
        self.assertEqual(links['shoot_rng']['time_raw'],16)

    def test_actual_first_only_is_event_specific(self):
        impacts=[e for r in self.current['records'] for e in r['anim_events']['events']
                 if e['name'] and e['name']['name']=='impact_event']
        self.assertEqual(len(impacts),6)
        for e in impacts:
            self.assertEqual(e['community_event_type'],'unk3')
            for selector in e['selectors'][:3]:
                self.assertEqual(selector['flags'],'0x00000012')
                self.assertEqual(selector['community_filter'],'firstOnly')
            self.assertEqual(e['selectors'][3]['flags'],'0x00004015')

    def test_public_source_locators_and_no_REA_claim(self):
        self.assertIsNone(self.current['rea_evidence_id'])
        for source in self.public['sources']:
            self.assertEqual(len(source['sha256']),64)
            self.assertTrue(any(commit in source['url'] for commit in self.public['commits'].values()))
            for observation in source['observations']:
                self.assertTrue(all(1<=n<=source['line_count'] for n in observation['lines']))


if __name__=='__main__':
    unittest.main(verbosity=2)
