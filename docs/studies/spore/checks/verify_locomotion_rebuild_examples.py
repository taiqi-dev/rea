"""Independent unusual-body locomotion and editor-cache state examples."""
from dataclasses import dataclass
import math
import unittest


def length_groups(lengths, ratio_limit=1.25):
    if not lengths or any(not math.isfinite(x) or x<=0 for x in lengths):
        raise ValueError('InvalidChainLength')
    groups=[]
    for x in sorted(lengths):
        if not groups or x/groups[-1][0]>ratio_limit:groups.append([x])
        else:groups[-1].append(x)
    return groups


def frequency_ratio(longest, group_length):
    desired=longest/group_length
    return min((.5,1.,2.),key=lambda r:(abs(math.log(r/desired)),r))


def support_height(intervals, belly_min):
    lo=max([belly_min]+[a for a,b in intervals]);hi=min(b for a,b in intervals)
    return (lo,hi) if lo<=hi else None


def leg_upper(length, horizontal, foot_z=0):
    if not math.isfinite(length) or not math.isfinite(horizontal) or length<=0 or horizontal<0:
        raise ValueError('InvalidReachData')
    if horizontal>length:return None
    return foot_z+math.sqrt(length*length-horizontal*horizontal)


def eligible_foot(normal_dot, can_support, geometry_current):
    return geometry_current and can_support and normal_dot>=math.cos(math.pi/4)


def select_mode(eligible_feet, approved_crawl, approved_hover):
    if eligible_feet:return 'Legged'
    if approved_crawl:return 'Crawl'
    if approved_hover:return 'Hover'
    return 'Disabled'


@dataclass
class Foot:
    state: str
    touchdown_at: float
    anchor: float


def advance_stop(foot, now, confirmed_contact):
    if foot.state=='Swing' and now>=foot.touchdown_at:
        foot.state='Stance' if confirmed_contact else 'NoContact'
    return foot.state


def hip_speed(vx, omega, radius):
    return math.hypot(vx, omega*radius)


def transition(old_mode,new_mode,root,shared_anchor,valid_contacts):
    if new_mode in ('Legged','Crawl') and valid_contacts<1:
        raise ValueError('TransitionContactMissing')
    return {'mode':new_mode,'root':root,'shared_anchor':shared_anchor,'transition_done':True}


@dataclass(frozen=True)
class Recipe:
    digest: str
    parts: tuple
    roles: tuple


@dataclass(frozen=True)
class Bundle:
    digest: str
    generation: int
    components: tuple
    bone_map: dict
    capabilities: tuple


@dataclass
class Job:
    generation: int
    digest: str
    cancel_requested: bool=False
    resource_state: str='Owned'
    completion_disposition: str|None=None


class EditorModel:
    def __init__(self,recipe):
        self.generation=1;self.recipe=recipe;self.history=[recipe];self.cursor=0
        self.pending=None;self.installed=None;self.events=[];self.content_cache={}

    def apply(self,recipe,record=True):
        self.generation+=1;self.recipe=recipe
        if record:
            self.history=self.history[:self.cursor+1]+[recipe];self.cursor+=1
        self.pending=(self.generation,recipe.digest)
        self.events.append(('InvalidateBindings',self.generation))

    def undo(self):
        if self.cursor==0:raise ValueError('NothingToUndo')
        self.cursor-=1;self.apply(self.history[self.cursor],False)

    def redo(self):
        if self.cursor+1>=len(self.history):raise ValueError('NothingToRedo')
        self.cursor+=1;self.apply(self.history[self.cursor],False)

    def start_latest(self):
        if self.pending is None:raise ValueError('NoPendingBuild')
        generation,digest=self.pending;self.pending=None
        return Job(generation,digest)

    def complete(self,job,bundle,cleanup_ok=True):
        if job.completion_disposition is not None:
            if cleanup_ok and job.resource_state=='CleanupFailedOwned':
                job.resource_state='Transferred' if job.completion_disposition=='Installed' else 'Released'
                self.events.append(('CleanupRetried',job.generation))
            self.events.append(('DuplicateCompletion',job.generation));return 'Duplicate'
        if (job.generation,job.digest)!=(self.generation,self.recipe.digest):
            result='Superseded'
        elif (bundle.generation,bundle.digest)!=(self.generation,self.recipe.digest):
            result='BundleIdentityMismatch'
        elif len(bundle.components)!=4:
            result='MissingBundleComponents'
        elif any(k!=(bundle.generation,bundle.digest) for k in bundle.components):
            result='MixedBundle'
        elif set(bundle.bone_map)!=set(self.recipe.parts) or bundle.capabilities!=self.recipe.roles:
            result='BodyContractMismatch'
        else:
            self.installed=bundle;self.content_cache[bundle.digest]=bundle;result='Installed'
        job.completion_disposition=result
        job.resource_state=('Transferred' if result=='Installed' else 'Released') if cleanup_ok else 'CleanupFailedOwned'
        self.events.append((result,job.generation));return result


