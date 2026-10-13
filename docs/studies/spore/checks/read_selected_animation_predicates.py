"""Bounded ANIM predicate observations and separately labelled independent model.

No original evaluator, fallback algorithm, runtime state or curve is recovered.
"""
import argparse
import collections
from datetime import datetime, timezone
import json
import mmap
from pathlib import Path
import struct
from zoneinfo import ZoneInfo

from read_selected_action_channels import read_anim_metadata
from read_selected_action_events import region, u32, hx
from read_selected_ability_properties import FormatError, digest, read_index
from read_selected_ability_properties import refpack, key_json

KNOWN_BITS = {1: 'uprightSpine', 2: 'hasGraspers', 4: 'hasFeet'}
PRIOR_SHA = '50c75ef6c46b979c43641a5c290743bebd5aba161bd3ca2b608cff10de2ef4a5'
EXE_SHA = 'f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d'


def decode_predicate(data, offset):
    raw = region(data, offset, 8, 'predicate')
    mask, values = struct.unpack('<II', raw)
    return dict(decoded_offset=offset, raw_8_bytes=raw.hex(), flags1=hx(mask),
                flags2=hx(values), community_requirements=[
                    dict(bit=hx(bit), name=name, required_value=bool(values & bit))
                    for bit, name in KNOWN_BITS.items() if mask & bit],
                unknown_flags1=hx(mask & ~7), unknown_flags2=hx(values & ~7),
                values_outside_selected_mask=hx(values & ~mask),
                is_default=mask == 0 and values == 0,
                native_evaluation='not-performed')


def read_predicates(data):
    meta = read_anim_metadata(data)
    result = dict(version=meta['version'], embedded_path=meta['embedded_path'],
                  whole_animation=decode_predicate(data, 0x154), channels=[], events=[])
    channel_pointer = u32(data, 0x148)
    for channel in meta['channels']:
        index = channel['resource_channel_index']
        base = u32(data, channel_pointer + index * 4)
        binding = u32(data, base + 0xAC)
        result['channels'].append(dict(channel_index=index, name=channel['name'],
            decoded_offset=base, bindFlags_decoded_offset=base + 0xAC,
            bindFlags=hx(binding), raw_bindFlags_4_bytes=region(data, base + 0xAC, 4, 'bind').hex(),
            community_require_bit_present=bool(binding & 4),
            primaryContext_decoded_offset=base + 0x8C,
            primaryContext_raw_16_bytes=region(data, base + 0x8C, 16, 'primary').hex(),
            primaryContext=channel['primaryContext'],
            secondaryContext_decoded_offset=base + 0x9C,
            secondaryContext_raw_16_bytes=region(data, base + 0x9C, 16, 'secondary').hex(),
            secondaryContext=channel['secondaryContext'],
            movementFlags=channel['movementFlags'],
            blendGroup=channel['community_blendGroup'], variantGroup=channel['community_variantGroup'],
            distinct_channel_predicate='not-declared-in-selected-community-format'))
    count, pointer = u32(data, 0x13C), u32(data, 0x140)
    if count > 4096:
        raise FormatError('event predicate budget exceeded')
    if count:
        region(data, pointer, count * 96, 'event table')
    for index in range(count):
        base = pointer + index * 96
        flags = u32(data, base)
        result['events'].append(dict(event_index=index, decoded_offset=base,
            flags=hx(flags), raw_flags_4_bytes=region(data, base, 4, 'flags').hex(),
            predicate_flag_present=bool(flags & 0x01000000),
            disabled_bit_present=bool(flags & 8), chance_bit_present=bool(flags & 0x02000000),
            archetype_raw=hx(u32(data, base + 0x34)), id=hx(u32(data, base + 0x3C)),
            predicate=decode_predicate(data, base + 0x50)))
    return result


def independent_evaluate(mask, values, facts):
    """Independent three-valued policy; deliberately not Spore's evaluator."""
    if mask < 0 or values < 0 or mask > 0xFFFFFFFF or values > 0xFFFFFFFF:
        return 'invalid'
    if (mask | values) & ~7:
        return 'unknown'
    unknown = False
    for bit, name in KNOWN_BITS.items():
        if mask & bit:
            value = facts.get(name)
            if value is not True and value is not False:
                unknown = True
                continue
            if value != bool(values & bit):
                return 'fail'
    return 'unknown' if unknown else 'pass'


def independent_select(candidates, facts, roles, body_revision, soul_revision):
    """Own deterministic preflight; caller supplies binding candidates per role."""
    rejected = []
    for candidate in candidates:
        state = independent_evaluate(candidate['mask'], candidate['values'], facts)
        if state != 'pass':
            rejected.append(dict(clip=candidate['id'], reason='condition-' + state))
            continue
        bindings = {}
        failed = None
        for requirement in candidate['required_roles']:
            choices = sorted(set(roles.get(requirement, [])))
            if not choices:
                failed = requirement
                break
            bindings[requirement] = choices[0]
        if failed is not None:
            rejected.append(dict(clip=candidate['id'], reason='missing-role', role=failed))
            continue
        return dict(status='ready', clip=candidate['id'], bindings=bindings,
                    body_revision=body_revision, soul_revision=soul_revision, rejected=rejected)
    return dict(status='no-compatible-animation', rejected=rejected,
                body_revision=body_revision, soul_revision=soul_revision)


