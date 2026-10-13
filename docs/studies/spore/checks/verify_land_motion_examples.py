"""Independent arithmetic/state checks for module 26; not Spore algorithms."""
from dataclasses import dataclass
import math
import unittest


def corridor_width(width, length, yaw, margin):
    if min(width, length) <= 0 or margin < 0:
        raise ValueError('invalid teaching body shape')
    return width * abs(math.cos(yaw)) + length * abs(math.sin(yaw)) + 2 * margin


def stop_speed(remaining, braking, latency):
    if braking <= 0 or latency < 0 or not all(math.isfinite(v) for v in (remaining, braking, latency)):
        raise ValueError('invalid braking input')
    return max(0, math.sqrt((braking * latency) ** 2 + 2 * braking * max(0, remaining)) - braking * latency)


def closest_distance(p, relative_velocity, horizon):
    if horizon < 0:
        raise ValueError('negative prediction horizon')
    speed2 = sum(v * v for v in relative_velocity)
    t = min(horizon, max(0, -sum(a * b for a, b in zip(p, relative_velocity)) / speed2)) if speed2 > 1e-12 else 0
    return math.sqrt(sum((a + b * t) ** 2 for a, b in zip(p, relative_velocity)))


def cadence(achieved_translation, yaw_rate, hip_radius, cycle_distance):
    if cycle_distance <= 0:
        raise ValueError('nonpositive cycle distance')
    return max(abs(achieved_translation), abs(yaw_rate * hip_radius)) / cycle_distance


def phase_lerp(a, b, u):
    delta = (b - a + .5) % 1 - .5
    return (a + delta * u) % 1


@dataclass
class ArrivalExample:
    arrived: bool = False
    elapsed: float = 0

    def tick(self, distance, achieved_speed, dt, facing=True, support=True):
        if not 1.35 <= distance <= 1.9:
            self.arrived, self.elapsed = False, 0
            return 'Approach'
        if not facing or not support or achieved_speed > .1:
            self.arrived, self.elapsed = False, 0
            return 'Settle'
        if self.arrived:
            return 'Arrived'
        if not 1.6 <= distance <= 1.8:
            self.elapsed = 0
            return 'Approach'
        self.elapsed += dt
        self.arrived = self.elapsed >= .15
        return 'Arrived' if self.arrived else 'Settle'


class LandMotionChecks(unittest.TestCase):
    def test_width_change_invalidates_narrow_route_but_detour_fits(self):
        self.assertLessEqual(corridor_width(.8, 1.6, 0, .1), 1.2)
        self.assertGreater(corridor_width(1.4, 1.6, 0, .1), 1.2)
        self.assertLessEqual(corridor_width(1.4, 1.6, 0, .1), 1.8)

    def test_turning_requires_more_clearance_than_forward_motion(self):
        required = corridor_width(.8, 1.6, math.pi / 6, .1)
        self.assertAlmostEqual(required, 1.692820323)
        self.assertGreater(required, 1.2)

    def test_braking_limits_satisfy_distance_and_response_constraint(self):
        for remaining in (.3, .1, 0):
            v = stop_speed(remaining, 2, .1)
            self.assertAlmostEqual(v * .1 + v * v / 4, remaining)
        self.assertAlmostEqual(stop_speed(.3, 2, .1), .9135528726)
        self.assertAlmostEqual(stop_speed(.1, 2, .1), .4633249581)
        self.assertAlmostEqual(2 * .1 + 2 * 2 / 4, 1.2)

    def test_invalid_braking_is_diagnostic(self):
        for braking, delay in [(0, .1), (2, -.1), (float('nan'), .1)]:
            with self.assertRaises(ValueError):
                stop_speed(.1, braking, delay)

    def test_future_collision_rejected_even_with_large_current_separation(self):
        self.assertEqual(closest_distance((4, 0), (-2, 0), 2), 0)
        self.assertAlmostEqual((4 - 1.3) / 2, 1.35)
        self.assertGreater(closest_distance((4, 0), (0, 0), 2), 1.3)
        self.assertGreater(closest_distance((4, 0), (2, 0), 2), 1.3)

    def test_attack_station_band_is_collision_and_reach_intersection(self):
        low, high = .7 + .5 + .15, 1.4 + .5
        self.assertAlmostEqual(low, 1.35)
        self.assertAlmostEqual(high, 1.9)
        self.assertTrue(low <= 1.7 <= high)

    def test_arrival_needs_slow_motion_support_and_dwell(self):
        arrival = ArrivalExample()
        self.assertEqual(arrival.tick(1.7, .2, .2), 'Settle')
        self.assertFalse(arrival.arrived)
        self.assertEqual(arrival.tick(1.7, .05, .1, support=False), 'Settle')
        self.assertEqual(arrival.tick(1.7, .05, .1), 'Settle')
        self.assertEqual(arrival.tick(1.7, .05, .1), 'Arrived')

    def test_arrival_hysteresis_and_moving_target_force_reapproach(self):
        arrival = ArrivalExample()
        self.assertEqual(arrival.tick(1.7, 0, .2), 'Arrived')
        self.assertEqual(arrival.tick(1.85, 0, .1), 'Arrived')
        self.assertEqual(arrival.tick(1.95, 0, .1), 'Approach')
        self.assertFalse(arrival.arrived)

    def test_achieved_speed_drives_cadence_and_wall_stop(self):
        self.assertAlmostEqual(cadence(1.2, 0, .4, .6), 2)
        self.assertAlmostEqual(cadence(.6, 0, .4, .6), 1)
        self.assertAlmostEqual(cadence(0, 0, .4, .6), 0)
        stance_time = .65 / 2
        self.assertAlmostEqual(1.2 * stance_time, .39)

    def test_turn_in_place_and_wider_hips_still_need_foot_motion(self):
        self.assertAlmostEqual(cadence(0, 1, .4, .6), 2 / 3)
        self.assertAlmostEqual(cadence(0, 1, .7, .6), 7 / 6)

    def test_phase_wrap_and_settling_do_not_freeze_airborne_foot(self):
        self.assertAlmostEqual(phase_lerp(.95, .05, .5), 0)
        self.assertAlmostEqual(phase_lerp(.95, .05, 1), .05)
        # A settling progress clock is independent of stopped locomotion cadence.
        progress, remaining_duration = .3, .2
        progress = min(1, progress + .1 / remaining_duration)
        self.assertAlmostEqual(progress, .8)
        progress = min(1, progress + .1 / remaining_duration)
        self.assertEqual(progress, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
