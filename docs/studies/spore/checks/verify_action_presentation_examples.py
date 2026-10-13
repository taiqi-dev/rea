"""Research format checks and independent presentation-policy examples."""
import hashlib
from dataclasses import replace
import json
import math
from pathlib import Path
import struct
import unittest

from read_action_presentation_resources import (reference, read_sound_section,
    read_visual_catalog, trace, IMPORT_MASK)
from read_selected_skinpaint_sections import FormatError, Section


def sound_fixture(flags=0, volume=0.0):
    raw = struct.pack('>IIIIIfff', 1, flags, 0, 0xD05B58ED, 0xCDCDCDCD, .05, 0., volume)
    section = Section(5,1,0,0,len(raw),1,hashlib.sha256(raw).hexdigest())
    return raw, section


def visual_fixture(target=None):
    raw = struct.pack('>hi',1,1)+b'\0'*25+struct.pack('>i',0)+b'\0'*16+struct.pack('>i',0)
    if target is not None:
        raw += struct.pack('>iII',target,0,0x819E2F71)
    return raw+struct.pack('>iii',-1,-1,0)


def own_frame(root, yaw_degrees, body_scale, part, socket, direction=(1.,0.,0.)):
    if any(len(v)!=3 or not all(math.isfinite(x) for x in v) for v in (root,part,socket,direction)):
        raise ValueError('InvalidVector')
    if not math.isfinite(yaw_degrees) or not math.isfinite(body_scale) or body_scale<=0:
        raise ValueError('InvalidRootFrame')
    angle=math.radians(yaw_degrees);c,s=math.cos(angle),math.sin(angle)
    def rotate(v):return (c*v[0]-s*v[1],s*v[0]+c*v[1],v[2])
    local=tuple((a+b)*body_scale for a,b in zip(part,socket));p=rotate(local)
    d=rotate(direction);n=math.sqrt(sum(v*v for v in d))
    if n==0:raise ValueError('ZeroDirection')
    return tuple(a+b for a,b in zip(root,p)),tuple(v/n for v in d)


class OwnPresentation:
    def __init__(self):
        self.body=('B',12);self.binding=4;self.parts={'M1','M2','H1'}
        self.action_active=True;self.delivered=set();self.effects={};self.damage=30

    def cue(self, slot, emitter, mode='follow', body=('B',12), binding=4, ordinal=0):
        if body!=self.body:return 'BodyRevisionInvalid'
        if binding!=self.binding:return 'BindingEpochInvalid'
        if not self.action_active:return 'InactiveAction'
        if emitter not in self.parts:return 'MissingEmitter'
        key=('bodyLife1','actionA',slot,ordinal)
        if key in self.delivered:return 'DuplicateCue'
        self.delivered.add(key);self.effects[key]={'mode':mode,'emitter':emitter,'position':(10,10,2)}
        return key

    def detach_and_cancel(self, part):
        self.parts.remove(part);self.body=('B',13);self.binding+=1;self.action_active=False
        for key,effect in list(self.effects.items()):
            if effect['mode']=='follow' and effect['emitter']==part:del self.effects[key]


def own_foot_mix(contacts, radius=4., max_gain=.55):
    if not math.isfinite(radius) or radius<=0 or not math.isfinite(max_gain) or max_gain<0:
        raise ValueError('InvalidMixPolicy')
    groups={};seen=set()
    for actor, serial, bucket, gain, distance in contacts:
        if not all(math.isfinite(x) and x>=0 for x in (gain,distance)):
            raise ValueError('InvalidContactGain')
        key=(actor,serial)
        if key in seen:continue
        seen.add(key)
        g=gain/(1+(distance/radius)**2)
        group=(actor,bucket);groups[group]=groups.get(group,0.)+g*g
    return {key:min(max_gain,math.sqrt(energy)) for key,energy in groups.items()}


def own_voice_budget(voices, cap):
    if not isinstance(cap,int) or isinstance(cap,bool) or cap<0:raise ValueError('InvalidVoiceCap')
    if len({v['id'] for v in voices})!=len(voices):raise ValueError('DuplicateVoiceId')
    for v in voices:
        if not math.isfinite(v['priority']) or not math.isfinite(v['audibility']) or v['audibility']<0:
            raise ValueError('InvalidVoiceScore')
    return sorted(voices,key=lambda v:(-v['priority'],-v['audibility'],v['id']))[:cap]


