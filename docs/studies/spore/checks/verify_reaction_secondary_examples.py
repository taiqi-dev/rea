"""Independent reaction/secondary-motion examples. No Spore execution or asset reads."""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
class Diagnostic(ValueError): pass
def finite(*values):
    if not all(math.isfinite(x) for x in values): raise Diagnostic("NonFinite")

@dataclass
class Action:
    state:str="Running"
    epoch:int=0
    body_revision:int=3
    control_generation:int=7
    committed:set=field(default_factory=set)

@dataclass
class Actor:
    hp:float=100.
    poise:float=25.
    energy:float=20.
    lifetime:int=11
    body_revision:int=3
    control_generation:int=7
    actions:dict=field(default_factory=lambda:{"A":Action()})
    reservations:dict=field(default_factory=lambda:{"A":8.})
    effects:dict=field(default_factory=dict)
    damage_ledger:set=field(default_factory=set)
    cooldown_until:int=0
    reaction_until:int=0
    episode_start:int|None=None
    immune_until:int=0
    nav_epoch:int=0

    @property
    def available_energy(self): return self.energy-sum(self.reservations.values())

    def commit(self,action_id,slot,ticket_epoch,tick):
        if self.hp<=0:raise Diagnostic("TerminalActor")
        a=self.actions[action_id]
        if a.state!="Running" or a.epoch!=ticket_epoch: raise Diagnostic("StaleAction")
        if (a.body_revision,a.control_generation)!=(self.body_revision,self.control_generation):
            raise Diagnostic("StaleBinding")
        if tick<self.reaction_until: raise Diagnostic("ReactionBlocksCommit")
        if slot in a.committed:return "DuplicateIgnored"
        costs={0:5.,1:3.}
        if slot not in costs:raise Diagnostic("UnknownEffectSlot")
        cost=costs[slot]
        if self.reservations.get(action_id,0)<cost:raise Diagnostic("ReservationMissing")
        self.energy-=cost;self.reservations[action_id]-=cost
        effect_id=f"E{11+len(self.effects)}"
        self.effects[effect_id]={"birth_action":action_id,"slot":slot,
                                 "birth_control":self.control_generation,"alive":True}
        a.committed.add(slot)
        if slot==0:self.cooldown_until=tick+100
        return effect_id

    def cancel(self,action_id):
        a=self.actions[action_id]
        if a.state=="Cancelled":return 0.
        released=self.reservations.pop(action_id,0.)
        a.state="Cancelled";a.epoch+=1
        return released

    def damage(self,event_id,target_lifetime,damage,poise_impact,tick):
        finite(damage,poise_impact)
        if min(damage,poise_impact)<0:raise Diagnostic("InvalidDamage")
        if target_lifetime!=self.lifetime:raise Diagnostic("StaleTargetLifetime")
        key=(event_id,target_lifetime)
        if key in self.damage_ledger:return "DuplicateIgnored"
        self.damage_ledger.add(key)
        self.hp=max(0.,self.hp-damage);self.poise=max(0.,self.poise-poise_impact)
        if self.hp<=0:
            for action_id in list(self.actions):self.cancel(action_id)
            self.nav_epoch+=1
            return "TerminalRoute"
        if self.poise>0 or tick<self.immune_until:return "VisualFlinch"
        if self.episode_start is None:self.episode_start=tick
        self.reaction_until=max(self.reaction_until,min(tick+12,self.episode_start+24))
        for action_id in list(self.actions):self.cancel(action_id)
        self.nav_epoch+=1
        return "Stagger"

    def recover(self,tick):
        if self.hp<=0:return "TerminalRoute"
        if tick<self.reaction_until:return "StillBlocked"
        if self.episode_start is not None:
            self.episode_start=None;self.poise=25.;self.immune_until=tick+4
        return "ReplanFromCurrentState"

    def nav_ticket(self,epoch,tick):
        if self.hp<=0:raise Diagnostic("TerminalActor")
        if epoch!=self.nav_epoch:raise Diagnostic("StaleNavigation")
        if tick<self.reaction_until:raise Diagnostic("ReactionBlocksNavigation")
        return "Accept"

