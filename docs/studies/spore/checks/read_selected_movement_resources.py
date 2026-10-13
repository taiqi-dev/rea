"""Read selected movement tuning and GAIT v11 summaries; no game execution.

Format sources: ../evidence/public-gait-format-sources.json. Path curves are
validated but not exported. These observations do not establish runtime use.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from read_selected_ability_properties import Cursor, FormatError, fnv, key_json, read_index, read_prop, refpack


def finite(values):
    if not all(math.isfinite(v) for v in values):
        raise FormatError('nonfinite GAIT numeric data')
    return values


def count(c, minimum_item_bytes):
    value, = c.unpack('<I')
    if value > (len(c.data) - c.pos) // minimum_item_bytes:
        raise FormatError('impossible GAIT count')
    return value


def read_gait(data):
    c = Cursor(data)
    magic, length, version, constant = c.unpack('<IIII')
    if (magic, length, version, constant) != (0x54494147, len(data), 11, 1):
        raise FormatError('unsupported GAIT header or size')
    steps, = c.unpack('<I')
    groups = count(c, 124)
    if steps > (len(data) - c.pos) // 8:
        raise FormatError('impossible step-length key count')
    step_keys = [dict(zip(('speedi', 'stepLength'), finite(c.unpack('<ff')))) for _ in range(steps)]
    names = ('stepGallop stepPhaseBiasH stepPhaseBiasV stepSkew footTilt tiltPoint '
             'toeCurlMax toeCurlBegin toeCurlEnd swayAmplitude swayPhase trackWidthReduction '
             'verticalPhaseOffset sagittalPhaseOffset lateralPhaseOffset maxVerticalOffset '
             'verticalDist walkRunShape maxSagittalOffset maxLateralOffset yawPhaseOffset '
             'pitchPhaseOffset rollPhaseOffset maxYawAngle maxPitchAngle maxRollAngle').split()
    group_keys = []
    spline_tail_counts = {}
    total_path_counts = {'position_keys': 0, 'rotation_keys': 0, 'bend_keys': 0}
    for _ in range(groups):
        speedi, step_height = finite(c.unpack('<ff'))
        taxon, = c.unpack('<i')
        fields = dict(zip(names, finite(c.unpack('<' + 'f' * len(names)))))
        taxa = count(c, 8)
        paths = count(c, 12)
        triggers, duties = [], []
        for _ in range(taxa):
            trigger, duty = finite(c.unpack('<ff'))
            triggers.append(trigger)
            duties.append(duty)
        for _ in range(paths):
            pos_count = count(c, 68)
            rot_count = count(c, 88)
            bend_count = count(c, 28)
            total_bytes = pos_count * 68 + rot_count * 88 + bend_count * 28
            if total_bytes > len(data) - c.pos:
                raise FormatError('GAIT path outside resource')
            for name, num, dimension in [('position_keys', pos_count, 3),
                                         ('rotation_keys', rot_count, 4),
                                         ('bend_keys', bend_count, 1)]:
                total_path_counts[name] += num
                for _ in range(num):
                    c.take(8)  # Serialized vftable and tick, not live pointers.
                    finite(c.unpack('<' + 'f' * dimension))
                    for _ in range(dimension):
                        finite(c.unpack('<ff'))
                        c.take(4)  # Two flags and a short.
                        tail, = c.unpack('<I')
                        # The pinned community reader requires CDCDCDCD here.
                        # Original bytes differ: treat the slot as an opaque
                        # uint32, retain its distribution, and claim no meaning.
                        tail_name = f'0x{tail:08x}'
                        spline_tail_counts[tail_name] = spline_tail_counts.get(tail_name, 0) + 1
        group_keys.append(dict(speedi=speedi, stepHeight=step_height, taxon=taxon,
                               taxon_count=taxa, path_count=paths, triggers=triggers,
                               dutyFactors=duties, **fields))
    if c.pos != len(data):
        raise FormatError('GAIT trailing bytes')
    return dict(version=version, stepLengthKeys=step_keys, gaitGroupKeys=group_keys,
                validated_path_counts=total_path_counts, fully_consumed_bytes=c.pos,
                opaque_spline_tail_counts=spline_tail_counts,
                spline_tail_semantics='opaque uint32; meaning unknown; community reader requires CDCDCDCD but original values differ')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent.parent / 'evidence'
    registry = json.loads((evidence / 'public-land-movement-registry.json').read_text(encoding='utf-8'))
    # Export only requested movement concepts, not unrelated combat/social fields.
    movement_names = set('creatureAvatarMinMouseRadius creatureAvatarMaxMouseRadius '
                         'creatureAvatarWASDTurningSpeed creatureAvatarWASDSlowTurningSpeed '
                         'creatureAvatarGoalStopDistance creatureMouseMoveGoalDistance '
                         'creatureMouseMoveMinRadius creatureDecelerationSpeedMultiplier '
                         'creatureAccelerationSpeedMultiplier creatureBaseAcceleration '
                         'creatureBaseDeceleration globalCreatureSprintSpeedBoost '
                         'creatureScaleMultiplier GaitBlendTime PolypodGaitStyle '
                         'GaitIsWalkingThreshold obstacleUses2DFootprint modelOverrideFootprintRadius '
                         'avoidEnemyDistance avoidEnemyForce avoidStrangerDistance avoidStrangerForce'.split())
    movement_names.update(f'globalCreatureSpeedGear{i}' for i in range(6))
    prop_names = {0xB2CCCB: 'parent'}
    declarations = registry['property_context'] + next(
        item['selected_declarations'] for item in registry['files'] if item['path'] == 'reg_property.txt')
    for item in declarations:
        parts = item['text'].split()
        if parts and parts[0] in movement_names:
            prop_names[int(parts[1], 16) if len(parts) > 1 and parts[1].startswith('0x') else fnv(parts[0])] = parts[0]
    gait_names = {fnv('gait' + str(i)): 'gait' + str(i) for i in range(7)}
    records, packages = [], []
    for filename in ('Spore_Game.package', 'PatchData.package'):
        path = args.data / filename
        data = path.read_bytes()
        entries, meta = read_index(data)
        packages.append(dict(path=str(path.resolve()), sha256=sha(data), bytes=len(data), **meta))
        for resource_key, entry in entries.items():
            is_prop = resource_key[0] == 0xB1B104 and resource_key[2] == fnv('CreatureGameTuning')
            is_gait = resource_key[0] == 0x25DF0112 and resource_key[1] == 0 and resource_key[2] in gait_names
            if not (is_prop or is_gait):
                continue
            if entry['memory_bytes'] > 2 * 1024 * 1024:
                raise FormatError('selected resource exceeds 2 MiB research budget')
            raw = data[entry['offset']:entry['offset'] + entry['stored_bytes']]
            decoded = refpack(raw, entry['memory_bytes']) if entry['compression'] else raw
            if len(decoded) != entry['memory_bytes']:
                raise FormatError('decoded size mismatch')
            record = dict(package=filename, name='CreatureGameTuning' if is_prop else gait_names[resource_key[2]],
                          key=key_json(resource_key), **entry, stored_sha256=sha(raw), decoded_sha256=sha(decoded))
            if is_prop:
                props = read_prop(decoded)
                record.update(property_count=len(props), property_ids=[f'0x{i:08x}' for i in props],
                              selected_properties={prop_names[i]: dict(id=f'0x{i:08x}', **v)
                                                   for i, v in props.items() if i in prop_names})
            else:
                try:
                    record['gait_summary'] = read_gait(decoded)
                except FormatError as error:
                    raise FormatError(f'{filename}/{gait_names[resource_key[2]]}: {error}') from error
            records.append(record)
    report = dict(kind='local-read-only-movement-resource-observations-not-REA-Evidence',
                  scope='CreatureGameTuning PROP variants and gait0..6 GAIT v11 only; no path curves exported',
                  package_order='unknown; both packages and all selected group variants retained separately',
                  format_source_commit=registry['commit'],
                  reader_sha256=sha(Path(__file__).read_bytes()),
                  shared_reader_sha256=sha(Path(__file__).with_name('read_selected_ability_properties.py').read_bytes()),
                  packages=packages, queried_property_names=sorted(movement_names), records=records)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(records=len(records), props=sum('selected_properties' in r for r in records),
                          gaits=sum('gait_summary' in r for r in records), output=str(args.output))))


if __name__ == '__main__':
    main()
