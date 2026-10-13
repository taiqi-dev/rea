"""Bounds, endian and reference checks for the limited skinpaint reader."""
import dataclasses
import math
from pathlib import Path
import struct
import unittest

from read_selected_skinpaint_sections import (FormatError, read_component_sections, read_distribute,
    section_payload, read_sequences, read_visual_exports, trace_selected_visual)


def distribute_record(particle=3, region=2, body=(.02, .98), selection=(), label=b'', bad_bool=None):
    flags = bytes((0, 1 if bad_bool is None else bad_bool, 0, 1))
    return (label+b'\0'+struct.pack('>ifiiff',particle,.05,-1,region,.7,-.7)
            +struct.pack('<ff',*body)+flags+struct.pack('>i',len(selection))
            +b''.join(struct.pack('>if',*item) for item in selection)+b'\x00')


def section(type_id, version, records):
    body=struct.pack('>I',len(records))+b''.join(records)
    return struct.pack('>HHI',type_id,version,len(body))+body


def effect(records, prefix=b''):
    return b'\x00\x04'+prefix+section(0x23,2,records)+b'\xff\xff'+b'UNREAD_VISUAL_SUFFIX'


def visual_block(kind=0x23, index=0):
    return (struct.pack('>BI',kind,0)+b'\0'*54+b'\0\xff'+struct.pack('>i',0)
            +b'\0'*36+struct.pack('>fi',1.,index))


def visual_record(blocks):
    return b'\0'*25+struct.pack('>i',0)+b'\0'*16+struct.pack('>i',len(blocks))+b''.join(blocks)


def visual_tail(records, export_index=0):
    return (struct.pack('>hi',1,len(records))+b''.join(records)
            +struct.pack('>iII',export_index,0,0x103691ce)
            +struct.pack('>iii',-1,-1,0))


