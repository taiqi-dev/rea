"""Independent calibration/transfer specification checks, not a game AI."""
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
import unittest


@dataclass(frozen=True)
class MetricKey:
    body_life: str
    provider: str
    mode: str
    dependency_digest: str
    context: str = 'distance1.0-1.5/movingMedium/flat'
    domain: str = 'editorProtocolV1'
    motor_style: str = 'normalV1'
    solver: str = 'ownSolverV1'
    technique: str = 'techniqueV1'
    learner: str = 'soulS1life'


@dataclass
class Evidence:
    success: int = 0
    failure: int = 0
    prior_a: float = 1.
    prior_b: float = 1.
    transfer_weight: float = 0.
    origins: list = field(default_factory=list)

    def estimate(self, penalty=1.):
        if any(isinstance(n,bool) or not isinstance(n,int) or n<0 for n in (self.success,self.failure)):
            raise ValueError('InvalidObservationCount')
        if not all(math.isfinite(x) for x in (self.prior_a,self.prior_b,penalty)) or min(self.prior_a,self.prior_b)<=0 or penalty<0:
            raise ValueError('InvalidPriorOrPenalty')
        a,b=self.prior_a+self.success,self.prior_b+self.failure
        mean=a/(a+b)
        sigma=math.sqrt(a*b/((a+b)**2*(a+b+1)))
        return {'mean':mean,'sigma':sigma,'score_probability':max(0.,mean-penalty*sigma),
                'real_observations':self.success+self.failure}


@dataclass(frozen=True)
class Attempt:
    identity: str
    key: MetricKey
    body_revision: int
    control_generation: int
    committed: bool


class CalibrationBook:
    def __init__(self):
        self.records={};self.history_records={};self.attempts={};self.receipts={};self.diagnostics=[]

    def register(self,attempt):
        if attempt.identity in self.attempts:raise ValueError('DuplicateAttemptIdentity')
        self.attempts[attempt.identity]=attempt

    def observe(self,identity,outcome,current_key,current_revision,current_control):
        if identity not in self.attempts:raise ValueError('UnknownAttempt')
        if identity in self.receipts:
            if self.receipts[identity]!=outcome:raise ValueError('ConflictingOutcomeReceipt')
            return 'DuplicateOutcome'
        attempt=self.attempts[identity]
        allowed={'Hit','ValidMiss','Busy','TargetGone','Interrupted','NoMeasurement','InvalidPose'}
        if outcome not in allowed:raise ValueError('UnknownOutcomeKind')
        self.receipts[identity]=outcome
        if outcome not in ('Hit','ValidMiss') or not attempt.committed:
            self.diagnostics.append((identity,outcome,'CensoredOrUncommitted'))
            return 'NotHitEvidence'
        current=(attempt.key==current_key and attempt.body_revision==current_revision
                 and attempt.control_generation==current_control)
        if current:
            evidence=self.records.setdefault(attempt.key,Evidence())
        else:
            base=self.records.get(attempt.key,Evidence())
            evidence=self.history_records.setdefault(attempt.key,replace(base,origins=list(base.origins)))
        if outcome=='Hit':evidence.success+=1
        else:evidence.failure+=1
        return 'CurrentEvidence' if current else 'HistoricalEvidenceOnly'

    def get(self,key):
        return self.records.get(key,Evidence())


def warm_prior(source,source_technique,target_technique,compatibility,weight_cap=2.):
    if not math.isfinite(weight_cap) or not 0<=weight_cap<=2:
        raise ValueError('InvalidTransferWeight')
    required={'same_program_version','same_provider_role','same_chain_topology',
              'compatible_mount_frame','shape_delta_within_policy','same_sensing_protocol','same_learner'}
    if set(compatibility)!=required or not all(isinstance(v,bool) for v in compatibility.values()):
        raise ValueError('IncompleteCompatibilityReceipt')
    if source_technique!=target_technique or not all(compatibility.values()):
        return Evidence(origins=['IncompatibleTransfer'])
    estimate=source.estimate()
    weight=min(weight_cap,float(estimate['real_observations']))
    p=estimate['mean']
    return Evidence(prior_a=1+weight*p,prior_b=1+weight*(1-p),transfer_weight=weight,
                    origins=['CompatibleWeakPriorOnly'])


