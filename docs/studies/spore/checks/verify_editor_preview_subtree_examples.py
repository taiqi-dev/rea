"""Independent preview isolation and subtree editing examples, not game runtime."""
from dataclasses import dataclass,replace
import copy
import json
import math
from pathlib import Path
import unittest


@dataclass(frozen=True)
class BodyKey:
    generation:int
    digest:str


@dataclass(frozen=True)
class TestResult:
    key:BodyKey
    suite:str
    outcomes:tuple
    measurements:tuple


class Sandbox:
    def __init__(self,key,current_key):
        if key!=current_key:raise ValueError('StalePreviewBody')
        self.key=key;self.epoch=1;self.running=True;self.damage=0;self.rewards=0
        self.resources={'actor':'Owned','dummy':'Owned','world':'Owned'};self.events=set()
    def effect(self,event_id,kind,target_realm,amount):
        if not self.running:raise ValueError('PreviewDisposed')
        if target_realm!='Sandbox':raise ValueError('CrossWorldPreviewEffect')
        if kind!='DummyDamage':raise ValueError('PreviewRewardForbidden')
        if not isinstance(amount,(int,float)) or not math.isfinite(amount) or amount<0:
            raise ValueError('InvalidPreviewDamage')
        if event_id in self.events:return 'Duplicate'
        self.events.add(event_id);self.damage+=amount;return 'RecordedDummyDamage'
    def callback(self,key,epoch):
        if not self.running or key!=self.key or epoch!=self.epoch:raise ValueError('SupersededPreviewCallback')
    def dispose(self,fail_resource=None):
        self.running=False;self.epoch+=1
        for key in self.resources:
            if self.resources[key] in ('Owned','CleanupFailedOwned'):
                self.resources[key]='CleanupFailedOwned' if key==fail_resource else 'Released'


def measure_case(reach,desired,belly_min,leg_length,horizontal,omega,hip_radius,conflict=False):
    if any(not math.isfinite(x) for x in (reach,desired,belly_min,leg_length,horizontal,omega,hip_radius)):
        raise ValueError('NonFiniteFunctionalInput')
    if min(reach,leg_length)<=0 or min(desired,horizontal,belly_min,hip_radius)<0:
        raise ValueError('InvalidFunctionalInput')
    support_upper=math.sqrt(leg_length**2-horizontal**2) if horizontal<=leg_length else None
    return {'Reach':'Pass' if desired<=reach else 'Fail',
            'Support':'Pass' if support_upper is not None and belly_min<=support_upper else 'Fail',
            'SharedOutput':'Fail' if conflict else 'Pass',
            'TurnHipSpeed':abs(omega)*hip_radius,'SupportUpper':support_upper}


def accept_result(result,current_key,required=('Reach','Support','SharedOutput'),expected_suite='suite1'):
    if result.key!=current_key:raise ValueError('StaleFunctionalResult')
    if len({k for k,v in result.outcomes})!=len(result.outcomes):raise ValueError('DuplicateFunctionalOutcome')
    if len({k for k,v in result.measurements})!=len(result.measurements):raise ValueError('DuplicateFunctionalMetric')
    outcomes=dict(result.outcomes)
    if not result.suite:raise ValueError('MissingSuiteIdentity')
    if result.suite!=expected_suite:raise ValueError('SupersededTestSuite')
    if any(name not in outcomes for name in required):raise ValueError('FunctionalCoverageIncomplete')
    if any(outcomes[name]!='Pass' for name in required):raise ValueError('FunctionalValidationFailed')
    metrics=dict(result.measurements)
    if any(name not in metrics for name in required):raise ValueError('FunctionalMetricsMissing')
    if any(not math.isfinite(metrics[name]) or metrics[name]>.005 or metrics[name]<0 for name in required):
        raise ValueError('FunctionalMetricContradiction')
    return 'AcceptCurrentDesign'


