"""Independent population scheduling/LOD examples and bounded reader checks."""
from dataclasses import dataclass,replace
import json
import math
from pathlib import Path
import struct
import unittest

from read_selected_ability_properties import FormatError,read_prop
from read_selected_creature_lod_properties import property_ids,select_properties


def visual_lod(old,distance):
    if not math.isfinite(distance) or distance<0:raise ValueError('InvalidLODDistance')
    if old=='High':return 'Low' if distance>80 else ('Medium' if distance>30 else 'High')
    if old=='Medium':return 'High' if distance<25 else ('Low' if distance>80 else 'Medium')
    if old=='Low':return 'High' if distance<25 else ('Medium' if distance<70 else 'Low')
    raise ValueError('UnknownVisualLOD')


def due(actor_id,tick,interval):return tick%interval==actor_id%interval
def gait_phase(tick,origin=0,frequency=1):return ((tick-origin)*frequency/60)%1


@dataclass(frozen=True)
class Job:
    actor:int
    cost:int
    mandatory:bool
    deadline:int
    kind:str


def admit(jobs,budget):
    if budget<0 or any(j.cost<=0 for j in jobs):raise ValueError('InvalidWorkBudget')
    mandatory=sorted((j for j in jobs if j.mandatory),key=lambda j:(j.deadline,j.actor,j.kind))
    optional=sorted((j for j in jobs if not j.mandatory),key=lambda j:(j.deadline,j.actor,j.kind))
    selected=list(mandatory);remaining=budget-sum(j.cost for j in mandatory)
    diagnostics=['MandatoryBudgetExceeded'] if remaining<0 else []
    skipped=[]
    for j in optional:
        if j.cost<=remaining:selected.append(j);remaining-=j.cost
        else:skipped.append(j)
    return selected,skipped,diagnostics


def population_jobs(tick):
    jobs=[]
    for actor in range(100):
        category='High' if actor<20 else ('Medium' if actor<50 else 'Low')
        pose_period,pose_cost,ai_period={'High':(1,6,6),'Medium':(3,3,15),'Low':(12,1,60)}[category]
        if due(actor,tick,pose_period):jobs.append(Job(actor,pose_cost,False,tick,'Pose'))
        if due(actor,tick,ai_period):jobs.append(Job(actor,4,actor<20,tick,'AI'))
    return jobs


@dataclass(frozen=True)
class Event:
    action:str
    ordinal:int
    tick:int
    generation:int
    executor:str
    damage:int
    requires_executor:bool=True


class Authority:
    def __init__(self,events,generation=1,executors=('H1',),cooldown_until=60):
        self.events=events;self.generation=generation;self.executors=set(executors)
        self.tick=0;self.seen=set();self.damage=0;self.diagnostics=[];self.cooldown_until=cooldown_until
    def advance(self,new_tick,max_substeps=120):
        if new_tick<self.tick:raise ValueError('NonMonotonicSimulationTime')
        if new_tick-self.tick>max_substeps:raise ValueError('CatchupBudgetExceeded')
        for tick in range(self.tick+1,new_tick+1):
            for e in sorted((e for e in self.events if e.tick==tick),key=lambda e:(e.action,e.ordinal)):
                ident=(e.action,e.ordinal)
                if ident in self.seen:continue
                self.seen.add(ident)
                if e.requires_executor and (e.generation!=self.generation or e.executor not in self.executors):
                    self.diagnostics.append(('StaleExecutorEvent',ident));continue
                self.damage+=e.damage
        self.tick=new_tick
    def cooldown_ready(self):return self.tick>=self.cooldown_until


def apply_async_pose(result_generation,current_generation,result_lod,current_lod,result_tick,current_tick,
                     result_epoch=0,current_epoch=0,last_published_tick=0):
    if result_generation!=current_generation:raise ValueError('StaleBodyPose')
    if result_lod!=current_lod:raise ValueError('SupersededVisualLOD')
    if result_epoch!=current_epoch:raise ValueError('SupersededVisualEpoch')
    if result_tick>current_tick:raise ValueError('FuturePoseSample')
    if result_tick<last_published_tick:raise ValueError('OlderPoseSample')
    return 'AcceptedVisualSample'


@dataclass(frozen=True)
class ActorView:
    generation:int
    capabilities:tuple
    cooldown_until:int
    action_event_ids:tuple
    visual_lod:str
    visual_epoch:int


def upgrade_view(view,distance):
    lod=visual_lod(view.visual_lod,distance)
    return replace(view,visual_lod=lod,visual_epoch=view.visual_epoch+(lod!=view.visual_lod))


def ai_interval(base_period,combat=False,incoming_threat=False):
    if base_period<=0:raise ValueError('InvalidAIInterval')
    return min(base_period,6) if combat or incoming_threat else base_period


