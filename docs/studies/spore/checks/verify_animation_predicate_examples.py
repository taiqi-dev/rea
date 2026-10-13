"""Synthetic decoder boundaries + independent binding policy, not game runtime."""
import argparse
import collections
import io
import json
from pathlib import Path
import struct
import unittest

from read_selected_animation_predicates import decode_predicate, read_predicates
from read_selected_animation_predicates import independent_evaluate as evaluate
from read_selected_animation_predicates import independent_select as select
from read_selected_animation_predicates import independent_plan_valid as valid
from read_selected_animation_predicates import digest, FormatError
from verify_action_event_reader import fixture, word


def scenario():
    candidates = [dict(id='right-swipe', mask=2, values=2, required_roles=['rightGrasper']),
                  dict(id='left-swipe', mask=2, values=2, required_roles=['leftGrasper']),
                  dict(id='body-shove', mask=0, values=0, required_roles=['torso'])]
    facts = dict(hasGraspers=True, hasFeet=True, uprightSpine=False)
    initial = select(candidates, facts, {'rightGrasper':['R22'], 'leftGrasper':['L11'], 'torso':['T0']}, 8, 3)
    after_break = select(candidates, facts, {'leftGrasper':['L11'], 'torso':['T0']}, 9, 3)
    no_hands = select(candidates, dict(facts, hasGraspers=False), {'torso':['T0']}, 10, 3)
    return candidates, facts, initial, after_break, no_hands


class PredicateTests(unittest.TestCase):
    def test_wire_boolean_requirements(self):
        p=decode_predicate(struct.pack('<II',7,6),0)
        self.assertEqual([(r['name'],r['required_value']) for r in p['community_requirements']],
                         [('uprightSpine',False),('hasGraspers',True),('hasFeet',True)])
    def test_wire_unknown_bits_retained(self):
        p=decode_predicate(struct.pack('<II',0x80000004,0x40000004),0)
        self.assertEqual(p['unknown_flags1'],'0x80000000')
        self.assertEqual(p['unknown_flags2'],'0x40000000')
    def test_wire_unselected_value_retained(self):
        self.assertEqual(decode_predicate(struct.pack('<II',0,4),0)['values_outside_selected_mask'],'0x00000004')
    def test_short_predicate(self):
        with self.assertRaises(FormatError): decode_predicate(b'1234567',0)
    def test_negative_predicate_offset(self):
        with self.assertRaises(FormatError): decode_predicate(b'12345678',-1)
    def test_animation_event_scopes_separate(self):
        d=fixture();word(d,0x154,4);word(d,0x158,0);word(d,0x500,0x1000001)
        word(d,0x550,2);word(d,0x554,2);p=read_predicates(d)
        self.assertEqual(p['whole_animation']['community_requirements'][0]['required_value'],False)
        self.assertEqual(p['events'][0]['predicate']['flags1'],'0x00000002')
        self.assertTrue(p['events'][0]['predicate_flag_present'])
    def test_event_bytes_without_gate_preserved(self):
        d=fixture();word(d,0x550,4);p=read_predicates(d)
        self.assertFalse(p['events'][0]['predicate_flag_present'])
        self.assertEqual(p['events'][0]['predicate']['flags1'],'0x00000004')
    def test_channel_require_separate(self):
        d=fixture();word(d,0x240+0xAC,0x01070005);p=read_predicates(d)
        self.assertTrue(p['channels'][0]['community_require_bit_present'])
        self.assertTrue(p['whole_animation']['is_default'])
        self.assertEqual(p['channels'][0]['variantGroup'],1)
    def test_bad_magic(self):
        d=fixture();word(d,0,0)
        with self.assertRaises(FormatError):read_predicates(d)
    def test_declared_size(self):
        d=fixture();word(d,4,1)
        with self.assertRaises(FormatError):read_predicates(d)
    def test_unsupported_version(self):
        d=fixture();word(d,8,0x13)
        with self.assertRaises(FormatError):read_predicates(d)
    def test_event_bounds(self):
        d=fixture();word(d,0x140,len(d)-10)
        with self.assertRaises(FormatError):read_predicates(d)
    def test_event_budget(self):
        d=fixture();word(d,0x13C,4097)
        with self.assertRaises(FormatError):read_predicates(d)
    def test_channel_bounds(self):
        d=fixture();word(d,0x200,len(d)-4)
        with self.assertRaises(FormatError):read_predicates(d)
    def test_default_policy(self):self.assertEqual(evaluate(0,0,{}),'pass')
    def test_true_requirement(self):self.assertEqual(evaluate(4,4,{'hasFeet':True}),'pass')
    def test_false_requirement(self):self.assertEqual(evaluate(4,0,{'hasFeet':False}),'pass')
    def test_boolean_mismatch(self):self.assertEqual(evaluate(4,4,{'hasFeet':False}),'fail')
    def test_unknown_fact(self):self.assertEqual(evaluate(4,4,{}),'unknown')
    def test_nonboolean_fact(self):self.assertEqual(evaluate(4,4,{'hasFeet':1}),'unknown')
    def test_unknown_bit_policy(self):self.assertEqual(evaluate(8,8,{}),'unknown')
    def test_invalid_word(self):self.assertEqual(evaluate(-1,0,{}),'invalid')
    def test_false_dominates_unknown(self):self.assertEqual(evaluate(7,7,{'hasFeet':False}),'fail')
    def test_stable_binding_order(self):
        c=[dict(id='x',mask=0,values=0,required_roles=['grasper'])]
        self.assertEqual(select(c,{}, {'grasper':['B','A','A']},1,1)['bindings'],{'grasper':'A'})
    def test_same_category_wrong_side(self):
        _,_,before,after,_=scenario();self.assertEqual(before['clip'],'right-swipe')
        self.assertEqual(after['clip'],'left-swipe')
        self.assertEqual(after['rejected'][0],dict(clip='right-swipe',reason='missing-role',role='rightGrasper'))
    def test_body_only_fallback(self):self.assertEqual(scenario()[4]['clip'],'body-shove')
    def test_no_silent_fallback(self):
        c,f,_,_,_=scenario();self.assertEqual(select(c[:2],dict(f,hasGraspers=False),{},1,1)['status'],'no-compatible-animation')
    def test_unknown_condition_rejected(self):
        self.assertEqual(select([dict(id='x',mask=8,values=8,required_roles=[])],{}, {},1,1)['rejected'][0]['reason'],'condition-unknown')
    def test_body_revision_invalidation(self):self.assertFalse(valid(scenario()[2],9,3,{'R22','L11','T0'}))
    def test_soul_revision_invalidation(self):self.assertFalse(valid(scenario()[2],8,4,{'R22','L11','T0'}))
    def test_removed_part_invalidation(self):self.assertFalse(valid(scenario()[2],8,3,{'L11','T0'}))
    def test_valid_plan(self):self.assertTrue(valid(scenario()[2],8,3,{'R22','L11','T0'}))


