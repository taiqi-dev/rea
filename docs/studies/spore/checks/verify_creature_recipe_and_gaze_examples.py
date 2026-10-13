"""Independent recipe compiler and constrained-angle examples; not Spore code."""
import argparse
import copy
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import unittest

from read_creature_recipe_and_gaze_metadata import xml_observations, creaturedata_header
from read_selected_ability_properties import FormatError, digest


CATALOG = {
    'torso': [('root', (0,0,0))], 'head':[('head',(0,0,0))],
    'eye':[('eye',(0,0,0))], 'mouth':[('jaw',(0,0,0)),('tip',(0,.2,0))],
    'arm':[('shoulder',(0,0,0)),('elbow',(.6,0,0)),('wrist',(.5,0,0))],
    'grasper':[('palm',(0,0,0)),('finger',(.2,0,0))],
    'leg':[('hip',(0,0,0)),('knee',(0,0,-.5)),('ankle',(0,0,-.5))],
    'foot':[('foot',(0,0,0))],
}


def add(a,b):return tuple(x+y for x,y in zip(a,b))


def own_recipe():
    parts=[]
    def part(ident,definition,parent=None,socket=None,offset=(0,0,0),side=1,level=1):
        parts.append(dict(id=ident,definition=definition,parent=parent,socket=socket,
                          offset=list(offset),side=side,scale=1.0,level=level))
    part('S0','torso')
    part('S1','torso','S0','root',(0,1,0));part('S2','torso','S1','root',(0,1,0))
    for i,side in enumerate((-1,1)):
        h='H'+str(i);part(h,'head','S2','root',(.4*side,.4,.5))
        part('M'+str(i),'mouth',h,'head',(0,.25,-.12))
        for eye,eside in enumerate((-1,1)):
            part('E'+str(i*2+eye),'eye',h,'head',(.12*eside,.2,.1))
    for i in range(4):
        side=-1 if i%2==0 else 1
        part('A'+str(i),'arm','S2' if i<2 else 'S1','root',(side,0,.3),side)
        part('G'+str(i),'grasper','A'+str(i),'wrist',(.1*side,0,0),side,[1,2,1,3][i])
    for i in range(6):
        side=-1 if i%2==0 else 1
        part('L'+str(i),'leg','S'+str(i//2),'root',(.6*side,0,-.3),side)
        part('F'+str(i),'foot','L'+str(i),'ankle',(0,.15,0),side)
    return dict(schema=1,recipe_id='own-four-hands-six-feet-two-heads',parts=parts,
                coordinates='metres; +Y forward,+Z up; identity reference rotations',asset_version='own-catalog-v1')


def compile_recipe(recipe):
    parts=recipe['parts'];lookup={p['id']:p for p in parts}
    if len(parts)!=len(lookup):raise ValueError('duplicate stable part ID')
    if len(parts)>1000:raise ValueError('part budget')
    if sum(p['parent'] is None for p in parts)!=1:raise ValueError('one root required')
    order=[];visiting=set();seen=set()
    def visit(ident):
        if ident in visiting:raise ValueError('parent cycle')
        if ident in seen:return
        if ident not in lookup:raise ValueError('missing parent')
        visiting.add(ident);p=lookup[ident]
        if p['parent'] is not None:visit(p['parent'])
        visiting.remove(ident);seen.add(ident);order.append(ident)
    for p in parts:visit(p['id'])
    bones={};part_bones={};capabilities={'Grasp':[],'Walk':[],'Bite':[]};sockets=[]
    for ident in order:
        p=lookup[ident];definition=p['definition']
        if definition not in CATALOG:raise ValueError('missing asset definition')
        if not math.isfinite(p['scale']) or p['scale']<=0:raise ValueError('nonpositive scale')
        if len(p['offset'])!=3 or not all(math.isfinite(v) for v in p['offset']):raise ValueError('invalid transform')
        parent=None;origin=(0,0,0)
        if p['parent'] is not None:
            parent=(p['parent'],p['socket'])
            if parent not in bones:raise ValueError('missing socket bone')
            origin=bones[parent]['bind_position']
        position=add(origin,p['offset']);ids=[]
        for joint,relative in CATALOG[definition]:
            position=add(position,tuple(v*p['scale']*(p['side'] if axis==0 else 1) for axis,v in enumerate(relative)))
            bone=(ident,joint);bones[bone]=dict(parent=parent,bind_position=position)
            ids.append(bone);parent=bone
        part_bones[ident]=ids
        if p['parent'] is not None:sockets.append(dict(part=ident,host_bone=list((p['parent'],p['socket'])),local_offset=p['offset']))
        cap={'grasper':'Grasp','foot':'Walk','mouth':'Bite'}.get(definition)
        if cap:
            if not isinstance(p['level'],int) or p['level']<1:raise ValueError('invalid provider level')
            capabilities[cap].append(dict(part=ident,level=p['level']))
    palette=sorted(bones);indices={bone:i for i,bone in enumerate(palette)}
    roles={name:[provider['part'] for provider in rows] for name,rows in capabilities.items()}
    return dict(parts=len(parts),bones=bones,part_bones=part_bones,palette=palette,indices=indices,
                sockets=sockets,capabilities=capabilities,roles=roles,
                levels={name:max((p['level'] for p in providers),default=0) for name,providers in capabilities.items()})


def normalized_weights(bundle, contributions):
    weights={}
    for bone,value in contributions:
        if bone not in bundle['bones']:raise ValueError('unknown influence bone')
        if not math.isfinite(value) or value<0:raise ValueError('invalid weight')
        weights[bone]=weights.get(bone,0)+value
    total=sum(weights.values())
    if total<=1e-12:raise ValueError('no positive weight')
    return {bone:v/total for bone,v in weights.items() if v>0}


def skin_translation(bind_position,weights,pose_deltas):
    return tuple(bind_position[axis]+sum(weight*pose_deltas.get(bone,(0,0,0))[axis]
                                        for bone,weight in weights.items()) for axis in range(3))


def detach_subtree(recipe,ident):
    if ident not in {p['id'] for p in recipe['parts']}:raise ValueError('unknown detached part')
    removed={ident}
    changed=True
    while changed:
        changed=False
        for p in recipe['parts']:
            if p['parent'] in removed and p['id'] not in removed:removed.add(p['id']);changed=True
    result=copy.deepcopy(recipe);result['parts']=[p for p in result['parts'] if p['id'] not in removed]
    return result,sorted(removed)


def desired_angles(origin,target):
    if len(origin)!=3 or len(target)!=3 or not all(math.isfinite(v) for v in (*origin,*target)):
        raise ValueError('nonfinite target')
    dx,dy,dz=(b-a for a,b in zip(origin,target));horizontal=math.hypot(dx,dy)
    if math.hypot(horizontal,dz)<=1e-8:raise ValueError('coincident target')
    return dict(yaw=math.degrees(math.atan2(dx,dy)),pitch=math.degrees(math.atan2(dz,horizontal)))


def clamp(v,limit):return min(limit,max(-limit,v))


def allocate_attention(requests,limits,torso_limits,torso_locked=None,neck_locked=None):
    """Own two-axis illustrative allocation; not unrestricted 3D IK."""
    torso_locked=torso_locked or {};neck_locked=neck_locked or {}
    if len({r['head'] for r in requests})!=len(requests):raise ValueError('duplicate head assignment')
    if any(not math.isfinite(v) or v<0 for v in torso_limits.values()):raise ValueError('invalid torso limit')
    for r in requests:
        if r['head'] not in limits:raise ValueError('missing head profile')
        if any(not math.isfinite(v) for v in (r['yaw'],r['pitch'],r['priority'])):raise ValueError('invalid request')
        if any(not math.isfinite(v) or v<0 for axis in limits[r['head']].values() for v in axis.values()):
            raise ValueError('invalid organ limit')
    ranked=sorted(requests,key=lambda r:(-r['priority'],r['head']))
    torso={};outputs={}
    for axis in ('yaw','pitch'):
        if axis in torso_locked:
            torso[axis]=torso_locked[axis]
            if not math.isfinite(torso[axis]) or abs(torso[axis])>torso_limits[axis]:raise ValueError('invalid torso lock')
        elif ranked:
            r=ranked[0];ls=limits[r['head']][axis];fixed=neck_locked.get((r['head'],axis))
            offered=(r[axis]-fixed-clamp(r[axis]-fixed,ls['eye'])) if fixed is not None else r[axis]-clamp(r[axis],ls['eye']+ls['neck'])
            torso[axis]=clamp(offered,torso_limits[axis])
        else:torso[axis]=0
        for r in ranked:
            ls=limits[r['head']][axis];remaining=r[axis]-torso[axis]
            fixed=neck_locked.get((r['head'],axis))
            if fixed is None:
                eye=clamp(remaining,ls['eye']);neck=clamp(remaining-eye,ls['neck'])
            else:
                if not math.isfinite(fixed) or abs(fixed)>ls['neck']:raise ValueError('invalid neck lock')
                neck=fixed;eye=clamp(remaining-neck,ls['eye'])
            realized=torso[axis]+neck+eye
            outputs.setdefault(r['head'],{})[axis]=dict(eye=eye,neck=neck,world=realized,error=r[axis]-realized)
    return dict(torso=torso,heads=outputs,shared_torso_policy='highest priority; head ID tie-break; motion lock respected')


def smooth_angle(current,goal,max_speed,dt):
    if not all(math.isfinite(v) for v in (current,goal,max_speed,dt)) or max_speed<0 or dt<0:raise ValueError('invalid smoothing')
    delta=(goal-current+180)%360-180
    return current+clamp(delta,max_speed*dt)


def attention_memory(now,seen,ttl,body_revision,soul_revision,current_body,current_soul):
    if not all(math.isfinite(v) for v in (now,seen,ttl)) or ttl<0 or seen>now:raise ValueError('invalid memory time')
    if (body_revision,soul_revision)!=(current_body,current_soul):return 'stale-owner'
    return 'remembered' if now-seen<=ttl else 'lost'


LIMITS={'H0':{'yaw':{'eye':25,'neck':50},'pitch':{'eye':15,'neck':20}},
        'H1':{'yaw':{'eye':20,'neck':35},'pitch':{'eye':15,'neck':20}}}
REQUESTS=[dict(head='H0',yaw=80,pitch=20,priority=100),dict(head='H1',yaw=-60,pitch=-10,priority=20)]
TORSO={'yaw':20,'pitch':10}


class RecipeTests(unittest.TestCase):
    def test_complete_counts(self):
        b=compile_recipe(own_recipe());self.assertEqual((b['parts'],len(b['bones'])),(31,57))
        self.assertEqual({k:len(v) for k,v in b['roles'].items()},{'Grasp':4,'Walk':6,'Bite':2})
    def test_sockets_reference_exact_host(self):
        b=compile_recipe(own_recipe());self.assertEqual(b['bones'][('G2','palm')]['parent'],('A2','wrist'))
    def test_joint_bind_position(self):
        self.assertEqual(compile_recipe(own_recipe())['bones'][('G2','palm')]['bind_position'],(-2.2,1,.3))
    def test_duplicate_part(self):
        r=own_recipe();r['parts'].append(copy.deepcopy(r['parts'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):compile_recipe(r)
    def test_missing_parent(self):
        r=own_recipe();r['parts'][1]['parent']='missing'
        with self.assertRaisesRegex(ValueError,'missing parent'):compile_recipe(r)
    def test_cycle(self):
        r=own_recipe();r['parts'][1]['parent']='S2'
        with self.assertRaisesRegex(ValueError,'cycle'):compile_recipe(r)
    def test_missing_asset(self):
        r=own_recipe();r['parts'][1]['definition']='missing'
        with self.assertRaisesRegex(ValueError,'asset'):compile_recipe(r)
    def test_missing_socket(self):
        r=own_recipe();r['parts'][1]['socket']='missing'
        with self.assertRaisesRegex(ValueError,'socket'):compile_recipe(r)
    def test_bad_scale(self):
        r=own_recipe();r['parts'][1]['scale']=0
        with self.assertRaisesRegex(ValueError,'scale'):compile_recipe(r)
    def test_nonfinite_transform(self):
        r=own_recipe();r['parts'][1]['offset'][0]=float('nan')
        with self.assertRaisesRegex(ValueError,'transform'):compile_recipe(r)
    def test_weights_normalize(self):
        b=compile_recipe(own_recipe());w=normalized_weights(b,[(('S1','root'),2),(('A2','shoulder'),3)])
        self.assertEqual(w,{('S1','root'):.4,('A2','shoulder'):.6})
    def test_unknown_influence(self):
        with self.assertRaisesRegex(ValueError,'unknown'):normalized_weights(compile_recipe(own_recipe()),[(('missing','root'),1)])
    def test_zero_weights(self):
        with self.assertRaisesRegex(ValueError,'positive'):normalized_weights(compile_recipe(own_recipe()),[(('S1','root'),0)])
    def test_negative_weights(self):
        with self.assertRaisesRegex(ValueError,'invalid'):normalized_weights(compile_recipe(own_recipe()),[(('S1','root'),-1)])
    def test_skin_motion(self):
        b=compile_recipe(own_recipe());w=normalized_weights(b,[(('S1','root'),2),(('A2','shoulder'),3)])
        self.assertEqual(skin_translation((-.4,1,.3),w,{('A2','shoulder'):(0,0,.2)}),(-.4,1,.42))
    def test_bind_identity(self):
        b=compile_recipe(own_recipe());w=normalized_weights(b,[(('G2','finger'),1)])
        self.assertEqual(skin_translation((1,2,3),w,{}),(1,2,3))
    def test_stable_identity_after_detach(self):
        r=own_recipe();after,removed=detach_subtree(r,'A0');b=compile_recipe(after)
        self.assertEqual(removed,['A0','G0']);self.assertEqual((b['parts'],len(b['bones'])),(29,52))
        self.assertIn(('G2','palm'),b['bones']);self.assertEqual(len(b['roles']['Grasp']),3)
    def test_unknown_detach(self):
        with self.assertRaisesRegex(ValueError,'unknown'):detach_subtree(own_recipe(),'not-present')
    def test_provider_max_not_sum(self):self.assertEqual(compile_recipe(own_recipe())['levels']['Grasp'],3)
    def test_xml_count_error(self):
        with self.assertRaises(FormatError):xml_observations(b'<sporemodel><blocks count="2"/></sporemodel>')
    def test_xml_entity_rejected(self):
        with self.assertRaises(FormatError):xml_observations(b'<!DOCTYPE x><sporemodel/>')
    def test_creaturedata_truncation(self):
        with self.assertRaises(FormatError):creaturedata_header(b'123')


class GazeTests(unittest.TestCase):
    def test_target_angles(self):
        a=desired_angles((0,0,0),(1,1,math.sqrt(2)));self.assertAlmostEqual(a['yaw'],45);self.assertAlmostEqual(a['pitch'],45)
    def test_coincident(self):
        with self.assertRaisesRegex(ValueError,'coincident'):desired_angles((0,0,0),(0,0,0))
    def test_nonfinite_target(self):
        with self.assertRaisesRegex(ValueError,'nonfinite'):desired_angles((0,0,0),(math.nan,0,0))
    def test_multi_head_shared_trunk(self):
        p=allocate_attention(REQUESTS,LIMITS,TORSO);self.assertEqual(p['torso'],{'yaw':5,'pitch':0})
        self.assertEqual(p['heads']['H0']['yaw'],dict(eye=25,neck=50,world=80,error=0))
        self.assertEqual(p['heads']['H1']['yaw'],dict(eye=-20,neck=-35,world=-50,error=-10))
    def test_pitch_allocated(self):
        p=allocate_attention(REQUESTS,LIMITS,TORSO);self.assertEqual(p['heads']['H0']['pitch']['eye'],15)
        self.assertEqual(p['heads']['H0']['pitch']['neck'],5)
    def test_motion_lock_respected(self):
        p=allocate_attention(REQUESTS,LIMITS,TORSO,{'yaw':0});self.assertEqual(p['heads']['H0']['yaw']['error'],5)
    def test_attack_neck_lock_respected(self):
        p=allocate_attention(REQUESTS,LIMITS,TORSO,{'yaw':0},{('H0','yaw'):20})
        self.assertEqual(p['heads']['H0']['yaw'],dict(eye=25,neck=20,world=45,error=35))
    def test_duplicate_head(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):allocate_attention([REQUESTS[0],REQUESTS[0]],LIMITS,TORSO)
    def test_missing_profile(self):
        with self.assertRaisesRegex(ValueError,'missing'):allocate_attention([dict(head='absent',yaw=1,pitch=0,priority=1)],LIMITS,TORSO)
    def test_negative_limit(self):
        with self.assertRaisesRegex(ValueError,'limit'):allocate_attention(REQUESTS,LIMITS,{'yaw':-1,'pitch':1})
    def test_invalid_lock(self):
        with self.assertRaisesRegex(ValueError,'lock'):allocate_attention(REQUESTS,LIMITS,TORSO,{'yaw':100})
    def test_empty_attention(self):self.assertEqual(allocate_attention([],LIMITS,TORSO)['heads'],{})
    def test_angular_rate(self):self.assertEqual(smooth_angle(0,80,90,.1),9)
    def test_angle_wrap(self):self.assertEqual(smooth_angle(179,-179,90,.1),181)
    def test_invalid_dt(self):
        with self.assertRaisesRegex(ValueError,'smoothing'):smooth_angle(0,1,90,-.1)
    def test_target_memory(self):self.assertEqual(attention_memory(.2,0,.25,8,3,8,3),'remembered')
    def test_lost_target(self):self.assertEqual(attention_memory(.4,0,.25,8,3,8,3),'lost')
    def test_soul_change(self):self.assertEqual(attention_memory(.1,0,.25,8,3,8,4),'stale-owner')
    def test_body_change(self):self.assertEqual(attention_memory(.1,0,.25,8,3,9,3),'stale-owner')
    def test_future_memory(self):
        with self.assertRaisesRegex(ValueError,'time'):attention_memory(0,1,.25,8,3,8,3)


def summary_example():
    recipe=own_recipe();bundle=compile_recipe(recipe);after,removed=detach_subtree(recipe,'A0');rebuilt=compile_recipe(after)
    weights=normalized_weights(bundle,[(('S1','root'),2),(('A2','shoulder'),3)])
    return dict(recipe=recipe,parts=bundle['parts'],bones=len(bundle['bones']),
        palette=[dict(index=i,bone_id=list(bone),parent=list(bundle['bones'][bone]['parent']) if bundle['bones'][bone]['parent'] else None,
                      bind_position=bundle['bones'][bone]['bind_position']) for i,bone in enumerate(bundle['palette'])],
        capabilities=bundle['capabilities'],levels=bundle['levels'],
        attack_binding=dict(executor='G2',palm_index=bundle['indices'][('G2','palm')],
                            auxiliary='A2',elbow_index=bundle['indices'][('A2','elbow')],socket_host=['A2','wrist']),
        skin_example=dict(bind_position=[-.4,1,.3],weights=[dict(bone=list(k),weight=v,palette_index=bundle['indices'][k]) for k,v in weights.items()],
                          posed_position=skin_translation((-.4,1,.3),weights,{('A2','shoulder'):(0,0,.2)}),UV_copies_share_logical_weights=True),
        detach=dict(removed=removed,parts=rebuilt['parts'],bones=len(rebuilt['bones']),grasper_providers=len(rebuilt['roles']['Grasp']),
                    retained_G2_id=['G2','palm'],before_index=bundle['indices'][('G2','palm')],after_index=rebuilt['indices'][('G2','palm')]))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(RecipeTests),
                             unittest.defaultTestLoader.loadTestsFromTestCase(GazeTests)])
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ev=Path(__file__).resolve().parent.parent/'evidence';inputs=[]
    for name in ('complete-creature-recipe-observations.json','gaze-head-attention-observations.json'):
        p=ev/name;inputs.append(dict(path=str(p.resolve()),sha256=digest(p.read_bytes())))
    documents=[]
    for name in ('50-complete-creature-recipe-runtime-bones-and-bindings.md',
                 '52-gaze-head-orientation-and-multi-organ-attention.md'):
        p=ev.parent/name;documents.append(dict(path=str(p.resolve()),sha256=digest(p.read_bytes())))
    outcome=dict(schema_version=1,modules=[50,52],timestamp_utc=datetime.now(timezone.utc).isoformat(),
        tests_run=result.testsRun,recipe_tests=22,gaze_tests=20,failures=len(result.failures),errors=len(result.errors),
        status='passed' if result.wasSuccessful() else 'failed',log=stream.getvalue(),evidence_inputs=inputs,document_inputs=documents,
        recipe_example=summary_example(),gaze_example=dict(requests=REQUESTS,limits=LIMITS,torso_limits=TORSO,
            steady=allocate_attention(REQUESTS,LIMITS,TORSO),
            attack_locked=allocate_attention(REQUESTS,LIMITS,TORSO,{'yaw':0},{('H0','yaw'):20}),
            first_frame_yaw=dict(eye=smooth_angle(0,25,180,.1),neck=smooth_angle(0,50,90,.1),torso=smooth_angle(0,5,45,.1))),
        verifier_sha256=digest(Path(__file__).read_bytes()),
        limitations='Own translation-only reference compiler and bounded two-axis angle examples; not full mesh/IK/physics/asset loader, not Spore behavior.')
    args.output.write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:outcome[k] for k in ('tests_run','failures','errors','status')}))
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