def ordered_tick_events(events):
    rank={"damage":0,"marker":1}
    return sorted(events,key=lambda x:(x[0],rank[x[1]],x[2]))

def remembered_observation(c0,observed_time,now,r0=.1,v_bound=2.):
    finite(c0,observed_time,now,r0,v_bound)
    if not 0<=c0<=1 or min(r0,v_bound)<0:raise Diagnostic("MalformedObservation")
    age=now-observed_time
    if age<0:raise Diagnostic("FutureObservation")
    return {"confidence":c0*math.exp(-age/4.),"error_radius":r0+v_bound*age,
            "position_kind":"last_observed_estimate","direct_visible":False}

def critical_step(q,v,omega,dt,forcing=0.):
    finite(q,v,omega,dt,forcing)
    if omega<=0 or dt<=0:raise Diagnostic("InvalidDynamicsStep")
    equilibrium=forcing/(omega*omega)
    y=q-equilibrium;b=v+omega*y;e=math.exp(-omega*dt)
    return equilibrium+(y+b*dt)*e,(v-omega*b*dt)*e

def hermite(q0,v0,q1,v1,duration,time):
    finite(q0,v0,q1,v1,duration,time)
    if duration<=0 or not 0<=time<=duration:raise Diagnostic("InvalidBlendTime")
    s=time/duration
    q=(2*s**3-3*s*s+1)*q0+(s**3-2*s*s+s)*duration*v0+(-2*s**3+3*s*s)*q1+(s**3-s*s)*duration*v1
    v=((6*s*s-6*s)*q0+(3*s*s-4*s+1)*duration*v0+(-6*s*s+6*s)*q1+(3*s*s-2*s)*duration*v1)/duration
    return q,v

def active_ancestors(parents,goals):
    marked={"root"}
    for node in goals:
        seen=set()
        while node is not None:
            if node not in parents:raise Diagnostic("MissingJoint")
            if node in seen:raise Diagnostic("TopologyCycle")
            marked.add(node);seen.add(node);node=parents[node]
    return marked

def clamp_angle(q,v,lo,hi):
    finite(q,v,lo,hi)
    if lo>=hi:raise Diagnostic("InvalidAngleLimits")
    if q>hi:return hi,min(v,0.),"UpperLimit"
    if q<lo:return lo,max(v,0.),"LowerLimit"
    return q,v,"WithinLimits"

def rebase_angle(q,v,old_parent,new_parent,old_parent_velocity,new_parent_velocity):
    finite(q,v,old_parent,new_parent,old_parent_velocity,new_parent_velocity)
    return q+old_parent-new_parent,v+old_parent_velocity-new_parent_velocity

@dataclass
class Secondary:
    q:float=.2
    v:float=0.
    mode:str="Passive"
    body_revision:int=3
    owner_epoch:int=0
    curve:tuple|None=None

    def step(self,omega,dt,forcing=0.):
        if self.mode!="Passive":raise Diagnostic("OutputNotOwned")
        self.q,self.v=critical_step(self.q,self.v,omega,dt,forcing)

    def take(self,target,duration):
        finite(target,duration)
        if duration<=0:raise Diagnostic("InvalidBlendTime")
        self.curve=(self.q,self.v,target,0.,duration)
        self.mode="AcquireBlend";self.owner_epoch+=1

    def sample_take(self,time):
        q0,v0,q1,v1,duration=self.curve
        self.q,self.v=hermite(q0,v0,q1,v1,duration,time)
        if time==duration:self.mode="Active"

    def release(self):
        self.mode="Passive";self.owner_epoch+=1

    def publish_passive_job(self,body_revision,owner_epoch,q,v):
        finite(q,v)
        if (body_revision,owner_epoch)!=(self.body_revision,self.owner_epoch):
            raise Diagnostic("StaleSecondaryJob")
        if self.mode!="Passive":raise Diagnostic("OutputNotOwned")
        self.q=q;self.v=v

    def collision_angle(self,visual_angle):
        return self.q

