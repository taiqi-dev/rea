"""Bounded metadata study: selected land ANIM names into FX catalogs.

Public layout locators: public-action-presentation-contracts.json and module36.
No game execution, complete particle/audio export, or native lookup is claimed.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import struct

from read_selected_ability_properties import read_index, read_prop, refpack
from read_selected_skinpaint_sections import (Cursor, FormatError,
    read_component_sections, read_sections_at, section_payload)

IMPORT_MASK = 0x7F000000
DIRECTORY_BUDGET = 8 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hx(value):
    return f'0x{value & 0xffffffff:08x}'


def key_json(key):
    return dict(zip(('type', 'group', 'instance'), map(hx, key)))


def reference(value, visual_count, import_count=None):
    if value == -1:
        return {'kind': 'null'}
    if value < 0:
        raise FormatError('UnsupportedNegativeEffectReference')
    if value & IMPORT_MASK:
        if value & IMPORT_MASK != IMPORT_MASK:
            raise FormatError('PartialImportMask')
        index = value & ~IMPORT_MASK
        if import_count is not None and not 0 <= index < import_count:
            raise FormatError('ImportIndexOutOfRange')
        return {'kind': 'import', 'index': index}
    if not 0 <= value < visual_count:
        raise FormatError('VisualIndexOutOfRange')
    return {'kind': 'visual', 'index': value}


def read_visual_catalog(data, start):
    c = Cursor(data)
    c.pos = start
    if c.number('>h') != 1:
        raise FormatError('UnsupportedVisualVersion')
    count = c.number('>i')
    if not 0 <= count <= min(50000, (len(data)-c.pos)//49):
        raise FormatError('ImpossibleVisualCount')
    visuals = []
    for ordinal in range(count):
        begin = c.pos
        c.take(12+8+4+1)
        lod_count = c.number('>i')
        if not 0 <= lod_count <= (len(data)-c.pos)//4:
            raise FormatError('ImpossibleVisualLODCount')
        c.take(lod_count*4+12+4)
        block_count = c.number('>i')
        if not 0 <= block_count <= (len(data)-c.pos)//109:
            raise FormatError('ImpossibleVisualBlockCount')
        blocks = []
        for index in range(block_count):
            bstart = c.pos
            kind, flags = c.number('>B'), c.number('>I')
            raw_transform = c.take(54)
            transform_flags, scale = struct.unpack_from('>Hf', raw_transform)
            rotation = list(struct.unpack_from('<9f', raw_transform, 6))
            offset = list(struct.unpack_from('<3f', raw_transform, 42))
            lod_begin, lod_end = c.number('>B'), c.number('>B')
            n = c.number('>i')
            if not 0 <= n <= (len(data)-c.pos-40)//12:
                raise FormatError('ImpossibleBlockLODCount')
            c.take(n*12)
            factors = list(struct.unpack('>6f', c.take(24)))
            app_flags, app_mask = c.number('>I'), c.number('>I')
            select_group, select_chance = c.number('>H'), c.number('>H')
            time_scale, target = c.number('>f'), c.number('>i')
            numbers = [scale, time_scale] + rotation + offset + factors
            if not all(math.isfinite(x) for x in numbers):
                raise FormatError('NonFiniteVisualBlockMetadata')
            blocks.append(dict(ordinal=index, decoded_byte_start=bstart,
                decoded_byte_end=c.pos, block_type=kind, flags_raw=hx(flags),
                component_index_raw=target, transform_flags_raw=transform_flags,
                raw_transform_54_bytes=raw_transform.hex(), scale=scale,
                rotation_matrix_le=rotation, offset_le=offset,
                lod_begin=lod_begin, lod_end=lod_end,
                emit_size_alpha_factors=factors, app_flags_raw=hx(app_flags),
                app_mask_raw=hx(app_mask), selection_group=select_group,
                selection_chance=select_chance, time_scale=time_scale))
        visuals.append(dict(ordinal=ordinal, decoded_byte_start=begin,
                            decoded_byte_end=c.pos, blocks=blocks))
    exports = []
    while True:
        target = c.number('>i')
        if target == -1:
            break
        group, name = c.number('>I'), c.number('>I')
        exports.append(dict(effect_index_raw=target, group=hx(group), name_hash=hx(name)))
    string_assignments = c.number('>i')
    n = c.number('>i')
    if not 0 <= n <= (len(data)-c.pos)//8:
        raise FormatError('ImpossibleImportCount')
    imports = [dict(group=hx(c.number('>I')), name_hash=hx(c.number('>I'))) for _ in range(n)]
    if c.pos != len(data):
        raise FormatError('EffectDirectoryTrailingBytes')
    for row in exports:
        if reference(row['effect_index_raw'], count, n)['kind'] == 'null':
            raise FormatError('NullExport')
    return dict(visuals=visuals, exports=exports, imports=imports,
                string_assignments_raw=string_assignments, decoded_end=c.pos)


def read_sound_section(data, section):
    if section.type_id != 5 or section.version != 1:
        raise FormatError('UnsupportedSoundSection')
    payload = section_payload(data, section)
    c = Cursor(payload)
    count = c.number('>I')
    if count != section.count or len(payload) != 4 + count*28:
        raise FormatError('InvalidSoundSectionLength')
    result = []
    for index in range(count):
        start = c.pos
        flags, group, name, track = [c.number('>I') for _ in range(4)]
        inv_sample, length, volume = [c.number('>f') for _ in range(3)]
        if not all(math.isfinite(x) for x in (inv_sample, length, volume)):
            raise FormatError('NonFiniteSoundMetadata')
        result.append(dict(ordinal=index, decoded_byte_start=section.body_start+start,
            raw_28_bytes=payload[start:c.pos].hex(), flags_raw=hx(flags),
            resource_id_pair=dict(group=hx(group), instance=hx(name)), track_id_raw=hx(track),
            inv_sample=inv_sample, length=length, volume=volume))
    return result


def read_sequences(data, section, visuals, imports):
    if section.type_id != 4 or section.version != 1:
        raise FormatError('UnsupportedSequenceSection')
    payload = section_payload(data, section)
    c = Cursor(payload)
    count = c.number('>i')
    if not 0 <= count == section.count <= (len(payload)-4)//8:
        raise FormatError('ImpossibleSequenceCount')
    result = []
    for index in range(count):
        n = c.number('>i')
        if not 0 <= n <= (len(payload)-c.pos-4)//12:
            raise FormatError('ImpossibleSequenceStepCount')
        steps = []
        for step in range(n):
            times = list(struct.unpack('<ff', c.take(8)))
            target = c.number('>i')
            reference(target, visuals, imports)
            if not all(math.isfinite(x) for x in times):
                raise FormatError('NonFiniteSequenceTime')
            steps.append(dict(ordinal=step, time_range_stored=times, visual_index_raw=target))
        result.append(dict(ordinal=index, steps=steps, flags_raw=hx(c.number('>I'))))
    if c.pos != len(payload):
        raise FormatError('SequenceTrailingBytes')
    return result


def trace(catalog, sequences, counts, target, ancestry=()):
    if len(ancestry) >= 64:
        raise FormatError('SelectedTraceDepthBudget')
    ref = reference(target, len(catalog['visuals']), len(catalog['imports']))
    if ref['kind'] == 'null':
        return [dict(path=list(ancestry), kind='null')]
    if ref['kind'] == 'import':
        return [dict(path=list(ancestry), kind='unresolved_import',
                     import_ref=catalog['imports'][ref['index']])]
    node = ('visual', ref['index'])
    if node in ancestry:
        raise FormatError('SelectedVisualCycle')
    ancestry = ancestry+(node,)
    leaves = []
    for block in catalog['visuals'][ref['index']]['blocks']:
        kind, value = block['block_type'], block['component_index_raw']
        if kind == 0:
            children = trace(catalog, sequences, counts, value, ancestry)
        elif kind == 4:
            if value == -1:
                children = [dict(path=list(ancestry), kind='null_sequence')]
            elif not 0 <= value < len(sequences):
                raise FormatError('SequenceIndexOutOfRange')
            else:
                children = []
                for step in sequences[value]['steps']:
                    for leaf in trace(catalog, sequences, counts, step['visual_index_raw'], ancestry+(('sequence', value),)):
                        leaf['sequence_time_ranges_stored'] = [step['time_range_stored']] + leaf.get('sequence_time_ranges_stored', [])
                        children.append(leaf)
        else:
            if value == -1:
                children = [dict(path=list(ancestry), kind='null_component', type=kind)]
            elif kind not in counts or not 0 <= value < counts[kind]:
                raise FormatError('ComponentIndexOutOfRange')
            else:
                children = [dict(path=list(ancestry)+[('component', kind, value)], kind='component', type=kind, index=value)]
        for child in children:
            child['blocks'] = [block]+child.get('blocks', [])
        leaves.extend(children)
        if len(leaves) > 4096:
            raise FormatError('SelectedTraceLeafBudget')
    return leaves


def capture(directory):
    evidence = Path(__file__).resolve().parent.parent/'evidence'
    prior_path = evidence/'local-selected-action-events.json'
    raw_prior = prior_path.read_bytes()
    prior = json.loads(raw_prior.decode('utf8'))
    events = []
    for row in prior['records']:
        for event in row['anim_events']['events']:
            if event['community_event_type'] not in ('effect', 'sound', 'sound2', 'footstep'):
                continue
            flags = int(event['flags'], 16)
            events.append(dict(package=row['package'], animation_key=row['key'],
                event_index=event['event_index'], event_id=event['id'],
                name=event['name']['name'] if event['name'] else None,
                kind=event['community_event_type'], event_group_raw=event['eventGroup'],
                event_flags_raw=event['flags'], disabled=event['disabled_bit_present'],
                community_update_flags={name:bool(flags&bit) for name,bit in (
                    ('position',0x800),('rotation',0x4000),('scale',0x100000),
                    ('particle_scale',0x1000),('apply_general_scale',0x200000))},
                selectors=event['selectors']))
    names = {e['event_id']:e['name'] for e in events}
    report = dict(kind='selected-land-action-presentation-resource-links-not-runtime',
        prior_evidence=dict(path=prior_path.as_posix(), sha256=digest(raw_prior)),
        reader=dict(path=Path(__file__).as_posix(), sha256=digest(Path(__file__).read_bytes())),
        packages=[], events_reused=events, directories=[], diagnostics=[], direct_sound_event_queries=[],
        coverage=dict(directory_group='0x40450200', directory_decoded_budget=DIRECTORY_BUDGET,
            other_quality_groups_not_read=True, selected_ANIM_payloads_reread=False,
            particle_payloads_decoded=False, audio_waveforms_read=False),
        limitations=['Matching export IDs are resource candidates; native lookup/loading precedence is not recovered.',
            'eventGroup and FX export group have separate identity; they are not assumed to be the same lookup key.',
            'Sound event ID and SoundEffect resource-ID pair are different reference domains.',
            'Only selected land action names are traced; shared catalogs are not other-stage gameplay studies.'])
    for package in ('Spore_Game.package', 'PatchData.package'):
        path = directory/package
        raw = path.read_bytes()
        entries, stats = read_index(raw)
        report['packages'].append(dict(path=path.as_posix(), bytes=len(raw), sha256=digest(raw), index=stats))
        for ident in sorted({e['event_id'] for e in events if e['kind']=='sound'}):
            candidates = []
            for candidate, cmeta in entries.items():
                if candidate[2] != int(ident,16):
                    continue
                found = dict(key=key_json(candidate), **cmeta)
                if cmeta['memory_bytes'] <= 131072:
                    cstored = raw[cmeta['offset']:cmeta['offset']+cmeta['stored_bytes']]
                    decoded = refpack(cstored,cmeta['memory_bytes']) if cmeta['compression']==0xffff else cstored
                    if len(decoded) != cmeta['memory_bytes']:
                        raise FormatError('SoundCandidateDecodedLengthMismatch')
                    found.update(stored_sha256=digest(cstored), decoded_sha256=digest(decoded),
                        decoded_prefix_64_bytes=decoded[:64].hex(), status='BoundedHeaderObservedNotSemanticallyDecoded')
                    if candidate[0] == 0x02B9F662:
                        try:
                            found['direct_properties'] = read_prop(decoded)
                            found['status'] = 'AudioPropDirectFieldsDecoded'
                        except ValueError as error:
                            found['property_diagnostic'] = str(error)
                            report['diagnostics'].append(dict(package=package, key=key_json(candidate), diagnostic=str(error)))
                else:
                    found['status']='NotReadAboveSoundMetadataBudget'
                candidates.append(found)
            report['direct_sound_event_queries'].append(dict(package=package,
                event_id=ident, name=names[ident], same_instance_candidates=candidates))
        for key, meta in entries.items():
            if key[0] != 0xEA5118B0 or key[1] != 0x40450200:
                continue
            row = dict(package=package, key=key_json(key), **meta)
            if meta['memory_bytes'] > DIRECTORY_BUDGET:
                row['status'] = 'NotReadAboveDeclaredBudget'
                report['directories'].append(row)
                continue
            stored = raw[meta['offset']:meta['offset']+meta['stored_bytes']]
            blob = refpack(stored, meta['memory_bytes']) if meta['compression']==0xffff else stored
            row.update(stored_sha256=digest(stored), decoded_sha256=digest(blob))
            try:
                if len(blob) != meta['memory_bytes']:
                    raise FormatError('DecodedLengthMismatch')
                sections, pos = read_component_sections(blob)
                resources, pos = read_sections_at(blob, pos)
                catalog = read_visual_catalog(blob, pos)
                sounds = []
                sequences = []
                for section in sections:
                    if section.type_id == 5:
                        sounds = read_sound_section(blob, section)
                    elif section.type_id == 4:
                        sequences = read_sequences(blob, section, len(catalog['visuals']), len(catalog['imports']))
                matches = []
                selected_sounds = set()
                for export in catalog['exports']:
                    if export['name_hash'] not in names:
                        continue
                    paths = trace(catalog, sequences, {s.type_id:s.count for s in sections}, export['effect_index_raw'])
                    for leaf in paths:
                        if leaf['kind']=='component' and leaf['type']==5:
                            selected_sounds.add(leaf['index'])
                    exported_ref = reference(export['effect_index_raw'], len(catalog['visuals']), len(catalog['imports']))
                    matches.append(dict(event_id=export['name_hash'], name=names[export['name_hash']], export=export, paths=paths,
                        direct_visual_block_count=len(catalog['visuals'][exported_ref['index']]['blocks']) if exported_ref['kind']=='visual' else None))
                sound_rows = []
                for index in sorted(selected_sounds):
                    sound = dict(sounds[index])
                    pair = sound['resource_id_pair']
                    sound['same_package_index_candidates'] = [key_json(k) for k in entries if k[1]==int(pair['group'],16) and k[2]==int(pair['instance'],16)]
                    sound_rows.append(sound)
                direct_sound_candidates = []
                for ident in sorted({e['event_id'] for e in events if e['kind']=='sound'}):
                    candidates = [key_json(k) for k in entries if k[2]==int(ident,16)]
                    direct_sound_candidates.append(dict(event_id=ident, name=names[ident], same_instance_candidates=candidates))
                row.update(status='ReadCatalogAndSelectedPaths',
                    ordinary_sections=[asdict(s) for s in sections], resource_sections=[asdict(s) for s in resources],
                    visual_count=len(catalog['visuals']), export_count=len(catalog['exports']), import_count=len(catalog['imports']),
                    string_assignments_raw=catalog['string_assignments_raw'], exact_decoded_end=catalog['decoded_end'],
                    sound_metadata_count=len(sounds), sequence_records_validated=len(sequences),
                    selected_matches=matches, selected_sound_components=sound_rows,
                    direct_sound_event_index_candidates=direct_sound_candidates)
            except (FormatError, ValueError, struct.error) as error:
                row.update(status='ParseDiagnostic', diagnostic=str(error))
                report['diagnostics'].append(dict(package=package, key=key_json(key), diagnostic=str(error)))
            report['directories'].append(row)
    report['coverage'].update(directory_records=len(report['directories']),
        parsed_directory_records=sum(r['status']=='ReadCatalogAndSelectedPaths' for r in report['directories']),
        matched_exports=sum(len(r.get('selected_matches', [])) for r in report['directories']),
        trace_leaves=sum(len(m['paths']) for r in report['directories'] for m in r.get('selected_matches', [])),
        selected_sound_components=sum(len(r.get('selected_sound_components', [])) for r in report['directories']))
    report['coverage']['audioProp_records_decoded'] = sum(c.get('status')=='AudioPropDirectFieldsDecoded'
        for q in report['direct_sound_event_queries'] for c in q['same_instance_candidates'])
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--data-directory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = capture(args.data_directory)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(dict(coverage=result['coverage'], diagnostics=result['diagnostics']), ensure_ascii=False))
