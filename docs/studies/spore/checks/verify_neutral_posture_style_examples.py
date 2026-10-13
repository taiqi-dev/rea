"""Independent body-neutral/style/ownership examples, not Spore execution."""
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Diagnostic(ValueError):
    pass


def finite(*values):
    if any(v is None for v in values):
        raise Diagnostic("UnknownBodyOrStyleParameter")
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise Diagnostic("NonFiniteBodyOrStyleParameter")


def clamp(v, low, high):
    finite(v, low, high)
    if low > high:
        raise Diagnostic("InvalidInterval")
    return max(low, min(high, v))


FEET = ((-.6, -.4), (-.6, .4), (0., -.4), (0., .4), (.6, -.4), (.6, .4))


@dataclass(frozen=True)
class Body:
    revision: int = 3
    recipe_digest: str = "own-recipe-A"
    bone_length: float = .6
    hip_foot_horizontal: float = .4
    min_knee: float = 20.
    max_knee: float = 100.
    com_x: float = .1
    com_y: float = .12
    chest_com_lever: float = .5
    feet: tuple = FEET
    has_hand: bool = True
    spine_axis: tuple = (1., 0., .1)

    def height_interval(self):
        finite(self.bone_length, self.hip_foot_horizontal, self.min_knee, self.max_knee)
        if self.bone_length <= 0 or self.hip_foot_horizontal < 0 or not 0 <= self.min_knee <= self.max_knee < 180:
            raise Diagnostic("InvalidBodyLegGeometry")
        dmin = 2 * self.bone_length * math.cos(math.radians(self.max_knee/2))
        dmax = 2 * self.bone_length * math.cos(math.radians(self.min_knee/2))
        r = self.hip_foot_horizontal
        if dmax <= r:
            raise Diagnostic("NoStandingHeight")
        return math.sqrt(max(0., dmin*dmin-r*r)), math.sqrt(dmax*dmax-r*r)

    def classification(self):
        if self.spine_axis is None:
            return "Unknown"
        finite(*self.spine_axis)
        size = math.sqrt(sum(v*v for v in self.spine_axis))
        if size == 0:
            return "Unknown"
        upright = abs(self.spine_axis[2])/size
        return "Upright" if upright >= .75 else "Prone" if upright <= .35 else "Mixed"


def support_margin(body, pitch):
    finite(body.com_x, body.com_y, body.chest_com_lever, pitch)
    # This own example's known rectangular support hull, not a general hull solver.
    if body.feet != FEET:
        raise Diagnostic("SupportHullNeedsRebuild")
    x = body.com_x + body.chest_com_lever*math.sin(math.radians(pitch))
    y = body.com_y
    return min(.6-x, .6+x, .4-y, .4+y)


def validate_pose(body, pose):
    if set(pose) != {"height", "pitch", "gaze", "hand"}:
        raise Diagnostic("UnknownPoseDOF")
    finite(*pose.values())
    lo, hi = body.height_interval()
    if not lo-1e-9 <= pose["height"] <= hi+1e-9:
        raise Diagnostic("LegJointLimit")
    if not -15 <= pose["pitch"] <= 15 or not -30 <= pose["gaze"] <= 30:
        raise Diagnostic("UpperBodyJointLimit")
    if not 0 <= pose["hand"] <= .35:
        raise Diagnostic("HandLimit")
    if support_margin(body, pose["pitch"]) < .08-1e-9:
        raise Diagnostic("InsufficientSupportMargin")
    return True


CAUTIOUS = {"height": .82, "pitch": 4., "gaze": 20., "hand": .1, "stride": .45, "windup": .5}
FIERCE = {"height": 1., "pitch": 12., "gaze": 0., "hand": .3, "stride": .7, "windup": .25}
NEUTRAL = {"height": .9, "pitch": 8., "gaze": 0., "hand": .1}


def plan_style(body, style):
    required = {"height", "pitch", "gaze", "hand", "stride", "windup"}
    if set(style) != required:
        raise Diagnostic("UnknownStyleParameter")
    finite(*style.values())
    if not body.has_hand:
        raise Diagnostic("MissingExecutionHand")
    if style["stride"] < 0 or style["windup"] <= 0:
        raise Diagnostic("InvalidStyleTiming")
    lo, hi = body.height_interval()
    pose = {"height": clamp(style["height"], lo, hi),
            "pitch": clamp(style["pitch"], -15., 15.),
            "gaze": clamp(style["gaze"], -30., 30.),
            "hand": clamp(style["hand"], 0., .35)}
    validate_pose(body, pose)
    if 1.875*.4/style["windup"] > 5.:
        raise Diagnostic("WindupPeakVelocityBudget")
    return {"pose": pose, "stride": clamp(style["stride"], .3, .8),
            "windup": style["windup"], "foot_anchors": body.feet,
            "body_revision": body.revision, "recipe_digest": body.recipe_digest}


