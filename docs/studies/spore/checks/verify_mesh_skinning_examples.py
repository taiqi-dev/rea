"""Independent 2D skinning/field contract examples, not the Spore implementation.

No renderer, complete surface extractor, collision solver or production rig is tested.
"""
import math
import unittest


IDENTITY = (1., 0., 0., 1., 0., 0.)


def transform(m, p):
    a, b, c, d, x, y = m
    return (a*p[0]+b*p[1]+x, c*p[0]+d*p[1]+y)


def multiply(a, b):
    aa, ab, ac, ad, ax, ay = a
    ba, bb, bc, bd, bx, by = b
    return (aa*ba+ab*bc, aa*bb+ab*bd, ac*ba+ad*bc,
            ac*bb+ad*bd, aa*bx+ab*by+ax, ac*bx+ad*by+ay)


def inverse(m):
    a, b, c, d, x, y = m
    det = a*d-b*c
    if not all(math.isfinite(v) for v in m) or abs(det) < 1e-10:
        raise ValueError('InvalidBindMatrix')
    return (d/det, -b/det, -c/det, a/det,
            (b*y-d*x)/det, (c*x-a*y)/det)


def normalize(raw, palette, limit=4):
    if limit < 1:
        raise ValueError('InvalidInfluenceLimit')
    if any(j not in palette for j in raw):
        raise ValueError('UnknownBone')
    if any(not math.isfinite(w) or w < 0 for w in raw.values()):
        raise ValueError('InvalidWeight')
    ordered = sorted(((j, w) for j, w in raw.items() if w > 0),
                     key=lambda item: (-item[1], item[0]))
    total = sum(w for _, w in ordered)
    if not math.isfinite(total) or total <= 0:
        raise ValueError('UnboundVertex')
    kept = ordered[:limit]
    kept_total = sum(w for _, w in kept)
    return {j: w/kept_total for j, w in kept}, (total-kept_total)/total


def skin(p, weights, bind, pose):
    if not weights or abs(sum(weights.values())-1) > 1e-9:
        raise ValueError('NonNormalizedWeights')
    result = [0., 0.]
    for j, w in weights.items():
        if j not in bind or j not in pose:
            raise ValueError('MissingBoneTransform')
        if not math.isfinite(w) or w < 0:
            raise ValueError('InvalidWeight')
        q = transform(multiply(pose[j], inverse(bind[j])), p)
        for i in (0, 1):
            result[i] += w*q[i]
    return tuple(result)


def kernel(p, center, radius, strength=1):
    # Our compact cubic kernel; not the developer's fourth-order polynomial.
    if radius <= 0 or strength <= 0:
        raise ValueError('InvalidPrimitive')
    q = sum((a-b)**2 for a, b in zip(p, center))/(radius*radius)
    return strength*max(0., 1-q)**3


def provenance_weights(contributors, palette, allowed):
    raw = {}
    for field, owners in contributors:
        if not math.isfinite(field) or field < 0:
            raise ValueError('InvalidFieldContribution')
        if abs(sum(owners.values())-1) > 1e-9:
            raise ValueError('InvalidPrimitiveOwnership')
        for j, share in owners.items():
            if not math.isfinite(share) or share < 0:
                raise ValueError('InvalidPrimitiveOwnership')
            if field > 0 and share > 0 and j not in allowed:
                raise ValueError('UnauthorizedSkinJoin')
            raw[j] = raw.get(j, 0)+field*share
    return normalize(raw, palette)[0]


def compile_bundle(mesh_rev, bind_rev, weights_rev, palette_rev, current_rev):
    if len({mesh_rev, bind_rev, weights_rev, palette_rev, current_rev}) != 1:
        raise ValueError('IncoherentOrSupersededBake')
    return current_rev