def verify_local(path):
    raw=path.read_bytes();j=json.loads(raw.decode('utf8'));prior_path=Path(j['prior']['path'])
    if digest(prior_path.read_bytes())!=j['prior']['sha256']:raise AssertionError('prior digest')
    prior=json.loads(prior_path.read_text(encoding='utf8'))
    old={(r['package'],str(r['key'])):r for r in prior['records'] if 'anim' in r}
    counts=collections.Counter()
    for r in j['records']:
        p=r['predicates'];o=old[(r['package'],str(r['key']))]
        for n in ('offset','stored_bytes','memory_bytes','compression','stored_sha256','decoded_sha256'):
            if r[n]!=o[n]:raise AssertionError(n)
        for item in [p['whole_animation']]+[e['predicate'] for e in p['events']]:
            mask,values=struct.unpack('<II',bytes.fromhex(item['raw_8_bytes']))
            if mask!=int(item['flags1'],16) or values!=int(item['flags2'],16):raise AssertionError('predicate words')
        counts['resources']+=1;counts['channels']+=len(p['channels']);counts['events']+=len(p['events'])
        for c in p['channels']:
            flags=struct.unpack('<I',bytes.fromhex(c['raw_bindFlags_4_bytes']))[0]
            if bool(flags&4)!=c['community_require_bit_present']:raise AssertionError('require bit')
            counts['require']+=bool(flags&4)
            if c['bindFlags_decoded_offset']!=c['decoded_offset']+0xAC:raise AssertionError('channel offset')
        for e in p['events']:
            if e['predicate']['decoded_offset']!=e['decoded_offset']+0x50:raise AssertionError('event offset')
            if e['predicate_flag_present']!=bool(int(e['flags'],16)&0x01000000):raise AssertionError('event gate')
    if counts!=dict(resources=46,channels=612,events=818,require=15):raise AssertionError(counts)
    return dict(status='passed',resource_checks=46,counts=dict(counts),evidence_sha256=digest(raw),
                scope='Evidence raw-byte/metadata consistency against28; no additional package reads in verifier.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PredicateTests))
    ev=Path(__file__).resolve().parent.parent/'evidence'
    local=verify_local(ev/'local-selected-animation-predicates.json')
    _,facts,before,after,nohands=scenario()
    output=dict(schema_version=1,module=45,tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                status='passed' if result.wasSuccessful() else 'failed',log=stream.getvalue(),local_consistency=local,
                independent_example=dict(facts=facts,initial=before,after_right_hand_removed=after,after_all_hands_removed=nohands),
                verifier_sha256=digest(Path(__file__).read_bytes()),limitations='Synthetic format tests and independent policy tests do not verify original fallback or runtime execution.')
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:output[k] for k in ('tests_run','failures','errors','status')}))
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
