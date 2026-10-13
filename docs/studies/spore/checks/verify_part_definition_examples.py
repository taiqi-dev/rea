"""Independent 2-D part-contract examples; no Spore execution or asset decoding."""
import math
import unittest


class ContractError(ValueError):
    pass


def curve(knots, q):
    if not math.isfinite(q) or not 0 <= q <= 1:
        raise ContractError('ParameterOutOfRange')
    if len(knots) < 2 or knots[0][0] != 0 or knots[-1][0] != 1:
        raise ContractError('CurveDomainMissing')
    if any(not math.isfinite(v) for knot in knots for v in knot):
        raise ContractError('NonFiniteCurve')
    if any(a[0] >= b[0] for a, b in zip(knots, knots[1:])):
        raise ContractError('CurveOrderInvalid')
    for a, b in zip(knots, knots[1:]):
        if q <= b[0]:
            return a[1] + (b[1] - a[1]) * (q - a[0]) / (b[0] - a[0])
    raise ContractError('CurveDomainMissing')


def drag_parameter(a, b, origin, direction):
    if any(len(v) != 3 for v in (a, b, origin, direction)) or any(
            not math.isfinite(x) for v in (a, b, origin, direction) for x in v):
        raise ContractError('InvalidDragVector')
    dot = lambda x, y: sum(u * v for u, v in zip(x, y))
    sub = lambda x, y: tuple(u - v for u, v in zip(x, y))
    segment = sub(b, a)
    length = math.sqrt(dot(segment, segment))
    ray_length = math.sqrt(dot(direction, direction))
    if length <= 1e-8 or ray_length <= 1e-8:
        raise ContractError('DegenerateDragFrame')
    e = tuple(v / length for v in segment)
    r = tuple(v / ray_length for v in direction)
    w = sub(origin, a)
    c = dot(e, r)
    denominator = 1 - c * c
    if denominator < 1e-6:
        raise ContractError('DragRayNearlyParallel')
    s = (dot(e, w) - c * dot(r, w)) / denominator
    t = c * s - dot(r, w)
    if t < 0:  # Closest point of the forward ray is its origin.
        s = dot(e, w)
    return max(0, min(1, s / length))


LENGTH = ((0, .08), (.5, .10), (1, .16))
OPEN = ((0, 0), (.5, 12), (1, 32))


def compile_jaw(q, revision):
    length = curve(LENGTH, q)
    # Edited landmarks, an authored template, and a separate attachment frame.
    return {'revision': revision, 'length': length,
            'hinge': (.15 * length, 0), 'tip': (length, 0),
            'connector': (.01, 0), 'motion_tags': {'mouth'},
            'contributions': {'bite': 2}, 'semantic_outputs': {'Open': 'jaw'}}


def pose_tip(reference, open_value, request_revision):
    if request_revision != reference['revision']:
        raise ContractError('StalePartBinding')
    angle = math.radians(curve(OPEN, open_value))
    hinge, tip = reference['hinge'], reference['tip']
    x, y = tip[0] - hinge[0], tip[1] - hinge[1]
    return (hinge[0] + x * math.cos(angle) - y * math.sin(angle),
            hinge[1] + x * math.sin(angle) + y * math.cos(angle))


def mount_point(point, connector, host_socket=(.4, .6), yaw=20):
    angle = math.radians(yaw)
    x, y = point[0] - connector[0], point[1] - connector[1]
    return (host_socket[0] + x * math.cos(angle) - y * math.sin(angle),
            host_socket[1] + x * math.sin(angle) + y * math.cos(angle))


def eligible(part, connected, healthy, ability, semantic):
    if not connected:
        return 'DetachedPart'
    if not healthy:
        return 'DisabledPart'
    if part['contributions'].get(ability, 0) <= 0:
        return 'CapabilityMissing'
    if semantic not in part['semantic_outputs']:
        return 'SemanticMappingMissing'
    return 'Eligible'


def validate_parent_graph(parents):
    for bone in parents:
        seen, node = set(), bone
        while node is not None:
            if node not in parents:
                raise ContractError('ParentBoneMissing')
            if node in seen:
                raise ContractError('BoneCycle')
            seen.add(node)
            node = parents[node]