class ReactionTests(unittest.TestCase):
    def test_01_light_hit_preserves_current_action(self):
        a=Actor();self.assertEqual(a.damage("H901",11,12,8,8),"VisualFlinch")
        self.assertEqual((a.hp,a.poise),(88.,17.));self.assertEqual(a.actions["A"].state,"Running")
    def test_02_duplicate_damage_is_idempotent(self):
        a=Actor();a.damage("H901",11,12,8,8);a.damage("H901",11,12,8,8)
        self.assertEqual((a.hp,a.poise),(88.,17.));self.assertEqual(len(a.damage_ledger),1)
    def test_03_committed_cost_and_unspent_reservation_separate(self):
        a=Actor();a.commit("A",0,0,6);a.damage("H901",11,12,8,8);a.damage("H902",11,18,20,9)
        self.assertEqual((a.hp,a.energy,a.available_energy),(70.,15.,15.))
        self.assertEqual(a.reaction_until,21);self.assertEqual(a.actions["A"].state,"Cancelled")
    def test_04_cancel_before_first_commit_releases_reservation(self):
        a=Actor();self.assertEqual(a.cancel("A"),8.)
        self.assertEqual((a.energy,a.available_energy,a.cooldown_until),(20.,20.,0))
    def test_05_spawned_effect_outlives_action(self):
        a=Actor();eid=a.commit("A",0,0,6);a.cancel("A");a.control_generation+=1
        self.assertTrue(a.effects[eid]["alive"]);self.assertEqual(a.effects[eid]["birth_control"],7)
    def test_06_old_marker_after_cancel_cannot_spawn(self):
        a=Actor();a.commit("A",0,0,6);a.cancel("A")
        with self.assertRaisesRegex(Diagnostic,"StaleAction"):a.commit("A",1,0,12)
        self.assertEqual((len(a.effects),a.energy),(1,15.))
    def test_07_same_tick_damage_precedes_uncommitted_marker(self):
        a=Actor()
        events=ordered_tick_events([(6,"marker","M0"),(6,"damage","H")])
        self.assertEqual(events[0][1],"damage")
        for tick,kind,event in events:
            if kind=="damage":a.damage(event,11,1,25,tick)
            else:
                with self.assertRaisesRegex(Diagnostic,"StaleAction"):a.commit("A",0,0,tick)
        self.assertFalse(a.effects);self.assertEqual(a.energy,20.)
    def test_08_cancel_is_idempotent_and_does_not_touch_other_reservation(self):
        a=Actor();a.actions["B"]=Action();a.reservations["B"]=2.
        a.cancel("A");epoch=a.actions["A"].epoch
        self.assertEqual(a.cancel("A"),0.);self.assertEqual(a.actions["A"].epoch,epoch)
        self.assertEqual(a.reservations,{"B":2.})
    def test_09_stale_target_lifetime_rejected(self):
        a=Actor()
        with self.assertRaisesRegex(Diagnostic,"StaleTargetLifetime"):a.damage("H",10,12,8,8)
        self.assertEqual(a.hp,100.)
    def test_10_invalid_damage_does_not_poison_ledger(self):
        a=Actor()
        with self.assertRaisesRegex(Diagnostic,"NonFinite"):a.damage("H",11,math.nan,8,8)
        self.assertNotIn(("H",11),a.damage_ledger)
        with self.assertRaisesRegex(Diagnostic,"InvalidDamage"):a.damage("H",11,-1,8,8)
    def test_11_repeat_stagger_has_episode_cap_and_recovery_grace(self):
        a=Actor();a.damage("H0",11,1,25,9)
        for tick in range(10,34):a.damage(f"H{tick}",11,.1,1,tick)
        self.assertEqual(a.reaction_until,33);a.recover(33)
        self.assertEqual(a.immune_until,37)
        self.assertEqual(a.damage("H34",11,1,25,34),"VisualFlinch")
    def test_12_recovery_requires_new_plan(self):
        a=Actor();a.damage("H",11,1,25,9)
        self.assertEqual(a.recover(20),"StillBlocked")
        self.assertEqual(a.recover(21),"ReplanFromCurrentState")
        self.assertEqual(a.actions["A"].state,"Cancelled")
        terminal=Actor();old_nav=terminal.nav_epoch
        self.assertEqual(terminal.damage("fatal",11,101,1,8),"TerminalRoute")
        self.assertGreater(terminal.nav_epoch,old_nav)
        self.assertEqual(terminal.recover(100),"TerminalRoute")
        with self.assertRaisesRegex(Diagnostic,"TerminalActor"):terminal.commit("A",0,0,100)
        with self.assertRaisesRegex(Diagnostic,"TerminalActor"):terminal.nav_ticket(old_nav,100)
        with self.assertRaisesRegex(Diagnostic,"TerminalActor"):terminal.nav_ticket(terminal.nav_epoch,100)
    def test_13_cooldown_survives_cancellation(self):
        a=Actor();a.commit("A",0,0,6);a.cancel("A")
        self.assertEqual(a.cooldown_until,106)
        a=Actor();a.control_generation=8
        with self.assertRaisesRegex(Diagnostic,"StaleBinding"):a.commit("A",0,0,6)
    def test_14_recovery_memory_and_navigation_not_omniscient(self):
        m=remembered_observation(.8,.1,1.05)
        self.assertAlmostEqual(m["confidence"],.6308775127848614)
        self.assertAlmostEqual(m["error_radius"],2.);self.assertFalse(m["direct_visible"])
        with self.assertRaisesRegex(Diagnostic,"MalformedObservation"):remembered_observation(1.2,.1,1.05)
        a=Actor();old=a.nav_epoch;a.damage("H",11,1,25,9);a.recover(21)
        with self.assertRaisesRegex(Diagnostic,"StaleNavigation"):a.nav_ticket(old,21)