@dataclass(frozen=True)
class Part:
    ident:str
    definition:str
    parent:str|None
    length:float
    angle:float
    cost:int
    shape:tuple=()
    mirror:str|None=None
    parent_socket:str='mount'
    child_sockets:tuple=()
    reference_mount:tuple=(0.,0.)


def validate(parts):
    ids=[p.ident for p in parts]
    if len(ids)!=len(set(ids)):raise ValueError('DuplicatePartId')
    lookup={p.ident:p for p in parts}
    if sum(p.parent is None for p in parts)!=1:raise ValueError('RootCountInvalid')
    for p in parts:
        if p.length<0 or not math.isfinite(p.length) or not math.isfinite(p.angle):raise ValueError('InvalidPartReference')
        if not isinstance(p.cost,int) or p.cost<0:raise ValueError('InvalidPartCost')
        if p.mirror is not None:
            if p.mirror not in lookup:raise ValueError('MirrorPartnerMissing')
            if lookup[p.mirror].mirror!=p.ident or p.mirror==p.ident:raise ValueError('MirrorMappingInvalid')
        seen=set();node=p
        while node.parent is not None:
            if node.ident in seen:raise ValueError('ParentCycle')
            seen.add(node.ident)
            if node.parent not in lookup:raise ValueError('ParentMissing')
            node=lookup[node.parent]
    return lookup


def subtree(parts,root):
    lookup=validate(parts)
    if root not in lookup:raise ValueError('SubtreeRootMissing')
    out={root};changed=True
    while changed:
        new={p.ident for p in parts if p.parent in out}
        changed=bool(new-out);out|=new
    return out


def copy_subtree(parts,root,new_host,id_map,new_reference_mount=None):
    old=validate(parts);members=subtree(parts,root)
    if new_host not in old:raise ValueError('ParentMissing')
    if set(id_map)!=members or len(set(id_map.values()))!=len(members) or set(id_map.values())&set(old):
        raise ValueError('InvalidCopyIdMap')
    clones=[];diagnostics=[]
    for p in parts:
        if p.ident not in members:continue
        mirror=id_map.get(p.mirror)
        if p.mirror is not None and p.mirror not in members:diagnostics.append('ExternalMirrorRelationCleared')
        clones.append(replace(p,ident=id_map[p.ident],parent=new_host if p.ident==root else id_map[p.parent],
                              shape=copy.deepcopy(p.shape),mirror=mirror,
                              reference_mount=new_reference_mount if p.ident==root and new_reference_mount is not None else p.reference_mount))
    out=tuple(parts)+tuple(clones);validate(out)
    return out,diagnostics


def replace_parent(parts,old_id,new_part,socket_map,accepted_shape_names):
    lookup=validate(parts)
    if old_id not in lookup:raise ValueError('ReplacementMissing')
    if new_part.ident in lookup:raise ValueError('ReplacementIdCollision')
    old=lookup[old_id]
    if old.mirror is not None:raise ValueError('MirroredReplacementRequiresPairTransaction')
    if any(name not in accepted_shape_names for name,value in old.shape):raise ValueError('ShapeParameterUnsupported')
    children=[p for p in parts if p.parent==old_id]
    if any(p.ident not in socket_map for p in children):raise ValueError('ChildSocketMigrationMissing')
    if any(socket_map[p.ident] not in new_part.child_sockets for p in children):raise ValueError('UnknownReplacementSocket')
    if len(set(socket_map[p.ident] for p in children))!=len(children):raise ValueError('ChildSocketCapacityExceeded')
    new_part=replace(new_part,parent=old.parent,shape=copy.deepcopy(old.shape),reference_mount=old.reference_mount)
    out=tuple(new_part if p.ident==old_id else replace(p,parent=new_part.ident,parent_socket=socket_map[p.ident]) if p.parent==old_id else p for p in parts)
    validate(out);return out


