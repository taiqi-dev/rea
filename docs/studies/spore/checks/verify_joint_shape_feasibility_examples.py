"""Own 3D joint/range/shape examples, not a recovered Spore solver."""
import argparse
import io
import json
import math
from pathlib import Path
import struct
import unittest

from read_joint_shape_feasibility_metadata import read_skin_pose_prefix, rotation_diagnostic
from read_selected_ability_properties import FormatError, digest

EPS=1e-9


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def scale(a,s):return tuple(x*s for x in a)
def norm(a):return math.sqrt(dot(a,a))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def clamp(v,low,high):return max(low,min(high,v))


def unit(v):
    if not all(math.isfinite(x) for x in v) or norm(v)<=EPS:raise ValueError('degenerate direction')
    return scale(v,1/norm(v))


def qnormalize(q):
    if len(q)!=4 or not all(math.isfinite(x) for x in q) or norm(q)<=EPS:raise ValueError('invalid quaternion')
    return scale(q,1/norm(q))


def qmultiply(a,b):
    w,x,y,z=a;s,u,v,t=b
    return (w*s-x*u-y*v-z*t,w*u+x*s+y*t-z*v,w*v-x*t+y*s+z*u,w*t+x*v-y*u+z*s)


def qaxis(axis,degrees):
    if not math.isfinite(degrees):raise ValueError('nonfinite angle')
    axis=unit(axis);r=math.radians(degrees)/2
    return (math.cos(r),*scale(axis,math.sin(r)))


def swing_twist(q,axis=(1,0,0)):
    q=qnormalize(q);axis=unit(axis);p=dot(q[1:],axis)
    t=(q[0],*scale(axis,p))
    if norm(t)<=EPS:return dict(status='TwistUndefinedAtHalfTurn')
    t=qnormalize(t);s=qmultiply(q,(t[0],-t[1],-t[2],-t[3]))
    angle=(math.degrees(2*math.atan2(dot(t[1:],axis),t[0]))+180)%360-180
    return dict(status='defined',swing_degrees=math.degrees(2*math.acos(clamp(abs(s[0]),0,1))),
                twist_degrees=angle,swing_quaternion=s,twist_quaternion=t)


def joint_check(q,swing_limit,twist_min,twist_max):
    if not all(math.isfinite(x) for x in (swing_limit,twist_min,twist_max)) or not 0<=swing_limit<=180 or twist_min>twist_max:
        raise ValueError('invalid joint limit')
    result=swing_twist(q)
    if result['status']!='defined':return dict(**result,feasible=False,reasons=['TwistUndefined'])
    reasons=[]
    if result['swing_degrees']>swing_limit+1e-7:reasons.append('SwingConeExceeded')
    if not twist_min-1e-7<=result['twist_degrees']<=twist_max+1e-7:reasons.append('TwistLimitExceeded')
    return dict(**result,feasible=not reasons,reasons=reasons)


def mirror_y_quaternion(q):
    w,x,y,z=qnormalize(q)
    # H R H for H=diag(1,-1,1), vector part is axial: det(H)*H*v.
    return (w,-x,y,-z)


def two_link(length1,length2,target,pole=(0,0,1),branch_sign=1):
    if not all(math.isfinite(x) and x>EPS for x in (length1,length2)):raise ValueError('invalid length')
    if branch_sign not in (-1,1):raise ValueError('invalid branch')
    d=norm(target)
    if not all(math.isfinite(x) for x in target):raise ValueError('invalid target')
    if d>length1+length2+EPS:return dict(status='LengthTooFar',distance=d)
    if d<abs(length1-length2)-EPS:return dict(status='LengthTooNear',distance=d)
    if d<=EPS:return dict(status='CoincidentTarget',distance=d)
    u=unit(target);pole=unit(pole);v=sub(pole,scale(u,dot(pole,u)))
    if norm(v)<=EPS:return dict(status='BendPlaneUndefined',distance=d)
    v=unit(v);a=(length1**2+d**2-length2**2)/(2*d)
    b=math.sqrt(max(0,length1**2-a*a))*branch_sign
    elbow=add(scale(u,a),scale(v,b));forearm=sub(target,elbow)
    hinge_normal=scale(cross(u,v),-1)
    signed=math.degrees(math.atan2(dot(hinge_normal,cross(elbow,forearm)),dot(elbow,forearm)))
    swing=math.degrees(math.acos(clamp(dot(unit(elbow),(1,0,0)),-1,1)))
    return dict(status='geometry-solved',distance=d,elbow=elbow,wrist=target,
                flex_degrees=signed,shoulder_swing_degrees=swing,
                length_errors=[norm(elbow)-length1,norm(forearm)-length2])