def independent_plan_valid(plan, body_revision, soul_revision, live_parts):
    return (plan['status'] == 'ready' and plan['body_revision'] == body_revision
            and plan['soul_revision'] == soul_revision
            and all(part in live_parts for part in plan['bindings'].values()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--data', type=Path, default=Path('E:/Steam/steamapps/common/Spore/Data'))
    parser.add_argument('--exe', type=Path, default=Path('E:/Steam/steamapps/common/Spore/SporeBin/SporeApp.exe'))
    args = parser.parse_args()
    observed_time = datetime.now(timezone.utc)
    evidence = Path(__file__).resolve().parent.parent / 'evidence'
    prior_path = evidence / 'local-selected-action-channels.json'
    prior_raw = prior_path.read_bytes()
    if digest(prior_raw) != PRIOR_SHA:
        raise FormatError('prior28 identity mismatch')
    executable = args.exe.read_bytes()
    if digest(executable) != EXE_SHA:
        raise FormatError('EXE identity mismatch')
    prior = json.loads(prior_raw.decode('utf8'))
    selected = [r for r in prior['records'] if 'anim' in r]
    if len(selected) != 46:
        raise FormatError('expected exactly46 prior ANIM resources')
    records, packages = [], []
    for expected in prior['packages']:
        path = args.data / Path(expected['path']).name
        with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            if digest(data) != expected['sha256']:
                raise FormatError('package digest mismatch')
            entries, index = read_index(data)
            packages.append(dict(path=str(path.resolve()), bytes=len(data), sha256=digest(data), **index))
            for old in [r for r in selected if r['package'] == path.name]:
                key = tuple(int(old['key'][s], 16) for s in ('type', 'group', 'instance'))
                entry = entries[key]
                for name in ('offset', 'stored_bytes', 'memory_bytes', 'compression'):
                    if entry[name] != old[name]:
                        raise FormatError('selected index mismatch')
                if entry['memory_bytes'] > 2 * 1024 * 1024:
                    raise FormatError('selected memory budget exceeded')
                stored = region(data, entry['offset'], entry['stored_bytes'], 'stored ANIM')
                decoded = refpack(stored, entry['memory_bytes']) if entry['compression'] else stored
                if digest(stored) != old['stored_sha256'] or digest(decoded) != old['decoded_sha256']:
                    raise FormatError('selected stored/decoded mismatch')
                records.append(dict(package=path.name, key=key_json(key), **entry,
                    stored_sha256=digest(stored), decoded_sha256=digest(decoded),
                    predicates=read_predicates(decoded)))
    if len(records) != 46:
        raise FormatError('selection count mismatch')
    anims = [r['predicates'] for r in records]
    whole = collections.Counter((a['whole_animation']['flags1'], a['whole_animation']['flags2']) for a in anims)
    event = collections.Counter((e['predicate_flag_present'], e['predicate']['flags1'], e['predicate']['flags2'])
                                for a in anims for e in a['events'])
    summary = dict(resource_versions=len(records), distinct_resource_keys=len({str(r['key']) for r in records}),
        channels_examined=sum(len(a['channels']) for a in anims),
        require_bit_channels=sum(c['community_require_bit_present'] for a in anims for c in a['channels']),
        event_records_examined=sum(len(a['events']) for a in anims),
        event_predicate_flag_records=sum(e['predicate_flag_present'] for a in anims for e in a['events']),
        nondefault_whole_predicates=sum(not a['whole_animation']['is_default'] for a in anims),
        whole_patterns=[dict(flags1=x, flags2=y, resources=n) for (x,y),n in sorted(whole.items())],
        event_patterns=[dict(flag_enabled=b, flags1=x, flags2=y, events=n) for (b,x,y),n in sorted(event.items())])
    contract = evidence / 'public-animation-predicate-contracts.json'
    output = dict(schema_version=1, module=45, kind='bounded-static-predicate-observations-not-REA-Evidence',
        fresh_read_scope='Full EXE/package digest; DBPF index; existing46 selected stored ANIMs freshly read/decompressed in memory; whole predicates, channel metadata and event predicate/flags only.',
        timestamp_utc=observed_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
        timestamp_pacific=observed_time.astimezone(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d %H:%M:%S %Z'),
        timestamp_authority='host system clock, America/Los_Angeles IANA conversion',
        target_executable_identity=dict(path=str(args.exe.resolve()), bytes=len(executable), sha256=digest(executable),
                                        digest_fresh=True, executed=False, PE_version_metadata='reused-not-reparsed'),
        prior=dict(path=str(prior_path.resolve()), sha256=PRIOR_SHA), packages=packages,
        format_contract=dict(path=str(contract.resolve()), sha256=digest(contract.read_bytes())),
        reader_sha256=digest(Path(__file__).read_bytes()), summary=summary, records=records,
        unknowns=['Native predicate evaluation and TLSA fallback order', 'HasFeet/HasGraspers/UprightSpine state calculation',
                  'Empty required channel consequence and whole/channel/event failure interaction',
                  'Effective package resolution', 'Runtime events, damage and selected limb execution'],
        coverage=dict(curves_decoded=False, model_assets_exported=False, predicates_executed=False,
                      runtime_observed=False, branch_fallback_recovered=False))
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