def reparent(parts,root,new_host,new_reference_mount=None):
    members=subtree(parts,root)
    if new_host in members:raise ValueError('ReparentIntoDescendant')
    out=tuple(replace(p,parent=new_host,reference_mount=new_reference_mount if new_reference_mount is not None else p.reference_mount) if p.ident==root else p for p in parts);validate(out);return out


def validate_ai_plan(parts,current_generation,plan_generation,executor):
    if current_generation!=plan_generation:raise ValueError('StaleAIPlan')
    if executor not in validate(parts):raise ValueError('ExecutorMissing')
    return 'CurrentExecutorBinding'


def chain_tip(parts,ids,mount=None):
    lookup=validate(parts);x,y=lookup[ids[0]].reference_mount if mount is None else mount;angle=0
    for ident in ids:
        p=lookup[ident];angle+=p.angle;r=math.radians(angle)
        x+=p.length*math.cos(r);y+=p.length*math.sin(r)
    return x,y


class Editor:
    def __init__(self,parts,wallet=120):
        validate(parts);self.parts=parts;self.wallet=wallet;self.generation=1;self.history=[parts]
    def commit(self,candidate,expected):
        if expected!=self.generation:raise ValueError('StaleEditTransaction')
        validate(candidate);delta=sum(p.cost for p in candidate)-sum(p.cost for p in self.parts)
        if delta>self.wallet:raise ValueError('InsufficientEditBudget')
        self.wallet-=delta;self.parts=candidate;self.generation+=1;self.history.append(candidate)
    def undo(self):
        if len(self.history)<2:raise ValueError('NothingToUndo')
        previous=self.history[-2];self.commit(previous,self.generation)
        self.history=self.history[:-2]


def fixture():
    return (Part('Body','Body',None,0,0,0),Part('U','Upper','Body',.5,30,20,(('thickness',.1),),reference_mount=(.4,0)),
            Part('F','Fore','U',.4,-20,15),Part('H','Palm','F',.1,0,10),
            Part('D1','Finger','H',.08,15,5),Part('D2','Finger','H',.06,-10,5))


def new_upper():
    return Part('U2','Upper2','Body',.35,30,25,child_sockets=('elbowMount',))


