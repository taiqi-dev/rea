"""Independent action/event/socket/window contracts, not Spore implementation."""
from dataclasses import dataclass, replace
import math
import unittest


class ExampleError(ValueError):
    pass


@dataclass(frozen=True)
class Slot:
    ordinal: int
    emitter: str
    time: float
    cost: float = 5.


@dataclass
class Action:
    ident: str
    revision: int
    soul_generation: int
    binding_epoch: int
    slots: tuple
    phase: str = 'Active'
    cursor: float = 0.
    started: bool = False
    reserved: float = 0.


@dataclass(frozen=True)
class Ticket:
    action_id: str
    ordinal: int
    emitter: str
    revision: int
    soul_generation: int
    binding_epoch: int
    logical_marker_time: float
    authority: str = 'SimulationMarker'


def edited_socket_world(root, angle, mount, socket):
    # socket and mount already belong to the current edited reference + pose.
    if any(len(row)!=3 for row in (root,mount,socket)) or not all(math.isfinite(v) for v in (*root, angle, *mount, *socket)):
        raise ExampleError('InvalidSocketPose')
    c, s = math.cos(angle), math.sin(angle)
    x,y,z = (a+b for a,b in zip(mount,socket))
    return ((root[0]+c*x-s*y, root[1]+s*x+c*y, root[2]+z), (c,s,0.))


class World:
    def __init__(self):
        self.revision = 42
        self.soul_generation = 7
        self.energy = 20.
        self.actions = {}
        self.parts = {'M1':True, 'M2':True}
        self.committed = set()
        self.projectiles = {}
        self.target_hp = 100.

    def start(self, ident, slots):
        if ident in self.actions:
            raise ExampleError('ActionIdentityReused')
        ordinals = [s.ordinal for s in slots]
        if any(not isinstance(n,int) or isinstance(n,bool) or n<0 for n in ordinals):
            raise ExampleError('InvalidEffectOrdinal')
        if len(set(ordinals)) != len(ordinals):
            raise ExampleError('DuplicateEffectOrdinal')
        if any(not math.isfinite(s.time) or s.time < 0 or not math.isfinite(s.cost) or s.cost < 0 for s in slots):
            raise ExampleError('InvalidEffectSlot')
        cost = sum(s.cost for s in slots)
        reserved = sum(a.reserved for a in self.actions.values())
        if self.energy-reserved < cost:
            raise ExampleError('InsufficientUnreservedEnergy')
        a=Action(ident,self.revision,self.soul_generation,1,tuple(slots),reserved=cost)
        self.actions[ident]=a
        return a

    def ticket(self, action, slot):
        return Ticket(action.ident,slot.ordinal,slot.emitter,action.revision,
                      action.soul_generation,action.binding_epoch,slot.time)

    def fire(self, ticket):
        if ticket.authority != 'SimulationMarker':
            return 'NonAuthoritativeEvent'
        a=self.actions.get(ticket.action_id)
        if a is None:
            return 'UnknownAction'
        if a.phase != 'Active':
            return 'ActionInactive'
        if ticket.binding_epoch != a.binding_epoch:
            return 'StaleBindingEpoch'
        if ticket.revision != a.revision or a.revision != self.revision:
            return 'StaleBodyRevision'
        if ticket.soul_generation != a.soul_generation or a.soul_generation != self.soul_generation:
            return 'StaleControlGeneration'
        slots=[s for s in a.slots if s.ordinal == ticket.ordinal]
        if not slots:
            return 'UnknownEffectOrdinal'
        slot=slots[0]
        if not math.isfinite(ticket.logical_marker_time) or ticket.logical_marker_time!=slot.time:
            return 'MarkerTimelineMismatch'
        if ticket.emitter != slot.emitter:
            return 'UnexpectedEmitter'
        if not self.parts.get(slot.emitter,False):
            return 'DependencyLost'
        key=(a.ident,slot.ordinal)  # No part/channel ID: one logical effect across notifications.
        if key in self.committed:
            return 'DuplicateIgnored'
        if a.reserved < slot.cost or self.energy < slot.cost:
            return 'ReservationInvalid'
        origin,direction=edited_socket_world((10.,2.,0.),math.pi/2,(.6,.2,.8),(.3,0.,0.))
        # Actor-local transaction; no claim of crash/network exactly-once delivery.
        self.energy-=slot.cost
        a.reserved-=slot.cost
        self.projectiles[key]={'origin':origin,'direction':direction,'source_action':a.ident,
                               'source_emitter':slot.emitter,'impacted':False}
        self.committed.add(key)
        return 'Spawned'

    def advance(self, action, new_time):
        if not math.isfinite(new_time) or new_time < action.cursor:
            raise ExampleError('InvalidTimelineAdvance')
        output=[]
        for slot in sorted(action.slots,key=lambda s:(s.time,s.ordinal)):
            due=action.cursor < slot.time <= new_time
            initial=not action.started and slot.time == 0
            if due or initial:
                output.append(self.fire(self.ticket(action,slot)))
        action.cursor=new_time
        action.started=True
        return output

    def cancel(self, action):
        if action.phase == 'Active':
            action.phase='Cancelled'
            action.binding_epoch+=1
            action.reserved=0.

    def detach(self, part):
        self.parts[part]=False
        self.revision+=1
        for action in self.actions.values():
            if any(s.emitter==part for s in action.slots):
                self.cancel(action)

    def impact(self, key, damage=12.):
        p=self.projectiles.get(key)
        if p is None:
            return 'UnknownProjectile'
        if p['impacted']:
            return 'DuplicateImpactIgnored'
        if not math.isfinite(damage) or damage < 0:
            raise ExampleError('InvalidDamage')
        self.target_hp-=damage
        p['impacted']=True
        return 'DamageCommitted'


