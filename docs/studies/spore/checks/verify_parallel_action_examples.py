"""Independent small contract models; not original Spore or production animation."""
from dataclasses import dataclass
import math
import unittest


@dataclass(frozen=True)
class Claim:
    key: str
    mode: str='Exclusive'
    contract: str=''
    magnitude: float=0


def compatible(a,b):
    if a.key!=b.key:return True
    return a.mode==b.mode and a.mode in ('Blend','Additive') and bool(a.contract) and a.contract==b.contract


class Coordinator:
    def __init__(self,energy=40):
        self.energy=energy;self.actions={};self.effects=set();self.next_token=1

    def reserve(self,name,claims,cost,priority=1,preempt=False,interruptible=True):
        victims=[]
        for token,a in self.actions.items():
            if a['active'] and any(not compatible(x,y) for x in claims for y in a['claims']):
                if not preempt or priority<=a['priority'] or not a['interruptible']:return 'ChannelConflict'
                victims.append(token)
        active=[a for token,a in self.actions.items() if a['active'] and token not in victims]
        if cost>self.energy-sum(a['reserved'] for a in active):return 'InsufficientEnergy'
        for claim in claims:
            if claim.mode=='Additive':
                used=sum(y.magnitude for a in active for y in a['claims'] if y.key==claim.key)
                used+=sum(y.magnitude for y in claims if y.key==claim.key)
                if used>15:return 'AdditiveBudgetExceeded'
        # Planning succeeded before mutating victims or installing any new claims.
        for token in victims:self.cancel(token,'Preempted')
        token=self.next_token;self.next_token+=1
        self.actions[token]=dict(name=name,claims=claims,reserved=cost,priority=priority,
                                 interruptible=interruptible,active=True,reason=None,ordinals=set())
        return token

    def cancel(self,token,reason):
        a=self.actions[token];a['active']=False;a['reserved']=0;a['reason']=reason

    def release(self,token):
        if not self.actions[token]['active']:return 'AlreadyReleased'
        self.cancel(token,'Completed');return 'Released'

    def effect(self,token,ordinal):
        a=self.actions[token]
        if not a['active']:return 'ActionInactive'
        if ordinal in a['ordinals']:return 'Duplicate'
        self.energy-=a['reserved'];a['reserved']=0;a['ordinals'].add(ordinal)
        self.effects.add((token,ordinal));return 'Committed'


def blend_position(base,goals):
    # Goal fields: priority, stable order, compatible group, weight, scalar position.
    if any(not math.isfinite(g[3]) or g[3]<0 for g in goals):raise ValueError('InvalidWeight')
    active=sorted((g for g in goals if g[3]>0),key=lambda g:(-g[0],g[1]))
    if not active:return base
    winner=active[0];same=[g for g in active if (g[0],g[2])==(winner[0],winner[2])]
    weight=sum(g[3] for g in same);target=sum(g[3]*g[4] for g in same)/weight
    return base+min(1,weight)*(target-base)


def slerp(a,b,t):
    dot=sum(x*y for x,y in zip(a,b))
    if dot<0:b=tuple(-x for x in b);dot=-dot
    dot=min(1,max(-1,dot))
    if dot>.9995:
        q=tuple((1-t)*x+t*y for x,y in zip(a,b));n=math.sqrt(sum(v*v for v in q))
        return tuple(v/n for v in q)
    angle=math.acos(dot);s=math.sin(angle)
    return tuple(math.sin((1-t)*angle)/s*x+math.sin(t*angle)/s*y for x,y in zip(a,b))


def support_hull(points):
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    halves=[]
    for seq in (sorted(set(points)),list(reversed(sorted(set(points))))):
        h=[]
        for p in seq:
            while len(h)>=2 and cross(h[-2],h[-1],p)<=0:h.pop()
            h.append(p)
        halves.append(h[:-1])
    return halves[0]+halves[1]


def supports(points,com,margin=.1):
    h=support_hull(points)
    if len(h)<3:return False
    for a,b in zip(h,h[1:]+h[:1]):
        edge=math.hypot(b[0]-a[0],b[1]-a[1])
        side=((b[0]-a[0])*(com[1]-a[1])-(b[1]-a[1])*(com[0]-a[0]))/edge
        if side<margin:return False
    return True


