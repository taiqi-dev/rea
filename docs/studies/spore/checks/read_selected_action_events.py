"""Bounded research reader for selected Creature ANIM event metadata.

Layout provenance: ../evidence/public-action-event-format-contracts.json.
No pose curves, model/texture assets, runtime dispatch, or damage are recovered.
"""
import argparse
import collections
import json
import math
import mmap
from pathlib import Path
import struct

from read_selected_action_channels import read_anim_metadata
from read_selected_ability_properties import FormatError, digest, key_json, read_index, refpack

EVENT_BYTES = 0x60
INFO_BYTES = 20
SELECTED_IDS = {
    0xD4772D6F: 'strike_lvl01',
    0xDC542B67: 'bite_lvl01_a',
    0x38ED1075: 'spit',
    0x2F7EA086: 'charge_rush_hit_name_hint',
}
EVENT_TYPES = {0: 'sound', 1: 'effect', 2: 'eventControl', 3: 'unk3',
               4: 'stop', 5: 'unk5', 6: 'sound2', 7: 'footstep',
               0x20000: 'unk20000', 0x20001: 'message'}
SELECTOR_TYPES = {0: 'none', 1: 'unk1', 2: 'default', 3: 'unk3',
                  4: 'standardBodies', 5: 'otherCreature',
                  6: 'otherStandardBodies', 7: 'unk7', 8: 'unk8', 9: 'unk9'}
FILTER_TYPES = {0: 'any', 0x10: 'firstOnly', 0x20: 'allExceptFirst',
                0x30: 'unk1', 0x40: 'unk2', 0x50: 'unk3', 0x60: 'unk4'}


def hx(value):
    return f'0x{value & 0xFFFFFFFF:08x}'


def region(data, offset, size, label):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise FormatError(f'{label} outside resource: offset={offset}, size={size}')
    return data[offset:offset + size]


def u32(data, offset, label='word'):
    return struct.unpack('<I', region(data, offset, 4, label))[0]


def float_word(word):
    value = struct.unpack('<f', struct.pack('<I', word))[0]
    return dict(raw=hx(word), value=value if math.isfinite(value) else None,
                classification='finite' if math.isfinite(value) else
                ('nan' if math.isnan(value) else 'infinity'))


def parameter(word, masked, int_flag, float_flag, id_flag):
    name = {int_flag: 'int', float_flag: 'float', id_flag: 'id'}.get(masked)
    result = dict(raw=hx(word), type_masked=hx(masked), community_type=name)
    if name == 'int':
        result['value'] = struct.unpack('<i', struct.pack('<I', word))[0]
    elif name == 'float':
        result['float'] = float_word(word)
    elif name == 'id':
        result['value'] = hx(word)
    return result


def name_at(data, pointer, budget=2048):
    region(data, pointer, 1, 'event name pointer')
    chunk = data[pointer:min(len(data), pointer + budget)]
    end = chunk.find(b'\0')
    if end < 0:
        raise FormatError('event name missing terminator within research budget')
    try:
        name = chunk[:end].decode('ascii')
    except UnicodeError as error:
        raise FormatError('event name is not ASCII') from error
    return dict(name=name, decoded_offset=pointer, byte_count=end + 1,
                raw_bytes=chunk[:end + 1].hex())


