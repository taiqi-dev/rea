"""Independent part-shape and local-animation contract checks, not Spore code."""
from dataclasses import dataclass
import math
import unittest

from verify_mesh_skinning_examples import IDENTITY, multiply, inverse, transform, skin


@dataclass(frozen=True)
class PartReference:
    length: float
    width: float
    angle: float
    revision: int
    shape_mode: str = 'Baked'


def bake(length_handle, width_handle, reference_angle, revision=1):
    if any(not math.isfinite(x) for x in (length_handle,width_handle,reference_angle)):
        raise ValueError('InvalidShapeValue')
    if not 0 <= length_handle <= 1 or not 0 <= width_handle <= 1:
        raise ValueError('ShapeHandleOutOfRange')
    return PartReference(10+8*length_handle,4+2*width_handle,reference_angle,revision)


def rotation(angle):
    r=math.radians(angle);c=math.cos(r);s=math.sin(r)
    return c,-s,s,c,0.,0.


def reference_delta(source_neutral, source_sample):
    return multiply(inverse(source_neutral),source_sample)


def pose_mouth(ref, amount, expected_revision, edit_operator=False):
    if expected_revision != ref.revision:
        raise ValueError('StalePartReference')
    if ref.shape_mode == 'Baked' and edit_operator:
        raise ValueError('ShapeAlreadyBaked')
    if not math.isfinite(amount) or not 0<=amount<=1:
        raise ValueError('InvalidSemanticValue')
    return transform(multiply(rotation(ref.angle),rotation(30*amount)),(ref.length,0))


def accumulate_positive_scales(scales):
    if any(not math.isfinite(s) or s<=0 for s in scales):
        raise ValueError('InvalidShapeScale')
    return math.exp(sum(math.log(s) for s in scales))


def qaxis(axis, angle):
    n=math.sqrt(sum(x*x for x in axis));a=math.radians(angle)/2
    if n<=0:raise ValueError('DegenerateAxis')
    return (math.cos(a),)+tuple(x/n*math.sin(a) for x in axis)


def qmul(a,b):
    w,x,y,z=a;v,i,j,k=b
    return (w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,
            w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v)


def qinverse(q):
    w,x,y,z=q;n=sum(v*v for v in q)
    if n<=0:raise ValueError('InvalidQuaternion')
    return (w/n,-x/n,-y/n,-z/n)


def qrotate(q,v):
    return qmul(qmul(q,(0,)+tuple(v)),qinverse(q))[1:]


def map_delta_axes(delta, source_to_target):
    return qmul(qmul(source_to_target,delta),qinverse(source_to_target))


def adaptive_translation(source_delta, source_length, target_length):
    if source_length<=0 or target_length<=0:
        raise ValueError('DegenerateFeatureScale')
    return source_delta*target_length/source_length


def claim_outputs(claims):
    seen=set()
    for key in claims:
        if key in seen:raise ValueError('DuplicatePoseWriter')
        seen.add(key)
    return seen


