"""Independent mirror/branch geometry examples; never reads or runs Spore."""
from __future__ import annotations
import json
import math
from pathlib import Path
import unittest

EPS = 1e-9
ROOT = Path(__file__).resolve().parents[1]
I = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
M = ((-1., 0., 0.), (0., 1., 0.), (0., 0., 1.))

class Diagnostic(ValueError):
    pass

def finite(values):
    if not all(math.isfinite(v) for v in values):
        raise Diagnostic("NonFinite")

def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, s): return tuple(x*s for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def norm(a): return math.sqrt(dot(a, a))
def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def mv(a, v): return tuple(dot(row, v) for row in a)
def transpose(a): return tuple(zip(*a))
def mm(a, b): return tuple(tuple(dot(row, col) for col in transpose(b)) for row in a)
def det(a): return dot(a[0], cross(a[1], a[2]))
def near(a, b, tol=1e-8): return norm(sub(a, b)) <= tol
def rz(angle):
    c, s = math.cos(angle), math.sin(angle)
    return ((c, -s, 0.), (s, c, 0.), (0., 0., 1.))

def valid_rotation(r):
    finite([v for row in r for v in row])
    if abs(det(r)-1.) > 1e-8:
        raise Diagnostic("ImproperMountRotation")
    product = mm(transpose(r), r)
    if any(abs(product[i][j]-I[i][j]) > 1e-8 for i in range(3) for j in range(3)):
        raise Diagnostic("ScaleOrShearInRotation")

def quat_matrix(q):
    finite(q)
    length = norm(q)
    if length <= EPS:
        raise Diagnostic("ZeroQuaternion")
    x, y, z, w = mul(q, 1/length)
    return ((1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
            (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
            (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)))

def mirror_rotation(r): return mm(mm(M, r), M)
def mirror_quat(q): return (q[0], -q[1], -q[2], q[3])

def mounted_point(body_r, body_p, mount_r, mount_p, scale, local):
    valid_rotation(body_r); valid_rotation(mount_r)
    finite((*body_p, *mount_p, *local, scale))
    if scale <= 0:
        raise Diagnostic("NonPositiveScale")
    return add(body_p, mv(body_r, add(mount_p, mv(mount_r, mul(local, scale)))))

def world_to_body(body_r, body_p, world):
    valid_rotation(body_r); finite((*body_p, *world))
    return mv(transpose(body_r), sub(world, body_p))

def reflect_world(body_r, body_p, world):
    return add(body_p, mv(body_r, mv(M, world_to_body(body_r, body_p, world))))

def apply_once(value, parity_already_applied):
    if parity_already_applied:
        raise Diagnostic("MirrorAlreadyApplied")
    return mv(M, value)

def require_revision(expected, actual):
    if expected != actual:
        raise Diagnostic("StaleBodyOrFrame")

def semantic_mirror(value, rule, domain):
    finite((value,))
    if not domain[0] <= value <= domain[1]: raise Diagnostic("OutsideDeclaredDomain")
    if rule == "invariant": output=value
    elif rule == "signed": output=-value
    else: raise Diagnostic("UnknownMirrorSemantic")
    if not domain[0] <= output <= domain[1]: raise Diagnostic("OutsideDeclaredDomain")
    return output

def ancestors(parents, leaf):
    seen = set()
    result = []
    while leaf is not None:
        if leaf in seen: raise Diagnostic("TopologyCycle")
        if leaf not in parents: raise Diagnostic("MissingJoint")
        seen.add(leaf); result.append(leaf); leaf = parents[leaf]
    return result

def active_union(parents, leaves):
    return set(j for leaf in leaves for j in ancestors(parents, leaf))

def circle_intersections(c0, r0, c1, r1):
    finite((*c0, *c1, r0, r1))
    if min(r0, r1) <= 0: raise Diagnostic("InvalidLength")
    delta = sub(c1, c0); distance = norm(delta)
    if distance <= EPS: raise Diagnostic("CoincidentCircleCenters")
    if distance > r0+r1+EPS or distance < abs(r0-r1)-EPS: return []
    axis = mul(delta, 1/distance)
    x = (r0*r0-r1*r1+distance*distance)/(2*distance)
    height = math.sqrt(max(0., r0*r0-x*x))
    middle = add(c0, mul(axis, x))
    perpendicular = (-axis[1], axis[0])
    return [add(middle, mul(perpendicular, height)), sub(middle, mul(perpendicular, height))]

def shared_branch_candidates(root, trunk, target_c, length_c, target_d, length_d):
    return [b for b in circle_intersections(target_c, length_c, target_d, length_d)
            if abs(norm(sub(b, root))-trunk) <= 1e-8]

def pin_goals(goals):
    result = {}
    for node, value in goals:
        finite(value)
        if node in result and not near(result[node], value):
            raise Diagnostic("ConflictingGoalsOnOneJoint")
        result[node] = value
    return result

def project_length(points, a, b, length, mobility, reference):
    finite((*points[a], *points[b], length, mobility[a], mobility[b]))
    if length <= 0 or min(mobility[a], mobility[b]) < 0:
        raise Diagnostic("InvalidLengthOrMobility")
    delta = sub(points[b], points[a]); distance = norm(delta)
    error = distance-length
    if abs(error) <= EPS: return
    weight = mobility[a]+mobility[b]
    if weight == 0: raise Diagnostic("FixedConstraintConflict")
    if distance <= EPS:
        delta = reference; distance = norm(delta)
        if distance <= EPS: raise Diagnostic("DegenerateReference")
    direction = mul(delta, 1/distance)
    points[a] = add(points[a], mul(direction, error*mobility[a]/weight))
    points[b] = sub(points[b], mul(direction, error*mobility[b]/weight))

def solve_lengths(points, constraints, mobility, iterations=300):
    points = dict(points)
    for _ in range(iterations):
        for a, b, length in constraints:
            project_length(points, a, b, length, mobility, (1., 0.))
        residual = max(abs(norm(sub(points[b], points[a]))-length) for a,b,length in constraints)
        if residual < 1e-8:
            return {"status":"Converged", "points":points, "max_length_error":residual}
    return {"status":"IterationBudgetExceeded", "points":points, "max_length_error":residual}

def checked_publish(current, staged, expected_revision, actual_revision):
    require_revision(expected_revision, actual_revision)
    if any(not math.isfinite(v) for p in staged.values() for v in p):
        raise Diagnostic("NonFinite")
    return dict(staged)

def cancel_action_cohort(goals, action_token):
    return [g for g in goals if g[0] != action_token]

def merge_gradients(entries):
    result = {}
    for joint, gradient in entries:
        finite(gradient)
        result[joint] = add(result.get(joint, (0.,)*len(gradient)), gradient)
    return result

class MirrorTests(unittest.TestCase):
    def test_01_reflection_is_involution(self):
        v=(2.,3.,-4.); self.assertTrue(near(mv(M,mv(M,v)),v))
    def test_02_conjugated_rotation_stays_proper(self):
        r=mirror_rotation(rz(.7)); valid_rotation(r); self.assertAlmostEqual(det(r),1.)
    def test_03_quaternion_matches_matrix_conjugation(self):
        q=(.2,.3,.4,.5)
        a=quat_matrix(mirror_quat(q)); b=mirror_rotation(quat_matrix(q))
        self.assertTrue(all(near(x,y) for x,y in zip(a,b)))
    def test_04_negating_quaternion_is_not_mirroring(self):
        q=(0.,0.,math.sin(.3),math.cos(.3))
        self.assertTrue(all(near(x,y) for x,y in zip(quat_matrix(q),quat_matrix(mul(q,-1)))))
        self.assertFalse(near(mv(quat_matrix(q),(1.,0.,0.)),mv(quat_matrix(mirror_quat(q)),(1.,0.,0.))))
    def test_05_axial_vector_parity(self):
        a=(1.,2.,0.); b=(0.,1.,3.)
        self.assertTrue(near(cross(mv(M,a),mv(M,b)),mul(mv(M,cross(a,b)),-1)))
    def test_06_triangle_winding_and_outward_normal(self):
        a=(0.,0.,0.);b=(1.,0.,0.);c=(0.,1.,0.)
        n=cross(sub(b,a),sub(c,a))
        mirrored_n=cross(sub(mv(M,c),mv(M,a)),sub(mv(M,b),mv(M,a)))
        self.assertTrue(near(mirrored_n,mv(M,n)))
    def test_07_mount_body_world_complete_example(self):
        p=mounted_point(rz(math.pi/2),(10.,0.,0.),rz(math.pi/2),(2.,0.,1.),1.,(0.,1.,0.))
        self.assertTrue(near(p,(10.,1.,1.)))
        mp=mounted_point(rz(math.pi/2),(10.,0.,0.),mirror_rotation(rz(math.pi/2)),(-2.,0.,1.),1.,mv(M,(0.,1.,0.)))
        self.assertTrue(near(mp,(10.,-1.,1.)))
    def test_08_reflection_plane_follows_body_frame(self):
        p=(10.,1.,1.)
        self.assertTrue(near(reflect_world(rz(math.pi/2),(10.,0.,0.),p),(10.,-1.,1.)))
        self.assertFalse(near(mv(M,p),(10.,-1.,1.)))
    def test_09_external_target_round_trip(self):
        r=rz(.9);origin=(3.,-2.,1.);v=(.5,2.,-.2)
        self.assertTrue(near(world_to_body(r,origin,add(origin,mv(r,v))),v))
    def test_10_double_mirror_is_diagnosed(self):
        with self.assertRaisesRegex(Diagnostic,"MirrorAlreadyApplied"): apply_once((1.,2.,3.),True)
    def test_11_improper_mount_rejected(self):
        with self.assertRaisesRegex(Diagnostic,"ImproperMountRotation"): valid_rotation(M)
    def test_12_nonuniform_scale_not_a_rotation(self):
        with self.assertRaisesRegex(Diagnostic,"ScaleOrShearInRotation"):valid_rotation(((2.,0.,0.),(0.,.5,0.),(0.,0.,1.)))
    def test_13_nonfinite_mount_rejected(self):
        with self.assertRaisesRegex(Diagnostic,"NonFinite"):mounted_point(I,(0.,0.,0.),I,(0.,0.,0.),1.,(math.nan,0.,0.))
    def test_14_zero_quaternion_rejected(self):
        with self.assertRaisesRegex(Diagnostic,"ZeroQuaternion"):quat_matrix((0.,0.,0.,0.))
    def test_15_semantic_scalars_have_explicit_rules(self):
        self.assertEqual(semantic_mirror(.6,"invariant",(0.,1.)),.6)
        self.assertEqual(semantic_mirror(.6,"signed",(-1.,1.)),-.6)
        with self.assertRaisesRegex(Diagnostic,"UnknownMirrorSemantic"):semantic_mirror(.6,"guess",(0.,1.))
        with self.assertRaisesRegex(Diagnostic,"OutsideDeclaredDomain"):semantic_mirror(-.6,"invariant",(0.,1.))
    def test_16_mount_revision_guard(self):
        with self.assertRaisesRegex(Diagnostic,"StaleBodyOrFrame"):require_revision((7,3),(7,4))

class BranchTests(unittest.TestCase):
    def test_17_shared_joint_has_one_identity(self):
        parents={"A":None,"B":"A","C":"B","D":"B"}
        self.assertEqual(active_union(parents,["C","D"]),{"A","B","C","D"})
    def test_18_topology_cycle_rejected(self):
        with self.assertRaisesRegex(Diagnostic,"TopologyCycle"):ancestors({"B":"C","C":"B"},"C")
    def test_19_individually_reachable_but_shared_incompatible(self):
        a=(0.,0.);c=(1.5,.5);d=(1.5,-.5)
        self.assertLess(norm(c),2.);self.assertLess(norm(d),2.)
        self.assertTrue(circle_intersections(a,1.,c,1.));self.assertTrue(circle_intersections(a,1.,d,1.))
        self.assertEqual(shared_branch_candidates(a,1.,c,1.,d,1.),[])
        bs=circle_intersections(c,1.,d,1.)
        self.assertAlmostEqual(min(abs(norm(b)-1.) for b in bs),math.sqrt(.75)-.5)
        tolerance=.01
        sine_bound=((1+tolerance)**2-(1-tolerance)**2)/2
        cosine_bound=math.sqrt(1-sine_bound*sine_bound)
        self.assertLess(3.5-3*cosine_bound,(1-tolerance)**2)
        self.assertGreater(3.5+3*cosine_bound,(1+tolerance)**2)
    def test_20_priority_fallback_preserves_bone_lengths(self):
        a=(0.,0.);c=(1.5,.5);choices=circle_intersections(a,1.,c,1.)
        b=min(choices,key=lambda v:norm(sub(v,(1.,0.))))
        self.assertTrue(near(b,(.9436491673103709,-.33094750193111255)))
        self.assertAlmostEqual(norm(b),1.);self.assertAlmostEqual(norm(sub(c,b)),1.)
        neutral_d=add(b,(b[1],-b[0]))
        self.assertAlmostEqual(norm(sub(neutral_d,b)),1.)
    def test_21_compatible_two_tip_solution(self):
        c=(1.5,math.sqrt(.75));d=(1.5,-math.sqrt(.75))
        result=solve_lengths({"A":(0.,0.),"B":(1.,0.),"C":c,"D":d},[("A","B",1.),("B","C",1.),("B","D",1.)],{"A":0.,"B":1.,"C":0.,"D":0.})
        self.assertEqual(result["status"],"Converged")
    def test_22_incompatible_targets_keep_failure_residual(self):
        result=solve_lengths({"A":(0.,0.),"B":(1.,0.),"C":(1.5,.5),"D":(1.5,-.5)},[("A","B",1.),("B","C",1.),("B","D",1.)],{"A":0.,"B":1.,"C":0.,"D":0.})
        self.assertEqual(result["status"],"IterationBudgetExceeded")
        self.assertGreater(result["max_length_error"],.1)
    def test_23_fixed_constraint_conflict_diagnosed(self):
        with self.assertRaisesRegex(Diagnostic,"FixedConstraintConflict"):
            project_length({"A":(0.,0.),"B":(2.,0.)},"A","B",1.,{"A":0.,"B":0.},(1.,0.))
    def test_24_zero_length_direction_requires_reference(self):
        p={"A":(0.,0.),"B":(0.,0.)}
        with self.assertRaisesRegex(Diagnostic,"DegenerateReference"):project_length(p,"A","B",1.,{"A":0.,"B":1.},(0.,0.))
        project_length(p,"A","B",1.,{"A":0.,"B":1.},(0.,1.));self.assertTrue(near(p["B"],(0.,1.)))
    def test_25_rigid_cross_constraint_adds_independent_conflict(self):
        c=(1.5,.5);d=(1.5,-.5)
        self.assertAlmostEqual(abs(norm(sub(c,d))-2.),1.)
        self.assertEqual(shared_branch_candidates((0.,0.),1.,c,1.,d,1.),[])
    def test_26_cancel_leaf_keeps_shared_ancestor_active(self):
        p={"A":None,"B":"A","C":"B","D":"B"}
        self.assertEqual(active_union(p,["C"]),{"A","B","C"})
        self.assertNotIn("D",active_union(p,["C"]))
    def test_27_stale_pose_cannot_partially_publish(self):
        current={"B":(1.,0.)};old=dict(current)
        with self.assertRaisesRegex(Diagnostic,"StaleBodyOrFrame"):checked_publish(current,{"B":(0.,1.)},7,8)
        self.assertEqual(current,old)
    def test_28_goal_alias_conflict_is_not_last_writer_wins(self):
        with self.assertRaisesRegex(Diagnostic,"ConflictingGoalsOnOneJoint"):
            pin_goals([("B",(1.,0.)),("B",(0.,1.))])
    def test_31_required_action_cohort_cancels_together(self):
        goals=[("handoff","C"),("handoff","D"),("independent","E")]
        self.assertEqual(cancel_action_cohort(goals,"handoff"),[("independent","E")])
    def test_32_shared_endpoint_gradients_merge_before_denominator(self):
        merged=merge_gradients([("B",(1.,0.)),("B",(-1.,0.)),("C",(0.,1.))])
        self.assertEqual(merged,{"B":(0.,0.),"C":(0.,1.)})
        self.assertEqual(sum(dot(g,g) for g in merged.values()),1.)

class ReusedEvidenceTests(unittest.TestCase):
    def test_29_selected_local_tree_is_part_internal(self):
        d=json.loads((ROOT/"evidence/local-selected-rigblock-metadata.json").read_text(encoding="utf-8"))
        skeleton=next(s for s in d["metadata"]["skeletons"] if s["section_index"]==16)
        parents={str(b["index"]): None if b["parent_index_raw"]==-1 else str(b["parent_index_raw"]) for b in skeleton["bones"]}
        self.assertEqual(ancestors(parents,"3"),["3","2","1","0"])
        self.assertEqual(ancestors(parents,"6"),["6","5","4","0"])
        self.assertEqual(ancestors(parents,"9"),["9","8","7","0"])
        self.assertEqual(len(active_union(parents,["3","6","9"])),10)
    def test_30_selected_global_and_local_flags_remain_distinct(self):
        d=json.loads((ROOT/"evidence/local-same-role-selector-observations.json").read_text(encoding="utf-8"))
        candidates=[e for e in d["examples"] if e["resource_record_index"]==0 and e["context_role"]=="primaryContext"]
        values={e["channel_name"]:int(e["context"]["flags"],16) for e in candidates}
        self.assertEqual(values["R hand"]&0x2000c,8)
        self.assertEqual(values["L hand"]&0x2000c,4)
        self.assertEqual(values["R foot"]&0x2000c,0x20004)
        self.assertEqual(values["L foot"]&0x2000c,0x20000)

if __name__ == "__main__":
    suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps({"kind":"independent-examples-and-reused-json-checks",
                      "tests_run":result.testsRun,"failures":len(result.failures),
                      "errors":len(result.errors),"success":result.wasSuccessful(),
                      "module_counts":{"41":16,"42":14,"reused_evidence":2},
                      "game_runtime_verified":False}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