class CreatureLODExamples(unittest.TestCase):
    def test_01_hysteresis_high_boundary(self):
        self.assertEqual(visual_lod('High',30),'High');self.assertEqual(visual_lod('High',30.1),'Medium')
        self.assertEqual(visual_lod('Medium',26),'Medium');self.assertEqual(visual_lod('Medium',24.9),'High')

    def test_02_hysteresis_far_boundary_and_teleport(self):
        self.assertEqual(visual_lod('Medium',80),'Medium');self.assertEqual(visual_lod('Medium',80.1),'Low')
        self.assertEqual(visual_lod('Low',70),'Low');self.assertEqual(visual_lod('Low',69.9),'Medium')
        self.assertEqual(visual_lod('Low',1),'High');self.assertEqual(visual_lod('High',100),'Low')

    def test_03_invalid_lod_keeps_diagnostic(self):
        for d in (-1,math.nan):
            with self.assertRaisesRegex(ValueError,'InvalidLODDistance'):visual_lod('High',d)
        with self.assertRaisesRegex(ValueError,'UnknownVisualLOD'):visual_lod('Unknown',1)

    def test_04_staggered_exact_population_counts(self):
        jobs=[j for t in range(1,61) for j in population_jobs(t)]
        self.assertEqual(sum(j.kind=='Pose' for j in jobs),2050)
        self.assertEqual(sum(j.kind=='AI' for j in jobs),370)
        self.assertEqual(sum(j.cost for j in jobs),10730)

    def test_05_population_peak_fits_example_budget(self):
        peak=max(sum(j.cost for j in population_jobs(t)) for t in range(1,61))
        self.assertEqual(peak,182)
        self.assertLessEqual(peak,190)
        for t in range(1,61):
            selected,skipped,diag=admit(population_jobs(t),190)
            self.assertFalse(skipped);self.assertFalse(diag)

    def test_06_staggering_spreads_visual_work(self):
        self.assertEqual(max(sum(j.kind=='Pose' for j in population_jobs(t)) for t in range(1,61)),35)
        self.assertEqual(sum(due(51,t,60) for t in range(1,61)),1)

    def test_07_budget_keeps_mandatory_ai_before_visual(self):
        jobs=[Job(0,10,True,1,'AI'),Job(1,6,False,1,'Pose'),Job(2,6,False,1,'Pose')]
        selected,skipped,diag=admit(jobs,16)
        self.assertEqual([j.actor for j in selected],[0,1]);self.assertEqual([j.actor for j in skipped],[2])
        self.assertFalse(diag)

    def test_08_overload_is_explicit_not_lost_mandatory_work(self):
        jobs=[Job(0,12,True,1,'AI'),Job(1,12,True,1,'AI'),Job(2,1,False,1,'Pose')]
        selected,skipped,diag=admit(jobs,20)
        self.assertEqual(len(selected),2);self.assertEqual(diag,['MandatoryBudgetExceeded']);self.assertEqual(len(skipped),1)

    def test_09_upgrade_continues_phase_not_restart(self):
        self.assertAlmostEqual(gait_phase(18),.3);self.assertAlmostEqual(gait_phase(78),.3)
        self.assertEqual(visual_lod('Low',5),'High');self.assertAlmostEqual(gait_phase(18),.3)

    def test_10_damage_independent_of_planner_or_visual_cadence(self):
        a=Authority([Event('A',0,12,1,'H1',7)])
        a.advance(30)
        self.assertEqual(a.damage,7);self.assertFalse(a.cooldown_ready())
        a.advance(60);self.assertTrue(a.cooldown_ready());self.assertEqual(a.damage,7)

    def test_11_time_jump_visits_intermediate_events(self):
        es=[Event('A',0,12,1,'H1',7),Event('A',1,20,1,'H1',5)]
        a,b=Authority(es),Authority(es);a.advance(30)
        for t in range(1,31):b.advance(t)
        self.assertEqual(a.damage,b.damage);self.assertEqual(a.damage,12)

    def test_12_duplicate_events_no_extra_damage(self):
        e=Event('A',0,12,1,'H1',7);a=Authority([e,e]);a.advance(30);a.advance(30)
        self.assertEqual(a.damage,7);self.assertEqual(len(a.seen),1)

    def test_13_dismembered_executor_event_invalidated(self):
        a=Authority([Event('A',0,12,1,'H1',7)],generation=2,executors=('H2',));a.advance(30)
        self.assertEqual(a.damage,0);self.assertEqual(a.diagnostics[0][0],'StaleExecutorEvent')
        self.assertEqual(a.cooldown_until,60)

    def test_14_catchup_reject_does_not_consume_time(self):
        a=Authority([Event('A',0,12,1,'H1',7)])
        with self.assertRaisesRegex(ValueError,'CatchupBudgetExceeded'):a.advance(180)
        self.assertEqual(a.tick,0);self.assertEqual(a.damage,0)
        a.advance(60);self.assertEqual(a.damage,7)

    def test_15_async_pose_rejects_body_or_lod_mismatch(self):
        self.assertEqual(apply_async_pose(2,2,'High','High',10,18),'AcceptedVisualSample')
        with self.assertRaisesRegex(ValueError,'StaleBodyPose'):apply_async_pose(1,2,'High','High',10,18)
        with self.assertRaisesRegex(ValueError,'SupersededVisualLOD'):apply_async_pose(2,2,'Low','High',10,18)

    def test_16_visual_upgrade_does_not_change_capability_or_cooldown(self):
        v=ActorView(2,('H1','Strike',3),60,('A:0',),'Low',4);new=upgrade_view(v,5)
        self.assertEqual(new.visual_lod,'High');self.assertEqual(new.visual_epoch,5)
        self.assertEqual((new.generation,new.capabilities,new.cooldown_until,new.action_event_ids),
                         (v.generation,v.capabilities,v.cooldown_until,v.action_event_ids))

    def test_21_lod_roundtrip_rejects_matching_but_old_quality(self):
        v=ActorView(2,(),60,(),'High',4);v=upgrade_view(v,100);v=upgrade_view(v,1)
        self.assertEqual(v.visual_lod,'High');self.assertEqual(v.visual_epoch,6)
        with self.assertRaisesRegex(ValueError,'SupersededVisualEpoch'):
            apply_async_pose(2,2,'High','High',10,18,result_epoch=4,current_epoch=6)

    def test_22_older_pose_cannot_overwrite_newer_sample(self):
        with self.assertRaisesRegex(ValueError,'OlderPoseSample'):
            apply_async_pose(2,2,'High','High',10,18,last_published_tick=17)
        with self.assertRaisesRegex(ValueError,'FuturePoseSample'):
            apply_async_pose(2,2,'High','High',19,18)

    def test_23_camera_far_actor_promoted_for_actual_combat(self):
        self.assertEqual(ai_interval(60),60)
        self.assertEqual(ai_interval(60,combat=True),6)
        self.assertEqual(ai_interval(60,incoming_threat=True),6)
        a=Authority([]);self.assertEqual(a.cooldown_until,60)

    def test_24_committed_projectile_survives_attacker_revision(self):
        e=Event('Projectile',0,12,1,'H1',7,requires_executor=False)
        a=Authority([e],generation=2,executors=('H2',));a.advance(30)
        self.assertEqual(a.damage,7);self.assertFalse(a.diagnostics)


