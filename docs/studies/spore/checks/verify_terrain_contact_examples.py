"""Independent terrain/contact examples; does not execute Spore."""
import math
import unittest


def height_interval(foot_z, hip_offset, horizontal, reach_min, reach_max):
    if horizontal > reach_max:
        raise ValueError('ChainUnreachable')
    return (foot_z-hip_offset+math.sqrt(max(0, reach_min**2-horizontal**2)),
            foot_z-hip_offset+math.sqrt(reach_max**2-horizontal**2))


def feasible_height(intervals, clearance):
    low = max([clearance] + [v[0] for v in intervals])
    high = min(v[1] for v in intervals)
    if low > high:
        raise ValueError('BodySupportInfeasible')
    return low, high


def required_lift(samples):
    result = 0.0
    for u, obstacle, base, margin in samples:
        b = 16*u*u*(1-u)*(1-u)
        if b == 0:
            if obstacle > base:
                raise ValueError('InvalidEndpoint')
            continue
        result = max(result, (obstacle+margin-base)/b)
    return result


def swing_state(start, duration, now, stopped):
    # stopped gates new swings, not the clock of this existing swing.
    return 'Settling' if now-start >= duration else 'Swing'


def triangle_contains_with_margin(points, p, margin):
    for i, a in enumerate(points):
        b = points[(i+1) % len(points)]
        cross = (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        if cross < margin*math.dist(a, b):
            return False
    return True


class TerrainExamples(unittest.TestCase):
    def test_short_leg_limits_height(self):
        _, high = height_interval(0, 0, .3, .1, .6)
        self.assertAlmostEqual(high, .5196152422706632)

    def test_wider_belly_makes_stance_infeasible(self):
        intervals = [height_interval(0, 0, .3, .1, .6)] * 2
        self.assertLessEqual(feasible_height(intervals, .45)[0], .5)
        with self.assertRaisesRegex(ValueError, 'BodySupportInfeasible'):
            feasible_height(intervals, .55)

    def test_replant_recovers_height(self):
        low, high = feasible_height([height_interval(0, 0, .2, .1, .6)], .55)
        self.assertLessEqual(low, .56)
        self.assertGreaterEqual(high, .56)

    def test_horizontal_unreachable_not_stretched(self):
        with self.assertRaisesRegex(ValueError, 'ChainUnreachable'):
            height_interval(0, 0, .7, .1, .6)

    def test_stair_lift_exceeds_default(self):
        lift = required_lift([(.25, .2, .05, .02)])
        self.assertAlmostEqual(lift, .3022222222222222)
        self.assertLess(.12, lift)
        self.assertGreaterEqual(.31, lift)

    def test_endpoint_contact_separate(self):
        with self.assertRaisesRegex(ValueError, 'InvalidEndpoint'):
            required_lift([(0, .1, 0, .02)])
        self.assertEqual(required_lift([(1, .2, .2, .02)]), 0)

    def test_platform_local_anchor_moves_with_platform(self):
        local = (1, 2, 0)
        translation = (3, -1, .5)
        world = tuple(a+b for a, b in zip(local, translation))
        self.assertEqual(world, (4, 1, .5))
        self.assertNotEqual(world, local)

    def test_turn_has_hip_velocity_when_root_is_stationary(self):
        # omega=(0,0,2), r=(.5,0,0) -> omega cross r=(0,1,0).
        self.assertEqual((0, 2*.5, 0), (0, 1, 0))

    def test_stop_does_not_freeze_airborne_foot(self):
        self.assertEqual(swing_state(2, .4, 2.2, True), 'Swing')
        self.assertEqual(swing_state(2, .4, 2.5, True), 'Settling')

    def test_lift_requires_remaining_support(self):
        triangle = [(0, 0), (1, 0), (0, 1)]
        self.assertTrue(triangle_contains_with_margin(triangle, (.2, .2), .05))
        self.assertFalse(triangle_contains_with_margin(triangle, (.8, .8), .05))
        self.assertFalse(triangle_contains_with_margin(triangle, (.01, .2), .05))


if __name__ == '__main__':
    unittest.main()