class MeshSkinningExamples(unittest.TestCase):
    def assertPoint(self, actual, expected):
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b)

    def test_bind_pose_identity_with_rotated_translated_bones(self):
        bind = {'trunk': (0,-1,1,0,2,3), 'arm': (2,0,0,1,4,1)}
        self.assertPoint(skin((1,.2), {'trunk':.4,'arm':.6}, bind, bind), (1,.2))

    def test_singular_bind_is_diagnostic(self):
        with self.assertRaisesRegex(ValueError, 'InvalidBindMatrix'):
            inverse((0,0,0,1,0,0))

    def test_negative_weight_rejected(self):
        with self.assertRaisesRegex(ValueError, 'InvalidWeight'):
            normalize({'arm':-.1}, ['arm'])

    def test_nan_weight_rejected(self):
        with self.assertRaisesRegex(ValueError, 'InvalidWeight'):
            normalize({'arm':float('nan')}, ['arm'])

    def test_zero_weight_does_not_silently_bind_to_root(self):
        with self.assertRaisesRegex(ValueError, 'UnboundVertex'):
            normalize({'arm':0}, ['arm'])

    def test_influence_cap_has_explicit_discarded_mass(self):
        w, dropped = normalize({'a':4,'b':3,'c':2,'d':1}, ['a','b','c','d'], 2)
        self.assertAlmostEqual(dropped,.3)
        self.assertAlmostEqual(w['a'],4/7)
        self.assertAlmostEqual(sum(w.values()),1)

    def test_unknown_bone_is_diagnostic(self):
        with self.assertRaisesRegex(ValueError, 'UnknownBone'):
            normalize({'old_hand':1}, ['new_hand'])

    def test_shared_weights_keep_uv_duplicates_coincident(self):
        bind = {'base':IDENTITY,'distal':IDENTITY}
        pose = {'base':IDENTITY,'distal':(0,-1,1,0,1,-1)}
        a = skin((1,.2), {'base':.5,'distal':.5}, bind, pose)
        b = skin((1,.2), {'base':.5,'distal':.5}, bind, pose)
        self.assertPoint(a, (.9,.1))
        self.assertPoint(a,b)

    def test_different_weights_open_same_bind_position(self):
        bind = {'base':IDENTITY,'distal':IDENTITY}
        pose = {'base':IDENTITY,'distal':(0,-1,1,0,1,-1)}
        a=skin((1,.2),{'base':.8,'distal':.2},bind,pose)
        b=skin((1,.2),{'base':.2,'distal':.8},bind,pose)
        self.assertPoint(a,(.96,.16)); self.assertPoint(b,(.84,.04))
        self.assertAlmostEqual(math.dist(a,b), .12*math.sqrt(2))

    def test_widen_rebind_does_not_apply_width_twice(self):
        new_bind={'shoulder':(1,0,0,1,.7,0)}
        self.assertPoint(skin((.7,.2),{'shoulder':1},new_bind,new_bind),(.7,.2))

    def test_old_bind_with_new_pose_would_double_move_mount(self):
        old_bind={'shoulder':(1,0,0,1,.4,0)}
        new_pose={'shoulder':(1,0,0,1,.7,0)}
        self.assertPoint(skin((.7,.2),{'shoulder':1},old_bind,new_pose),(1.,.2))

    def test_field_provenance_blends_joint_owners(self):
        w=provenance_weights([(2,{'spine':1}),(1,{'upper':.75,'lower':.25})],
                             ['spine','upper','lower'], {'spine','upper','lower'})
        self.assertAlmostEqual(w['spine'],2/3)
        self.assertAlmostEqual(w['lower'],1/12)

    def test_adjacent_unconnected_limb_is_not_allowed_to_bind(self):
        with self.assertRaisesRegex(ValueError,'UnauthorizedSkinJoin'):
            provenance_weights([(1,{'other_leg':1})],['own_leg','other_leg'],{'own_leg'})

    def test_compact_kernel_has_no_outside_contribution(self):
        self.assertEqual(kernel((1,0),(0,0),1),0)
        self.assertEqual(kernel((2,0),(0,0),1),0)

    def test_same_radius_does_not_guarantee_connected_surface(self):
        level=.25
        near=kernel((.4,0),(0,0),1)+kernel((.4,0),(.8,0),1)
        far=kernel((.95,0),(0,0),1)+kernel((.95,0),(1.9,0),1)
        self.assertGreater(near,level);self.assertLess(far,level)

    def test_uv_duplicates_must_share_trimming_result(self):
        w, _=normalize({'a':1,'b':1,'c':1},['a','b','c'],2)
        other, _=normalize({'c':1,'b':1,'a':1},['c','b','a'],2)
        self.assertEqual(w,other)

    def test_bone_palette_uses_identity_not_old_slot(self):
        old=['spine','left','right'];new=['right','spine','left']
        stable={'right':.75,'spine':.25}
        packed=[(new.index(j),w) for j,w in stable.items()]
        decoded={new[i]:w for i,w in packed}
        self.assertEqual(decoded,stable)
        self.assertNotEqual({new[old.index(j)]:w for j,w in stable.items()},stable)

    def test_bundle_rejects_mixed_mesh_and_bind_revisions(self):
        with self.assertRaisesRegex(ValueError,'IncoherentOrSupersededBake'):
            compile_bundle(2,1,2,2,2)

    def test_complete_but_stale_bundle_rejected(self):
        with self.assertRaisesRegex(ValueError,'IncoherentOrSupersededBake'):
            compile_bundle(1,1,1,1,2)

    def test_coherent_current_bundle_accepted(self):
        self.assertEqual(compile_bundle(2,2,2,2,2),2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
