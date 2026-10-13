"""Own capability rules plus bounded selected-format consistency, not Spore reducer."""
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import struct
import unittest

from read_capability_contribution_records import read_capability_prop, registry_fields
from read_selected_ability_properties import FormatError, read_prop


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Contribution:
    capability: str
    quality: int
    capacity: float


@dataclass(frozen=True)
class Part:
    ident: str
    contributions: tuple
    health_factor: float = 1.
    fatigue: float = 0.
    attached: bool = True
    functional: bool = True
    profile: bool = True
    occupied: bool = False


PARTS=(Part('H1',(Contribution('strike',1,3.),),fatigue=.2),
       Part('H2',(Contribution('strike',3,5.),),health_factor=.8,fatigue=.1),
       Part('H3',(Contribution('strike',2,4.),),fatigue=.5))


def summarize(parts,revision,body_id='B1'):
    if not isinstance(revision,int) or isinstance(revision,bool) or revision<0:
        raise ContractError('InvalidBodyRevision')
    seen=set(); result={}; excluded=[]
    for p in parts:
        if p.ident in seen:raise ContractError('DuplicatePartIdentity')
        seen.add(p.ident)
        if not all(math.isfinite(v) and 0<=v<=1 for v in (p.health_factor,p.fatigue)):
            raise ContractError('InvalidFunctionalFactors')
        local=set()
        for c in p.contributions:
            if c.capability not in ('strike','bite','battery','mouth'):
                raise ContractError('UnknownCapabilityDefinition')
            if c.capability in local:raise ContractError('DuplicatePartContribution')
            local.add(c.capability)
            if not isinstance(c.quality,int) or isinstance(c.quality,bool) or c.quality<0:
                raise ContractError('InvalidQuality')
            if not math.isfinite(c.capacity) or c.capacity<0:raise ContractError('InvalidCapacity')
            summary=result.setdefault(c.capability,dict(providers=[],count=0,max_quality=0,sum_quality=0,capacity=0.))
            if not p.attached or not p.functional or p.health_factor==0:
                excluded.append((p.ident,c.capability,'ProviderNonfunctional'));continue
            effective=c.capacity*p.health_factor*(1-p.fatigue)
            summary['providers'].append(dict(part_id=p.ident,quality=c.quality,capacity=effective))
            summary['count']+=1;summary['max_quality']=max(summary['max_quality'],c.quality)
            summary['sum_quality']+=c.quality;summary['capacity']+=effective
    return dict(body_id=body_id,revision=revision,capabilities=result,excluded=excluded)


def choose_local_providers(parts,summary,expected_revision,min_quality,required_count=1,minimum_capacity=0.,expected_body_id='B1'):
    if summary['body_id']!=expected_body_id:raise ContractError('CapabilitySnapshotBodyMismatch')
    if summary['revision']!=expected_revision:raise ContractError('StaleCapabilitySnapshot')
    if required_count<1:raise ContractError('InvalidRequiredProviderCount')
    if not math.isfinite(minimum_capacity) or minimum_capacity<0:raise ContractError('InvalidRequiredCapacity')
    candidates=[];rejected=[]
    for p in parts:
        contribution=next((c for c in p.contributions if c.capability=='strike'),None)
        reason=None
        if not p.attached or not p.functional or p.health_factor==0:reason='ProviderNonfunctional'
        elif contribution is None or contribution.quality<min_quality:reason='LocalQualityInsufficient'
        elif contribution.capacity*p.health_factor*(1-p.fatigue)<minimum_capacity:reason='LocalCapacityInsufficient'
        elif not p.profile:reason='RequiredProfileMissing'
        elif p.occupied:reason='EssentialOutputOccupied'
        if reason:rejected.append((p.ident,reason))
        else:candidates.append(p.ident)
    return dict(eligible=candidates,rejected=rejected,
                feasible=len(candidates)>=required_count,
                reason='Eligible' if len(candidates)>=required_count else 'InsufficientDistinctProviders')


def own_threshold(summary,capability,minimum_max):
    if capability not in summary['capabilities']:
        return 'CapabilityUndefinedForBody'
    row=summary['capabilities'][capability]
    if row['count']==0:return 'NoFunctionalProviders'
    return 'Qualified' if row['max_quality']>=minimum_max else 'BodyQualityInsufficient'