def read_event(data, offset, index):
    raw = region(data, offset, EVENT_BYTES, 'event record')
    flags = u32(raw, 0)
    selectors = []
    for selector_index, role in enumerate(('positionSource', 'rotationSource', 'scaleSource', 'source4')):
        relative = 4 + selector_index * 12
        selector_raw = raw[relative:relative + 12]
        selector_flags, select_flags = struct.unpack_from('<II', selector_raw)
        cap = selector_raw[8:12]
        type_value, filter_value = selector_flags & 15, selector_flags & 0x70
        selectors.append(dict(selector_index=selector_index, role=role,
                              decoded_offset=offset + relative, relative_offset=relative,
                              raw_12_bytes=selector_raw.hex(), flags=hx(selector_flags),
                              selectFlags=hx(select_flags), capability_bytes=cap.hex(),
                              capability_ascii=cap.rstrip(b'\0').decode('ascii')
                              if all(v < 128 for v in cap) else None,
                              community_type_value=type_value,
                              community_type=SELECTOR_TYPES.get(type_value),
                              community_filter_value=filter_value,
                              community_filter=FILTER_TYPES.get(filter_value)))
    archetype = u32(raw, 0x34)
    ident, pointer = u32(raw, 0x3C), u32(raw, 0x40)
    parameter0, parameter1 = u32(raw, 0x44), u32(raw, 0x4C)
    event_type = flags & 0x20007
    return dict(event_index=index, decoded_offset=offset, raw_96_bytes=raw.hex(),
                flags=hx(flags), community_event_type_value=event_type,
                community_event_type=EVENT_TYPES.get(event_type),
                selectors=selectors, archetype_raw=hx(archetype),
                eventGroup=hx(u32(raw, 0x38)), id=hx(ident), name_pointer=pointer,
                name=name_at(data, pointer) if ident else None,
                parameter0=parameter(parameter0, flags & 0x300, 0x100, 0x200, 0x300),
                maxSqrDist=float_word(u32(raw, 0x48)),
                parameter1=parameter(parameter1, flags & 0xC0000, 0x40000, 0x80000, 0xC0000),
                chance_float_if_flag=float_word(parameter1) if flags & 0x2000000 else None,
                disabled_bit_present=bool(flags & 8),
                predicate_flag_present=bool(flags & 0x1000000),
                predicate_raw_8_bytes=raw[0x50:0x58].hex(),
                unknown_tail_8_bytes=raw[0x58:0x60].hex())