def bundle_for(editor, generation=None, digest=None, components=None):
    g=editor.generation if generation is None else generation
    d=editor.recipe.digest if digest is None else digest
    return Bundle(d,g,((g,d),)*4 if components is None else components,
                  {p:i for i,p in enumerate(editor.recipe.parts)},editor.recipe.roles)


def remap_action(part_id,expected_generation,bundle):
    if expected_generation!=bundle.generation:raise ValueError('StaleActionBinding')
    if part_id not in bundle.bone_map:raise ValueError('ExecutorMissing')
    return bundle.bone_map[part_id]


class LocomotionExamples(unittest.TestCase):
    def test_01_long_short_groups(self):
        gs=length_groups([.9,.6,.9,.9,.6,.9]);self.assertEqual(list(map(len,gs)),[2,4])
        self.assertEqual(frequency_ratio(.9,.6),2);self.assertEqual(frequency_ratio(.9,.9),1)

    def test_02_group_ratio_boundary(self):
        self.assertEqual(length_groups([1,1.25]),[[1,1.25]])
        self.assertEqual(length_groups([1,1.2501]),[[1],[1.2501]])
        with self.assertRaisesRegex(ValueError,'InvalidChainLength'):length_groups([0])

    def test_03_short_legs_limit_body_height(self):
        upper=leg_upper(.6,.3);self.assertAlmostEqual(upper,.5196152422706632)
        self.assertIsNotNone(support_height([(.1,upper)],.45))
        self.assertIsNone(support_height([(.1,upper)],.55))
        self.assertGreater(leg_upper(.6,.2),.56)

    def test_04_sideways_foot_not_automatically_support(self):
        self.assertFalse(eligible_foot(0,True,True));self.assertFalse(eligible_foot(1,False,True))
        self.assertFalse(eligible_foot(1,True,False));self.assertTrue(eligible_foot(1,True,True))

    def test_05_no_feet_requires_explicit_mode(self):
        self.assertEqual(select_mode(0,True,False),'Crawl')
        self.assertEqual(select_mode(0,False,True),'Hover')
        self.assertEqual(select_mode(0,False,False),'Disabled')

    def test_06_stop_does_not_freeze_airborne_foot(self):
        f=Foot('Swing',.25,.3)
        self.assertEqual(advance_stop(f,.2,True),'Swing')
        self.assertEqual(advance_stop(f,.25,True),'Stance');self.assertEqual(f.anchor,.3)

    def test_07_failed_landing_not_fake_stance(self):
        f=Foot('Swing',.25,.3);self.assertEqual(advance_stop(f,.25,False),'NoContact')

    def test_08_turning_has_nonzero_hip_speed(self):
        self.assertAlmostEqual(hip_speed(0,1,.4),.4)
        self.assertAlmostEqual(hip_speed(0,1,.7),.7)

    def test_09_transition_preserves_root_and_retained_anchor(self):
        r=transition('Legged','Crawl',(2,.4),(.5,0),2)
        self.assertEqual(r['root'],(2,.4));self.assertEqual(r['shared_anchor'],(.5,0))
        with self.assertRaisesRegex(ValueError,'TransitionContactMissing'):
            transition('Legged','Crawl',(2,.4),None,0)