class SecondaryTests(unittest.TestCase):
    def test_15_critical_damping_complete_numeric_step(self):
        q,v=critical_step(.2,0.,10.,.1)
        self.assertAlmostEqual(q,.14715177646857694);self.assertAlmostEqual(v,-.7357588823428847)
    def test_16_exact_constant_forcing_is_substep_invariant(self):
        direct=critical_step(.2,.3,10.,.1,5.)
        half=critical_step(*critical_step(.2,.3,10.,.05,5.),10.,.05,5.)
        self.assertTrue(all(abs(a-b)<1e-12 for a,b in zip(direct,half)))
    def test_17_active_tip_marks_ancestors_not_sibling_ears(self):
        p={"root":None,"torso":"root","tail1":"torso","tail2":"tail1","ear":"torso"}
        self.assertEqual(active_ancestors(p,["tail2"]),{"root","torso","tail1","tail2"})
    def test_18_passive_cannot_write_during_active_takeover(self):
        s=Secondary();s.take(.4,.2)
        with self.assertRaisesRegex(Diagnostic,"OutputNotOwned"):s.step(10.,.1)
    def test_19_acquisition_preserves_position_and_velocity_at_entry(self):
        s=Secondary();s.step(10.,.1);q,v=s.q,s.v;s.take(.4,.2);s.sample_take(0.)
        self.assertAlmostEqual(s.q,q);self.assertAlmostEqual(s.v,v)
    def test_20_hermite_midpoint_and_end(self):
        q0,v0=critical_step(.2,0.,10.,.1)
        q,v=hermite(q0,v0,.4,0.,.2,.1)
        self.assertAlmostEqual(q,.25518191617571634)
        end=hermite(q0,v0,.4,0.,.2,.2);self.assertAlmostEqual(end[0],.4);self.assertAlmostEqual(end[1],0.)
    def test_21_return_seeds_actual_current_pose(self):
        s=Secondary();s.take(.4,.2);s.sample_take(.2);s.release()
        self.assertEqual((s.q,s.v,s.mode),(.4,0.,"Passive"))
        s.step(10.,.1);self.assertAlmostEqual(s.q,.2943035529371539);self.assertAlmostEqual(s.v,-1.4715177646857693)
    def test_22_parent_rebase_preserves_world_angle_and_velocity(self):
        q,v=rebase_angle(.1,.2,.2,.3,.4,.1)
        self.assertAlmostEqual(.3+q,.2+.1);self.assertAlmostEqual(.1+v,.4+.2)
    def test_23_clamp_removes_only_outward_velocity(self):
        q,v,why=clamp_angle(.7,2.,-.5,.5);self.assertEqual((q,v,why),(.5,0.,"UpperLimit"))
        q,v,why=clamp_angle(.7,-2.,-.5,.5);self.assertEqual(v,-2.)
    def test_24_old_secondary_job_cannot_overwrite_active_pose(self):
        s=Secondary();old=s.owner_epoch;s.take(.4,.2);before=(s.q,s.v)
        with self.assertRaisesRegex(Diagnostic,"StaleSecondaryJob"):s.publish_passive_job(3,old,.9,5.)
        self.assertEqual((s.q,s.v),before)
    def test_25_body_revision_invalidates_old_job(self):
        s=Secondary();s.body_revision=4
        with self.assertRaisesRegex(Diagnostic,"StaleSecondaryJob"):s.publish_passive_job(3,0,.9,5.)
    def test_26_invalid_dynamics_remains_diagnostic(self):
        for omega,dt in [(0.,.1),(10.,0.),(10.,-.1)]:
            with self.assertRaisesRegex(Diagnostic,"InvalidDynamicsStep"):critical_step(.2,0.,omega,dt)
        with self.assertRaisesRegex(Diagnostic,"NonFinite"):critical_step(math.inf,0.,10.,.1)
    def test_27_collision_authority_does_not_follow_display_lod(self):
        s=Secondary();s.step(10.,.1)
        self.assertEqual(s.collision_angle(.9),s.collision_angle(0.))
        self.assertAlmostEqual(s.collision_angle(.9),.14715177646857694)
    def test_28_passive_update_has_no_feedback_to_parent(self):
        parent={"q":.3,"v":1.,"acceleration":10.};before=dict(parent)
        child=Secondary();child.step(10.,.1,-.2*parent["acceleration"])
        self.assertEqual(parent,before)
        self.assertLess(child.q,critical_step(.2,0.,10.,.1)[0])

