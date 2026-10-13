"""Research parser boundary checks and actual selected configuration assertions."""
import json
from pathlib import Path
import struct
import unittest
from read_selected_ability_properties import FormatError
from read_selected_action_channels import read_tlsa, read_anim_metadata


def text(value):return struct.pack('>I',len(value))+value.encode('utf-16-le')


def tlsa(version):
    b=struct.pack('>IIII',0x74736c61,version,1,123)
    if version<=8:
        if version==8:b+=struct.pack('>f',.5)
        b+=struct.pack('>I',1)+text('a')+struct.pack('>IffBfBIII',456,1,-1,0,-1,1,0,0,0)
    else:
        b+=text('group')+struct.pack('>ffBB',.5,-1,0,1)
        if version==10:b+=b'\0'
        b+=struct.pack('>IIIIfIffI',0,0,0,1,1,1,1,-1,456)+text('a')
    return b


def anim():
    b=bytearray(0x400)
    def u(off,v):struct.pack_into('<I',b,off,v)
    u(0,0x4d494e41);u(4,len(b));u(8,21)
    path=b'C:\\research\\creature\\demo.animation\0';b[12:12+len(path)]=path
    u(0x144,1);u(0x148,0x200);u(0x200,0x220)
    u(0x220,0x4e414843);b[0x228:0x22a]=b'x\0'
    b[0x220+0x90:0x220+0x94]=b'grsp'
    u(0x220+0xac,0x07040004)
    u(0x220+0xd4,1);u(0x220+0xd8,0x340)
    u(0x220+0xdc,1);u(0x220+0xe0,0x320)
    u(0x320,0x11);u(0x32c,8)
    return b


class ReaderChecks(unittest.TestCase):
    def test_tlsa_supported_versions_preserve_serialized_absence(self):
        for v in (7,8,9,10):
            r=read_tlsa(tlsa(v),{123})
            g=r['selected_groups'][0]
            self.assertTrue(g['allowLocomotion'])
            self.assertEqual(g['priorityOverride'],None if v==7 else .5)
            self.assertEqual(g['choices'][0]['animations'][0]['id'],'0x000001c8')

    def test_unselected_groups_traversed_but_not_exported(self):
        r=read_tlsa(tlsa(10),{999})
        self.assertEqual(r['selected_groups'],[])
        self.assertEqual(r['fully_consumed_bytes'],len(tlsa(10)))

    def test_tlsa_invalid_header_count_truncation_and_trailing_rejected(self):
        cases=[tlsa(10)[:-1],tlsa(10)+b'X',b'bad!'+tlsa(10)[4:]]
        for off,value in ((4,11),(8,10001)):
            b=bytearray(tlsa(10));struct.pack_into('>I',b,off,value);cases.append(b)
        for b in cases:
            with self.assertRaises(FormatError):read_tlsa(b,{123})

    def test_tlsa_invalid_boolean_and_nonfinite_number_rejected(self):
        b=bytearray(tlsa(9));name_end=16+len(text('group'))
        struct.pack_into('>f',b,name_end,float('nan'))
        with self.assertRaises(FormatError):read_tlsa(b,{123})
        b=bytearray(tlsa(9));b[name_end+8]=2
        with self.assertRaises(FormatError):read_tlsa(b,{123})

    def test_anim_separate_component_types_and_group_bits(self):
        r=read_anim_metadata(anim());c=r['channels'][0]
        self.assertEqual((c['community_blendGroup'],c['community_variantGroup']),(4,7))
        self.assertEqual(c['primaryContext']['capability_ascii'],'grsp')
        self.assertEqual(c['components'][0]['type'],1)
        self.assertIn('not decoded',r['coverage'])

    def test_anim_out_of_range_pointers_and_zero_stride_rejected(self):
        for off,value in ((4,12),(0x148,0x1000),(0x200,0x1000),(0x220+0xe0,0x1000),(0x32c,0)):
            b=anim();struct.pack_into('<I',b,off,value)
            with self.assertRaises(FormatError):read_anim_metadata(b)

    def test_observed_attack_groups_and_patch_versions(self):
        p=Path(__file__).resolve().parent.parent/'evidence/local-selected-action-channels.json'
        d=json.loads(p.read_text(encoding='utf-8'));rs=d['records']
        self.assertEqual((sum('tlsa' in r for r in rs),sum('anim' in r for r in rs)),(2,46))
        self.assertEqual(d['missing_animation_ids'],[])
        for r in (r for r in rs if 'tlsa' in r):
            self.assertEqual(len(r['tlsa']['selected_groups']),13)
            for g in r['tlsa']['selected_groups']:
                self.assertEqual(g['allowLocomotion'],g['id']!='0x044ddeaf')
                self.assertEqual(g['blendInTime'],-1)
            if r['tlsa']['version']==7:
                self.assertTrue(all(g['priorityOverride'] is None for g in r['tlsa']['selected_groups']))
            else:
                strike=next(g for g in r['tlsa']['selected_groups'] if g['id']=='0x044ddd75')
                self.assertEqual(strike['priorityOverride'],1.5)
                self.assertEqual([len(c['animations']) for c in strike['choices']],[4]*6)

    def test_observed_channel_covarying_bits_and_metadata_coverage(self):
        p=Path(__file__).resolve().parent.parent/'evidence/local-selected-action-channels.json'
        d=json.loads(p.read_text(encoding='utf-8'))
        rows=[r for r in d['records'] if 'anim' in r]
        self.assertEqual(sum(len(r['anim']['channels']) for r in rows),612)
        self.assertEqual({r['anim']['version'] for r in rows if r['package']=='Spore_Game.package'},{21})
        self.assertEqual({r['anim']['version'] for r in rows if r['package']=='PatchData.package'},{25})
        bite=next(r['anim'] for r in rows if r['package']=='Spore_Game.package'
                  and r['anim']['embedded_path'].endswith('com_bite_lvl01_a.animation'))
        cs={c['name']:c for c in bite['channels']}
        self.assertEqual(cs['head']['community_variantGroup'],1)
        self.assertEqual(cs['mouthMorphs']['community_variantGroup'],1)
        self.assertEqual(cs['FX head']['community_blendGroup'],cs['head']['community_blendGroup'])


if __name__=='__main__':unittest.main(verbosity=2)