class LODReaderExamples(unittest.TestCase):
    def test_17_registry_explicit_ids_and_bare_fnv(self):
        p=Path(__file__).resolve().parent.parent/'evidence/public-creature-lod-contracts.json'
        ids=property_ids(json.loads(p.read_text(encoding='utf-8')))
        self.assertEqual(ids['creatureSimulationLOD_MinDistanceLow'],0x052583bc)
        self.assertEqual(ids['creatureSimulationLOD_MinDistanceMed'],0x052583d4)
        self.assertNotEqual(ids['useHighAnimLOD'],0)

    def test_18_prop_float_values_and_selected_absence(self):
        blob=struct.pack('>I',2)+struct.pack('>IHHf',0x052583bc,13,0,100)+struct.pack('>IHHf',0x052583d4,13,0,75)
        props=read_prop(blob)
        selected=select_properties(props,{'Low':0x052583bc,'Med':0x052583d4,'Absent':1})
        self.assertEqual(selected['Low']['values'],[100]);self.assertEqual(selected['Med']['values'],[75])
        self.assertNotIn('Absent',selected)

    def test_19_malformed_prop_not_defaulted(self):
        blob=struct.pack('>I',1)+struct.pack('>IHHf',0x052583bc,13,0,math.nan)
        with self.assertRaisesRegex(FormatError,'nonfinite'):read_prop(blob)
        with self.assertRaises(FormatError):read_prop(blob[:-2])

    def test_20_real_local_lod_values_and_eight_selected_keys(self):
        p=Path(__file__).resolve().parent.parent/'evidence/local-selected-creature-lod-properties.json'
        j=json.loads(p.read_text(encoding='utf-8'));self.assertEqual(len(j['records']),8)
        bases=[r for r in j['records'] if r['key']['group']=='0xad56080c'];self.assertEqual(len(bases),2)
        for r in bases:
            self.assertEqual(r['selected_properties']['creatureSimulationLOD_MinDistanceLow']['values'],[100])
            self.assertEqual(r['selected_properties']['creatureSimulationLOD_MinDistanceMed']['values'],[75])
            self.assertTrue(r['prior_identity_matched'])


if __name__=='__main__':unittest.main(verbosity=2)
