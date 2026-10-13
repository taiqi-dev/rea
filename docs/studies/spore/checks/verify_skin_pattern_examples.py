"""Independent skin-coordinate, density, seam and rebuild examples.

No original Spore renderer, paint script, UV packer or mesh regeneration is run.
"""
from dataclasses import dataclass, replace
import hashlib
import heapq
import json
import math
import unittest


def stripe_phase(u, length, mode, count=4, spacing=.1, origin=0.):
    if not all(math.isfinite(x) for x in (u, length, spacing, origin)) or length <= 0 or spacing <= 0:
        raise ValueError('InvalidPatternMetric')
    if mode == 'relative':
        if type(count) is not int or count <= 0:
            raise ValueError('InvalidPatternCount')
        return count*u+origin
    if mode == 'physical':
        return u*length/spacing+origin
    raise ValueError('UnknownDensityPolicy')


def stripe_mask(phase, width=.2):
    if not math.isfinite(phase) or not 0 < width <= 1:
        raise ValueError('InvalidStripe')
    distance = abs((phase+.5) % 1-.5)
    return distance < width/2


def closed_angular_count(radius, desired_spacing):
    if not all(math.isfinite(x) and x > 0 for x in (radius, desired_spacing)):
        raise ValueError('InvalidPatternMetric')
    # Explicit nearest positive integer; not language-specific banker's rounding.
    return max(1, math.floor(2*math.pi*radius/desired_spacing+.5))


def spot_distance(u, theta, center_u, center_theta, length, radius, mode):
    angular = (theta-center_theta+math.pi) % (2*math.pi)-math.pi
    if mode == 'relative':
        return math.hypot((u-center_u)/.025, angular/.2)
    if mode == 'physical':
        return math.hypot(length*(u-center_u)/.01, radius*angular/.01)
    raise ValueError('UnknownDensityPolicy')


def spot_target_count(area, density):
    if not all(math.isfinite(v) and v >= 0 for v in (area, density)):
        raise ValueError('InvalidSpotDensity')
    return math.floor(area*density+.5)


def phase_blend(phases, weights):
    if len(phases) != len(weights) or not phases or any(w < 0 or not math.isfinite(w) for w in weights):
        raise ValueError('InvalidPhaseWeights')
    if any(not math.isfinite(p) for p in phases) or sum(weights) <= 0:
        raise ValueError('InvalidPhaseWeights')
    x = sum(w*math.cos(2*math.pi*p) for p, w in zip(phases, weights))/sum(weights)
    y = sum(w*math.sin(2*math.pi*p) for p, w in zip(phases, weights))/sum(weights)
    if math.hypot(x, y) < 1e-8:
        raise ValueError('JointPhaseConflict')
    return (math.atan2(y, x)/(2*math.pi)) % 1


def stable_value(seed, region, cell):
    payload = json.dumps([seed, region, cell], separators=(',', ':')).encode('utf-8')
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], 'big')/2**64


@dataclass(frozen=True)
class Anchor:
    part: str
    u: float
    theta: float


def remap_cylinder(anchor, part, length, radius):
    if anchor.part != part:
        raise ValueError('AnchorPartMismatch')
    if not 0 <= anchor.u <= 1 or not all(math.isfinite(v) for v in (anchor.u, anchor.theta, length, radius)) or min(length, radius) <= 0:
        raise ValueError('InvalidAnchorOrSurface')
    return (radius*math.cos(anchor.theta), radius*math.sin(anchor.theta), length*anchor.u)


def graph_distance(edges, start, goal, allowed):
    if start not in allowed or goal not in allowed:
        raise ValueError('DisallowedPaintRegion')
    queue = [(0., start)]
    best = {start: 0.}
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != best[node]:
            continue
        if node == goal:
            return distance
        for other, weight in edges.get(node, ()):
            if weight < 0 or not math.isfinite(weight):
                raise ValueError('InvalidSurfaceEdge')
            if other not in allowed:
                continue
            candidate = distance+weight
            if candidate < best.get(other, math.inf):
                best[other] = candidate
                heapq.heappush(queue, (candidate, other))
    raise ValueError('PaintSurfaceDisconnected')


def barycentric_surface(vertices, weights):
    if len(vertices) != 3 or len(weights) != 3 or abs(sum(weights)-1) > 1e-9 or min(weights) < 0:
        raise ValueError('InvalidBarycentric')
    return tuple(sum(w*p[i] for w, p in zip(weights, vertices)) for i in range(3))


def dilate_owned_chart(valid, chart_domain):
    # Scalar 1D toy; production uses per-chart 2D and geometric seam correspondences.
    if not valid or not set(valid) <= set(chart_domain):
        raise ValueError('InvalidChartDomain')
    result = {}
    for x in chart_domain:
        source = min(valid, key=lambda s: (abs(x-s), s))
        result[x] = valid[source]
    return result