def hermite(q0, v0, q1, v1, duration, t):
    finite(q0, v0, q1, v1, duration, t)
    if duration <= 0 or not 0 <= t <= duration:
        raise Diagnostic("InvalidHandoffTime")
    u = t/duration
    q = (2*u**3-3*u*u+1)*q0+(u**3-2*u*u+u)*duration*v0+(-2*u**3+3*u*u)*q1+(u**3-u*u)*duration*v1
    v = (6*u*u-6*u)*q0/duration+(3*u*u-4*u+1)*v0+(-6*u*u+6*u)*q1/duration+(3*u*u-2*u)*v1
    return q, v


def curve_extrema(q0, v0, q1, v1, duration):
    finite(q0, v0, q1, v1, duration)
    if duration <= 0:
        raise Diagnostic("InvalidHandoffTime")
    # q'(u)=a*u²+b*u+c; validate complete curve, not just endpoints.
    a = 6*(q0-q1)/duration+3*(v0+v1)
    b = 6*(q1-q0)/duration-4*v0-2*v1
    c = v0
    pos_u, vel_u = [0., 1.], [0., 1.]
    if abs(a) > 1e-12:
        disc = b*b-4*a*c
        if disc >= 0:
            pos_u += [u for u in ((-b-math.sqrt(disc))/(2*a), (-b+math.sqrt(disc))/(2*a)) if 0 < u < 1]
        extremum = -b/(2*a)
        if 0 < extremum < 1: vel_u.append(extremum)
    elif abs(b) > 1e-12:
        u = -c/b
        if 0 < u < 1: pos_u.append(u)
    positions = [hermite(q0,v0,q1,v1,duration,u*duration)[0] for u in pos_u]
    velocities = [abs(hermite(q0,v0,q1,v1,duration,u*duration)[1]) for u in vel_u]
    return min(positions), max(positions), max(velocities)


class Controller:
    def __init__(self, body=Body()):
        self.body, self.generation, self.owner_epoch = body, 7, 2
        self.pose = dict(plan_style(body, CAUTIOUS)["pose"])
        self.velocity = {k: 0. for k in self.pose}; self.velocity["hand"] = .2
        self.claims = {"handA.position": "old-soul", "foot1.anchor": "support"}
        self.soul_owner = "old-soul"
        self.action_duration = .8
        self.action_state = "Windup"
        self.committed = set()
        self.gait_phase = .37
        self.curves = None
        self.curve_ticket = None

    def ticket(self):
        return self.generation, self.body.revision, self.owner_epoch

    def reserve(self, dof, owner):
        if dof.startswith("foot"):
            raise Diagnostic("SupportDOFNotStyleOwned")
        if dof in self.claims and self.claims[dof] != owner:
            raise Diagnostic("OutputLeaseConflict")
        self.claims[dof] = owner

    def swap_soul(self, style, duration=.4, new_owner="new-soul"):
        if self.claims.get("handA.position") != self.soul_owner:
            raise Diagnostic("OutputLeaseConflict")
        target = plan_style(self.body, style)["pose"]
        validate_pose(self.body, self.pose)
        limits = {"height": .8, "pitch": 45., "gaze": 90., "hand": 1.}
        ranges = {"height": self.body.height_interval(), "pitch": (-15.,15.), "gaze": (-30.,30.), "hand": (0.,.35)}
        curves = {k: (self.pose[k], self.velocity[k], target[k], 0., duration) for k in self.pose}
        for k, args in curves.items():
            minimum, maximum, peak = curve_extrema(*args)
            if minimum < ranges[k][0]-1e-9 or maximum > ranges[k][1]+1e-9:
                raise Diagnostic("HandoffTrajectoryLimit")
            if peak > limits[k]+1e-9:
                raise Diagnostic("HandoffVelocityBudget")
        pmin, pmax, _ = curve_extrema(*curves["pitch"])
        if min(support_margin(self.body,pmin),support_margin(self.body,pmax)) < .08-1e-9:
            raise Diagnostic("HandoffSupportViolation")
        # Atomic commit after all preflight: no old/new writer overlap.
        self.generation += 1; self.owner_epoch += 1
        self.action_state = "Cancelled"
        self.claims["handA.position"] = new_owner
        self.soul_owner = new_owner
        self.curves = curves
        self.curve_ticket = self.ticket()

    def sample_handoff(self, t):
        if self.curves is None:
            raise Diagnostic("NoPreparedHandoff")
        if self.curve_ticket != self.ticket():
            raise Diagnostic("StaleHandoffBodyOrController")
        next_pose, next_velocity = {}, {}
        for k, args in self.curves.items():
            next_pose[k], next_velocity[k] = hermite(*args, t)
        validate_pose(self.body, next_pose)
        self.pose, self.velocity = next_pose, next_velocity

    def publish(self, ticket, pose):
        if ticket != self.ticket():
            raise Diagnostic("StalePoseJob")
        validate_pose(self.body, pose)
        self.pose = dict(pose)


