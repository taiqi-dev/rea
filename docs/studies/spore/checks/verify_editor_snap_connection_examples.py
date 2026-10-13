"""Independent snapping/frame/transaction examples; not original Spore code."""
from dataclasses import dataclass, replace
import math
import unittest


def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,k):return tuple(x*k for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(a):
    n=math.sqrt(dot(a,a))
    if not math.isfinite(n) or n<1e-10:raise ValueError('DegenerateFrameVector')
    return mul(a,1/n)


def ray_triangle(origin,direction,a,b,c):
    if any(not math.isfinite(x) for p in (origin,direction,a,b,c) for x in p):
        raise ValueError('NonFinitePickInput')
    if dot(direction,direction)<1e-16:raise ValueError('DegeneratePickRay')
    e1,e2=sub(b,a),sub(c,a)
    if dot(cross(e1,e2),cross(e1,e2))<1e-16:raise ValueError('DegeneratePickTriangle')
    h=cross(direction,e2);det=dot(e1,h)
    if abs(det)<1e-10:return None
    s=sub(origin,a);u=dot(s,h)/det;q=cross(s,e1);v=dot(direction,q)/det;t=dot(e2,q)/det
    if t<0 or u<0 or v<0 or u+v>1:return None
    return {'point':add(origin,mul(direction,t)),'barycentric':(1-u-v,u,v),'ray_t':t}


def frame(normal,preferred=(0,0,1)):
    n=unit(normal);t=sub(preferred,mul(n,dot(preferred,n)))
    if dot(t,t)<1e-16:
        axis=min(((1,0,0),(0,1,0),(0,0,1)),key=lambda a:abs(dot(a,n)))
        t=sub(axis,mul(n,dot(axis,n)))
    t=unit(t);b=cross(n,t)
    return t,b,n


def rotate_by_frame(f,v):return tuple(sum(f[j][i]*v[j] for j in range(3)) for i in range(3))
def determinant(f):return dot(f[0],cross(f[1],f[2]))


def roll_frame(f,angle):
    c,s=math.cos(angle),math.sin(angle)
    return add(mul(f[0],c),mul(f[1],s)),add(mul(f[0],-s),mul(f[1],c)),f[2]


def part_origin_for_socket(surface,f,socket_local):
    return sub(surface,rotate_by_frame(f,socket_local))


def cylinder_mount(radius,z,phi):
    if not math.isfinite(radius) or radius<=0:raise ValueError('InvalidHostRadius')
    n=(math.cos(phi),math.sin(phi),0)
    return (radius*n[0],radius*n[1],z),frame(n)


def normal_after_scale(n,scale):
    if any(not math.isfinite(x) or x<=0 for x in scale):raise ValueError('InvalidShapeScale')
    return unit(tuple(x/s for x,s in zip(n,scale)))


@dataclass(frozen=True)
class Candidate:
    stable_id:str
    pixels:float
    legal:bool=True


def choose_snap(candidates,current=None,enter=8,leave=12):
    if enter<=0 or leave<enter:raise ValueError('InvalidSnapHysteresis')
    if any(not math.isfinite(c.pixels) or c.pixels<0 for c in candidates):raise ValueError('InvalidSnapDistance')
    old=next((c for c in candidates if c.stable_id==current and c.legal),None)
    if old and old.pixels<=leave:return old.stable_id
    valid=[c for c in candidates if c.legal and c.pixels<=enter]
    return min(valid,key=lambda c:(c.pixels,c.stable_id)).stable_id if valid else None


def validate_connection(parents,child,host,slot_kind,accepted_kinds,lengths):
    if host not in parents:raise ValueError('ParentMissing')
    if child not in parents:raise ValueError('ChildMissing')
    if slot_kind not in accepted_kinds:raise ValueError('ConnectorIncompatible')
    if not lengths or any(not math.isfinite(x) or x<.01 for x in lengths):raise ValueError('DegenerateBoneChain')
    out=dict(parents);out[child]=host
    for node in out:
        seen=set();at=node
        while at is not None:
            if at in seen:raise ValueError('ConnectionCycle')
            if at not in out:raise ValueError('ParentMissing')
            seen.add(at);at=out[at]
    if sum(parent is None for parent in out.values())!=1:raise ValueError('InvalidRootCount')
    return out


def validate_mirror_pairs(parents,pairs):
    for a,b in pairs.items():
        if a not in parents or b not in parents:raise ValueError('MirrorPartnerMissing')
        if a==b or pairs.get(b)!=a:raise ValueError('MirrorNotReciprocal')


class Transaction:
    def __init__(self,parents):
        self.parents=dict(parents);self.generation=1;self.history=[dict(parents)];self.preview=None
    def propose(self,edits):
        self.preview=None
        proposed=dict(self.parents)
        for child,host,slot,accepted,lengths in edits:
            proposed=validate_connection(proposed,child,host,slot,accepted,lengths)
        self.preview=proposed
        return proposed
    def commit(self,expected):
        if expected!=self.generation:raise ValueError('StaleDragBase')
        if self.preview is None:raise ValueError('NoValidPreview')
        self.parents=dict(self.preview);self.generation+=1;self.history.append(dict(self.parents));self.preview=None
    def cancel(self):self.preview=None
    def undo(self):
        if len(self.history)<2:raise ValueError('NothingToUndo')
        self.history.pop();self.parents=dict(self.history[-1]);self.generation+=1;self.preview=None


class SnapConnectionExamples(unittest.TestCase):
    def setUp(self):self.parents={'body':None,'arm':'body','hand':'arm','mirrorArm':'body','eye':'body'}

    def test_01_ray_triangle_returns_actual_surface(self):
        h=ray_triangle((.2,.2,1),(0,0,-1),(0,0,0),(1,0,0),(0,1,0))
        self.assertEqual(h['point'],(.2,.2,0));self.assertAlmostEqual(h['ray_t'],1)
        for a,b in zip(h['barycentric'],(.6,.2,.2)):self.assertAlmostEqual(a,b)

    def test_02_missed_and_behind_ray_not_hit(self):
        tri=((0,0,0),(1,0,0),(0,1,0))
        self.assertIsNone(ray_triangle((2,2,1),(0,0,-1),*tri))
        self.assertIsNone(ray_triangle((.2,.2,1),(0,0,1),*tri))

    def test_03_parallel_and_degenerate_geometry(self):
        self.assertIsNone(ray_triangle((.2,.2,1),(1,0,0),(0,0,0),(1,0,0),(0,1,0)))
        with self.assertRaisesRegex(ValueError,'DegeneratePickTriangle'):
            ray_triangle((0,0,1),(0,0,-1),(0,0,0),(1,0,0),(2,0,0))

    def test_04_nonfinite_ray_diagnosed(self):
        with self.assertRaisesRegex(ValueError,'NonFinitePickInput'):
            ray_triangle((math.nan,0,1),(0,0,-1),(0,0,0),(1,0,0),(0,1,0))
        with self.assertRaisesRegex(ValueError,'DegeneratePickRay'):
            ray_triangle((0,0,1),(0,0,0),(0,0,0),(1,0,0),(0,1,0))

    def test_05_surface_frame_is_proper_and_normal_aligned(self):
        f=frame((1,0,0));self.assertAlmostEqual(determinant(f),1)
        self.assertEqual(f[2],(1,0,0));self.assertAlmostEqual(dot(f[0],f[2]),0)

    def test_06_frame_fallback_when_tangent_parallel(self):
        f=frame((0,0,1));self.assertAlmostEqual(determinant(f),1)
        with self.assertRaisesRegex(ValueError,'DegenerateFrameVector'):frame((0,0,0))

    def test_07_socket_alignment_not_mesh_origin(self):
        p,f=cylinder_mount(.4,.3,0);socket=(0,0,-.05)
        origin=part_origin_for_socket(p,f,socket)
        self.assertAlmostEqual(origin[0],.45)
        self.assertEqual(add(origin,rotate_by_frame(f,socket)),p)

    def test_08_widen_recomputes_mount_without_child_scale(self):
        old,f=cylinder_mount(.4,.3,0);new,g=cylinder_mount(.7,.3,0)
        oldo=part_origin_for_socket(old,f,(0,0,-.05));newo=part_origin_for_socket(new,g,(0,0,-.05))
        self.assertAlmostEqual(newo[0]-oldo[0],.3)
        self.assertAlmostEqual(math.sqrt(dot(rotate_by_frame(g,(0,0,.5)),rotate_by_frame(g,(0,0,.5)))),.5)

    def test_09_mirrored_surface_frames_keep_handedness(self):
        a,f=cylinder_mount(.7,.3,.2);b,g=cylinder_mount(.7,.3,math.pi-.2)
        for x,y in zip(b,(-a[0],a[1],a[2])):self.assertAlmostEqual(x,y)
        self.assertAlmostEqual(determinant(f),1);self.assertAlmostEqual(determinant(g),1)

    def test_10_inverse_transpose_for_nonuniform_shape(self):
        n=normal_after_scale((1,1,0),(2,1,1));self.assertAlmostEqual(n[1]/n[0],2)
        with self.assertRaisesRegex(ValueError,'InvalidShapeScale'):normal_after_scale((1,0,0),(0,1,1))

    def test_11_snap_hysteresis_prevents_boundary_chatter(self):
        self.assertEqual(choose_snap([Candidate('A',7.9)]),'A')
        self.assertEqual(choose_snap([Candidate('A',8.1)],'A'),'A')
        self.assertEqual(choose_snap([Candidate('A',12)],'A'),'A')
        self.assertIsNone(choose_snap([Candidate('A',12.1)],'A'))

    def test_12_stable_tie_and_illegal_snap_filter(self):
        self.assertEqual(choose_snap([Candidate('B',4),Candidate('A',4)]),'A')
        self.assertIsNone(choose_snap([Candidate('A',1,False)],'A'))

    def test_13_invalid_snap_input_diagnosed(self):
        with self.assertRaisesRegex(ValueError,'InvalidSnapDistance'):choose_snap([Candidate('A',math.nan)])
        with self.assertRaisesRegex(ValueError,'InvalidSnapHysteresis'):choose_snap([],enter=12,leave=8)

    def test_14_legal_reparent_preserves_identity(self):
        out=validate_connection(self.parents,'hand','body','soft',{'soft'},[.5,.5])
        self.assertEqual(out['hand'],'body');self.assertEqual(set(out),set(self.parents))

    def test_15_descendant_reparent_rejects_cycle(self):
        with self.assertRaisesRegex(ValueError,'ConnectionCycle'):
            validate_connection(self.parents,'arm','hand','soft',{'soft'},[.5])

    def test_16_self_and_missing_parent_rejected(self):
        with self.assertRaisesRegex(ValueError,'ConnectionCycle'):
            validate_connection(self.parents,'arm','arm','soft',{'soft'},[.5])
        with self.assertRaisesRegex(ValueError,'ParentMissing'):
            validate_connection(self.parents,'arm','missing','soft',{'soft'},[.5])

    def test_17_connector_types_not_distance_only(self):
        with self.assertRaisesRegex(ValueError,'ConnectorIncompatible'):
            validate_connection(self.parents,'arm','eye','limbSocket',{'detailSocket'},[.5])

    def test_18_zero_or_nonfinite_chain_diagnosed(self):
        for length in (0,.009,math.nan):
            with self.assertRaisesRegex(ValueError,'DegenerateBoneChain'):
                validate_connection(self.parents,'arm','body','soft',{'soft'},[length])

    def test_19_drag_preview_does_not_commit_recipe(self):
        t=Transaction(self.parents);t.propose([('hand','body','soft',{'soft'},[.5])])
        self.assertEqual(t.parents,self.parents);self.assertEqual(t.generation,1)
        t.commit(1);self.assertEqual(t.parents['hand'],'body');self.assertEqual(t.generation,2)

    def test_20_invalid_mirror_edit_has_no_partial_commit(self):
        t=Transaction(self.parents)
        with self.assertRaisesRegex(ValueError,'ConnectorIncompatible'):
            t.propose([('arm','body','soft',{'soft'},[.5]),('mirrorArm','eye','limbSocket',{'detailSocket'},[.5])])
        self.assertEqual(t.parents,self.parents);self.assertIsNone(t.preview)

    def test_21_stale_commit_refused_without_mutation(self):
        t=Transaction(self.parents);t.propose([('hand','body','soft',{'soft'},[.5])])
        with self.assertRaisesRegex(ValueError,'StaleDragBase'):t.commit(0)
        self.assertEqual(t.parents,self.parents);self.assertEqual(t.generation,1)

    def test_22_cancel_keeps_original_parent_graph(self):
        t=Transaction(self.parents);t.propose([('hand','body','soft',{'soft'},[.5])]);t.cancel()
        self.assertEqual(t.parents,self.parents);self.assertIsNone(t.preview)

    def test_23_undo_restores_content_with_new_generation(self):
        t=Transaction(self.parents);t.propose([('hand','body','soft',{'soft'},[.5])]);t.commit(1);t.undo()
        self.assertEqual(t.parents,self.parents);self.assertEqual(t.generation,3)

    def test_24_repeated_preview_uses_committed_base(self):
        t=Transaction(self.parents);edit=[('hand','body','soft',{'soft'},[.5])]
        a=t.propose(edit);b=t.propose(edit)
        self.assertEqual(a,b);self.assertEqual(t.parents,self.parents);self.assertEqual(len(t.history),1)

    def test_25_invalid_sample_cannot_commit_older_preview(self):
        t=Transaction(self.parents);t.propose([('hand','body','soft',{'soft'},[.5])])
        with self.assertRaisesRegex(ValueError,'ConnectionCycle'):
            t.propose([('arm','hand','soft',{'soft'},[.5])])
        with self.assertRaisesRegex(ValueError,'NoValidPreview'):t.commit(1)
        self.assertEqual(t.parents,self.parents)

    def test_26_mirror_partners_must_exist(self):
        validate_mirror_pairs(self.parents,{'arm':'mirrorArm','mirrorArm':'arm'})
        with self.assertRaisesRegex(ValueError,'MirrorPartnerMissing'):
            validate_mirror_pairs(self.parents,{'arm':'missing'})

    def test_27_mirror_mapping_reciprocal_and_not_self(self):
        for pairs in ({'arm':'arm'},{'arm':'mirrorArm'}):
            with self.assertRaisesRegex(ValueError,'MirrorNotReciprocal'):
                validate_mirror_pairs(self.parents,pairs)

    def test_28_empty_chain_and_extra_root_diagnosed(self):
        with self.assertRaisesRegex(ValueError,'DegenerateBoneChain'):
            validate_connection(self.parents,'arm','body','soft',{'soft'},[])
        invalid=dict(self.parents);invalid['orphan']=None
        with self.assertRaisesRegex(ValueError,'InvalidRootCount'):
            validate_connection(invalid,'arm','body','soft',{'soft'},[.5])

    def test_29_declared_local_mirror_axis_matches_mount_frame(self):
        a,f=cylinder_mount(.7,.3,.2);b,g=cylinder_mount(.7,.3,math.pi-.2)
        source=roll_frame(f,.3);partner=roll_frame(g,-.3)
        signs=(1,-1,1)
        reflected=tuple((-col[0]*sign,col[1]*sign,col[2]*sign) for col,sign in zip(source,signs))
        for got,want in zip(reflected,partner):
            for x,y in zip(got,want):self.assertAlmostEqual(x,y)
        self.assertAlmostEqual(determinant(partner),1)

    def test_30_user_roll_socket_alignment_applied_once(self):
        p,f=cylinder_mount(.4,.3,0);f=roll_frame(f,math.pi/2);socket=(.03,.02,-.05)
        origin=part_origin_for_socket(p,f,socket)
        for a,b in zip(origin,(.45,.03,.32)):self.assertAlmostEqual(a,b)
        for a,b in zip(add(origin,rotate_by_frame(f,socket)),p):self.assertAlmostEqual(a,b)


if __name__=='__main__':unittest.main(verbosity=2)