class PreviewExamples(unittest.TestCase):
    def test_01_old_body_preview_refused(self):
        with self.assertRaisesRegex(ValueError,'StalePreviewBody'):Sandbox(BodyKey(42,'A'),BodyKey(43,'B'))
    def test_02_dummy_effect_isolated_and_deduplicated(self):
        s=Sandbox(BodyKey(43,'B'),BodyKey(43,'B'))
        self.assertEqual(s.effect('hit0','DummyDamage','Sandbox',7),'RecordedDummyDamage')
        self.assertEqual(s.effect('hit0','DummyDamage','Sandbox',7),'Duplicate')
        self.assertEqual(s.damage,7);self.assertEqual(s.rewards,0)
    def test_03_world_effect_and_rewards_rejected(self):
        s=Sandbox(BodyKey(43,'B'),BodyKey(43,'B'))
        with self.assertRaisesRegex(ValueError,'CrossWorldPreviewEffect'):s.effect('a','DummyDamage','World',7)
        with self.assertRaisesRegex(ValueError,'PreviewRewardForbidden'):s.effect('b','Reward','Sandbox',7)
        self.assertEqual(s.damage,0)
    def test_04_new_body_case_exposes_support_failure(self):
        m=measure_case(1,.8,.55,.6,.3,1,.7)
        self.assertEqual(m['Reach'],'Pass');self.assertEqual(m['Support'],'Fail')
        self.assertAlmostEqual(m['SupportUpper'],.5196152422706632);self.assertAlmostEqual(m['TurnHipSpeed'],.7)
    def test_05_adjusted_foot_case_and_output_conflict(self):
        m=measure_case(1,.8,.55,.6,.2,1,.7,True)
        self.assertEqual(m['Support'],'Pass');self.assertEqual(m['SharedOutput'],'Fail')
    def test_06_incomplete_or_failed_result_not_accept(self):
        k=BodyKey(43,'B')
        for outcomes,reason in [((), 'FunctionalCoverageIncomplete'),((('Reach','Pass'),('Support','Fail'),('SharedOutput','Pass')),'FunctionalValidationFailed')]:
            with self.assertRaisesRegex(ValueError,reason):accept_result(TestResult(k,'suite1',outcomes,()),k)
    def test_07_pass_result_must_match_current_generation(self):
        k=BodyKey(43,'B');r=TestResult(k,'suite1',(('Reach','Pass'),('Support','Pass'),('SharedOutput','Pass')),
                                     (('Reach',0.),('Support',0.),('SharedOutput',0.)))
        self.assertEqual(accept_result(r,k),'AcceptCurrentDesign')
        with self.assertRaisesRegex(ValueError,'StaleFunctionalResult'):accept_result(r,BodyKey(44,'B'))
    def test_08_disposal_rejects_callbacks_and_keeps_failed_cleanup_owner(self):
        k=BodyKey(43,'B');s=Sandbox(k,k);s.dispose('actor')
        self.assertEqual(s.resources['actor'],'CleanupFailedOwned')
        with self.assertRaisesRegex(ValueError,'SupersededPreviewCallback'):s.callback(k,1)
        s.dispose();self.assertEqual(s.resources['actor'],'Released')
    def test_09_invalid_measurements_keep_diagnostics(self):
        with self.assertRaisesRegex(ValueError,'NonFiniteFunctionalInput'):measure_case(1,.8,.55,.6,math.nan,1,.7)
    def test_10_real_selected_preview_resource_fields(self):
        j=json.loads((Path(__file__).resolve().parent.parent/'evidence/local-selected-editor-preview-properties.json').read_text(encoding='utf-8'))
        self.assertEqual(len(j['records']),10)
        for r in j['records']:
            n=r['instance_names'][0]['name'];f=r['selected_fields']
            self.assertIn('animID',f)
            if n=='creature_rest_pose':self.assertEqual(f['animRespondsToEvent']['values'][0]['instance'],'0x6581b78e')
            if n=='creature_button_attack_1':self.assertEqual(f['animName']['values'],['_final/creature/com_bite'])

    def test_21_missing_metrics_or_stale_suite_cannot_accept(self):
        k=BodyKey(43,'B');r=TestResult(k,'suite1',(('Reach','Pass'),('Support','Pass'),('SharedOutput','Pass')),())
        with self.assertRaisesRegex(ValueError,'FunctionalMetricsMissing'):accept_result(r,k)
        with self.assertRaisesRegex(ValueError,'SupersededTestSuite'):accept_result(replace(r,suite='old'),k)
        with self.assertRaisesRegex(ValueError,'FunctionalMetricContradiction'):
            accept_result(replace(r,measurements=(('Reach',.02),('Support',0.),('SharedOutput',0.))),k)

    def test_22_disposed_sandbox_cannot_apply_effect(self):
        k=BodyKey(43,'B');s=Sandbox(k,k);s.dispose()
        with self.assertRaisesRegex(ValueError,'PreviewDisposed'):s.effect('hit0','DummyDamage','Sandbox',7)
        self.assertEqual(s.damage,0)

    def test_27_invalid_damage_cannot_poison_dummy_or_event_ledger(self):
        k=BodyKey(43,'B');s=Sandbox(k,k)
        for amount in (math.nan,math.inf,-1,'7'):
            with self.assertRaisesRegex(ValueError,'InvalidPreviewDamage'):s.effect('hit0','DummyDamage','Sandbox',amount)
        self.assertEqual(s.damage,0);self.assertFalse(s.events)

    def test_28_duplicate_result_fields_not_folded_silently(self):
        k=BodyKey(43,'B');r=TestResult(k,'suite1',(('Reach','Pass'),('Reach','Fail')),())
        with self.assertRaisesRegex(ValueError,'DuplicateFunctionalOutcome'):accept_result(r,k)
        r=replace(r,outcomes=(('Reach','Pass'),),measurements=(('Reach',0.),('Reach',.1)))
        with self.assertRaisesRegex(ValueError,'DuplicateFunctionalMetric'):accept_result(r,k)