class OwnPostureTests(unittest.TestCase):
    def test_01_static_recipe_not_changed_by_two_styles(self):
        b=Body(); before=b; a=plan_style(b,CAUTIOUS); z=plan_style(b,FIERCE)
        self.assertEqual(b,before); self.assertEqual(a["recipe_digest"],z["recipe_digest"])
    def test_02_leg_height_interval_from_length_and_joint_limits(self):
        lo,hi=Body().height_interval()
        self.assertAlmostEqual(lo,.6595250655,places=6); self.assertAlmostEqual(hi,1.1120155965,places=6)
    def test_03_same_body_different_feasible_styles(self):
        a,z=plan_style(Body(),CAUTIOUS),plan_style(Body(),FIERCE)
        self.assertEqual((a["pose"]["height"],z["pose"]["height"]),(.82,1.))
        self.assertEqual((a["stride"],z["stride"]),(.45,.7))
    def test_04_style_clamps_height_without_changing_shape(self):
        s=dict(FIERCE,height=4.); b=Body(); p=plan_style(b,s)
        self.assertAlmostEqual(p["pose"]["height"],b.height_interval()[1]); self.assertEqual(b.bone_length,.6)
    def test_05_joint_limit_clamp_is_explicit(self):
        p=plan_style(Body(),dict(CAUTIOUS,pitch=70.,gaze=-80.))
        self.assertEqual((p["pose"]["pitch"],p["pose"]["gaze"]),(15.,-30.))
    def test_06_missing_hand_is_not_created_by_soul(self):
        with self.assertRaisesRegex(Diagnostic,"MissingExecutionHand"):plan_style(replace(Body(),has_hand=False),FIERCE)
    def test_07_unknown_mass_or_geometry_not_defaulted(self):
        for b in [replace(Body(),com_y=None),replace(Body(),bone_length=None)]:
            with self.assertRaisesRegex(Diagnostic,"UnknownBodyOrStyle"):plan_style(b,FIERCE)
    def test_08_nan_and_unknown_style_fields_diagnostic(self):
        with self.assertRaisesRegex(Diagnostic,"NonFinite"):plan_style(Body(),dict(FIERCE,pitch=math.nan))
        with self.assertRaisesRegex(Diagnostic,"UnknownStyle"):plan_style(Body(),dict(FIERCE,extra=1))
    def test_09_eccentric_body_preserved_support_violation_rejected(self):
        b=replace(Body(),com_y=.36)
        with self.assertRaisesRegex(Diagnostic,"InsufficientSupport"):plan_style(b,FIERCE)
        self.assertEqual(b.com_y,.36)
    def test_10_support_margin_of_both_example_styles(self):
        self.assertAlmostEqual(support_margin(Body(),4.),.28)
        self.assertAlmostEqual(support_margin(Body(),12.),.28)
    def test_11_six_leg_count_and_upright_are_separate(self):
        b=Body(); self.assertEqual(len(b.feet),6); self.assertEqual(b.classification(),"Prone")
        self.assertEqual(replace(b,spine_axis=(0,0,1)).classification(),"Upright")
    def test_12_unknown_and_mixed_orientation_remain_explicit(self):
        self.assertEqual(replace(Body(),spine_axis=None).classification(),"Unknown")
        self.assertEqual(replace(Body(),spine_axis=(1,0,1)).classification(),"Mixed")
    def test_13_low_body_uses_own_feasible_height(self):
        b=replace(Body(),bone_length=.3,hip_foot_horizontal=.2)
        p=plan_style(b,dict(CAUTIOUS,height=.38))
        self.assertEqual(p["pose"]["height"],.38); self.assertEqual(b.bone_length,.3)
    def test_14_no_support_or_invalid_leg_reports_reason(self):
        with self.assertRaisesRegex(Diagnostic,"NoStandingHeight"):plan_style(replace(Body(),hip_foot_horizontal=2.),CAUTIOUS)
        with self.assertRaisesRegex(Diagnostic,"SupportHullNeedsRebuild"):plan_style(replace(Body(),feet=FEET[:2]),CAUTIOUS)
    def test_15_support_output_cannot_be_reserved_by_style(self):
        c=Controller()
        with self.assertRaisesRegex(Diagnostic,"SupportDOF"):c.reserve("foot1.anchor","soul")
        self.assertEqual(c.claims["foot1.anchor"],"support")
    def test_16_existing_action_lease_conflict_diagnostic(self):
        c=Controller()
        with self.assertRaisesRegex(Diagnostic,"OutputLeaseConflict"):c.reserve("handA.position","another-action")
        self.assertEqual(c.claims["handA.position"],"old-soul")
    def test_17_handoff_preserves_initial_position_velocity(self):
        c=Controller(); q,v=dict(c.pose),dict(c.velocity); c.swap_soul(FIERCE); c.sample_handoff(0.)
        self.assertEqual(c.pose,q); self.assertEqual(c.velocity,v)
    def test_18_handoff_midpoint_full_numerical_example(self):
        c=Controller(); c.swap_soul(FIERCE); c.sample_handoff(.2)
        self.assertAlmostEqual(c.pose["height"],.91); self.assertAlmostEqual(c.pose["pitch"],8.)
        self.assertAlmostEqual(c.pose["gaze"],10.); self.assertAlmostEqual(c.pose["hand"],.21)
        self.assertAlmostEqual(c.velocity["height"],.675); self.assertAlmostEqual(c.velocity["hand"],.7)
    def test_19_handoff_endpoint_and_gait_anchor_continuity(self):
        c=Controller(); b=c.body; c.swap_soul(FIERCE); c.sample_handoff(.4)
        self.assertEqual(c.pose,plan_style(b,FIERCE)["pose"])
        self.assertEqual(c.gait_phase,.37); self.assertEqual(c.body.feet,FEET)
        self.assertTrue(all(abs(x)<1e-9 for x in c.velocity.values()))
    def test_20_old_pose_job_invalid_after_swap(self):
        c=Controller(); ticket=c.ticket(); c.swap_soul(FIERCE)
        with self.assertRaisesRegex(Diagnostic,"StalePoseJob"):c.publish(ticket,NEUTRAL)
    def test_21_swap_cancels_pending_action_preserves_committed_effect(self):
        c=Controller(); c.committed.add("earlier-hit"); c.swap_soul(FIERCE)
        self.assertEqual(c.action_state,"Cancelled"); self.assertEqual(c.committed,{"earlier-hit"})
        self.assertEqual(c.action_duration,.8)
    def test_22_invalid_transition_preflight_does_not_half_swap(self):
        c=Controller(); before=(c.ticket(),dict(c.claims),c.action_state,dict(c.pose))
        with self.assertRaisesRegex(Diagnostic,"HandoffVelocityBudget"):c.swap_soul(FIERCE,.08)
        self.assertEqual((c.ticket(),c.claims,c.action_state,c.pose),before)
    def test_23_curve_peak_checked_analytically_not_only_endpoints(self):
        lo,hi,peak=curve_extrema(.1,.2,.3,0.,.4)
        self.assertAlmostEqual(peak,.7041666667); self.assertAlmostEqual(lo,.1); self.assertAlmostEqual(hi,.3)
        lo,hi,_=curve_extrema(.1,5.,.1,0.,.4)
        self.assertGreater(hi,.35)
    def test_24_changed_body_revision_invalidates_pose_job(self):
        c=Controller(); ticket=c.ticket(); c.body=replace(c.body,revision=4)
        with self.assertRaisesRegex(Diagnostic,"StalePoseJob"):c.publish(ticket,NEUTRAL)
    def test_25_short_windup_cannot_override_velocity_budget(self):
        with self.assertRaisesRegex(Diagnostic,"WindupPeak"):plan_style(Body(),dict(FIERCE,windup=.1))
    def test_26_stride_and_invalid_timing_policy(self):
        p=plan_style(Body(),dict(FIERCE,stride=2.)); self.assertEqual(p["stride"],.8)
        with self.assertRaisesRegex(Diagnostic,"InvalidStyleTiming"):plan_style(Body(),dict(FIERCE,windup=-1.))