def capsule_sphere_clearance(a,b,c,arm_radius,other_radius):
    if not all(math.isfinite(v) for v in (*a,*b,*c,arm_radius,other_radius)) or min(arm_radius,other_radius)<0:
        raise ValueError('invalid contact geometry')
    d=sub(b,a);den=dot(d,d)
    t=clamp(dot(sub(c,a),d)/den,0,1) if den>EPS**2 else 0
    distance=norm(sub(add(a,scale(d,t)),c))
    return dict(parameter=t,axis_distance=distance,clearance=distance-arm_radius-other_radius)


BEFORE=dict(length1=1.0,length2=.8,radius=.08,reference_flex=90,shoulder_swing_max=80,
            elbow_min=10,elbow_max=130,hand_twist_min=-35,hand_twist_max=35,body_revision=8)
AFTER=dict(BEFORE,length1=1.6,radius=.28,reference_flex=110,body_revision=9)
PHASES={'windup':dict(target=(.8,.6,0),hand_twist=15),
        'power':dict(target=(1.4,.2,0),hand_twist=30)}
NEIGHBOR=dict(center=(1.4,.55,0),radius=.12)


def phase_check(body,phase,neighbor=NEIGHBOR,branch_sign=1):
    shape_valid=(body['length1']>0 and body['length2']>0 and body['radius']>0)
    reference_valid=body['elbow_min']<=body['reference_flex']<=body['elbow_max']
    pose=two_link(body['length1'],body['length2'],phase['target'],branch_sign=branch_sign)
    report=dict(shape_valid=shape_valid,reference_within_hard_limits=reference_valid,
                body_revision=body['body_revision'],pose=pose,reasons=[],swept_path_validated=False)
    if not shape_valid:report['reasons'].append('ShapeInvalid')
    if not reference_valid:report['reasons'].append('ReferenceOutsideHardLimits')
    if pose['status']!='geometry-solved':report['reasons'].append(pose['status']);report['feasible']=False;return report
    if pose['shoulder_swing_degrees']>body['shoulder_swing_max']+1e-7:report['reasons'].append('ShoulderConeExceeded')
    if not body['elbow_min']-1e-7<=pose['flex_degrees']<=body['elbow_max']+1e-7:report['reasons'].append('ElbowFlexExceeded')
    if not body['hand_twist_min']<=phase['hand_twist']<=body['hand_twist_max']:report['reasons'].append('HandTwistExceeded')
    contacts=[capsule_sphere_clearance(a,b,neighbor['center'],body['radius'],neighbor['radius'])
              for a,b in (((0,0,0),pose['elbow']),(pose['elbow'],pose['wrist']))]
    report['contacts']=contacts
    if any(c['clearance']<0 for c in contacts):report['reasons'].append('NeighborPenetration')
    report['reference_preference_error_degrees']=pose['flex_degrees']-body['reference_flex']
    report['feasible']=not report['reasons']
    return report


def sample_skin_fixture():
    data=bytearray(16+64*2);struct.pack_into('<Iiii',data,0,16,2,0,0)
    for i in range(2):struct.pack_into('<16f',data,16+i*64,*([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,0]))
    return data,dict(index=6,data_offset=0,size=len(data))


