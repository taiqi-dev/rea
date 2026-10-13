"""Executable independent specifications; no Spore selector or PCTP formulas."""
from dataclasses import dataclass, replace
import math
import unittest


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class Effector:
    part_id: str
    role: str
    reach: float
    distance: float
    hit_probability: float
    damage: float
    windup: float
    fatigue: float
    root_yaw: float
    connected: bool = True
    level: int = 1
    profile_present: bool = True
    occupied: bool = False
    cooldown_ready: bool = True
    support_safe: bool = True


HANDS = (
    Effector('H1', 'hand', .9, 1.1, .9, 12, .25, .1, .1),
    Effector('H2', 'hand', 1.25, 1., .85, 12, .35, .1, .15),
    Effector('H3', 'hand', 1.2, .8, .9, 12, .25, .3, .35, occupied=True),
    Effector('H4', 'hand', 1.1, .95, .7, 12, .4, .2, .2),
)


def rank_effectors(parts, required_role='hand'):
    accepted, rejected = [], []
    seen = set()
    for p in parts:
        if p.part_id in seen:
            raise SpecError('DuplicatePartIdentity')
        seen.add(p.part_id)
        numbers = (p.reach, p.distance, p.hit_probability, p.damage,
                   p.windup, p.fatigue, p.root_yaw)
        if not all(math.isfinite(v) for v in numbers):
            raise SpecError('InvalidCandidateNumeric')
        if (p.reach <= 0 or p.distance < 0 or p.damage < 0 or p.windup < 0
                or not 0 <= p.hit_probability <= 1 or not 0 <= p.fatigue <= 1):
            raise SpecError('InvalidCandidateDomain')
        reason = None
        if not p.connected:
            reason = 'PartUnavailable'
        elif p.role != required_role:
            reason = 'RoleMismatch'
        elif p.level < 1:
            reason = 'CapabilityInsufficient'
        elif not p.profile_present:
            reason = 'RequiredProfileMissing'
        elif p.occupied:
            reason = 'EssentialOutputOccupied'
        elif not p.cooldown_ready:
            reason = 'CooldownNotReady'
        elif p.distance > p.reach:
            reason = 'Unreachable'
        elif not p.support_safe:
            reason = 'SupportUnsafe'
        if reason:
            rejected.append((p.part_id, reason))
        else:
            # All constants and units are independently chosen for this example.
            score = (p.hit_probability * p.damage / (p.windup + .2)
                     - 2 * p.fatigue - 3 * abs(p.root_yaw))
            accepted.append((p.part_id, score))
    return sorted(accepted, key=lambda row: (-row[1], row[0])), rejected


class Claims:
    def __init__(self):
        self.owners = {}

    def acquire(self, action_id, outputs, plan_revision, current_revision):
        if plan_revision != current_revision:
            raise SpecError('StaleBodyRevision')
        if len(set(outputs)) != len(outputs):
            raise SpecError('DuplicateOutputClaim')
        if any(key in self.owners for key in outputs):
            raise SpecError('EssentialOutputOccupied')
        # Actor-local commit: all checks before any writes.
        for key in outputs:
            self.owners[key] = action_id

    def release(self, action_id):
        self.owners = {k: owner for k, owner in self.owners.items() if owner != action_id}


def bind_variant(part_id, role, revision, current_revision, bone_map, helpers):
    if revision != current_revision:
        raise SpecError('StaleBodyRevision')
    names = {'hand': ('fingerA', 'fingerB'), 'foot': ('ankle', 'toe')}
    if role not in names:
        raise SpecError('RoleMismatch')
    outputs = [(part_id, name) for name in names[role]]
    if part_id not in helpers:
        raise SpecError('RequiredHelperMissing')
    outputs.append(helpers[part_id])
    if any(key not in bone_map for key in outputs):
        raise SpecError('StableBoneMappingMissing')
    return tuple((key, bone_map[key]) for key in outputs)


@dataclass(frozen=True)
class Contribution:
    action_id: str
    contract: str
    priority: int
    weight: float
    value: float


def mix_scalar(neutral, default_value, default_weight, contributions):
    if (not all(math.isfinite(v) for v in (neutral, default_value, default_weight))
            or not 0 < neutral < 1 or not 0 <= default_value <= 1 or default_weight < 0):
        raise SpecError('InvalidDefaultProfile')
    identities = [c.action_id for c in contributions]
    if len(set(identities)) != len(identities):
        raise SpecError('DuplicateContributionIdentity')
    for c in contributions:
        if not math.isfinite(c.weight) or c.weight < 0 or not math.isfinite(c.value) or not 0 <= c.value <= 1:
            raise SpecError('InvalidContribution')
    active = sorted((c for c in contributions if c.weight > 0),
                    key=lambda c: (-c.priority, c.action_id))
    if active:
        winner = active[0]
        allowed = [c for c in active if (c.priority, c.contract) == (winner.priority, winner.contract)]
        suppressed = [c.action_id for c in active if c not in allowed]
    else:
        allowed, suppressed = [], []
    total = default_weight + sum(c.weight for c in allowed)
    if total == 0:
        return neutral, suppressed, 'NeutralFallback'
    value = (default_weight * default_value + sum(c.weight * c.value for c in allowed)) / total
    return value, suppressed, 'WeightedDefaultAndCompatibleActions'