class EvidenceTests(unittest.TestCase):
    def read(self,name):return json.loads((ROOT/"evidence"/name).read_text(encoding="utf-8"))
    def test_27_six_new_idle_resources_and_exact_groups(self):
        d=self.read("local-selected-idle-posture-metadata.json")
        self.assertEqual(d["coverage"]["anim_count"],6); self.assertEqual(d["coverage"]["channels"],51)
        self.assertEqual(d["diagnostics"],[])
        for r in d["tlsa_records"]:
            self.assertEqual([g["id"] for g in r["tlsa"]["selected_groups"]],["0x04866d8e","0x04866dab","0x04866db9"])
    def test_28_idle_flag_is_only_loop_and_not_default_posture(self):
        d=self.read("local-selected-idle-posture-metadata.json")
        for r in d["tlsa_records"]:
            self.assertEqual([g["idle"] for g in r["tlsa"]["selected_groups"]],[False,True,False])
            self.assertEqual([g["endMode"] for g in r["tlsa"]["selected_groups"]],[0,1,0])
    def test_29_group_namespace_differs_from_resource_instances(self):
        d=self.read("local-selected-idle-posture-metadata.json")
        for r in d["tlsa_records"]:
            pairs=[(g["id"],g["choices"][0]["animations"][0]["id"]) for g in r["tlsa"]["selected_groups"]]
            self.assertEqual(pairs,[("0x04866d8e","0xcb38a593"),("0x04866dab","0xcee6aab3"),("0x04866db9","0x0921d851")])
    def test_30_zero_predicates_do_not_classify_body_upright_false(self):
        d=self.read("local-selected-idle-posture-metadata.json")
        self.assertTrue(all(r["whole_predicate"]["raw_8_bytes"]=="0000000000000000" for r in d["anim_records"]))
        self.assertTrue(all(r["whole_predicate"]["native_evaluation"]=="not-performed" for r in d["anim_records"]))
    def test_31_posture_capability_raw_one_two_preserved(self):
        d=self.read("local-selected-capability-contributions.json")
        values=[r["direct_capability_fields"]["modelCapabilityPosture"]["values"] for r in d["selected_parts"] if "modelCapabilityPosture" in r["direct_capability_fields"]]
        self.assertEqual(values,[[1],[2]])
    def test_32_all_manifest_local_identity_hashes_match(self):
        m=self.read("public-neutral-posture-style-contracts.json")
        for entry in m["local_evidence"]:
            self.assertEqual(hashlib.sha256((ROOT/entry["path"]).read_bytes()).hexdigest(),entry["sha256"])