class Examples(unittest.TestCase):
    def test_identity_joint(self):self.assertTrue(joint_check((1,0,0,0),80,-35,35)['feasible'])
    def test_3d_swing(self):self.assertAlmostEqual(joint_check(qaxis((0,1,1),60),80,-35,35)['swing_degrees'],60)
    def test_cone_reject(self):self.assertEqual(joint_check(qaxis((0,1,0),90),80,-35,35)['reasons'],['SwingConeExceeded'])
    def test_twist_reject(self):self.assertEqual(joint_check(qaxis((1,0,0),40),80,-35,35)['reasons'],['TwistLimitExceeded'])
    def test_composed_swing_twist(self):
        d=swing_twist(qmultiply(qaxis((0,0,1),40),qaxis((1,0,0),20)))
        self.assertAlmostEqual(d['swing_degrees'],40);self.assertAlmostEqual(d['twist_degrees'],20)
    def test_quaternion_sign(self):
        q=qaxis((1,0,0),20);self.assertAlmostEqual(swing_twist(q)['twist_degrees'],swing_twist(scale(q,-1))['twist_degrees'])
    def test_mirror_twist(self):self.assertAlmostEqual(swing_twist(mirror_y_quaternion(qaxis((1,0,0),20)))['twist_degrees'],-20)
    def test_double_mirror(self):
        q=qnormalize((1,2,3,4));self.assertAlmostEqual(abs(dot(q,mirror_y_quaternion(mirror_y_quaternion(q)))),1)
    def test_asymmetric_mirror_bounds(self):
        mirrored=mirror_y_quaternion(qaxis((1,0,0),30))
        self.assertTrue(joint_check(mirrored,80,-40,10)['feasible'])
        self.assertFalse(joint_check(mirrored,80,-10,40)['feasible'])
    def test_half_turn_singularity(self):self.assertEqual(swing_twist(qaxis((0,1,0),180))['status'],'TwistUndefinedAtHalfTurn')
    def test_invalid_quaternion(self):
        with self.assertRaisesRegex(ValueError,'quaternion'):swing_twist((0,0,0,0))
    def test_nonfinite_quaternion(self):
        with self.assertRaisesRegex(ValueError,'quaternion'):swing_twist((math.nan,0,0,0))
    def test_bad_limit(self):
        with self.assertRaisesRegex(ValueError,'limit'):joint_check((1,0,0,0),190,0,1)
    def test_before_windup(self):self.assertTrue(phase_check(BEFORE,PHASES['windup'])['feasible'])
    def test_before_power(self):self.assertTrue(phase_check(BEFORE,PHASES['power'])['feasible'])
    def test_after_windup_flex(self):
        p=phase_check(AFTER,PHASES['windup']);self.assertIn('ElbowFlexExceeded',p['reasons'])
        self.assertEqual(p['pose']['status'],'geometry-solved')
    def test_after_power_contact(self):
        p=phase_check(AFTER,PHASES['power']);self.assertEqual(p['reasons'],['NeighborPenetration'])
        self.assertAlmostEqual(p['contacts'][1]['clearance'],-.05)
    def test_reference_separate(self):
        p=phase_check(AFTER,PHASES['windup']);self.assertTrue(p['shape_valid']);self.assertTrue(p['reference_within_hard_limits'])
        self.assertFalse(p['feasible'])
    def test_invalid_reference_retained(self):self.assertIn('ReferenceOutsideHardLimits',phase_check(dict(BEFORE,reference_flex=150),PHASES['power'])['reasons'])
    def test_length_too_far(self):self.assertEqual(two_link(1,.8,(3,0,0))['status'],'LengthTooFar')
    def test_length_too_near(self):self.assertEqual(two_link(1.6,.8,(.5,0,0))['status'],'LengthTooNear')
    def test_equal_lengths_zero_target(self):self.assertEqual(two_link(1,1,(0,0,0))['status'],'CoincidentTarget')
    def test_parallel_pole(self):self.assertEqual(two_link(1,1,(0,0,1))['status'],'BendPlaneUndefined')
    def test_invalid_length(self):
        with self.assertRaisesRegex(ValueError,'length'):two_link(0,1,(1,0,0))
    def test_lengths_preserved(self):
        p=two_link(1,.8,(.8,.6,0));self.assertLess(max(abs(e) for e in p['length_errors']),1e-12)
    def test_reverse_branch_reject(self):self.assertIn('ElbowFlexExceeded',phase_check(BEFORE,PHASES['windup'],branch_sign=-1)['reasons'])
    def test_removed_neighbor_only_fixes_contact(self):
        n=dict(center=(10,10,10),radius=.12)
        self.assertTrue(phase_check(AFTER,PHASES['power'],n)['feasible'])
        self.assertIn('ElbowFlexExceeded',phase_check(AFTER,PHASES['windup'],n)['reasons'])
    def test_segment_closest_endpoint(self):self.assertAlmostEqual(capsule_sphere_clearance((0,0,0),(1,0,0),(2,0,0),.1,.2)['clearance'],.7)
    def test_zero_segment_contact(self):self.assertAlmostEqual(capsule_sphere_clearance((0,0,0),(0,0,0),(0,0,1),.1,.2)['clearance'],.7)
    def test_invalid_contact(self):
        with self.assertRaisesRegex(ValueError,'contact'):capsule_sphere_clearance((0,0,0),(1,0,0),(2,0,0),-.1,.2)
    def test_no_swept_guarantee(self):self.assertFalse(phase_check(BEFORE,PHASES['power'])['swept_path_validated'])
    def test_length_minimum_with_joint_limit(self):
        d=math.sqrt(AFTER['length1']**2+AFTER['length2']**2+2*AFTER['length1']*AFTER['length2']*math.cos(math.radians(130)))
        self.assertGreater(d,1.0);self.assertLess(d,math.sqrt(2))
    def test_skin_pose_prefix(self):
        data,s=sample_skin_fixture();p=read_skin_pose_prefix(data,s);self.assertEqual(len(p['rows']),2)
    def test_skin_pose_bounds(self):
        data,s=sample_skin_fixture();struct.pack_into('<I',data,0,1000)
        with self.assertRaises(FormatError):read_skin_pose_prefix(data,s)
    def test_skin_pose_nonfinite(self):
        data,s=sample_skin_fixture();struct.pack_into('<f',data,16,math.inf)
        with self.assertRaises(FormatError):read_skin_pose_prefix(data,s)
    def test_skin_pose_budget(self):
        data,s=sample_skin_fixture()
        with self.assertRaises(FormatError):read_skin_pose_prefix(data,s,5)
    def test_rotation_diagnostic(self):self.assertAlmostEqual(rotation_diagnostic((1,0,0,0),qaxis((1,0,0),40))['quaternion_geodesic_candidate_degrees'],40)
    def test_rotation_zero(self):
        with self.assertRaises(FormatError):rotation_diagnostic((0,0,0,0),(1,0,0,0))
    def test_shape_revision_identity(self):self.assertNotEqual(BEFORE['body_revision'],AFTER['body_revision'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Examples))
    base=Path(__file__).resolve().parent.parent;input_path=base/'evidence/joint-limits-shape-feasibility-observations.json'
    raw=input_path.read_bytes();e=json.loads(raw.decode('utf8'));verified_rows=0
    for prefix in e['skin_pose_prefixes']:
        for row in prefix['rows']:
            values=struct.unpack('<16f',bytes.fromhex(row['raw_64_bytes']))
            if list(values[12:15])!=row['community_invPoseTranslation_raw']:raise AssertionError('skin raw mismatch')
            if row['decoded_offset']!=prefix['pointer']+row['pose_ordinal']*64:raise AssertionError('skin offset')
            verified_rows+=1
    for track in e['local_track_prefixes']:
        for row in track['samples']:
            values=struct.unpack('<8f',bytes.fromhex(row['raw32']))
            if list(values[:4])!=row['rotation_raw'] or list(values[4:7])!=row['location_raw'] or values[7]!=row['time_raw']:
                raise AssertionError('track raw mismatch')
            verified_rows+=1
    doc=base/'55-joint-limits-shape-edits-and-motion-feasibility.md'
    result=dict(schema_version=1,module=55,tests_run=r.testsRun,failures=len(r.failures),errors=len(r.errors),
        status='passed' if r.wasSuccessful() else 'failed',log=stream.getvalue(),
        evidence_input=dict(path=str(input_path.resolve()),sha256=digest(raw)),
        document_input=dict(path=str(doc.resolve()),sha256=digest(doc.read_bytes())) if doc.exists() else None,
        local_raw_consistency=dict(checked_rows=verified_rows,status='passed'),
        own_example=dict(before=BEFORE,after=AFTER,phases=PHASES,neighbor=NEIGHBOR,
            results={label:{phase:phase_check(body,p) for phase,p in PHASES.items()} for label,body in [('before',BEFORE),('after',AFTER)]},
            radial_minimum_with_elbow_max={label:math.sqrt(body['length1']**2+body['length2']**2+2*body['length1']*body['length2']*math.cos(math.radians(body['elbow_max']))) for label,body in [('before',BEFORE),('after',AFTER)]}),
        verifier_sha256=digest(Path(__file__).read_bytes()),
        limitations='Independent circular swing cone/twist checks, two-link pose samples and capsule-sphere examples only; no native solver, full trajectory or muscle physics verified.')
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:result[k] for k in ('tests_run','failures','errors','status')}))
    print(json.dumps(dict(raw_rows_checked=verified_rows,phase_reasons={label:{phase:row['reasons'] for phase,row in rows.items()} for label,rows in result['own_example']['results'].items()})))
    if not r.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
