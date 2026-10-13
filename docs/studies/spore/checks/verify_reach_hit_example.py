"""Check only the independent example in module 25; not Spore's implementation."""
from dataclasses import dataclass
import math
import unittest


def sphere_distance(anchor, center, radius):
    if radius < 0 or not all(math.isfinite(v) for v in (*anchor, *center, radius)):
        raise ValueError('invalid example geometry')
    return math.dist(anchor, center), radius


def shell_intersects(anchor, center, radius, lengths):
    if len(lengths) != 2 or any(not math.isfinite(v) or v <= 0 for v in lengths):
        raise ValueError('example requires two positive finite segments')
    distance, radius = sphere_distance(anchor, center, radius)
    return max(0, distance - radius) <= sum(lengths) and distance + radius >= abs(lengths[0] - lengths[1])


@dataclass
class EffectExample:
    body: str = 'body-A'
    generation: int = 1
    bound_part: str = 'right-hand'
    functional: bool = True
    resolved: bool = False
    damage_commits: int = 0

    def event(self, body, generation, part, in_reach, ordinal=0):
        if body != self.body or generation != self.generation:
            return 'StaleController'
        if ordinal != 0:
            return 'UnexpectedEffectOrdinal'
        if not self.functional:
            return 'BodyChanged'
        if part != self.bound_part:
            return 'UnboundPresentationPart'
        if self.resolved:
            return 'DuplicateEffect'
        self.resolved = True
        self.damage_commits += int(in_reach)
        return 'Hit' if in_reach else 'Miss'


class ExampleChecks(unittest.TestCase):
    def test_long_hand_reaches_short_hand_requires_approach(self):
        self.assertTrue(shell_intersects((0, .4, 0), (4, 0, 0), .5, (2, 1.6)))
        self.assertFalse(shell_intersects((0, -.4, 0), (4, 0, 0), .5, (1.2, 1)))
        distance, radius = sphere_distance((0, -.4, 0), (4, 0, 0), .5)
        approach_time = (distance - radius - 2.2) / 2
        self.assertAlmostEqual(approach_time, .6599751242)
        self.assertAlmostEqual(8 - 4 * (.4 + approach_time), 3.7600995031)

    def test_retreat_causes_miss_and_changes_strategy_cost(self):
        self.assertFalse(shell_intersects((0, .4, 0), (4.8, 0, 0), .5, (2, 1.6)))
        distance, radius = sphere_distance((0, -.4, 0), (4.8, 0, 0), .5)
        approach_time = (distance - radius - 2.2) / 2
        physical_score = 8 - 4 * (.4 + approach_time) - 4
        spell_score = 5 - 4 * .4 - 3
        self.assertAlmostEqual(approach_time, 1.0583189158)
        self.assertGreater(spell_score, physical_score)

    def test_close_target_must_intersect_inner_as_well_as_outer_bound(self):
        self.assertFalse(shell_intersects((0, 0, 0), (.2, 0, 0), .1, (3, 1)))
        # Nearest surface is inside the inner bound, but another contact is reachable.
        self.assertTrue(shell_intersects((0, 0, 0), (2, 0, 0), 1, (3, 1)))

    def test_invalid_geometry_retains_diagnostic(self):
        for radius, lengths in [(-1, (2, 1)), (.5, (math.nan, 1)), (.5, (0, 1))]:
            with self.assertRaises(ValueError):
                shell_intersects((0, 0, 0), (4, 0, 0), radius, lengths)

    def test_multi_part_presentation_does_not_add_damage(self):
        action = EffectExample()
        self.assertEqual(action.event('body-A', 1, 'left-hand', True), 'UnboundPresentationPart')
        self.assertEqual(action.event('body-A', 1, 'right-hand', True), 'Hit')
        self.assertEqual(action.event('body-A', 1, 'right-hand', True), 'DuplicateEffect')
        self.assertEqual(action.damage_commits, 1)

    def test_miss_resolves_ordinal_without_later_retry_damage(self):
        action = EffectExample()
        self.assertEqual(action.event('body-A', 1, 'right-hand', False), 'Miss')
        self.assertEqual(action.event('body-A', 1, 'right-hand', True), 'DuplicateEffect')
        self.assertEqual(action.damage_commits, 0)

    def test_dismemberment_and_body_change_reject_old_bound_events(self):
        action = EffectExample(functional=False)
        self.assertEqual(action.event('body-A', 1, 'right-hand', True), 'BodyChanged')
        action = EffectExample(body='body-B', generation=2)
        self.assertEqual(action.event('body-A', 1, 'right-hand', True), 'StaleController')
        self.assertEqual(action.damage_commits, 0)

    def test_undeclared_ordinal_is_rejected_not_counted_as_new_hit(self):
        action = EffectExample()
        self.assertEqual(action.event('body-A', 1, 'right-hand', True, 1), 'UnexpectedEffectOrdinal')
        self.assertFalse(action.resolved)


if __name__ == '__main__':
    unittest.main(verbosity=2)