class FormatChecks(unittest.TestCase):
    def test_import_mask_is_7f_not_high_sign_bit(self):
        self.assertEqual(reference(IMPORT_MASK|2,3,3),{'kind':'import','index':2})
    def test_partial_import_mask_rejected(self):
        with self.assertRaises(FormatError):reference(0x01000000,3,3)
    def test_null_and_unsupported_negative_separate(self):
        self.assertEqual(reference(-1,1),{'kind':'null'})
        with self.assertRaises(FormatError):reference(-2,1)
    def test_reference_outside_namespace_rejected(self):
        for x in (4,IMPORT_MASK|4):
            with self.assertRaises(FormatError):reference(x,4,4)
    def test_sound_big_endian_pair_and_inactive_volume(self):
        raw,s=sound_fixture();r=read_sound_section(raw,s)[0]
        self.assertEqual(r['resource_id_pair'],{'group':'0x00000000','instance':'0xd05b58ed'})
        self.assertEqual(r['volume'],0.)
        self.assertEqual(int(r['flags_raw'],16)&4,0)
    def test_sound_version_rejected(self):
        raw,s=sound_fixture();s=replace(s,version=2)
        with self.assertRaises(FormatError):read_sound_section(raw,s)
    def test_sound_length_mismatch_rejected(self):
        raw,s=sound_fixture();s=replace(s,count=2)
        with self.assertRaises(FormatError):read_sound_section(raw,s)
    def test_sound_identity_mismatch_rejected(self):
        raw,s=sound_fixture()
        damaged=bytearray(raw);damaged[4]^=1
        with self.assertRaises(FormatError):read_sound_section(damaged,s)
    def test_sound_nonfinite_rejected(self):
        raw,s=sound_fixture(volume=float('nan'))
        with self.assertRaises(FormatError):read_sound_section(raw,s)
    def test_visual_empty_export_is_not_missing(self):
        j=read_visual_catalog(visual_fixture(0),0)
        self.assertEqual(len(j['exports']),1)
        self.assertEqual(trace(j,[],{},0),[])
    def test_visual_unsupported_version_rejected(self):
        raw=bytearray(visual_fixture());struct.pack_into('>h',raw,0,2)
        with self.assertRaises(FormatError):read_visual_catalog(raw,0)
    def test_visual_truncated_or_trailing_rejected(self):
        for raw in (visual_fixture()[:-1],visual_fixture()+b'x'):
            with self.assertRaises(FormatError):read_visual_catalog(raw,0)
    def test_visual_cycle_diagnosed(self):
        cat={'visuals':[{'blocks':[{'block_type':0,'component_index_raw':0}]}],'imports':[]}
        with self.assertRaises(FormatError):trace(cat,[],{},0)
    def test_component_index_diagnosed(self):
        cat={'visuals':[{'blocks':[{'block_type':1,'component_index_raw':2}]}],'imports':[]}
        with self.assertRaises(FormatError):trace(cat,[],{1:2},0)
    def test_import_reference_retains_distinct_pair(self):
        cat={'visuals':[],'imports':[{'group':'0x00000002','name_hash':'0x00000003'}]}
        self.assertEqual(trace(cat,[],{},IMPORT_MASK)[0]['kind'],'unresolved_import')


class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.base=Path(__file__).resolve().parent.parent/'evidence'
        self.j=json.loads((self.base/'local-selected-action-presentation-resources.json').read_text(encoding='utf8'))
    def test_input_and_reader_identity(self):
        for row in (self.j['prior_evidence'],self.j['reader']):
            self.assertEqual(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest(),row['sha256'])
    def test_actual_catalog_scope_and_counts(self):
        c=self.j['coverage']
        self.assertEqual((c['directory_records'],c['matched_exports'],c['trace_leaves'],c['selected_sound_components'],c['audioProp_records_decoded']),(6,10,20,1,4))
        self.assertEqual(self.j['diagnostics'],[])
        self.assertTrue(all(r['package']=='PatchData.package' for r in self.j['directories']))
    def test_actual_disabled_sound_and_scale_flags(self):
        e=self.j['events_reused'];sound=[x for x in e if x['kind']=='sound'];fx=[x for x in e if x['kind']=='effect']
        self.assertEqual((len(sound),sum(x['disabled'] for x in sound),len(fx)),(18,8,26))
        self.assertEqual(sum(x['community_update_flags']['position'] for x in fx),10)
        self.assertFalse(any(x['community_update_flags']['apply_general_scale'] for x in fx))
    def test_actual_gain_and_sample_array_counts(self):
        rows={q['name']:c['direct_properties'] for q in self.j['direct_sound_event_queries'] for c in q['same_instance_candidates'] if 'direct_properties' in c}
        self.assertEqual([len(rows[n][str(0x701ed91e)]['values']) for n in ('scom_charge_rush_hit','sfx_crg_mucus_launch','sfx_crg_strike_lvl1_swish','scom_bite')],[1,4,2,8])
        self.assertAlmostEqual(rows['sfx_crg_strike_lvl1_swish'][str(0x25df0108)]['values'][0],.65,places=6)
    def test_alias_and_sound_prop_format_source(self):
        j=json.loads((self.base/'public-action-presentation-contracts.json').read_text(encoding='utf8'))
        prop=next(r for r in j['sources'] if r['path']=='reg_property.txt')
        aliases=[r['text'].split()[0] for r in prop['selected_lines'] if r['id']=='0x5f6317d5']
        self.assertEqual(set(aliases),{'musicTemplate','parentAudio'})
        self.assertTrue(any(r['path'].endswith('/PropConverter.java') and r['status']=='read' for r in j['sources']))