def prop_fixture(include_box=False):
    value=struct.pack('>IHH',0xb1c3e5c0,9,0)+struct.pack('>i',2)
    box=(struct.pack('>IHHII',0x12345678,0x39,0x30,1,24)+bytes(range(24))) if include_box else b''
    return struct.pack('>I',2 if include_box else 1)+value+box


class OwnAggregationExamples(unittest.TestCase):
    def test_max_sum_count_capacity_are_separate(self):
        r=summarize(PARTS,42)['capabilities']['strike']
        self.assertEqual((r['max_quality'],r['sum_quality'],r['count']),(3,6,3))
        self.assertAlmostEqual(r['capacity'],8.)

    def test_one_grade_three_part_is_not_three_providers(self):
        r=summarize([PARTS[1]],42)['capabilities']['strike']
        self.assertEqual((r['max_quality'],r['count']),(3,1))

    def test_body_tier_does_not_upgrade_weak_executor(self):
        summary=summarize(PARTS,42)
        self.assertEqual(own_threshold(summary,'strike',3),'Qualified')
        r=choose_local_providers(PARTS,summary,42,3)
        self.assertEqual(r['eligible'],['H2'])

    def test_qualified_but_busy_is_not_executable(self):
        parts=[replace(p,occupied=True) if p.ident=='H2' else p for p in PARTS]
        summary=summarize(parts,42)
        self.assertEqual(own_threshold(summary,'strike',3),'Qualified')
        result=choose_local_providers(parts,summary,42,3)
        self.assertFalse(result['feasible'])
        self.assertIn(('H2','EssentialOutputOccupied'),result['rejected'])

    def test_two_hand_mode_requires_distinct_qualified_parts(self):
        s=summarize(PARTS,42)
        self.assertTrue(choose_local_providers(PARTS,s,42,2,2)['feasible'])
        single=[PARTS[1]];s=summarize(single,42)
        self.assertFalse(choose_local_providers(single,s,42,2,2)['feasible'])

    def test_detach_max_provider_reduces_summary(self):
        parts=[replace(p,attached=False) if p.ident=='H2' else p for p in PARTS]
        s=summarize(parts,43);r=s['capabilities']['strike']
        self.assertEqual((r['max_quality'],r['sum_quality'],r['count']),(2,3,2))
        self.assertAlmostEqual(r['capacity'],4.4)
        self.assertEqual(own_threshold(s,'strike',3),'BodyQualityInsufficient')

    def test_missing_profile_is_distinct_from_missing_level(self):
        parts=[replace(PARTS[1],profile=False)]
        s=summarize(parts,42)
        self.assertEqual(own_threshold(s,'strike',3),'Qualified')
        self.assertEqual(choose_local_providers(parts,s,42,3)['rejected'],[('H2','RequiredProfileMissing')])

    def test_explicit_mirror_instances_count_twice(self):
        a=replace(PARTS[0],ident='left');b=replace(PARTS[0],ident='right')
        self.assertEqual(summarize([a,b],42)['capabilities']['strike']['count'],2)

    def test_duplicate_instance_or_contribution_rejected(self):
        with self.assertRaisesRegex(ContractError,'DuplicatePartIdentity'):summarize([PARTS[0],PARTS[0]],42)
        bad=replace(PARTS[0],contributions=PARTS[0].contributions*2)
        with self.assertRaisesRegex(ContractError,'DuplicatePartContribution'):summarize([bad],42)

    def test_unknown_or_bad_numeric_capabilities_rejected(self):
        for c,reason in ((Contribution('unknown',1,1),'UnknownCapability'),
                         (Contribution('strike',True,1),'InvalidQuality'),
                         (Contribution('strike',1,math.nan),'InvalidCapacity')):
            with self.assertRaisesRegex(ContractError,reason):summarize([Part('X',(c,))],42)

    def test_zero_health_provider_excluded(self):
        s=summarize([replace(PARTS[1],health_factor=0)],42)
        self.assertEqual(own_threshold(s,'strike',3),'NoFunctionalProviders')
        self.assertFalse(choose_local_providers([replace(PARTS[1],health_factor=0)],s,42,1)['feasible'])

    def test_zero_capacity_preserves_quality_by_own_policy(self):
        s=summarize([replace(PARTS[1],fatigue=1)],42)['capabilities']['strike']
        self.assertEqual(s['max_quality'],3);self.assertEqual(s['capacity'],0)

    def test_zero_capacity_skill_requirement_rejects_executor(self):
        parts=[replace(PARTS[1],fatigue=1)];s=summarize(parts,42)
        self.assertEqual(choose_local_providers(parts,s,42,3,minimum_capacity=1)['rejected'],[('H2','LocalCapacityInsufficient')])

    def test_same_revision_other_body_cannot_reuse_summary(self):
        with self.assertRaisesRegex(ContractError,'BodyMismatch'):
            choose_local_providers(PARTS,summarize(PARTS,42,'other-body'),42,1)

    def test_stale_snapshot_not_reused_after_change(self):
        with self.assertRaisesRegex(ContractError,'StaleCapabilitySnapshot'):
            choose_local_providers(PARTS,summarize(PARTS,42),43,1)

    def test_soul_ability_inventory_not_body_contribution(self):
        s=summarize(PARTS,42);soul_skills={'SoulBolt'}
        self.assertNotIn('SoulBolt',s['capabilities']);self.assertIn('SoulBolt',soul_skills)

    def test_one_mouth_grade_two_is_count_one(self):
        r=summarize([Part('M1',(Contribution('mouth',2,1),))],42)['capabilities']['mouth']
        self.assertEqual((r['max_quality'],r['count']),(2,1))