def own_finger_delta(value, neutral=.2):
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise SpecError('MotionValueOutOfRange')
    return 40 * (value - neutral) / (1 - neutral) if value >= neutral else 10 * (value - neutral) / neutral


def hull(points):
    points = sorted(set(points))
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for output, rows in ((lower, points), (upper, reversed(points))):
        for p in rows:
            while len(output) >= 2 and cross(output[-2], output[-1], p) <= 0:
                output.pop()
            output.append(p)
    return lower[:-1] + upper[:-1]


def support_margin(contacts, removed, com=(0., 0.)):
    points = [p for key, p in contacts.items() if key != removed]
    for p in points + [com]:
        if len(p) != 2 or not all(math.isfinite(v) for v in p):
            raise SpecError('InvalidSupportGeometry')
    poly = hull(points)
    if len(poly) < 3:
        raise SpecError('SupportDegenerate')
    distances = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        length = math.hypot(b[0]-a[0], b[1]-a[1])
        signed = ((b[0]-a[0])*(com[1]-a[1]) - (b[1]-a[1])*(com[0]-a[0])) / length
        distances.append(signed)
    return min(distances)


FEET = {'F1':(-.4,.6), 'F2':(.4,.6), 'F3':(-.5,0),
        'F4':(.5,0), 'F5':(-.4,-.6), 'F6':(.4,-.6)}


