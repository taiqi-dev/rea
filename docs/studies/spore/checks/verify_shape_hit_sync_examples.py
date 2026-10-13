"""Independent collision/revision examples, not original-game validation."""
from dataclasses import dataclass, replace
import math
import unittest


@dataclass(frozen=True)
class Body:
    generation: int
    shape_revision: int
    part_ids: tuple
    fist_radius: float
    appearance_revision: int = 1


def stamp(body):
    return body.generation, body.shape_revision


def interval_overlap(a, b):
    return max(a[0], b[0]) <= min(a[1], b[1])


def touch(a, radius_a, b, radius_b):
    return abs(a-b) <= radius_a+radius_b


def sphere_sweep_1d(a, b, c, radius):
    if abs(a-c) <= radius:
        return 0.0
    delta = b-a
    if abs(delta) < 1e-12:
        return None
    roots = sorted(((c-radius-a)/delta, (c+radius-a)/delta))
    return next((t for t in roots if 0 <= t <= 1), None)


class Actor:
    def __init__(self, body):
        self.body = body
        self.query_stamp = stamp(body)
        self.events = set()

    def commit(self, candidate, prepare):
        query = prepare(candidate)  # May fail; neither published value changed.
        if query != stamp(candidate):
            raise ValueError('QueryStampMismatch')
        self.body, self.query_stamp = candidate, query

    def physical_token_valid(self, token_stamp, part_id):
        return token_stamp == stamp(self.body) and part_id in self.body.part_ids

    def hit_once(self, action, ordinal, target):
        key = action, ordinal, target
        if key in self.events:
            return False
        self.events.add(key)
        return True


class ShapeHitExamples(unittest.TestCase):
    def setUp(self):
        self.old = Body(1, 1, ('fist', 'foot'), .08)

    def test_widen_changes_narrowphase_result(self):
        self.assertFalse(touch(1.2, .08, 1.48, .15))
        self.assertTrue(touch(1.2, .16, 1.48, .15))

    def test_stale_broadphase_would_hide_new_hit(self):
        target = (1.48-.15, 1.48+.15)
        self.assertFalse(interval_overlap((1.12, 1.28), target))
        self.assertTrue(interval_overlap((1.04, 1.36), target))

    def test_registration_failure_preserves_complete_old_body(self):
        actor = Actor(self.old)
        def denied(candidate):
            raise ValueError('RegistrationDenied')
        with self.assertRaisesRegex(ValueError, 'RegistrationDenied'):
            actor.commit(replace(self.old, shape_revision=2, fist_radius=.16), denied)
        self.assertEqual(actor.body, self.old)
        self.assertEqual(actor.query_stamp, stamp(self.old))

    def test_commit_requires_matching_query_revision(self):
        actor = Actor(self.old)
        new = replace(self.old, shape_revision=2)
        with self.assertRaisesRegex(ValueError, 'QueryStampMismatch'):
            actor.commit(new, lambda _: stamp(self.old))
        self.assertEqual(actor.body, self.old)
        actor.commit(new, stamp)
        self.assertEqual(stamp(actor.body), actor.query_stamp)

    def test_detached_fist_invalidates_action(self):
        actor = Actor(replace(self.old, shape_revision=2, part_ids=('foot',)))
        self.assertFalse(actor.physical_token_valid(stamp(self.old), 'fist'))

    def test_same_recipe_revision_on_new_body_is_not_same_body(self):
        actor = Actor(replace(self.old, generation=2))
        self.assertFalse(actor.physical_token_valid(stamp(self.old), 'fist'))

    def test_appearance_does_not_invalidate_physical_token(self):
        actor = Actor(replace(self.old, appearance_revision=2))
        self.assertTrue(actor.physical_token_valid(stamp(self.old), 'fist'))

    def test_sweep_catches_hit_between_nonoverlapping_endpoints(self):
        self.assertFalse(touch(0, .1, 1, .1))
        self.assertFalse(touch(2, .1, 1, .1))
        self.assertAlmostEqual(sphere_sweep_1d(0, 2, 1, .2), .4)

    def test_sweep_handles_zero_motion_and_initial_overlap(self):
        self.assertIsNone(sphere_sweep_1d(0, 0, 1, .2))
        self.assertEqual(sphere_sweep_1d(1, 1, 1, .2), 0)

    def test_event_dedup_is_per_target_and_effect(self):
        actor = Actor(self.old)
        self.assertTrue(actor.hit_once('sweep', 0, 'a'))
        self.assertFalse(actor.hit_once('sweep', 0, 'a'))
        self.assertTrue(actor.hit_once('sweep', 0, 'b'))
        self.assertTrue(actor.hit_once('sweep', 1, 'a'))

    def test_reach_reassessment_after_length_edit(self):
        target_surface_distance = 1.05
        self.assertFalse(target_surface_distance <= .8)
        self.assertTrue(target_surface_distance <= 1.2)

    def test_render_lod_does_not_change_authoritative_hit(self):
        simulation_center = 1.2
        hit = touch(simulation_center, .16, 1.48, .15)
        for rendered_center in (1.1, 1.2, 1.3):
            # Rendering is not an input to this simulation query.
            self.assertEqual(touch(simulation_center, .16, 1.48, .15), hit)


if __name__ == '__main__':
    unittest.main()
