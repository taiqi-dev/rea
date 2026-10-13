"""Independent contact mathematics and state examples; not Spore runtime tests."""
from dataclasses import dataclass
import math
import unittest


def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, s): return tuple(x*s for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def norm(a): return math.sqrt(dot(a, a))
def clamp(x): return min(1., max(0., x))


def closest_segments(a, b, c, d):
    """Minimize a convex quadratic over the closed parameter square."""
    if any(not math.isfinite(x) for p in (a, b, c, d) for x in p):
        raise ValueError('NonFiniteProxy')
    u, v, w = sub(b, a), sub(d, c), sub(a, c)
    A, B, C, D, E = dot(u, u), dot(u, v), dot(v, v), dot(u, w), dot(v, w)
    candidates = [(0., 0.)]
    if C > 1e-16:
        candidates += [(0., clamp(E/C)), (1., clamp((E+B)/C))]
    if A > 1e-16:
        candidates += [(clamp(-D/A), 0.), (clamp((B-D)/A), 1.)]
    det = A*C-B*B
    if det > 1e-12*A*C:
        s, t = (B*E-C*D)/det, (A*E-B*D)/det
        if 0 <= s <= 1 and 0 <= t <= 1:
            candidates.append((s, t))
    s, t = min(candidates, key=lambda q: (norm(sub(add(a, mul(u, q[0])), add(c, mul(v, q[1])))), q))
    p, q = add(a, mul(u, s)), add(c, mul(v, t))
    return p, q, s, t


def capsule_gap(a, b, ra, c, d, rb, margin=0.):
    if any(not math.isfinite(x) or x < 0 for x in (ra, rb, margin)):
        raise ValueError('InvalidProxyRadius')
    p, q, s, t = closest_segments(a, b, c, d)
    return norm(sub(p, q))-ra-rb-margin, p, q, s, t


def outward_normal(p, q, fallback=(0., 1., 0.)):
    d = sub(p, q)
    if norm(d) <= 1e-10: d = fallback
    if norm(d) <= 1e-10 or any(not math.isfinite(x) for x in d):
        raise ValueError('SeparationNormalUndefined')
    return mul(d, 1/norm(d))


@dataclass(frozen=True)
class Permit:
    pair: tuple
    phase: str
    revision: int
    max_penetration: float


def permitted(permit, pair, phase, revision, penetration):
    return (permit is not None and frozenset(permit.pair) == frozenset(pair)
            and permit.phase == phase and permit.revision == revision
            and 0 <= penetration <= permit.max_penetration)


def join_excluded(p, q, joint, join_radius):
    return norm(sub(p, joint)) <= join_radius and norm(sub(q, joint)) <= join_radius


def sphere_contact(center, radius, approach, hand_radius):
    n = outward_normal(approach, center)
    return add(center, mul(n, radius)), add(center, mul(n, radius+hand_radius))


def require_revision(*revisions):
    if len(set(revisions)) != 1: raise ValueError('StaleContactGeometry')


def outcome(target_error, penetration, length_error, tolerance=.001):
    if max(penetration, length_error) > tolerance:
        return 'ConstraintConflict'
    if target_error > tolerance: return 'ContactTargetUnreachable'
    return 'ContactReady'


class BodyContactExamples(unittest.TestCase):
    def test_01_crossing_segments(self):
        p, q, s, t = closest_segments((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0))
        self.assertEqual(p, q); self.assertAlmostEqual(s, .5); self.assertAlmostEqual(t, .5)

    def test_02_parallel_and_degenerate_segments(self):
        p, q, *_ = closest_segments((0, 0, 0), (1, 0, 0), (0, 2, 0), (1, 2, 0))
        self.assertAlmostEqual(norm(sub(p, q)), 2)
        p, q, *_ = closest_segments((.5, 0, 0), (.5, 0, 0), (0, 1, 0), (1, 1, 0))
        self.assertAlmostEqual(norm(sub(p, q)), 1)

    def test_03_widening_changes_clearance(self):
        p=(0, 0, 0); a=(-.3, .6, 0); b=(.3, .6, 0)
        before=capsule_gap(a,b,.08,p,p,.4,.02)[0]
        after=capsule_gap(a,b,.08,p,p,.7,.02)[0]
        self.assertAlmostEqual(before, .1); self.assertAlmostEqual(after, -.2)

    def test_04_single_free_point_projection(self):
        hand=(.2,.1,0); center=(0,0,0); required=.7+.08+.02
        n=outward_normal(hand,center)
        corrected=add(hand,mul(n,required-norm(hand)))
        self.assertAlmostEqual(norm(corrected), required)
        # This free point calculation makes no claim about a connected IK chain.

    def test_05_coincident_witness_uses_explicit_normal(self):
        self.assertEqual(outward_normal((0,0,0),(0,0,0)),(0.,1.,0.))
        with self.assertRaisesRegex(ValueError,'SeparationNormalUndefined'):
            outward_normal((0,0,0),(0,0,0),(0,0,0))

    def test_06_contact_permission_is_narrow(self):
        permit=Permit(('finger.tip','fruit.surface'),'Grasp',4,.003)
        self.assertTrue(permitted(permit,('fruit.surface','finger.tip'),'Grasp',4,.002))
        self.assertFalse(permitted(permit,('forearm','torso'),'Grasp',4,.002))
        self.assertFalse(permitted(permit,permit.pair,'Reach',4,.002))
        self.assertFalse(permitted(permit,permit.pair,'Grasp',3,.002))
        self.assertFalse(permitted(permit,permit.pair,'Grasp',4,.01))

    def test_07_connected_segments_only_exclude_join_region(self):
        self.assertTrue(join_excluded((.01,0,0),(0,.01,0),(0,0,0),.05))
        self.assertFalse(join_excluded((.5,0,0),(.5,.01,0),(0,0,0),.05))

    def test_08_surface_goal_includes_hand_radius(self):
        surface, palm=sphere_contact((1.2,0,0),.2,(0,0,0),.05)
        self.assertAlmostEqual(surface[0], 1.)
        self.assertAlmostEqual(palm[0], .95)
        self.assertGreater(norm(palm), .7+.05+.02)
        self.assertNotEqual(palm,(1.2,0,0))

    def test_09_long_mouth_can_hit_torso(self):
        root=(.65,.5,0); short=(.5,.5,0); long=(-.25,.5,0); c=(0,0,0)
        self.assertGreater(capsule_gap(root,short,.08,c,c,.52,.02)[0],0)
        self.assertAlmostEqual(capsule_gap(root,long,.08,c,c,.52,.02)[0],-.12)

    def test_10_revision_mismatch_refuses_contact(self):
        require_revision(4,4,4)
        with self.assertRaisesRegex(ValueError,'StaleContactGeometry'):
            require_revision(4,3,4)

    def test_11_failure_does_not_become_ready(self):
        self.assertEqual(outcome(.1,0,0),'ContactTargetUnreachable')
        self.assertEqual(outcome(0,.01,0),'ConstraintConflict')
        self.assertEqual(outcome(0,0,.01),'ConstraintConflict')
        self.assertEqual(outcome(.0002,.0001,.0001),'ContactReady')

    def test_12_invalid_geometry_has_diagnostics(self):
        with self.assertRaisesRegex(ValueError,'InvalidProxyRadius'):
            capsule_gap((0,0,0),(1,0,0),-.1,(0,1,0),(1,1,0),.1)
        with self.assertRaisesRegex(ValueError,'NonFiniteProxy'):
            closest_segments((math.nan,0,0),(1,0,0),(0,1,0),(1,1,0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