class HandoffInvalidationTests(unittest.TestCase):
    def test_33_body_swap_rejects_inflight_handoff_curve(self):
        c=Controller();c.swap_soul(FIERCE);before=dict(c.pose);c.body=replace(c.body,revision=4)
        with self.assertRaisesRegex(Diagnostic,"StaleHandoffBody"):c.sample_handoff(.2)
        self.assertEqual(c.pose,before)
    def test_34_soul_swap_cannot_steal_external_action_output(self):
        c=Controller();c.claims["handA.position"]="external-task";before=c.ticket()
        with self.assertRaisesRegex(Diagnostic,"OutputLeaseConflict"):c.swap_soul(FIERCE)
        self.assertEqual(c.ticket(),before)
    def test_35_feasible_endpoints_do_not_allow_overshooting_handoff(self):
        c=Controller();c.velocity["hand"]=5.;before=c.ticket()
        with self.assertRaisesRegex(Diagnostic,"HandoffTrajectoryLimit"):c.swap_soul(FIERCE)
        self.assertEqual(c.ticket(),before);self.assertEqual(c.action_state,"Windup")
    def test_36_second_handoff_captures_current_pose_and_velocity(self):
        c=Controller();c.swap_soul(FIERCE);c.sample_handoff(.2)
        q,v=dict(c.pose),dict(c.velocity)
        c.swap_soul(CAUTIOUS,new_owner="third-soul");c.sample_handoff(0.)
        self.assertEqual(c.pose,q);self.assertEqual(c.velocity,v)
        self.assertEqual(c.generation,9);self.assertEqual(c.claims["handA.position"],"third-soul")


if __name__=="__main__":
    suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps({"kind":"independent-neutral-posture-style-examples","tests_run":result.testsRun,
                      "failures":len(result.failures),"errors":len(result.errors),"success":result.wasSuccessful(),
                      "counts":{"own_posture_style":30,"static_evidence":6},"target_runtime_verified":False}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