class SubtreeExamples(unittest.TestCase):
    def test_11_copy_all_descendants_with_new_ids(self):
        parts=fixture();ids={x:'copy_'+x for x in ('U','F','H','D1','D2')};out,diag=copy_subtree(parts,'U','Body',ids)
        self.assertEqual(len(out),11);self.assertFalse(diag)
        self.assertEqual(validate(out)['copy_D1'].parent,'copy_H');self.assertEqual(validate(out)['D1'].parent,'H')
        self.assertAlmostEqual(sum(p.cost for p in out)-sum(p.cost for p in parts),55)
    def test_12_copy_id_collision_or_incomplete_map_rejected(self):
        for m in ({'U':'U'},{'U':'a'}):
            with self.assertRaisesRegex(ValueError,'InvalidCopyIdMap'):copy_subtree(fixture(),'U','Body',m)
    def test_13_replacement_retains_descendant_ids(self):
        out=replace_parent(fixture(),'U',new_upper(),{'F':'elbowMount'},{'thickness'})
        self.assertNotIn('U',validate(out));self.assertEqual(validate(out)['F'].parent,'U2')
        self.assertTrue({'F','H','D1','D2'}<=set(validate(out)))
        self.assertEqual(validate(out)['F'].parent_socket,'elbowMount')
    def test_14_replacement_displacement_from_reference_chain(self):
        before=chain_tip(fixture(),['U','F','H','D1'])
        out=replace_parent(fixture(),'U',new_upper(),{'F':'elbowMount'},{'thickness'})
        after=chain_tip(out,['U2','F','H','D1'])
        self.assertAlmostEqual(after[0]-before[0],-.15*math.cos(math.pi/6))
        self.assertAlmostEqual(after[1]-before[1],-.075)
        self.assertEqual(validate(out)['D1'].length,.08)
    def test_15_missing_socket_or_shape_mapping_rejected(self):
        new=new_upper()
        with self.assertRaisesRegex(ValueError,'ChildSocketMigrationMissing'):replace_parent(fixture(),'U',new,{}, {'thickness'})
        with self.assertRaisesRegex(ValueError,'ShapeParameterUnsupported'):replace_parent(fixture(),'U',new,{'F':'elbow'},set())
    def test_16_reparent_keeps_id_but_refuses_descendant_cycle(self):
        out=reparent(fixture(),'F','Body');self.assertEqual(validate(out)['F'].parent,'Body')
        with self.assertRaisesRegex(ValueError,'ReparentIntoDescendant'):reparent(fixture(),'U','D1')
    def test_17_copy_cost_and_undo_preserve_external_reward(self):
        e=Editor(fixture());out,_=copy_subtree(e.parts,'U','Body',{x:'copy_'+x for x in ('U','F','H','D1','D2')})
        e.commit(out,1);self.assertEqual(e.wallet,65);e.wallet+=7;e.undo()
        self.assertEqual(e.wallet,127);self.assertEqual(e.parts,fixture());self.assertEqual(e.generation,3)
    def test_18_replacement_delta_cost_is_five(self):
        e=Editor(fixture());out=replace_parent(e.parts,'U',new_upper(),{'F':'elbowMount'},{'thickness'})
        e.commit(out,1);self.assertEqual(e.wallet,115)
    def test_19_budget_or_stale_transaction_keeps_original(self):
        e=Editor(fixture(),wallet=1);out,_=copy_subtree(e.parts,'U','Body',{x:'copy_'+x for x in ('U','F','H','D1','D2')})
        with self.assertRaisesRegex(ValueError,'InsufficientEditBudget'):e.commit(out,1)
        with self.assertRaisesRegex(ValueError,'StaleEditTransaction'):e.commit(out,0)
        self.assertEqual(e.parts,fixture());self.assertEqual(e.generation,1)
    def test_20_duplicate_or_missing_parent_graph_diagnosed(self):
        with self.assertRaisesRegex(ValueError,'DuplicatePartId'):validate(fixture()+(fixture()[1],))
        with self.assertRaisesRegex(ValueError,'ParentMissing'):validate(tuple(replace(p,parent='missing') if p.ident=='D1' else p for p in fixture()))

    def test_23_negative_cost_never_turns_copy_into_reward(self):
        bad=tuple(replace(p,cost=-20) if p.ident=='U' else p for p in fixture())
        with self.assertRaisesRegex(ValueError,'InvalidPartCost'):Editor(bad)

    def test_24_external_mirror_copy_relation_explicitly_cleared(self):
        parts=(Part('Body','Body',None,0,0,0),Part('A','Upper','Body',.5,0,20,mirror='B'),
               Part('B','Upper','Body',.5,0,20,mirror='A'))
        out,diag=copy_subtree(parts,'A','Body',{'A':'C'})
        self.assertEqual(validate(out)['C'].mirror,None)
        self.assertEqual(diag,['ExternalMirrorRelationCleared']);self.assertEqual(validate(out)['A'].mirror,'B')

    def test_25_retained_hand_still_invalidates_old_ai_plan(self):
        out=replace_parent(fixture(),'U',new_upper(),{'F':'elbowMount'},{'thickness'})
        with self.assertRaisesRegex(ValueError,'StaleAIPlan'):validate_ai_plan(out,2,1,'H')
        self.assertEqual(validate_ai_plan(out,2,2,'H'),'CurrentExecutorBinding')

    def test_26_removed_upper_not_redirected_to_copy(self):
        out=replace_parent(fixture(),'U',new_upper(),{'F':'elbowMount'},{'thickness'})
        with self.assertRaisesRegex(ValueError,'ExecutorMissing'):validate_ai_plan(out,2,2,'U')

    def test_29_unknown_replacement_socket_rejects_without_charging(self):
        e=Editor(fixture())
        with self.assertRaisesRegex(ValueError,'UnknownReplacementSocket'):
            replace_parent(e.parts,'U',new_upper(),{'F':'missingPort'},{'thickness'})
        self.assertEqual(e.wallet,120);self.assertEqual(e.parts,fixture());self.assertEqual(e.generation,1)

    def test_30_complete_copy_replace_reparent_and_three_undos(self):
        original=fixture()+(Part('Chest','Patch','Body',0,0,0),);e=Editor(original)
        ids={x:'copy_'+x for x in ('U','F','H','D1','D2')}
        out,_=copy_subtree(e.parts,'U','Body',ids,(.4,1));e.commit(out,1)
        self.assertAlmostEqual(chain_tip(e.parts,['copy_U','copy_F','copy_H','copy_D1'])[1],1.370633549772721)
        e.commit(replace_parent(e.parts,'U',new_upper(),{'F':'elbowMount'},{'thickness'}),2)
        e.commit(reparent(e.parts,'U2','Chest',(.7,.2)),3)
        self.assertAlmostEqual(chain_tip(e.parts,['U2','F','H','D1'])[0],1.5680173907935895)
        self.assertEqual(e.wallet,60);e.wallet+=7
        e.undo();self.assertEqual(validate(e.parts)['U2'].reference_mount,(.4,0));self.assertEqual(e.wallet,67)
        e.undo();self.assertIn('U',validate(e.parts));self.assertEqual(e.wallet,72)
        e.undo();self.assertEqual(e.parts,original);self.assertEqual(e.wallet,127);self.assertEqual(e.generation,7)


if __name__=='__main__':unittest.main(verbosity=2)