def rank_probability(evidence,damage,body_cost,soul_cost,duration,risk_loss,hard_allowed=True):
    values=(damage,body_cost,soul_cost,duration,risk_loss)
    if not all(math.isfinite(v) and v>=0 for v in values):raise ValueError('InvalidPlanValue')
    if not hard_allowed:return {'status':'HardRejected','score':None}
    estimate=evidence.estimate()
    score=estimate['score_probability']*damage/30-.25*(body_cost/10+soul_cost/20)-.05*duration-risk_loss/30
    return dict(status='Eligible',score=score,estimate=estimate)


def validate_commit(plan_revision,plan_control,current_revision,current_control,hard_allowed):
    if (plan_revision,plan_control)!=(current_revision,current_control):return 'StalePlan'
    return 'Allowed' if hard_allowed else 'HardRejectedAtCommit'


def admit_probes(probes,time_budget,attempt_budget,hostiles_present=False):
    if not math.isfinite(time_budget) or time_budget<0 or isinstance(attempt_budget,bool) or not isinstance(attempt_budget,int) or attempt_budget<0:
        raise ValueError('InvalidProbeBudget')
    if hostiles_present:return [],'ProbeUnsafeContext'
    if len({p['id'] for p in probes})!=len(probes):raise ValueError('DuplicateProbeIdentity')
    for p in probes:
        if not math.isfinite(p['seconds']) or p['seconds']<=0:raise ValueError('InvalidProbeDuration')
        if isinstance(p['criticality'],bool) or not isinstance(p['criticality'],int) or p['criticality']<0:
            raise ValueError('InvalidProbeCriticality')
    selected=[];spent=0.
    for p in sorted(probes,key=lambda p:(p['criticality'],p['id'])):
        if len(selected)>=attempt_budget:break
        if spent+p['seconds']>time_budget:continue
        selected.append(p);spent+=p['seconds']
    return selected,'Admitted' if len(selected)==len(probes) else 'PartialCoverage'


def scenario():
    right=Evidence(8,2);left=Evidence(4,2);soul=Evidence(5,1)
    before={'RightClaw':rank_probability(right,30,6,0,.7,3),
            'LeftClaw':rank_probability(left,20,4,0,.5,2),
            'SoulBolt':rank_probability(soul,24,0,8,.6,1)}
    after=dict(before);after['RightClaw']=rank_probability(Evidence(),30,6,0,.7,3)
    measured=dict(after);measured['RightClaw']=rank_probability(Evidence(4,0),30,6,0,.7,3)
    return {'before':before,'after_shape_change':after,'after_four_new_trials':measured}


class PosteriorChecks(unittest.TestCase):
    def test_no_observations_remain_uncertain(self):
        e=Evidence().estimate();self.assertEqual(e['mean'],.5)
        self.assertAlmostEqual(e['sigma'],math.sqrt(1/12));self.assertEqual(e['real_observations'],0)
    def test_right_hand_counts_and_penalty(self):
        e=Evidence(8,2).estimate();self.assertEqual(e['mean'],.75)
        self.assertAlmostEqual(e['sigma'],math.sqrt(27/1872))
        self.assertAlmostEqual(e['score_probability'],.6299038846461846)
    def test_left_hand_counts_differ(self):
        e=Evidence(4,2).estimate();self.assertEqual(e['mean'],.625)
        self.assertAlmostEqual(e['sigma'],math.sqrt(15/576))
    def test_large_penalty_is_clamped(self):
        self.assertEqual(Evidence().estimate(100)['score_probability'],0.)
    def test_bad_counts_diagnosed(self):
        for n in (-1,.5,True):
            with self.assertRaises(ValueError):Evidence(success=n).estimate()
    def test_nonfinite_prior_and_penalty_diagnosed(self):
        for e in (Evidence(prior_a=0),Evidence(prior_b=float('nan'))):
            with self.assertRaises(ValueError):e.estimate()
        with self.assertRaises(ValueError):Evidence().estimate(-1)