class ParallelExamples(unittest.TestCase):
    def test_distinct_hands_and_separate_degrees_of_freedom_coexist(self):
        c=Coordinator()
        a=c.reserve('slash',[Claim('RF.pos')],10)
        b=c.reserve('shield',[Claim('LB.rot')],15)
        self.assertIsInstance(a,int);self.assertIsInstance(b,int)
        self.assertIsInstance(c.reserve('RF twist',[Claim('RF.rot')],0),int)

    def test_same_hand_conflict_is_atomic(self):
        c=Coordinator();a=c.reserve('slash',[Claim('RF.pos')],10)
        self.assertEqual(c.reserve('ritual',[Claim('LF.pos'),Claim('RF.pos')],0),'ChannelConflict')
        self.assertEqual(len(c.actions),1);self.assertTrue(c.actions[a]['active'])

    def test_shared_ancestor_can_conflict_despite_different_hands(self):
        c=Coordinator();c.reserve('slash',[Claim('RF.pos'),Claim('torso.yaw')],0)
        self.assertEqual(c.reserve('bow',[Claim('LF.pos'),Claim('torso.yaw')],0),'ChannelConflict')

    def test_compatible_additive_torso_goals_share_but_budget_still_limits(self):
        c=Coordinator();contract='same torso frame, cosmetic yaw'
        self.assertIsInstance(c.reserve('slash',[Claim('yaw','Additive',contract,8)],0),int)
        self.assertIsInstance(c.reserve('shield',[Claim('yaw','Additive',contract,6)],0),int)
        self.assertEqual(c.reserve('extra',[Claim('yaw','Additive',contract,2)],0),'AdditiveBudgetExceeded')

    def test_incompatible_blend_contracts_are_not_shared_numeric_groups(self):
        c=Coordinator();c.reserve('A',[Claim('torso','Blend','A/group7')],0)
        self.assertEqual(c.reserve('B',[Claim('torso','Blend','B/group7')],0),'ChannelConflict')

    def test_resource_failure_does_not_preempt_or_partially_claim(self):
        c=Coordinator(10);a=c.reserve('A',[Claim('RF')],5)
        self.assertEqual(c.reserve('B',[Claim('RF'),Claim('LF')],20,priority=9,preempt=True),'InsufficientEnergy')
        self.assertTrue(c.actions[a]['active']);self.assertEqual(len(c.actions),1)

    def test_committed_effect_survives_preemption_and_late_callback_rejected(self):
        c=Coordinator();a=c.reserve('slash',[Claim('RF')],10)
        b=c.reserve('shield',[Claim('LB')],15);self.assertEqual(c.effect(b,0),'Committed')
        stagger=c.reserve('stagger',[Claim('RF'),Claim('LB')],0,priority=9,preempt=True)
        self.assertIsInstance(stagger,int)
        self.assertEqual(c.energy,25);self.assertEqual(c.actions[a]['reserved'],0)
        self.assertEqual(c.effect(a,0),'ActionInactive');self.assertIn((b,0),c.effects)

    def test_duplicate_ordinal_and_old_release_do_not_affect_new_owner(self):
        c=Coordinator();a=c.reserve('A',[Claim('RF')],10)
        self.assertEqual(c.effect(a,0),'Committed');self.assertEqual(c.effect(a,0),'Duplicate')
        c.release(a);b=c.reserve('B',[Claim('RF')],0)
        self.assertEqual(c.release(a),'AlreadyReleased');self.assertTrue(c.actions[b]['active'])

    def test_zero_weight_does_not_take_ownership_and_bad_weights_rejected(self):
        self.assertEqual(blend_position(0,[(100,0,'A',0,20),(10,1,'B',1,2)]),2)
        for w in (-1,float('nan')):
            with self.assertRaises(ValueError):blend_position(0,[(1,0,'A',w,2)])

    def test_group_weight_normalization_fade_and_stable_ties(self):
        self.assertAlmostEqual(blend_position(0,[(10,0,'A',.6,1),(10,1,'A',.4,0)]),.6)
        self.assertAlmostEqual(blend_position(0,[(10,0,'A',.25,2)]),.5)
        self.assertEqual(blend_position(0,[(10,1,'B',1,20),(10,0,'A',1,2)]),2)

    def test_quaternion_hemisphere_and_midpoint(self):
        q=(1,0,0,0);self.assertEqual(slerp(q,(-1,0,0,0),.5),q)
        q60=(math.cos(math.pi/6),0,0,math.sin(math.pi/6))
        q120=(math.cos(math.pi/3),0,0,math.sin(math.pi/3))
        q90=slerp(q60,q120,.5)
        self.assertAlmostEqual(q90[0],math.sqrt(.5));self.assertAlmostEqual(q90[3],math.sqrt(.5))

    def test_kick_releases_contact_only_after_support_plan_is_safe(self):
        feet=[(-.6,.8),(.6,0),(-.6,-.8)]
        self.assertTrue(supports(feet,(0,0)))
        self.assertFalse(supports(feet[1:],(0,0)))
        five=[(-.6,0),(-.6,-.8),(.6,.8),(.6,0),(.6,-.8)]
        self.assertTrue(supports(five,(0,0)))


if __name__=='__main__':unittest.main(verbosity=2)