def active_sweep(t0,t1,p0,p1,window_start,window_end):
    numbers=(t0,t1,*p0,*p1,window_start,window_end)
    if len(p0)!=2 or len(p1)!=2 or not all(math.isfinite(x) for x in numbers) or t1<=t0 or window_end<=window_start:
        raise ExampleError('InvalidSweepInterval')
    lo=max(t0,window_start); hi=min(t1,window_end)
    if lo>=hi:
        return None
    def point(t):
        f=(t-t0)/(t1-t0)
        return tuple(a+(b-a)*f for a,b in zip(p0,p1))
    return point(lo),point(hi)


def point_segment_distance(p,a,b):
    if any(len(row)!=2 for row in (p,a,b)) or not all(math.isfinite(v) for row in (p,a,b) for v in row):
        raise ExampleError('InvalidHitGeometry')
    delta=tuple(y-x for x,y in zip(a,b))
    length2=sum(v*v for v in delta)
    projection=sum((x-y)*v for x,y,v in zip(p,a,delta))/length2 if length2 else 0.
    projection=max(0.,min(1.,projection))
    return math.sqrt(sum((x-(y+projection*v))**2 for x,y,v in zip(p,a,delta)))


def hit_window_once(ledger, action_id, ordinal, target_life_id, sweep, center, target_radius, weapon_radius):
    if not all(math.isfinite(x) and x>=0 for x in (target_radius,weapon_radius)):
        raise ExampleError('InvalidHitRadius')
    if sweep is None:
        return 'NoActiveSweep'
    key=(action_id,ordinal,target_life_id)
    if key in ledger:
        return 'DuplicateHitIgnored'
    if point_segment_distance(center,*sweep)>target_radius+weapon_radius:
        return 'Miss'
    ledger.add(key)
    return 'Hit'


