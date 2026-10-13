"""Boundary tests for the narrowly selected scalar key reader."""
import json
from pathlib import Path
import struct
import unittest

from read_selected_ability_properties import FormatError
from read_selected_part_deform_keys import read_scalar_keys


def fixture():
    b=bytearray(0x600)
    def u(off,v):struct.pack_into('<I',b,off,v)
    u(0,0x4d494e41);u(4,len(b));u(8,25)
    p=b'C:\\research\\creature\\demo.animation\0';b[12:12+len(p)]=p
    u(0x144,1);u(0x148,0x200);u(0x200,0x220);u(0x220,0x4e414843)
    b[0x228:0x234]=b'mouthMorphs\0';b[0x2b0:0x2b4]=b'mout'
    u(0x220+0xd4,2);u(0x220+0xd8,0x400);u(0x220+0xdc,2);u(0x220+0xe0,0x320)
    for off,typ,keyoff in [(0x320,0,0),(0x340,3,20)]:
        u(off,typ);u(off+8,keyoff);u(off+12,60)
    u(0x344,0x89E06A31)
    for i in range(2):
        struct.pack_into('<i',b,0x400+i*60,i*10)
        struct.pack_into('<ff',b,0x414+i*60,.25+i*.5,1)
    return b


class ScalarReaderChecks(unittest.TestCase):
    def test_reads_interleaved_value_and_weight_without_evaluation(self):
        r=read_scalar_keys(fixture(),0)
        self.assertEqual(r['info_times_raw'],[0,10])
        self.assertEqual([s['value_raw'] for s in r['components'][0]['samples']],[.25,.75])
        self.assertIn('no evaluation',r['coverage'])

    def test_legacy_version_is_explicitly_rejected(self):
        b=fixture();struct.pack_into('<I',b,8,21)
        with self.assertRaisesRegex(FormatError,'version25'):read_scalar_keys(b,0)

    def test_wrong_capability_rejected(self):
        b=fixture();b[0x2b0:0x2b4]=b'grsp'
        with self.assertRaisesRegex(FormatError,'mouthMorphs/mout'):read_scalar_keys(b,0)

    def test_channel_index_is_bounded(self):
        with self.assertRaisesRegex(FormatError,'channel index'):read_scalar_keys(fixture(),1)

    def test_truncated_scalar_component_rejected(self):
        b=fixture();struct.pack_into('<I',b,0x340+8,0x1ad)
        with self.assertRaisesRegex(FormatError,'scalar key outside'):read_scalar_keys(b,0)

    def test_nan_sample_rejected(self):
        b=fixture();struct.pack_into('<f',b,0x414,float('nan'))
        with self.assertRaisesRegex(FormatError,'nonfinite'):read_scalar_keys(b,0)

    def test_short_stride_rejected(self):
        b=fixture();struct.pack_into('<I',b,0x340+12,20)
        with self.assertRaisesRegex(FormatError,'40-byte'):read_scalar_keys(b,0)

    def test_actual_selected_record_keeps_raw_ids_and_values(self):
        p=Path(__file__).resolve().parent.parent/'evidence/local-selected-part-deform-keys.json'
        r=json.loads(p.read_text(encoding='utf8'));s=r['scalar_keys']
        self.assertEqual(s['channel_metadata']['name'],'mouthMorphs')
        self.assertEqual(s['version'],25)
        self.assertEqual(len(s['components']),4)
        self.assertTrue(all(len(c['samples'])==5 for c in s['components']))
        self.assertEqual(s['components'][0]['metadata']['id'],'0x89e06a31')


if __name__=='__main__':unittest.main(verbosity=2)