class ExistingEvidenceTests(unittest.TestCase):
    def test_29_selected_attack_id_lists_have_no_direct_reaction_ids(self):
        d=json.loads((ROOT/"evidence/local-selected-attack-properties.json").read_text(encoding="utf-8"))
        ids={"0x075e00b7","0x07a7ffd5","0x07a7ffd9","0x075e0100"}
        self.assertEqual(len(d["records"]),50)
        for r in d["records"]:
            self.assertEqual(len(r["property_ids"]),r["property_count"])
            self.assertFalse(ids.intersection(x.lower() for x in r["property_ids"]))
    def test_30_ear_eye_selectors_do_not_establish_pose_goals(self):
        d=json.loads((ROOT/"evidence/local-same-role-selector-observations.json").read_text(encoding="utf-8"))
        patterns=[x for x in d["statistics"]["unique_context_patterns"] if x["context_role"]=="primaryContext" and x["capability_ascii"] in {"ear","eye"}]
        self.assertEqual({x["capability_ascii"] for x in patterns},{"ear","eye"})
        self.assertEqual([x["occurrences"] for x in patterns],[46,46])
        self.assertTrue(all(x["flags"]=="0x00000000" for x in patterns))

if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps({"kind":"independent-reaction-secondary-examples",
                      "tests_run":result.testsRun,"failures":len(result.failures),
                      "errors":len(result.errors),"success":result.wasSuccessful(),
                      "module_counts":{"47":14,"48":14,"existing_json":2},
                      "game_runtime_verified":False}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