class AttributionChecks(unittest.TestCase):
    def setUp(self):
        self.k=MetricKey('B1life','R','Claw','Rshape1');self.book=CalibrationBook()
    def add(self,ident='A1',committed=True,key=None):
        self.book.register(Attempt(ident,key or self.k,8,3,committed))
    def test_hit_increments_success(self):
        self.add();self.assertEqual(self.book.observe('A1','Hit',self.k,8,3),'CurrentEvidence')
        self.assertEqual(self.book.get(self.k).success,1)
    def test_valid_miss_increments_failure(self):
        self.add();self.book.observe('A1','ValidMiss',self.k,8,3)
        self.assertEqual(self.book.get(self.k).failure,1)
    def test_duplicate_outcome_not_extra_trial(self):
        self.add();self.book.observe('A1','Hit',self.k,8,3)
        self.assertEqual(self.book.observe('A1','Hit',self.k,8,3),'DuplicateOutcome')
        self.assertEqual(self.book.get(self.k).success,1)
        with self.assertRaisesRegex(ValueError,'ConflictingOutcomeReceipt'):
            self.book.observe('A1','ValidMiss',self.k,8,3)
    def test_busy_and_target_gone_not_hit_failures(self):
        for i,outcome in enumerate(('Busy','TargetGone','Interrupted','NoMeasurement','InvalidPose')):
            self.add(str(i));self.assertEqual(self.book.observe(str(i),outcome,self.k,8,3),'NotHitEvidence')
        self.assertEqual(self.book.get(self.k).estimate()['real_observations'],0)
    def test_uncommitted_late_hit_cannot_be_credited(self):
        self.add(committed=False)
        self.assertEqual(self.book.observe('A1','Hit',self.k,8,3),'NotHitEvidence')
    def test_committed_old_body_effect_updates_history_only(self):
        self.add();new=replace(self.k,dependency_digest='Rshape2')
        self.assertEqual(self.book.observe('A1','Hit',new,9,3),'HistoricalEvidenceOnly')
        self.assertEqual(self.book.get(new).estimate()['real_observations'],0)
        self.assertEqual(self.book.history_records[self.k].success,1)
    def test_old_control_cannot_update_current_motor_model(self):
        self.book.records[self.k]=Evidence(8,2)
        self.add();self.assertEqual(self.book.observe('A1','Hit',self.k,8,4),'HistoricalEvidenceOnly')
        self.assertEqual(self.book.get(self.k).success,8)
        self.assertEqual(self.book.history_records[self.k].success,9)
    def test_unknown_and_duplicate_attempt_diagnosed(self):
        with self.assertRaises(ValueError):self.book.observe('unknown','Hit',self.k,8,3)
        self.add()
        with self.assertRaises(ValueError):self.add()
        with self.assertRaises(ValueError):self.book.observe('A1','invented',self.k,8,3)
    def test_new_context_or_combat_domain_has_no_direct_samples(self):
        self.book.records[self.k]=Evidence(8,2)
        for k in (replace(self.k,context='distance2.0-2.5/movingMedium/flat'),replace(self.k,domain='combatV1')):
            self.assertEqual(self.book.get(k).estimate()['real_observations'],0)
    def test_shape_change_does_not_invalidate_unrelated_left_scope(self):
        left=MetricKey('B1life','L','Claw','Lshape1');self.book.records[left]=Evidence(4,2)
        self.assertEqual(self.book.get(left).estimate()['mean'],.625)
        self.assertEqual(self.book.get(replace(self.k,dependency_digest='Rshape2')).estimate()['real_observations'],0)
    def test_clone_and_new_body_do_not_share_observations(self):
        self.book.records[self.k]=Evidence(8,2)
        for key in (replace(self.k,provider='Rclone'),replace(self.k,body_life='B2life')):
            self.assertEqual(self.book.get(key).estimate()['real_observations'],0)
    def test_style_change_separates_motor_calibration(self):
        self.book.records[self.k]=Evidence(8,2)
        self.assertEqual(self.book.get(replace(self.k,motor_style='aggressiveV2')).estimate()['real_observations'],0)
    def test_another_soul_or_technique_has_no_direct_motor_samples(self):
        self.book.records[self.k]=Evidence(8,2)
        for key in (replace(self.k,learner='soulS2life'),replace(self.k,technique='techniqueV2')):
            self.assertEqual(self.book.get(key).estimate()['real_observations'],0)
    def test_array_palette_index_is_not_metric_identity(self):
        key_after_palette_repack=replace(self.k)
        self.assertEqual(self.k,key_after_palette_repack)