class RebuildExamples(unittest.TestCase):
    def setUp(self):
        self.a=Recipe('A',('H1','H2'),('strike','grasp'))
        self.b=Recipe('B',('H2','H1'),('strike','grasp'))
        self.c=Recipe('C',('H2','W1'),('glide','grasp'))
        self.e=EditorModel(self.a)

    def test_10_continuous_edits_coalesce_pending(self):
        self.e.apply(self.b);self.e.apply(self.c)
        j=self.e.start_latest();self.assertEqual((j.generation,j.digest),(3,'C'))

    def test_11_late_job_after_edit_rejected(self):
        self.e.apply(self.b);j=self.e.start_latest();old=bundle_for(self.e)
        self.e.apply(self.c);self.assertEqual(self.e.complete(j,old),'Superseded')
        self.assertIsNone(self.e.installed);self.assertEqual(j.resource_state,'Released')

    def test_12_undo_uses_new_generation(self):
        self.e.apply(self.b);j=self.e.start_latest();old=bundle_for(self.e)
        self.e.undo();self.assertEqual((self.e.generation,self.e.recipe.digest),(3,'A'))
        self.assertEqual(self.e.complete(j,old),'Superseded')

    def test_13_redo_does_not_accept_old_matching_digest_job(self):
        self.e.apply(self.b);j=self.e.start_latest();old=bundle_for(self.e)
        self.e.undo();self.e.redo();self.assertEqual(self.e.recipe.digest,'B')
        self.assertEqual(self.e.generation,4);self.assertEqual(self.e.complete(j,old),'Superseded')

    def test_14_mixed_mesh_bind_capability_bundle_refused(self):
        self.e.apply(self.b);j=self.e.start_latest()
        b=bundle_for(self.e,components=((2,'B'),(1,'A'),(2,'B'),(2,'B')))
        self.assertEqual(self.e.complete(j,b),'MixedBundle');self.assertIsNone(self.e.installed)

    def test_15_cancel_is_request_not_completion_guarantee(self):
        self.e.apply(self.b);j=self.e.start_latest();j.cancel_requested=True;old=bundle_for(self.e)
        self.e.apply(self.c);self.assertEqual(self.e.complete(j,old),'Superseded')

    def test_16_duplicate_completion_no_second_release(self):
        self.e.apply(self.b);j=self.e.start_latest();b=bundle_for(self.e)
        self.assertEqual(self.e.complete(j,b),'Installed')
        self.assertEqual(self.e.complete(j,b),'Duplicate');self.assertEqual(j.resource_state,'Transferred')

    def test_17_cleanup_failure_retains_ownership(self):
        self.e.apply(self.b);j=self.e.start_latest();b=bundle_for(self.e);self.e.apply(self.c)
        self.assertEqual(self.e.complete(j,b,False),'Superseded')
        self.assertEqual(j.resource_state,'CleanupFailedOwned')

    def test_18_remapping_uses_stable_identity(self):
        self.e.apply(self.b);b=bundle_for(self.e)
        self.assertEqual(remap_action('H1',2,b),1)
        with self.assertRaisesRegex(ValueError,'StaleActionBinding'):remap_action('H1',1,b)

    def test_19_removed_executor_not_substituted(self):
        self.e.apply(self.c);b=bundle_for(self.e)
        with self.assertRaisesRegex(ValueError,'ExecutorMissing'):remap_action('H1',2,b)

    def test_20_new_edit_after_undo_discards_redo_branch(self):
        self.e.apply(self.b);self.e.undo();self.e.apply(self.c)
        with self.assertRaisesRegex(ValueError,'NothingToRedo'):self.e.redo()

    def test_21_valid_current_bundle_installs_all_contracts(self):
        self.e.apply(self.c);j=self.e.start_latest();b=bundle_for(self.e)
        self.assertEqual(self.e.complete(j,b),'Installed')
        self.assertEqual(self.e.installed.capabilities,('glide','grasp'))
        self.assertEqual(self.e.installed.bone_map,{'H2':0,'W1':1})

    def test_22_empty_or_partial_bundle_refused(self):
        for components in ((),((1,'A'),)):
            j=Job(1,'A');b=bundle_for(self.e,components=components)
            self.assertEqual(self.e.complete(j,b),'MissingBundleComponents')
            self.assertIsNone(self.e.installed)

    def test_23_installed_cleanup_failure_cannot_publish_again(self):
        self.e.apply(self.b);j=self.e.start_latest();b=bundle_for(self.e)
        self.assertEqual(self.e.complete(j,b,False),'Installed')
        self.assertEqual(j.resource_state,'CleanupFailedOwned')
        self.assertEqual(j.completion_disposition,'Installed')
        self.assertEqual(self.e.complete(j,b,False),'Duplicate')
        self.assertEqual(self.e.complete(j,b,True),'Duplicate')
        self.assertEqual(j.resource_state,'Transferred')
        self.assertEqual(sum(e[0]=='Installed' for e in self.e.events),1)

    def test_24_superseded_cleanup_retry_cannot_reprocess_result(self):
        self.e.apply(self.b);j=self.e.start_latest();b=bundle_for(self.e);self.e.apply(self.c)
        self.assertEqual(self.e.complete(j,b,False),'Superseded')
        self.assertEqual(self.e.complete(j,b,True),'Duplicate')
        self.assertEqual(j.resource_state,'Released')
        self.assertEqual(sum(e[0]=='Superseded' for e in self.e.events),1)


if __name__=='__main__':unittest.main(verbosity=2)