class Examples(unittest.TestCase):
    def test_drag_complete_example(self):
        q = drag_parameter((0, .04, 0), (.08, .04, 0),
                           (.06, .04, 1), (0, 0, -1))
        self.assertAlmostEqual(q, .75)
        self.assertAlmostEqual(compile_jaw(q, 7)['length'], .13)

    def test_drag_clamps_interaction(self):
        self.assertEqual(drag_parameter((0, 0, 0), (1, 0, 0),
                                        (2, 0, 1), (0, 0, -1)), 1)

    def test_parallel_ray_is_diagnostic(self):
        with self.assertRaisesRegex(ContractError, 'NearlyParallel'):
            drag_parameter((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 0, 0))

    def test_ray_behind_origin(self):
        self.assertAlmostEqual(drag_parameter((0, 0, 0), (1, 0, 0),
                                              (.25, 0, -1), (0, 0, -1)), .25)

    def test_degenerate_handle(self):
        with self.assertRaisesRegex(ContractError, 'Degenerate'):
            drag_parameter((0, 0, 0), (0, 0, 0), (0, 0, 1), (0, 0, -1))

    def test_nonfinite_drag_is_diagnostic(self):
        with self.assertRaisesRegex(ContractError, 'InvalidDragVector'):
            drag_parameter((0, 0, 0), (1, 0, 0), (math.nan, 0, 1), (0, 0, -1))

    def test_curve_default_is_authored(self):
        self.assertAlmostEqual(curve(LENGTH, .5), .10)
        self.assertAlmostEqual(curve(OPEN, .75), 22)
        self.assertNotEqual(curve(OPEN, .75), .75 * 32)

    def test_invalid_curve(self):
        with self.assertRaisesRegex(ContractError, 'CurveOrderInvalid'):
            curve(((0, 1), (.5, 2), (.5, 3), (1, 4)), .5)

    def test_nonfinite_parameter(self):
        with self.assertRaisesRegex(ContractError, 'OutOfRange'):
            curve(LENGTH, math.nan)

    def test_dynamic_motion_preserves_shape(self):
        ref = compile_jaw(.75, 7)
        result = pose_tip(ref, .75, 7)
        self.assertAlmostEqual(math.dist(ref['hinge'], result), .1105)
        self.assertEqual(ref['tip'], (.13, 0))

    def test_neutral_returns_edited_reference(self):
        ref = compile_jaw(.75, 7)
        self.assertEqual(pose_tip(ref, 0, 7), ref['tip'])

    def test_mount_aligns_connector_not_mesh_origin(self):
        ref = compile_jaw(.75, 7)
        self.assertEqual(mount_point(ref['connector'], ref['connector']), (.4, .6))
        self.assertNotEqual(mount_point(ref['connector'], (0, 0)), (.4, .6))

    def test_same_asset_distinct_part_targets(self):
        left, right = compile_jaw(.75, 7), compile_jaw(.75, 7)
        before = right.copy()
        self.assertNotEqual(pose_tip(left, .75, 7), pose_tip(right, 0, 7))
        self.assertEqual(right, before)

    def test_motion_tag_not_skill_contribution(self):
        part = compile_jaw(.75, 7)
        part['contributions'] = {}
        self.assertIn('mouth', part['motion_tags'])
        self.assertEqual(eligible(part, True, True, 'bite', 'Open'), 'CapabilityMissing')

    def test_contribution_not_motion_implementation(self):
        part = compile_jaw(.75, 7)
        part['semantic_outputs'] = {}
        self.assertEqual(eligible(part, True, True, 'bite', 'Open'), 'SemanticMappingMissing')

    def test_detach_or_damage_removes_executor(self):
        part = compile_jaw(.75, 7)
        self.assertEqual(eligible(part, False, True, 'bite', 'Open'), 'DetachedPart')
        self.assertEqual(eligible(part, True, False, 'bite', 'Open'), 'DisabledPart')

    def test_shape_revision_rebind(self):
        ref = compile_jaw(.75, 8)
        with self.assertRaisesRegex(ContractError, 'StalePartBinding'):
            pose_tip(ref, .75, 7)

    def test_authoring_hierarchy_failures(self):
        validate_parent_graph({'root': None, 'jaw': 'root'})
        with self.assertRaisesRegex(ContractError, 'BoneCycle'):
            validate_parent_graph({'root': 'jaw', 'jaw': 'root'})
        with self.assertRaisesRegex(ContractError, 'ParentBoneMissing'):
            validate_parent_graph({'jaw': 'absent'})

    def test_full_numeric_chain(self):
        ref = compile_jaw(.75, 7)
        local = pose_tip(ref, .75, 7)
        world = mount_point(local, ref['connector'])
        self.assertAlmostEqual(local[0], .0195 + .1105 * math.cos(math.radians(22)))
        self.assertAlmostEqual(local[1], .1105 * math.sin(math.radians(22)))
        self.assertAlmostEqual(world[0], .4 + .0095 * math.cos(math.radians(20))
                               + .1105 * math.cos(math.radians(42)))
        self.assertAlmostEqual(world[1], .6 + .0095 * math.sin(math.radians(20))
                               + .1105 * math.sin(math.radians(42)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