class ActionEffectExamples(unittest.TestCase):
    def cast(self,slots=None):
        w=World(); a=w.start('A17',slots if slots is not None else [Slot(0,'M2',.3)])
        return w,a

    def test_frame_skips_marker_but_fires_once(self):
        w,a=self.cast(); self.assertEqual(w.advance(a,.2),[])
        self.assertEqual(w.advance(a,.4),['Spawned'])
        self.assertEqual(w.advance(a,.5),[])
        self.assertEqual(len(w.projectiles),1)
        self.assertEqual(w.energy,15)

    def test_duplicate_same_slot_across_channels(self):
        w,a=self.cast(); ticket=w.ticket(a,a.slots[0])
        self.assertEqual(w.fire(ticket),'Spawned')
        self.assertEqual(w.fire(ticket),'DuplicateIgnored')
        self.assertEqual(w.energy,15)

    def test_non_authoritative_animation_event_cannot_fire(self):
        w,a=self.cast(); ticket=replace(w.ticket(a,a.slots[0]),authority='AnimationVFX')
        self.assertEqual(w.fire(ticket),'NonAuthoritativeEvent')
        self.assertEqual(w.energy,20)

    def test_other_mouth_cannot_create_same_effect(self):
        w,a=self.cast(); ticket=replace(w.ticket(a,a.slots[0]),emitter='M1')
        self.assertEqual(w.fire(ticket),'UnexpectedEmitter')
        self.assertEqual(len(w.projectiles),0)

    def test_explicit_two_mouth_volley_has_two_ordinals(self):
        w,a=self.cast([Slot(0,'M1',.3),Slot(1,'M2',.3)])
        self.assertEqual(w.advance(a,.4),['Spawned','Spawned'])
        self.assertEqual(len(w.projectiles),2)
        self.assertEqual(w.energy,10)

    def test_cancel_before_marker_releases_unpaid_reservation(self):
        w,a=self.cast(); old=w.ticket(a,a.slots[0]); w.cancel(a)
        self.assertEqual(w.fire(old),'ActionInactive')
        self.assertEqual((w.energy,a.reserved,len(w.projectiles)),(20,0,0))

    def test_detach_before_fire_invalidates_old_callback(self):
        w,a=self.cast(); old=w.ticket(a,a.slots[0]); w.detach('M2')
        self.assertEqual(w.fire(old),'ActionInactive')
        self.assertEqual(w.energy,20)

    def test_detach_after_fire_does_not_revoke_projectile(self):
        w,a=self.cast(); w.advance(a,.4); w.detach('M2')
        self.assertEqual(w.impact(('A17',0)),'DamageCommitted')
        self.assertEqual(w.target_hp,88)
        self.assertEqual(w.energy,15)

    def test_duplicate_projectile_impact_not_extra_damage(self):
        w,a=self.cast(); w.advance(a,.4)
        self.assertEqual(w.impact(('A17',0)),'DamageCommitted')
        self.assertEqual(w.impact(('A17',0)),'DuplicateImpactIgnored')
        self.assertEqual(w.target_hp,88)

    def test_old_binding_epoch_after_rebind_is_rejected(self):
        w,a=self.cast(); old=w.ticket(a,a.slots[0]); a.binding_epoch+=1
        self.assertEqual(w.fire(old),'StaleBindingEpoch')
        self.assertEqual(w.energy,20)

    def test_rebuild_revision_rejects_old_bound_socket(self):
        w,a=self.cast(); w.revision+=1
        self.assertEqual(w.fire(w.ticket(a,a.slots[0])),'StaleBodyRevision')

    def test_soul_change_rejects_old_control(self):
        w,a=self.cast(); w.soul_generation+=1
        self.assertEqual(w.fire(w.ticket(a,a.slots[0])),'StaleControlGeneration')

    def test_unknown_action_and_slot_have_reasons(self):
        w,a=self.cast(); ticket=w.ticket(a,a.slots[0])
        self.assertEqual(w.fire(replace(ticket,action_id='unknown')),'UnknownAction')
        self.assertEqual(w.fire(replace(ticket,ordinal=99)),'UnknownEffectOrdinal')

    def test_marker_time_must_match_owned_slot(self):
        w,a=self.cast(); ticket=w.ticket(a,a.slots[0])
        self.assertEqual(w.fire(replace(ticket,logical_marker_time=.1)),'MarkerTimelineMismatch')
        self.assertEqual(w.energy,20)

    def test_bad_geometry_and_ordinals_are_diagnostic(self):
        with self.assertRaisesRegex(ExampleError,'InvalidEffectOrdinal'):
            World().start('A',[Slot(-1,'M1',.1)])
        with self.assertRaisesRegex(ExampleError,'InvalidHitGeometry'):
            point_segment_distance((math.nan,0),(0,0),(1,0))
        with self.assertRaisesRegex(ExampleError,'InvalidSocketPose'):
            edited_socket_world((0,0),0,(0,0,0),(0,0,0))

    def test_dependency_state_checked_before_spawn(self):
        w,a=self.cast(); w.parts['M2']=False
        self.assertEqual(w.fire(w.ticket(a,a.slots[0])),'DependencyLost')
        self.assertEqual(a.reserved,5)

    def test_socket_position_uses_selected_edited_part(self):
        p,d=edited_socket_world((10,2,0),math.pi/2,(.6,.2,.8),(.3,0,0))
        for value,expected in zip(p,(9.8,2.9,.8)):
            self.assertAlmostEqual(value,expected)
        self.assertAlmostEqual(d[0],0)
        self.assertAlmostEqual(d[1],1)

    def test_window_clips_pose_step_before_sweep(self):
        sweep=active_sweep(.2,.45,(0,0),(2,0),.25,.4)
        self.assertAlmostEqual(sweep[0][0],.4)
        self.assertAlmostEqual(sweep[1][0],1.6)
        self.assertEqual(hit_window_once(set(),'H','W0','T-life1',sweep,(1,.2),.15,.1),'Hit')

    def test_target_reached_only_outside_window_is_miss(self):
        sweep=active_sweep(.2,.45,(0,0),(2,0),.25,.4)
        self.assertEqual(hit_window_once(set(),'H','W0','T-life1',sweep,(1.95,0),.05,.1),'Miss')

    def test_hit_ledger_excludes_channel_part_ids(self):
        ledger=set(); sweep=((.4,0),(1.6,0))
        self.assertEqual(hit_window_once(ledger,'A',0,'T-life1',sweep,(1,.2),.15,.1),'Hit')
        self.assertEqual(hit_window_once(ledger,'A',0,'T-life1',sweep,(1,.2),.15,.1),'DuplicateHitIgnored')

    def test_explicit_second_swing_and_new_target_life(self):
        ledger=set(); sweep=((0,0),(2,0))
        for ordinal,life in ((0,'T-life1'),(1,'T-life1'),(0,'T-life2')):
            self.assertEqual(hit_window_once(ledger,'A',ordinal,life,sweep,(1,0),.1,.1),'Hit')
        self.assertEqual(len(ledger),3)

    def test_no_overlap_means_no_attack_segment(self):
        sweep=active_sweep(.5,.6,(0,0),(1,0),.25,.4)
        self.assertIsNone(sweep)
        self.assertEqual(hit_window_once(set(),'A',0,'T',sweep,(0,0),.1,.1),'NoActiveSweep')

    def test_event_at_start_only_once(self):
        w,a=self.cast([Slot(0,'M2',0)])
        self.assertEqual(w.advance(a,0),['Spawned'])
        self.assertEqual(w.advance(a,0),[])

    def test_duplicate_ordinals_and_action_reuse_rejected(self):
        w,a=self.cast()
        with self.assertRaisesRegex(ExampleError,'ActionIdentityReused'):
            w.start('A17',[])
        with self.assertRaisesRegex(ExampleError,'DuplicateEffectOrdinal'):
            w.start('A18',[Slot(0,'M1',.1),Slot(0,'M2',.2)])

    def test_reservations_are_counted_across_actions(self):
        w,a=self.cast([Slot(0,'M2',.3,15)])
        with self.assertRaisesRegex(ExampleError,'InsufficientUnreservedEnergy'):
            w.start('A18',[Slot(0,'M1',.2,6)])
        w.cancel(a)
        self.assertEqual(w.start('A18',[Slot(0,'M1',.2,6)]).reserved,6)

    def test_bad_numeric_inputs_are_diagnostic(self):
        w,a=self.cast()
        with self.assertRaisesRegex(ExampleError,'InvalidEffectSlot'):
            w.start('A18',[Slot(0,'M1',math.nan)])
        with self.assertRaisesRegex(ExampleError,'InvalidTimelineAdvance'):
            w.advance(a,-.1)
        with self.assertRaisesRegex(ExampleError,'InvalidSweepInterval'):
            active_sweep(1,1,(0,0),(1,0),.2,.3)

    def test_cancel_half_volley_keeps_committed_cost_and_effect(self):
        w,a=self.cast([Slot(0,'M1',.2),Slot(1,'M2',.4)])
        self.assertEqual(w.advance(a,.3),['Spawned'])
        w.cancel(a)
        self.assertEqual((w.energy,a.reserved,len(w.projectiles)),(15,0,1))
        self.assertEqual(w.advance(a,.5),['ActionInactive'])


if __name__=='__main__':
    unittest.main(verbosity=2)
