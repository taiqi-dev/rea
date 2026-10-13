"""Independent editor/motion binding examples, not original PCTP semantics."""
from dataclasses import dataclass
import math
import unittest


class BindingError(ValueError):
    pass


@dataclass(frozen=True)
class ProfileKey:
    definition: str
    role: str
    channel: int


@dataclass(frozen=True)
class Command:
    space: str
    part_id: str
    revision: int
    role: str
    channel: int
    value: float


HAND = ProfileKey('own-hand-v3', 'hand', 1)
MOUTH = ProfileKey('own-mouth-v2', 'mouth', 1)
PROFILES = {
    HAND: {'neutral': .2, 'positive_degrees': 40, 'negative_degrees': 10,
           'output_bone': 'finger', 'semantic': 'Grip'},
    MOUTH: {'neutral': .3, 'positive_degrees': 30, 'negative_degrees': 5,
            'output_bone': 'jaw', 'semantic': 'Open'}
}


def build_part(part_id, definition, role, revision, width_parameter=.5,
               connected=True, enabled=True, grasp=1, bone_indices=None):
    if not math.isfinite(width_parameter) or not 0 <= width_parameter <= 1:
        raise BindingError('ShapeParameterInvalid')
    width = .03 + .02 * width_parameter
    profiles = {key: value for key, value in PROFILES.items()
                if key.definition == definition and key.role == role}
    if not profiles:
        raise BindingError('DefinitionRoleMissing')
    indices = {'finger': 0, 'jaw': 1} if bone_indices is None else bone_indices
    for profile in profiles.values():
        if profile['output_bone'] not in indices:
            raise BindingError('StableBoneMappingMissing')
    return {'id': part_id, 'definition': definition, 'role': role, 'revision': revision,
            'width': width, 'shape_parameter': width_parameter,
            'connected': connected, 'enabled': enabled, 'grasp': grasp,
            'profiles': profiles, 'bone_indices': indices}


def sample_own_delta(profile, value):
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise BindingError('MotionValueOutOfRange')
    neutral = profile['neutral']
    if not 0 < neutral < 1:
        raise BindingError('ProfileNeutralInvalid')
    if value >= neutral:
        return profile['positive_degrees'] * (value - neutral) / (1 - neutral)
    return profile['negative_degrees'] * (value - neutral) / neutral


def bind_motion(part, command):
    if command.space != 'Motion':
        raise BindingError('ParameterSpaceMismatch')
    if command.part_id != part['id']:
        raise BindingError('PartInstanceMismatch')
    if command.revision != part['revision']:
        raise BindingError('StaleBodyRevision')
    if not part['connected'] or not part['enabled']:
        raise BindingError('PartUnavailable')
    key = ProfileKey(part['definition'], command.role, command.channel)
    if key not in part['profiles']:
        raise BindingError('RequiredProfileMissing')
    profile = part['profiles'][key]
    delta = sample_own_delta(profile, command.value)
    return {'part_id': part['id'], 'bone_id': profile['output_bone'],
            'bone_index': part['bone_indices'][profile['output_bone']], 'delta_degrees': delta}


def grip_candidates(parts):
    available, rejected = [], []
    for part in parts:
        reason = None
        if not part['connected'] or not part['enabled']:
            reason = 'PartUnavailable'
        elif part['grasp'] < 1:
            reason = 'CapabilityInsufficient'
        elif not any(v['semantic'] == 'Grip' for v in part['profiles'].values()):
            reason = 'RequiredProfileMissing'
        if reason:
            rejected.append({'part_id':part['id'],'reason':reason})
        else:
            available.append(part['id'])
    return {'available':available,'rejected':rejected}


def compile_catalog(rows):
    result = {}
    for alias, role in rows:
        if alias in result:
            raise BindingError('DuplicateAlias')
        result[alias] = role
    return result