class TransferAndPolicyChecks(unittest.TestCase):
    def setUp(self):
        self.receipt={k:True for k in ('same_program_version','same_provider_role','same_chain_topology',
                                     'compatible_mount_frame','shape_delta_within_policy','same_sensing_protocol','same_learner')}
    def test_compatible_transfer_is_capped_weak_prior(self):
        e=warm_prior(Evidence(8,2),'T1','T1',self.receipt)
        self.assertEqual((e.success,e.failure,e.transfer_weight),(0,0,2.))
        self.assertEqual((e.prior_a,e.prior_b),(2.5,1.5))
        self.assertEqual(e.estimate()['mean'],.625)
    def test_no_source_samples_means_no_transfer_weight(self):
        e=warm_prior(Evidence(),'T1','T1',self.receipt);self.assertEqual(e.transfer_weight,0.)
    def test_incompatible_transfer_not_silent_direct_copy(self):
        e=warm_prior(Evidence(8,2),'T1','T2',self.receipt)
        self.assertEqual(e.origins,['IncompatibleTransfer']);self.assertEqual(e.estimate()['mean'],.5)
        e=warm_prior(Evidence(8,2),'T1','T1',dict(self.receipt,same_chain_topology=False))
        self.assertEqual(e.transfer_weight,0.)
        e=warm_prior(Evidence(8,2),'T1','T1',dict(self.receipt,same_learner=False))
        self.assertEqual(e.transfer_weight,0.)
    def test_missing_receipt_or_excess_weight_rejected(self):
        with self.assertRaises(ValueError):warm_prior(Evidence(),'T1','T1',{})
        with self.assertRaises(ValueError):warm_prior(Evidence(),'T1','T1',self.receipt,3)
    def test_hard_condition_not_overridden_by_success_history(self):
        self.assertEqual(rank_probability(Evidence(100,0),30,1,0,.2,0,False)['status'],'HardRejected')
    def test_complete_example_selects_right_then_soul_then_right(self):
        s=scenario()
        best=lambda rows:max(rows,key=lambda n:rows[n]['score'])
        self.assertEqual([best(s[k]) for k in ('before','after_shape_change','after_four_new_trials')],['RightClaw','SoulBolt','RightClaw'])
        self.assertAlmostEqual(s['before']['RightClaw']['score'],.3449038846461846)
        self.assertAlmostEqual(s['after_four_new_trials']['RightClaw']['score'],.4074743,places=6)
    def test_invalid_scoring_values_rejected(self):
        for damage in (-1,float('inf')):
            with self.assertRaises(ValueError):rank_probability(Evidence(),damage,0,0,1,0)
    def test_stale_plan_rechecked_at_commit(self):
        self.assertEqual(validate_commit(8,3,9,3,True),'StalePlan')
        self.assertEqual(validate_commit(8,3,8,3,False),'HardRejectedAtCommit')
    def test_probe_budget_is_bounded_and_repeatable(self):
        probes=[dict(id=f'R{i}',criticality=0,seconds=.9) for i in range(4)]
        selected,status=admit_probes(probes,3.6,4)
        self.assertEqual((len(selected),status),(4,'Admitted'))
        self.assertEqual(len(admit_probes(probes,1.8,4)[0]),2)
    def test_active_hostile_context_does_not_run_editor_probes(self):
        self.assertEqual(admit_probes([],1,1,True),([], 'ProbeUnsafeContext'))
    def test_invalid_probe_time_budget_and_duplicate_id(self):
        with self.assertRaises(ValueError):admit_probes([],float('nan'),1)
        with self.assertRaises(ValueError):admit_probes([dict(id='x',criticality=0,seconds=0)],1,1)
        with self.assertRaisesRegex(ValueError,'InvalidProbeCriticality'):
            admit_probes([dict(id='x',criticality=float('nan'),seconds=.1)],1,1)
        p=dict(id='x',criticality=0,seconds=.1)
        with self.assertRaises(ValueError):admit_probes([p,p],1,2)


class ReferenceChecks(unittest.TestCase):
    def test_existing_study_inputs_match_recorded_identities(self):
        path=Path(__file__).resolve().parent.parent/'evidence/soul-body-calibration-study-references.json'
        j=json.loads(path.read_text(encoding='utf8'))
        self.assertFalse(j['new_original_game_payload_reads'])
        for row in j['inputs']:
            p=Path(row['path']);self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),row['sha256'])


if __name__=='__main__':
    unittest.main(verbosity=2)