def encode_normal(world_normal, frame):
    return tuple(sum(a*b for a, b in zip(world_normal, axis)) for axis in frame)


def decode_normal(local_normal, frame):
    return tuple(sum(local_normal[k]*frame[k][i] for k in range(3)) for i in range(3))


@dataclass(frozen=True)
class BakeKey:
    shape: int
    paint: int
    atlas_digest: str
    algorithm: str = 'own-v1'
    quality: str = 'HQ'


def publish_skin(current, completed, bundle):
    if completed != current:
        return 'Superseded'
    if set(bundle) != {'mesh', 'uv', 'color', 'height', 'normal'} or any(v != current for v in bundle.values()):
        return 'MixedSkinBundle'
    return 'Published'


class SkinPatternExamples(unittest.TestCase):
    def test_limb_extension_relative_keeps_four_cycles(self):
        self.assertEqual(stripe_phase(1, .4, 'relative'), 4)
        self.assertEqual(stripe_phase(1, .8, 'relative'), 4)
        self.assertAlmostEqual(.4/4, .1)
        self.assertAlmostEqual(.8/4, .2)

    def test_limb_extension_physical_adds_cycles(self):
        self.assertEqual(stripe_phase(1, .4, 'physical'), 4)
        self.assertEqual(stripe_phase(1, .8, 'physical'), 8)
        self.assertTrue(stripe_mask(stripe_phase(.5, .8, 'physical')))

    def test_width_relative_eight_stripes_spread_apart(self):
        self.assertAlmostEqual(2*math.pi*.2/8, .15707963267948966)
        self.assertAlmostEqual(2*math.pi*.4/8, .3141592653589793)

    def test_physical_angular_count_closes_circular_seam(self):
        self.assertEqual(closed_angular_count(.2, .2), 6)
        self.assertEqual(closed_angular_count(.4, .2), 13)
        n = closed_angular_count(.4, .2)
        for theta in (.0, .1, 2.4):
            self.assertEqual(stripe_mask(n*theta/(2*math.pi)), stripe_mask(n*(theta+2*math.pi)/(2*math.pi)))

    def test_noninteger_physical_wrap_has_phase_discontinuity(self):
        phase = 2*math.pi*.2/.2
        self.assertGreater(abs(phase-round(phase)), .2)
        self.assertNotEqual(stripe_mask(0), stripe_mask(phase))

    def test_circular_phase_blend_handles_wrap(self):
        phase = phase_blend((.99, .01), (1, 1))
        self.assertLess(min(phase, 1-phase), 1e-9)
        self.assertGreater(abs(.5-phase), .49)

    def test_opposite_phases_have_explicit_conflict(self):
        with self.assertRaisesRegex(ValueError, 'JointPhaseConflict'):
            phase_blend((0, .5), (1, 1))
        with self.assertRaisesRegex(ValueError, 'InvalidPhaseWeights'):
            phase_blend((0, .1), (-1, 1))

    def test_seed_is_per_persistent_region_not_array_position(self):
        initial = {part: stable_value(42, part, 7) for part in ('torso', 'legA', 'legB')}
        changed = {part: stable_value(42, part, 7) for part in ('newArm', 'legB', 'torso', 'legA')}
        for part, value in initial.items():
            self.assertEqual(changed[part], value)
        self.assertNotEqual(changed['newArm'], changed['legA'])

    def test_relative_spot_shape_stretches_with_limb(self):
        self.assertAlmostEqual(spot_distance(.525, 0, .5, 0, .4, .05, 'relative'), 1)
        self.assertAlmostEqual(spot_distance(.525, 0, .5, 0, .8, .05, 'relative'), 1)
        self.assertAlmostEqual((.525-.5)*.4, .01)
        self.assertAlmostEqual((.525-.5)*.8, .02)

    def test_physical_spot_radius_stays_same_when_limb_extends(self):
        self.assertAlmostEqual(spot_distance(.525, 0, .5, 0, .4, .05, 'physical'), 1)
        self.assertAlmostEqual(spot_distance(.5125, 0, .5, 0, .8, .05, 'physical'), 1)
        self.assertAlmostEqual(spot_distance(.525, 0, .5, 0, .8, .05, 'physical'), 2)

    def test_spot_density_counts_are_targets_not_guaranteed_population(self):
        self.assertEqual(spot_target_count(.12, 100), 12)
        self.assertEqual(spot_target_count(.24, 100), 24)
        with self.assertRaisesRegex(ValueError, 'InvalidSpotDensity'):
            spot_target_count(math.nan, 100)

    def test_canonical_anchor_survives_width_and_length_change(self):
        a = Anchor('legA', .25, math.pi/2)
        old = remap_cylinder(a, 'legA', .4, .05)
        new = remap_cylinder(a, 'legA', .8, .1)
        self.assertAlmostEqual(old[1], .05)
        self.assertAlmostEqual(new[1], .1)
        self.assertAlmostEqual(old[2], .1)
        self.assertAlmostEqual(new[2], .2)

    def test_anchor_cannot_jump_to_nearby_new_limb(self):
        with self.assertRaisesRegex(ValueError, 'AnchorPartMismatch'):
            remap_cylinder(Anchor('legA', .5, 0), 'legB', .4, .05)

    def test_geodesic_footprint_does_not_take_spatial_shortcut(self):
        # A and B may be only .01m apart spatially; connected surface route is 4m.
        edges = {'A': [('torso', 2)], 'torso': [('B', 2)], 'B': []}
        self.assertEqual(graph_distance(edges, 'A', 'B', {'A', 'torso', 'B'}), 4)
        with self.assertRaisesRegex(ValueError, 'PaintSurfaceDisconnected'):
            graph_distance(edges, 'A', 'B', {'A', 'B'})

    def test_two_uv_charts_evaluate_the_same_surface_sample(self):
        vertices = ((0, 0, 0), (1, 0, 0), (0, 1, 0))
        p = barycentric_surface(vertices, (.2, .3, .5))
        # UV chart placements differ, but pigment comes from p, not either UV.
        charts = ((.22, .30), (.72, .80))
        colors = [stripe_mask(4*p[0]) for uv in charts]
        self.assertEqual(colors[0], colors[1])
        self.assertEqual(p, (.3, .5, 0))

    def test_seam_padding_fills_edge_but_respects_other_chart(self):
        red = dilate_owned_chart({1: 1., 2: 1.}, {0, 1, 2, 3})
        blue = dilate_owned_chart({6: 0., 7: 0.}, {5, 6, 7, 8})
        self.assertEqual(red[3], 1)
        self.assertEqual(blue[5], 0)
        self.assertNotIn(5, red)
        self.assertNotIn(3, blue)
        # Without padding, bilinear with an empty edge would darken red to .5.
        self.assertEqual((red[2]+red[3])/2, 1)

    def test_mirrored_tangent_frames_need_different_stored_normals(self):
        world = (.2, .1, math.sqrt(.95))
        frame_a = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        frame_b = ((-1, 0, 0), (0, 1, 0), (0, 0, 1))
        a, b = encode_normal(world, frame_a), encode_normal(world, frame_b)
        self.assertNotEqual(a, b)
        self.assertEqual(decode_normal(a, frame_a), decode_normal(b, frame_b))
        self.assertNotEqual(decode_normal(a, frame_b), world)

    def test_pattern_updates_do_not_modify_geometry(self):
        p = remap_cylinder(Anchor('legA', .4, .3), 'legA', .8, .1)
        for count in (4, 8, 13):
            stripe_mask(stripe_phase(.4, .8, 'relative', count=count))
            self.assertEqual(remap_cylinder(Anchor('legA', .4, .3), 'legA', .8, .1), p)

    def test_old_repaint_cannot_replace_current_shape(self):
        old = BakeKey(4, 1, 'atlasA')
        current = BakeKey(5, 1, 'atlasB')
        bundle = dict.fromkeys(('mesh', 'uv', 'color', 'height', 'normal'), old)
        self.assertEqual(publish_skin(current, old, bundle), 'Superseded')

    def test_uv_repack_without_repaint_is_rejected(self):
        current = BakeKey(5, 2, 'atlasB')
        bundle = dict.fromkeys(('mesh', 'uv', 'color', 'height', 'normal'), current)
        bundle['color'] = replace(current, atlas_digest='atlasA')
        self.assertEqual(publish_skin(current, current, bundle), 'MixedSkinBundle')

    def test_complete_current_skin_is_published(self):
        current = BakeKey(5, 2, 'atlasB')
        bundle = dict.fromkeys(('mesh', 'uv', 'color', 'height', 'normal'), current)
        self.assertEqual(publish_skin(current, current, bundle), 'Published')

    def test_missing_height_or_normal_is_not_partial_success(self):
        current = BakeKey(5, 2, 'atlasB')
        bundle = dict.fromkeys(('mesh', 'uv', 'color', 'normal'), current)
        self.assertEqual(publish_skin(current, current, bundle), 'MixedSkinBundle')

    def test_invalid_density_and_anchor_preserve_diagnostics(self):
        with self.assertRaisesRegex(ValueError, 'InvalidPatternMetric'):
            stripe_phase(.5, math.nan, 'physical')
        with self.assertRaisesRegex(ValueError, 'InvalidAnchorOrSurface'):
            remap_cylinder(Anchor('legA', 1.1, 0), 'legA', .8, .1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