class OwnPolicyChecks(unittest.TestCase):
    def test_socket_scale_and_yaw_applied_once(self):
        p,d=own_frame((10,5,0),90,2,(2,0,1),(.5,0,0))
        for a,b in zip(p,(10,10,2)):self.assertAlmostEqual(a,b)
        for a,b in zip(d,(0,1,0)):self.assertAlmostEqual(a,b)
    def test_direction_normalized_independent_of_uniform_scale(self):
        self.assertEqual(own_frame((0,0,0),0,9,(0,0,0),(0,0,0),(3,0,0))[1],(1.,0.,0.))
    def test_invalid_scale_and_zero_direction_diagnosed(self):
        for scale in (0,-1,float('nan')):
            with self.assertRaises(ValueError):own_frame((0,0,0),0,scale,(0,0,0),(0,0,0))
        with self.assertRaises(ValueError):own_frame((0,0,0),0,1,(0,0,0),(0,0,0),(0,0,0))
    def test_duplicate_channels_share_semantic_cue(self):
        x=OwnPresentation();x.cue('LaunchSound','M1')
        self.assertEqual(x.cue('LaunchSound','M2'),'DuplicateCue')
    def test_explicit_dual_volley_has_two_ordinals(self):
        x=OwnPresentation();x.cue('LaunchSound','M1',ordinal=0);x.cue('LaunchSound','M2',ordinal=1)
        self.assertEqual(len(x.effects),2)
    def test_effect_and_sound_slots_are_separate(self):
        x=OwnPresentation();x.cue('MuzzleFx','M1');x.cue('LaunchSound','M1')
        self.assertEqual(len(x.effects),2)
    def test_stale_body_and_binding_rejected(self):
        x=OwnPresentation()
        self.assertEqual(x.cue('A','M1',body=('B',11)),'BodyRevisionInvalid')
        self.assertEqual(x.cue('A','M1',binding=3),'BindingEpochInvalid')
        self.assertEqual(x.cue('A','M1',body=('Other',12)),'BodyRevisionInvalid')
    def test_missing_emitter_does_not_create_effect(self):
        x=OwnPresentation();self.assertEqual(x.cue('A','M0'),'MissingEmitter');self.assertFalse(x.effects)
    def test_detach_retires_follow_but_preserves_world_effect(self):
        x=OwnPresentation();follow=x.cue('Trail','M1');world=x.cue('Projectile','M1',mode='world')
        x.detach_and_cancel('M1');self.assertNotIn(follow,x.effects);self.assertIn(world,x.effects)
        self.assertEqual(x.cue('A','M2',body=('B',13),binding=5),'InactiveAction')
    def test_world_effect_position_does_not_follow_new_root(self):
        x=OwnPresentation();world=x.cue('Impact','M1',mode='world');x.detach_and_cancel('M1')
        self.assertEqual(x.effects[world]['position'],(10,10,2))
    def test_foot_contacts_mix_energy_and_cap_gain(self):
        contacts=[('B',i,0,.3,2.) for i in range(6)]
        self.assertAlmostEqual(own_foot_mix(contacts)[('B',0)],.55)
        self.assertAlmostEqual(own_foot_mix(contacts[:1])[('B',0)],.24)
    def test_repeat_contact_serial_is_not_second_step(self):
        contact=('B',2,0,.3,2.)
        self.assertEqual(own_foot_mix([contact,contact]),own_foot_mix([contact]))
    def test_other_actor_or_time_bucket_not_merged(self):
        self.assertEqual(len(own_foot_mix([('B',1,0,.3,2),('C',1,0,.3,2),('B',2,1,.3,2)])),3)
    def test_invalid_audio_numbers_diagnosed(self):
        for g in (-1,float('nan')):
            with self.assertRaises(ValueError):own_foot_mix([('B',1,0,g,2)])
        with self.assertRaises(ValueError):own_foot_mix([],radius=0)
    def test_voice_priority_audibility_and_stable_tie(self):
        voices=[dict(id='step',priority=1,audibility=.9),dict(id='impact',priority=3,audibility=.4),dict(id='a',priority=2,audibility=.5),dict(id='b',priority=2,audibility=.5)]
        self.assertEqual([v['id'] for v in own_voice_budget(voices,2)],['impact','a'])
    def test_voice_cap_zero_and_bad_input(self):
        self.assertEqual(own_voice_budget([],0),[])
        with self.assertRaises(ValueError):own_voice_budget([],-1)
        with self.assertRaises(ValueError):own_voice_budget([dict(id='x',priority=0,audibility=-1)],1)
    def test_duplicate_voice_id_diagnosed(self):
        voice=dict(id='x',priority=0,audibility=.5)
        with self.assertRaises(ValueError):own_voice_budget([voice,voice],1)
    def test_presentation_drop_cannot_undo_damage(self):
        x=OwnPresentation();x.cue('ImpactFx','M1');x.detach_and_cancel('M1')
        own_voice_budget([],0);self.assertEqual(x.damage,30)


if __name__ == '__main__':
    unittest.main(verbosity=2)