def read_action_events(data):
    meta = read_anim_metadata(data)
    count, event_pointer = u32(data, 0x13C), u32(data, 0x140)
    if count > 4096:
        raise FormatError('selected event-table research budget exceeded')
    if count:
        region(data, event_pointer, count * EVENT_BYTES, 'event table')
    events = [read_event(data, event_pointer + index * EVENT_BYTES, index) for index in range(count)]
    channel_pointer = u32(data, 0x148)
    references, channels, zero_examples = [], [], []
    info_rows = 0
    zero_starts = collections.Counter()
    for channel in meta['channels']:
        ci = channel['resource_channel_index']
        base = u32(data, channel_pointer + ci * 4)
        key_count, key_pointer = u32(data, base + 0xD4), u32(data, base + 0xD8)
        info_components = [c for c in channel['components'] if c['type'] == 0]
        channel_row = dict(channel_index=ci, name=channel['name'], decoded_offset=base,
                           primaryContext=channel['primaryContext'],
                           secondaryContext=channel['secondaryContext'],
                           movementFlags=channel['movementFlags'], bindFlags=channel['bindFlags'],
                           info_component_count=len(info_components), keyframe_count=key_count)
        channels.append(channel_row)
        for component in info_components:
            if component['id'] != '0x4f464e49':
                raise FormatError('type0 component has unexpected INFO identifier')
            if key_count and component['keyframe_stride'] < INFO_BYTES:
                raise FormatError('INFO stride shorter than serialized20bytes')
            for keyframe in range(key_count):
                offset = key_pointer + component['keyframe_offset'] + keyframe * component['keyframe_stride']
                raw = region(data, offset, INFO_BYTES, 'INFO keyframe')
                time = struct.unpack_from('<i', raw, 0)[0]
                start, number = struct.unpack_from('<HB', raw, 8)
                info_rows += 1
                row = dict(channel_index=ci, channel_name=channel['name'], keyframe_index=keyframe,
                           component_index=component['index'], decoded_offset=offset,
                           raw_20_bytes=raw.hex(), time_raw=time,
                           unknown_word_4=hx(u32(raw, 4)), eventStartIndex=start, eventCount=number,
                           unknown_byte_B=raw[11], flags=hx(u32(raw, 12)),
                           unknown_tail_word_10=hx(u32(raw, 16)))
                if number:
                    if start > count or number > count - start:
                        raise FormatError(f'INFO event range outside table: channel={ci}, key={keyframe}, start={start}, count={number}, table={count}')
                    row['event_indices'] = list(range(start, start + number))
                    row['event_range_status'] = 'legal-nonzero-range'
                    references.append(row)
                else:
                    zero_starts[start] += 1
                    if len(zero_examples) < 3:
                        row['event_range_status'] = 'count-zero-no-dereference'
                        zero_examples.append(row)
    hits = collections.Counter(index for row in references for index in row['event_indices'])
    id_rows = collections.defaultdict(list)
    for event in events:
        if event['id'] != '0x00000000':
            id_rows[event['id']].append(event['event_index'])
    repeated = [dict(event_index=index, reference_count=number,
                     references=[dict(channel_index=r['channel_index'], keyframe_index=r['keyframe_index'],
                                      time_raw=r['time_raw'], info_decoded_offset=r['decoded_offset'])
                                 for r in references if index in r['event_indices']])
                for index, number in sorted(hits.items()) if number > 1]
    return dict(version=meta['version'], embedded_path=meta['embedded_path'],
                header=dict(length_raw=meta['length_raw'], frameLengthWordRaw=hx(u32(data, 0x11C)),
                            frameLengthSDKFloatCandidate=float_word(u32(data, 0x11C)),
                            eventCount=count, eventPointer=event_pointer,
                            channelCount=len(channels), channelPointer=channel_pointer),
                events=events, channels=channels, info_event_references=references,
                repeated_event_index_references=repeated,
                same_id_multiple_table_entries=[dict(id=ident, event_indices=indices)
                                                for ident, indices in sorted(id_rows.items()) if len(indices) > 1],
                zero_count_INFO_examples=zero_examples,
                zero_count_start_histogram=[dict(eventStartIndex=k, rows=v) for k, v in sorted(zero_starts.items())],
                coverage=dict(event_records=count, INFO_rows_examined=info_rows,
                              nonzero_INFO_rows=len(references), zero_count_INFO_rows=sum(zero_starts.values()),
                              event_reference_occurrences=sum(hits.values()),
                              distinct_referenced_event_indices=len(hits),
                              unreferenced_event_indices=[i for i in range(count) if i not in hits],
                              all_nonzero_INFO_ranges_legal=True,
                              repeated_event_index_count=len(repeated),
                              curve_components_decoded=False, predicates_evaluated=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path('E:/Steam/steamapps/common/Spore/Data'))
    parser.add_argument('--prior', type=Path, default=Path(__file__).parent.parent / 'evidence/local-selected-action-channels.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exe', type=Path, default=Path('E:/Steam/steamapps/common/Spore/SporeBin/SporeApp.exe'))
    args = parser.parse_args()
    executable = args.exe.read_bytes()
    executable_sha = digest(executable)
    if executable_sha != 'f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d':
        raise FormatError('selected executable identity mismatch')
    prior_bytes = args.prior.read_bytes()
    if digest(prior_bytes) != '50c75ef6c46b979c43641a5c290743bebd5aba161bd3ca2b608cff10de2ef4a5':
        raise FormatError('selected28 evidence identity mismatch')
    prior = json.loads(prior_bytes.decode('utf8'))
    selected = [r for r in prior['records'] if 'anim' in r and int(r['key']['instance'], 16) in SELECTED_IDS]
    results, packages, diagnostics = [], [], []
    for expected in prior['packages']:
        path = args.data / Path(expected['path']).name
        with path.open('rb') as stream:
            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                sha = digest(data)
                if sha != expected['sha256']:
                    raise FormatError('package identity mismatch')
                entries, index = read_index(data)
                packages.append(dict(path=str(path.resolve()), bytes=len(data), sha256=sha, **index))
                for old in [r for r in selected if r['package'] == path.name]:
                    resource_key = tuple(int(old['key'][s], 16) for s in ('type', 'group', 'instance'))
                    entry = entries[resource_key]
                    if any(entry[n] != old[n] for n in ('offset', 'stored_bytes', 'memory_bytes', 'compression')):
                        raise FormatError('selected index entry differs from28')
                    if entry['memory_bytes'] > 2 * 1024 * 1024:
                        raise FormatError('selected ANIM memory budget exceeded')
                    stored = data[entry['offset']:entry['offset'] + entry['stored_bytes']]
                    decoded = refpack(stored, entry['memory_bytes']) if entry['compression'] else stored
                    if digest(stored) != old['stored_sha256'] or digest(decoded) != old['decoded_sha256']:
                        raise FormatError('selected stored/decoded identity differs from28')
                    record = dict(package=path.name, key=key_json(resource_key), **entry,
                                  sample_name=SELECTED_IDS[resource_key[2]],
                                  stored_sha256=digest(stored), decoded_sha256=digest(decoded))
                    try:
                        record['anim_events'] = read_action_events(decoded)
                        record['status'] = 'decoded-event-metadata'
                    except FormatError as error:
                        record['status'] = 'format-diagnostic'
                        record['diagnostic'] = str(error)
                        diagnostics.append(dict(package=path.name, key=key_json(resource_key), error=str(error)))
                    results.append(record)
    if len(selected) != 8 or len(results) != len(selected):
        raise FormatError('expected exactly eight existing representative resource versions')
    contracts_path = Path(__file__).parent.parent / 'evidence/public-action-event-format-contracts.json'
    contracts_bytes = contracts_path.read_bytes()
    good = [record['anim_events'] for record in results if record['status'] == 'decoded-event-metadata']
    event_types = collections.Counter(event['community_event_type'] for parsed in good for event in parsed['events'])
    selector_filters = collections.Counter(selector['community_filter'] for parsed in good
                                          for event in parsed['events'] for selector in event['selectors'])
    output = dict(schema_version=1, kind='bounded-selected-event-observations-not-REA-Evidence',
                  module='40-selected-action-events-and-emitter-bindings',
                  rea_evidence_id=None, prior_evidence=dict(path=str(args.prior), sha256=digest(prior_bytes)),
                  public_format_contracts=dict(path=str(contracts_path.resolve()), bytes=len(contracts_bytes),
                                               sha256=digest(contracts_bytes)),
                  target_executable_identity=dict(path=str(args.exe.resolve()), bytes=len(executable),
                                                  sha256=executable_sha, execution=False),
                  reader=dict(path=str(Path(__file__).resolve()), sha256=digest(Path(__file__).read_bytes())),
                  packages=packages, selected_ids={hx(k): v for k, v in SELECTED_IDS.items()},
                  records=results, diagnostics=diagnostics,
                  coverage=dict(selected_resource_versions=len(results),
                                successfully_decoded=len(good),
                                event_records=sum(p['coverage']['event_records'] for p in good),
                                INFO_rows=sum(p['coverage']['INFO_rows_examined'] for p in good),
                                nonzero_INFO_rows=sum(p['coverage']['nonzero_INFO_rows'] for p in good),
                                zero_count_INFO_rows=sum(p['coverage']['zero_count_INFO_rows'] for p in good),
                                event_reference_occurrences=sum(p['coverage']['event_reference_occurrences'] for p in good),
                                all_nonzero_INFO_ranges_legal=all(p['coverage']['all_nonzero_INFO_ranges_legal'] for p in good),
                                repeated_event_index_references=sum(p['coverage']['repeated_event_index_count'] for p in good),
                                event_types=dict(event_types), selector_filters=dict(selector_filters),
                                all_selector_selectFlags_zero=all(s['selectFlags'] == '0x00000000'
                                                                 for p in good for e in p['events'] for s in e['selectors']),
                                all_selector_capability_bytes_zero=all(s['capability_bytes'] == '00000000'
                                                                       for p in good for e in p['events'] for s in e['selectors']),
                                actual_reads='Fresh selected stored bytes and in-memory decompression; both digests matched28.',
                                curves_exported=False, runtime_observed=False),
                  address_scope='Offsets refer to decoded ANIM; package offset is compressed-storage location. No function or live address.',
                  limits=['INFO event time is raw, not an asserted scheduler or damage time.',
                          'Repeated references are metadata, not proof of duplicate execution.',
                          'Event selectors differ from channel role selectors; source4 remains unknown.',
                          'Names, message IDs and parameters do not establish damage, hits or projectile consumers.'],
                  not_performed=['Runtime, private saves, model/texture export, curve export, predicate evaluation, configuration changes'])
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')
    print(json.dumps(dict(records=len(results), diagnostics=len(diagnostics), output=str(args.output),
                         events=sum(r.get('anim_events', {}).get('coverage', {}).get('event_records', 0) for r in results),
                         INFO_rows=sum(r.get('anim_events', {}).get('coverage', {}).get('INFO_rows_examined', 0) for r in results))))
    if diagnostics:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