class FormatAndEvidenceChecks(unittest.TestCase):
    def test_primitive_projection_matches_unchanged_helper(self):
        data=prop_fixture();self.assertEqual(read_capability_prop(data),read_prop(data))

    def test_bbox_opaque_24_does_not_hide_later_fields(self):
        parsed=read_capability_prop(prop_fixture(True))
        self.assertEqual(parsed[0xb1c3e5c0]['values'],[2])
        self.assertEqual(parsed[0x12345678]['values'][0]['raw_24_bytes'],bytes(range(24)).hex())

    def test_bbox_bad_size_and_truncation_fail(self):
        data=bytearray(prop_fixture(True));struct.pack_into('>I',data,28,23)
        with self.assertRaises(FormatError):read_capability_prop(data)
        with self.assertRaises(FormatError):read_capability_prop(prop_fixture(True)[:-1])

    def test_transform_38_not_mistaken_for_bbox_39(self):
        data=bytearray(prop_fixture(True));struct.pack_into('>H',data,20,0x38)
        with self.assertRaisesRegex(FormatError,'UnsupportedCapabilityProfileType'):read_capability_prop(data)

    def test_duplicate_property_and_trailing_bytes_fail(self):
        data=prop_fixture();record=data[4:]
        with self.assertRaises(FormatError):read_capability_prop(struct.pack('>I',2)+record+record)
        with self.assertRaises(FormatError):read_capability_prop(data+b'X')

    def test_registry_explicit_ID_not_name_hash(self):
        r=registry_fields('modelCapabilityStrike 0xb1c3e5c0\ncreatureAbilityRequiredCAPs 0x04052a6b')
        self.assertEqual(r['modelCapabilityStrike']['id'],'0xb1c3e5c0')

    def test_actual_four_selected_definitions_and_direct_values(self):
        d=json.loads((Path(__file__).resolve().parent.parent/'evidence/local-selected-capability-contributions.json').read_text(encoding='utf-8'))
        self.assertEqual(len(d['selected_parts']),4);self.assertEqual(d['diagnostics'],[])
        rows={r['name']:r for r in d['selected_parts']}
        self.assertEqual(rows['ce_grasper_bird_02']['direct_capability_fields']['modelCapabilityStrike']['values'],[2])
        mouth=rows['ce_mouth_amphibian_omnivore_02']['direct_capability_fields']
        self.assertEqual(mouth['modelCapabilityMouth']['values'],[2]);self.assertEqual(mouth['modelCapabilityBite']['values'],[1])

    def test_actual_reader_and_old_requirement_identity(self):
        d=json.loads((Path(__file__).resolve().parent.parent/'evidence/local-selected-capability-contributions.json').read_text(encoding='utf-8'))
        for row in (d['reader'],d['existing_ability_evidence']):
            self.assertEqual(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest(),row['sha256'])
        self.assertIsNone(d['rea_evidence_id'])


if __name__=='__main__':unittest.main(verbosity=2)