class BindingExamples(unittest.TestCase):
    def hand(self, **kwargs):
        return build_part('H1', 'own-hand-v3', 'hand', 12, **kwargs)

    def request(self, **kwargs):
        values = {'space':'Motion','part_id':'H1','revision':12,'role':'hand','channel':1,'value':.6}
        values.update(kwargs)
        return Command(**values)

    def test_complete_widen_then_grip(self):
        part = self.hand(width_parameter=.75)
        result = bind_motion(part, self.request())
        self.assertAlmostEqual(part['width'], .045)
        self.assertAlmostEqual(result['delta_degrees'], 20)
        self.assertEqual(part['shape_parameter'], .75)

    def test_shape_cannot_enter_motion(self):
        with self.assertRaisesRegex(BindingError, 'SpaceMismatch'):
            bind_motion(self.hand(), self.request(space='Shape'))

    def test_role_and_definition_namespace(self):
        hand = self.hand()
        mouth = build_part('M1', 'own-mouth-v2', 'mouth', 12)
        self.assertNotEqual(HAND, MOUTH)
        self.assertAlmostEqual(bind_motion(hand, self.request())['delta_degrees'], 20)
        r=bind_motion(mouth,self.request(part_id='M1',role='mouth',value=.6))
        self.assertAlmostEqual(r['delta_degrees'], 90/7)

    def test_wrong_role_is_diagnostic(self):
        with self.assertRaisesRegex(BindingError, 'RequiredProfileMissing'):
            bind_motion(self.hand(),self.request(role='mouth'))

    def test_neutral_is_not_zero(self):
        self.assertAlmostEqual(bind_motion(self.hand(),self.request(value=.2))['delta_degrees'],0)
        self.assertAlmostEqual(bind_motion(self.hand(),self.request(value=0))['delta_degrees'],-10)

    def test_joint_target_fresh_no_accumulation(self):
        part=self.hand()
        a=bind_motion(part,self.request());b=bind_motion(part,self.request())
        self.assertEqual(a,b)
        self.assertAlmostEqual(b['delta_degrees'],20)

    def test_two_instances_do_not_share_requests(self):
        with self.assertRaisesRegex(BindingError, 'InstanceMismatch'):
            bind_motion(self.hand(),self.request(part_id='H2'))

    def test_revision_rejects_old_request(self):
        with self.assertRaisesRegex(BindingError, 'StaleBodyRevision'):
            bind_motion(self.hand(),self.request(revision=11))

    def test_bone_array_reorder_keeps_stable_mapping(self):
        a=bind_motion(self.hand(),self.request())
        b=bind_motion(self.hand(bone_indices={'finger':7,'jaw':0}),self.request())
        self.assertEqual(a['bone_id'],b['bone_id'])
        self.assertNotEqual(a['bone_index'],b['bone_index'])

    def test_missing_bone_mapping(self):
        with self.assertRaisesRegex(BindingError,'MappingMissing'):
            self.hand(bone_indices={'jaw':0})

    def test_decorative_part_and_required_profile(self):
        normal=self.hand()
        decor=build_part('H2','own-hand-v3','hand',12,grasp=0)
        broken=build_part('H3','own-hand-v3','hand',12);broken['profiles']={}
        result=grip_candidates([normal,decor,broken])
        self.assertEqual(result['available'],['H1'])
        self.assertEqual([r['reason'] for r in result['rejected']],
                         ['CapabilityInsufficient','RequiredProfileMissing'])
        with self.assertRaisesRegex(BindingError,'DefinitionRoleMissing'):
            build_part('H4','unknown-definition','hand',12)

    def test_detached_part_cannot_execute(self):
        part=self.hand(connected=False)
        self.assertEqual(grip_candidates([part])['available'],[])
        with self.assertRaisesRegex(BindingError,'Unavailable'):
            bind_motion(part,self.request())

    def test_duplicate_alias_not_last_write_wins(self):
        with self.assertRaisesRegex(BindingError,'DuplicateAlias'):
            compile_catalog([('Grasper','hand'),('Grasper','mouth')])

    def test_invalid_motion_target(self):
        for value in (math.nan,-.1,1.1):
            with self.assertRaisesRegex(BindingError,'OutOfRange'):
                bind_motion(self.hand(),self.request(value=value))

    def test_user_local_orientation_preserved(self):
        # Own policy: widening updates placement but preserves authored/user rotation.
        a,b=self.hand(width_parameter=.5),self.hand(width_parameter=.75)
        mount_yaw=20
        delta=bind_motion(b,self.request())['delta_degrees']
        self.assertEqual(mount_yaw+delta,40)
        self.assertAlmostEqual((b['width']-a['width'])/2,.0025)


if __name__ == '__main__':
    unittest.main(verbosity=2)