class PartDeformationExamples(unittest.TestCase):
    def assertPoint(self,a,b):
        for x,y in zip(a,b):self.assertAlmostEqual(x,y)

    def test_shape_handles_bake_reference_dimensions(self):
        ref=bake(.25,.75,20)
        self.assertEqual((ref.length,ref.width),(12,5.5))

    def test_opening_keeps_baked_mouth_length(self):
        ref=bake(.25,.75,20)
        self.assertAlmostEqual(math.hypot(*pose_mouth(ref,.5,1)),12)

    def test_open_pose_keeps_reference_orientation_once(self):
        p=pose_mouth(bake(.25,.75,20),.5,1)
        self.assertAlmostEqual(math.degrees(math.atan2(p[1],p[0])),35)

    def test_neutral_returns_edited_reference_not_source_default(self):
        ref=bake(.25,.75,20)
        self.assertPoint(pose_mouth(ref,0,1),transform(rotation(20),(12,0)))

    def test_no_frame_to_frame_shape_accumulation(self):
        ref=bake(.25,.75,20)
        first=pose_mouth(ref,.5,1)
        for _ in range(100):self.assertPoint(pose_mouth(ref,.5,1),first)
        self.assertEqual(ref.length,12)

    def test_nonzero_source_neutral_is_removed(self):
        delta=reference_delta(rotation(10),rotation(25))
        self.assertPoint(transform(delta,(1,0)),transform(rotation(15),(1,0)))

    def test_rebased_delta_keeps_new_target_reference(self):
        delta=reference_delta(rotation(10),rotation(25))
        self.assertPoint(transform(multiply(rotation(20),delta),(12,0)),
                         transform(rotation(35),(12,0)))

    def test_neutral_rebased_delta_is_identity(self):
        delta=reference_delta(rotation(10),rotation(10))
        self.assertPoint(transform(delta,(3,2)),(3,2))

    def test_baked_shape_operator_cannot_run_again(self):
        with self.assertRaisesRegex(ValueError,'ShapeAlreadyBaked'):
            pose_mouth(bake(.25,.75,20),.5,1,edit_operator=True)

    def test_old_part_reference_rejected_after_edit(self):
        with self.assertRaisesRegex(ValueError,'StalePartReference'):
            pose_mouth(bake(.25,.75,20,revision=2),.5,1)

    def test_shape_scale_accumulates_by_own_log_policy(self):
        self.assertAlmostEqual(accumulate_positive_scales([1.5,1.2]),1.8)

    def test_zero_shape_scale_is_diagnostic(self):
        with self.assertRaisesRegex(ValueError,'InvalidShapeScale'):
            accumulate_positive_scales([0])

    def test_noncommuting_rotations_require_order(self):
        a=qaxis((1,0,0),90);b=qaxis((0,1,0),90)
        self.assertGreater(math.dist(qrotate(qmul(a,b),(0,0,1)),
                                    qrotate(qmul(b,a),(0,0,1))),1)

    def test_retargeted_local_axis_changes_with_target_reference(self):
        delta=qaxis((1,0,0),30);mapping=qaxis((0,0,1),90)
        target=map_delta_axes(delta,mapping)
        self.assertPoint(qrotate(target,(0,0,1)),qrotate(qaxis((0,1,0),30),(0,0,1)))

    def test_feature_scaling_changes_dynamic_offset_only(self):
        self.assertEqual(adaptive_translation(2,10,12),2.4)
        self.assertEqual(12+adaptive_translation(2,10,12),14.4)

    def test_zero_source_feature_scale_is_diagnostic(self):
        with self.assertRaisesRegex(ValueError,'DegenerateFeatureScale'):
            adaptive_translation(2,0,12)

    def test_internal_skin_at_neutral_retains_baked_vertices(self):
        bind={'jaw':rotation(20)}
        self.assertPoint(skin((12,0),{'jaw':1},bind,bind),(12,0))

    def test_factored_internal_skin_mount_applies_once(self):
        bind={'jaw':IDENTITY};pose={'jaw':rotation(15)}
        internal=skin((12,0),{'jaw':1},bind,pose)
        self.assertPoint(transform(rotation(20),internal),transform(rotation(35),(12,0)))

    def test_absolute_solver_pose_does_not_add_rest_again(self):
        absolute=rotation(35)
        final=transform(absolute,(12,0))
        wrong=transform(multiply(rotation(20),absolute),(12,0))
        self.assertGreater(math.dist(final,wrong),4)

    def test_grasp_and_arm_pose_have_distinct_outputs(self):
        self.assertEqual(len(claim_outputs(['arm.endPose','hand.grip'])),2)

    def test_two_writers_to_one_local_bone_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'DuplicatePoseWriter'):
            claim_outputs(['finger.pose','finger.pose'])

    def test_invalid_semantic_value_is_not_silent(self):
        with self.assertRaisesRegex(ValueError,'InvalidSemanticValue'):
            pose_mouth(bake(.25,.75,20),1.5,1)


if __name__=='__main__':
    unittest.main(verbosity=2)