class SelectedSkinReader(unittest.TestCase):
    def parse(self,data,particles=8):
        sections,end=read_component_sections(data)
        target=next(s for s in sections if s.type_id==0x23)
        return read_distribute(data,target,particles),end

    def test_variable_string_and_selection_have_exact_boundaries(self):
        blob=effect([distribute_record(label=b'anchor',selection=((5,.3),(6,.8))),distribute_record(particle=-1)])
        rows,end=self.parse(blob)
        self.assertEqual(rows[0]['label'],'anchor')
        self.assertEqual([r['particle_index'] for r in rows[0]['particle_select']],[5,6])
        self.assertEqual(rows[1]['particle_index'],-1)
        self.assertEqual(rows[0]['decoded_byte_end'],rows[1]['decoded_byte_start'])
        self.assertEqual(blob[end:],b'UNREAD_VISUAL_SUFFIX')

    def test_mixed_endian_body_range_is_not_big_endian(self):
        rows,_=self.parse(effect([distribute_record()]))
        self.assertAlmostEqual(rows[0]['body_range'][0],.02,places=7)
        self.assertAlmostEqual(rows[0]['body_range'][1],.98,places=7)
        self.assertAlmostEqual(rows[0]['spacing'],.05,places=7)

    def test_unknown_section_is_retained_opaque_and_skipped_by_size(self):
        opaque=section(0x7fff,19,[b'opaque\x00data'])
        blob=effect([distribute_record()],opaque)
        sections,end=read_component_sections(blob)
        self.assertEqual([s.type_id for s in sections],[0x7fff,0x23])
        self.assertEqual(section_payload(blob,sections[0])[4:],b'opaque\x00data')
        self.assertEqual(self.parse(blob)[0][0]['particle_index'],3)

    def test_truncated_header_and_oversized_section(self):
        for blob in (b'\0',b'\0\x04\0\x23\0',b'\0\x04'+struct.pack('>HHI',0x23,2,2**32-1)+b'\0'*4):
            with self.subTest(blob=blob),self.assertRaises(FormatError):
                read_component_sections(blob)

    def test_missing_terminator_and_duplicate_sections(self):
        one=section(0x23,2,[distribute_record()])
        with self.assertRaisesRegex(FormatError,'MissingComponentTerminator'):
            read_component_sections(b'\0\x04'+one)
        with self.assertRaisesRegex(FormatError,'DuplicateComponentType'):
            read_component_sections(b'\0\x04'+one+one+b'\xff\xff')

    def test_component_version_is_explicit(self):
        blob=effect([distribute_record()]); sections,_=read_component_sections(blob)
        with self.assertRaisesRegex(FormatError,'UnsupportedDistributeSection'):
            read_distribute(blob,dataclasses.replace(sections[0],version=3),8)
        with self.assertRaisesRegex(FormatError,'UnsupportedEffectVersion'):
            read_component_sections(b'\0\x05\xff\xff')

    def test_bad_reference_does_not_alias_other_component_types(self):
        for particle in (-2,8):
            with self.subTest(particle=particle),self.assertRaisesRegex(FormatError,'ParticleIndexOutOfRange'):
                self.parse(effect([distribute_record(particle=particle)]))
        with self.assertRaisesRegex(FormatError,'ParticleIndexOutOfRange'):
            self.parse(effect([distribute_record(selection=((9,.5),))]))

    def test_impossible_record_count_and_trailing_record_data(self):
        blob=effect([distribute_record()]); sections,_=read_component_sections(blob)
        broken=bytearray(blob);struct.pack_into('>I',broken,sections[0].body_start,1000000)
        updated=read_component_sections(broken)[0][0]
        with self.assertRaisesRegex(FormatError,'ImpossibleDistributeCount'):
            read_distribute(broken,updated,8)
        extra=b'\0\x04'+section(0x23,2,[distribute_record()+b'extra'])+b'\xff\xff'
        with self.assertRaisesRegex(FormatError,'DistributeTrailingBytes'):
            self.parse(extra)

    def test_invalid_boolean_and_nonfinite_are_diagnostic(self):
        with self.assertRaisesRegex(FormatError,'InvalidBoolean'):
            self.parse(effect([distribute_record(bad_bool=2)]))
        with self.assertRaisesRegex(FormatError,'NonFiniteDistributeValue'):
            self.parse(effect([distribute_record(body=(math.inf,1))]))

    def test_raw_finite_cd_pattern_is_preserved_not_normalized(self):
        raw=distribute_record(body=(struct.unpack('<f',bytes.fromhex('cdcdcdcd'))[0],1))
        row=self.parse(effect([raw]))[0][0]
        self.assertEqual(row['raw_float_fields']['body_range_hex'][:8],'cdcdcdcd')
        self.assertEqual(row['body_range'][0],-431602080.)

    def test_payload_digest_prevents_wrong_source_slice(self):
        blob=effect([distribute_record()]); target=read_component_sections(blob)[0][0]
        broken=bytearray(blob);broken[target.body_start+10]^=1
        with self.assertRaisesRegex(FormatError,'SectionIdentityMismatch'):
            read_distribute(broken,target,8)

    def test_visual_block_and_export_exact_end(self):
        blob=visual_tail([visual_record([visual_block()])])
        parsed=read_visual_exports(blob,0)
        self.assertEqual(parsed['decoded_end'],len(blob))
        self.assertEqual(parsed['exports'][0]['name_hash'],'0x103691ce')
        self.assertEqual(parsed['visuals'][0]['blocks'][0]['component_index_raw'],0)
        self.assertEqual(parsed['visuals'][0]['blocks'][0]['decoded_byte_end']-
                         parsed['visuals'][0]['blocks'][0]['decoded_byte_start'],109)

    def test_visual_bad_export_and_trailing_bytes(self):
        with self.assertRaisesRegex(FormatError,'ExportVisualIndexOutOfRange'):
            read_visual_exports(visual_tail([visual_record([])],export_index=1),0)
        with self.assertRaisesRegex(FormatError,'EffectDirectoryTrailingBytes'):
            read_visual_exports(visual_tail([visual_record([])])+b'\0',0)

    def test_sequence_time_is_little_endian_and_wait_is_null(self):
        record=struct.pack('>i',2)+struct.pack('<ff',.25,.5)+struct.pack('>i',0)
        record+=struct.pack('<ff',-1,-1)+struct.pack('>iI',-1,0)
        blob=b'\0\x04'+section(4,1,[record])+b'\xff\xff'
        s=read_component_sections(blob)[0][0]
        rows=read_sequences(blob,s,1)
        self.assertEqual(rows[0]['steps'][0]['time_range_stored'],[.25,.5])
        self.assertEqual(rows[0]['steps'][1]['visual_index'],-1)

    def test_sequence_graph_distinguishes_visual_and_component_indices(self):
        visuals=[{'blocks':[{'block_type':4,'component_index_raw':0}]},
                 {'blocks':[{'block_type':0x23,'component_index_raw':2,
                             'decoded_byte_start':100,'decoded_byte_end':209,'flags_raw':0}]}]
        sequences=[{'steps':[{'ordinal':0,'visual_index':1,'time_range_stored':[-1,-1]}]}]
        result=trace_selected_visual(0,visuals,sequences,{0x23:3})
        self.assertEqual(result[0]['path'],[('visual',0),('sequence',0),('visual',1),('component',0x23,2)])

    def test_selected_graph_cycle_is_diagnostic(self):
        visuals=[{'blocks':[{'block_type':4,'component_index_raw':0}]}]
        sequences=[{'steps':[{'ordinal':0,'visual_index':0,'time_range_stored':[-1,-1]}]}]
        with self.assertRaisesRegex(FormatError,'SelectedEffectCycle'):
            trace_selected_visual(0,visuals,sequences,{})


if __name__=='__main__':
    unittest.main(verbosity=2)