class IndependentSelectionExamples(unittest.TestCase):
    def test_hand_ranking_and_rejections(self):
        ranks, rejects = rank_effectors(HANDS)
        self.assertEqual([x[0] for x in ranks], ['H2','H4'])
        self.assertAlmostEqual(ranks[0][1], 17.89545454545454)
        self.assertAlmostEqual(ranks[1][1], 13.)
        self.assertEqual(rejects, [('H1','Unreachable'),('H3','EssentialOutputOccupied')])

    def test_detach_replans_new_action(self):
        changed = [replace(p,connected=False) if p.part_id == 'H2' else p for p in HANDS]
        self.assertEqual(rank_effectors(changed)[0][0][0], 'H4')

    def test_tie_is_stable_identity_order(self):
        a=replace(HANDS[1],part_id='A'); b=replace(a,part_id='B')
        self.assertEqual(rank_effectors([b,a])[0][0][0],'A')

    def test_invalid_candidate_has_diagnostic(self):
        for p in (replace(HANDS[1],reach=math.nan), replace(HANDS[1],hit_probability=1.1)):
            with self.assertRaisesRegex(SpecError,'InvalidCandidate'):
                rank_effectors([p])

    def test_duplicate_instances_rejected(self):
        with self.assertRaisesRegex(SpecError,'DuplicatePart'):
            rank_effectors([HANDS[0],HANDS[0]])

    def test_role_level_profile_checks(self):
        for part, reason in ((replace(HANDS[1],role='foot'),'RoleMismatch'),
                             (replace(HANDS[1],level=0),'CapabilityInsufficient'),
                             (replace(HANDS[1],profile_present=False),'RequiredProfileMissing')):
            self.assertEqual(rank_effectors([part])[1][0][1],reason)

    def test_two_bones_and_corresponding_helper(self):
        mapping={('H2','fingerA'):7,('H2','fingerB'):8,('Arm2','shoulder'):4}
        bound=bind_variant('H2','hand',42,42,mapping,{'H2':('Arm2','shoulder')})
        self.assertEqual([x[1] for x in bound],[7,8,4])

    def test_missing_helper_or_bone_is_explicit(self):
        with self.assertRaisesRegex(SpecError,'HelperMissing'):
            bind_variant('H2','hand',42,42,{}, {})
        with self.assertRaisesRegex(SpecError,'BoneMappingMissing'):
            bind_variant('H2','hand',42,42,{}, {'H2':('Arm2','shoulder')})

    def test_stale_binding_is_rejected(self):
        with self.assertRaisesRegex(SpecError,'StaleBodyRevision'):
            bind_variant('H2','hand',42,43,{}, {})

    def test_bone_reorder_keeps_instance_identity(self):
        keys=[('H2','fingerA'),('H2','fingerB'),('Arm2','shoulder')]
        a=bind_variant('H2','hand',42,42,dict(zip(keys,[7,8,4])),{'H2':keys[-1]})
        b=bind_variant('H2','hand',43,43,dict(zip(keys,[2,9,1])),{'H2':keys[-1]})
        self.assertEqual([x[0] for x in a],[x[0] for x in b])
        self.assertNotEqual([x[1] for x in a],[x[1] for x in b])

    def test_claim_failure_is_atomic(self):
        claims=Claims(); claims.acquire('shield',[('H3','fingerA')],42,42)
        with self.assertRaisesRegex(SpecError,'Occupied'):
            claims.acquire('strike',[('H2','fingerA'),('H3','fingerA')],42,42)
        self.assertNotIn(('H2','fingerA'),claims.owners)

    def test_old_release_does_not_release_new_owner(self):
        claims=Claims(); key=('H2','fingerA')
        claims.acquire('old',[key],42,42); claims.release('old')
        claims.acquire('new',[key],43,43); claims.release('old')
        self.assertEqual(claims.owners[key],'new')

    def test_commit_rechecks_revision(self):
        with self.assertRaisesRegex(SpecError,'StaleBodyRevision'):
            Claims().acquire('strike',[('H2','fingerA')],42,43)

    def test_default_and_one_action(self):
        q,blocked,_=mix_scalar(.2,.35,.25,[Contribution('A','grip',1,.75,.8)])
        self.assertAlmostEqual(q,.6875)
        self.assertAlmostEqual(own_finger_delta(q),24.375)
        self.assertAlmostEqual(.6*own_finger_delta(q),14.625)
        self.assertEqual(blocked,[])

    def test_default_and_two_compatible_actions(self):
        q,_,_=mix_scalar(.2,.35,.25,[Contribution('A','grip',1,.75,.8),Contribution('B','grip',1,.25,.6)])
        self.assertAlmostEqual(q,.67)
        self.assertAlmostEqual(own_finger_delta(q),23.5)

    def test_idle_default_and_zero_weight(self):
        self.assertAlmostEqual(mix_scalar(.2,.35,.25,[])[0],.35)
        self.assertAlmostEqual(own_finger_delta(.35),7.5)
        self.assertEqual(mix_scalar(.2,.35,0,[]),(.2,[],'NeutralFallback'))

    def test_zero_weight_does_not_claim_priority(self):
        q,_,_=mix_scalar(.2,.35,.25,[Contribution('Z','other',99,0,1),Contribution('A','grip',1,.75,.8)])
        self.assertAlmostEqual(q,.6875)

    def test_incompatible_and_lower_priority_are_suppressed(self):
        q,blocked,_=mix_scalar(.2,.35,.25,[Contribution('A','grip',2,.75,.8),
              Contribution('B','open',2,.25,.1),Contribution('C','grip',1,.25,.6)])
        self.assertAlmostEqual(q,.6875)
        self.assertEqual(blocked,['B','C'])

    def test_invalid_weights_values_and_duplicates(self):
        for row in (Contribution('A','grip',1,-.1,.5),Contribution('A','grip',1,1,math.nan)):
            with self.assertRaisesRegex(SpecError,'InvalidContribution'):
                mix_scalar(.2,.35,.25,[row])
        row=Contribution('A','grip',1,.5,.5)
        with self.assertRaisesRegex(SpecError,'DuplicateContribution'):
            mix_scalar(.2,.35,.25,[row,row])

    def test_default_profile_invalid(self):
        with self.assertRaisesRegex(SpecError,'InvalidDefaultProfile'):
            mix_scalar(.2,.35,-1,[])

    def test_fresh_pose_no_accumulation(self):
        outputs=[20+own_finger_delta(.6875) for _ in range(2)]
        self.assertEqual(outputs,[44.375,44.375])

    def test_three_contacts_cannot_release_stance_foot(self):
        with self.assertRaisesRegex(SpecError,'SupportDegenerate'):
            support_margin({k:FEET[k] for k in ('F1','F4','F5')},'F1')

    def test_settle_then_release_foot(self):
        margin=support_margin(FEET,'F1')
        self.assertAlmostEqual(margin,.3/math.sqrt(1.17))
        self.assertGreater(margin,.1)

    def test_foot_ranking_before_and_after_support_transition(self):
        feet = [Effector('F1','foot',.9,.7,.8,10,.3,.1,.1,support_safe=False),
                Effector('F2','foot',.9,.7,.9,10,.2,.1,.1,cooldown_ready=False),
                Effector('F3','foot',.9,.7,.8,10,.3,.1,.1,level=0),
                Effector('F4','foot',.9,.8,.6,10,.4,.2,.2,support_safe=False),
                Effector('F5','foot',.6,1,.8,10,.3,.1,.1),
                Effector('F6','foot',.9,.7,.8,10,.3,.1,.1,profile_present=False)]
        self.assertEqual(rank_effectors(feet,'foot')[0],[])
        settled=[replace(p,support_safe=True) for p in feet]
        ranks,_=rank_effectors(settled,'foot')
        self.assertEqual([x[0] for x in ranks],['F1','F4'])
        self.assertAlmostEqual(ranks[0][1],15.5)
        self.assertAlmostEqual(ranks[1][1],9.)

    def test_selected_foot_binds_its_leg_helper(self):
        mapping={('F1','ankle'):3,('F1','toe'):4,('Leg1','hip'):1}
        result=bind_variant('F1','foot',43,43,mapping,{'F1':('Leg1','hip')})
        self.assertEqual([x[1] for x in result],[3,4,1])

    def test_three_collinear_contacts_fail(self):
        with self.assertRaisesRegex(SpecError,'SupportDegenerate'):
            support_margin({'A':(-1,0),'B':(0,0),'C':(1,0)},'none')

    def test_com_outside_support_is_rejected(self):
        self.assertLess(support_margin(FEET,'F1',com=(2,0)),0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
