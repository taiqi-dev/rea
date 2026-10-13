"""Bounded research metadata reader for one explicitly selected Creature RW4.

No vertex, texture, material, or complete animation asset is exported.
Format provenance: ../evidence/public-part-definition-contracts.json.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from read_selected_ability_properties import FormatError, refpack


MAGIC = bytes.fromhex('89525734773332000d0a1a0a00200400343534003030300000000000')
HANDLE = 0x00ff0000
SKELETON = 0x00070002
BASE = 0x00010030
KEYFRAME = 0x00070001
SKIN_LINKS = 0x0007000c


def digest(data):
    return hashlib.sha256(data).hexdigest()


def span(data, offset, size, label):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise FormatError(f'{label} outside RW4: offset={offset}, size={size}')
    return data[offset:offset + size]


def unpack(data, offset, fmt, label):
    return struct.unpack(fmt, span(data, offset, struct.calcsize(fmt), label))


def reference_info(raw, sections):
    kind = raw >> 22
    if kind == 0:
        if raw >= len(sections):
            raise FormatError(f'RW object index out of bounds: {raw}')
        return {'raw': f'0x{raw:08x}', 'kind': 'direct-object', 'section_index': raw,
                'type': sections[raw]['type']}
    if kind == 1:
        return {'raw': f'0x{raw:08x}', 'kind': 'null-encoding'}
    if kind == 2:
        return {'raw': f'0x{raw:08x}', 'kind': 'unresolved-subreference',
                'source_mask_index': raw & 0x3ffff}
    return {'raw': f'0x{raw:08x}', 'kind': 'unsupported-reference-encoding'}


def read_metadata(data):
    span(data, 0, 0x98, 'header')
    if data[:28] != MAGIC:
        raise FormatError('RW4 signature differs from selected format profile')
    kind, = unpack(data, 0x1c, '<I', 'kind')
    if kind != 1:
        raise FormatError(f'selected reader requires MODEL=1, got {kind:#x}')
    count, = unpack(data, 0x24, '<I', 'section count')
    table, = unpack(data, 0x30, '<I', 'section table')
    base, = unpack(data, 0x44, '<I', 'base buffer')
    if count == 0 or count > len(data) // 24:
        raise FormatError('impossible section count')
    span(data, table, count * 24, 'section table')
    sections = []
    for index in range(count):
        pointer, unknown, size, alignment, type_index, type_code = unpack(
            data, table + index * 24, '<Iiiiii', 'section record')
        actual = pointer + base if type_code == BASE else pointer
        body = span(data, actual, size, f'section {index}')
        sections.append({'index': index, 'table_offset': table + index * 24,
                         'raw_data_pointer': pointer, 'data_offset': actual,
                         'size': size, 'alignment': alignment,
                         'type_code_index': type_index, 'type': f'0x{type_code:08x}',
                         'field_04': unknown, 'body_sha256': digest(body)})
    handles, skeletons, animations, skin_links = [], [], [], []
    for section in sections:
        start, size = section['data_offset'], section['size']
        if section['type'] == f'0x{HANDLE:08x}':
            if size < 64:
                raise FormatError('truncated morph handle')
            handle_id, unknown, *values = unpack(data, start, '<ii6dfI', 'morph handle')
            coordinates, default, ref = values[:6], values[6], values[7]
            if any(not math.isfinite(v) for v in coordinates + [default]):
                raise FormatError('non-finite morph handle')
            animation_reference = reference_info(ref, sections)
            if animation_reference['kind'] == 'direct-object' and animation_reference['type'] != f'0x{KEYFRAME:08x}':
                raise FormatError('morph handle references a non-animation object')
            handles.append({'section_index': section['index'],
                            'handle_id': f'0x{handle_id & 0xffffffff:08x}',
                            'unknown_integer': unknown,
                            'start': coordinates[:3], 'end': coordinates[3:],
                            'default_time_raw': default,
                            'animation_reference': animation_reference,
                            'parsed_bytes': 64, 'unparsed_tail_bytes': size - 64})
        elif section['type'] == f'0x{SKELETON:08x}':
            if size < 24:
                raise FormatError('truncated skeleton header')
            flags, parents, names, bones, skeleton_id, duplicate = unpack(
                data, start, '<IIIiIi', 'skeleton header')
            if bones < 0 or bones > len(data) // 4 or bones != duplicate:
                raise FormatError('invalid skeleton count/duplicate count')
            for ptr, label in ((flags, 'flags'), (parents, 'parents'), (names, 'names')):
                span(data, ptr, bones * 4, f'skeleton {label} range')
            entries = []
            for ordinal in range(bones):
                name, = unpack(data, names + ordinal * 4, '<I', 'bone name')
                flag, = unpack(data, flags + ordinal * 4, '<I', 'bone flags')
                parent, = unpack(data, parents + ordinal * 4, '<i', 'bone parent')
                entries.append({'index': ordinal, 'name_id': f'0x{name:08x}',
                                'flags_raw': f'0x{flag:08x}', 'parent_index_raw': parent})
            skeletons.append({'section_index': section['index'], 'bone_count': bones,
                              'duplicate_count': duplicate,
                              'skeleton_id': f'0x{skeleton_id:08x}',
                              'array_ranges_checked': True, 'array_contents_read': True,
                              'bones': entries})
        elif section['type'] == f'0x{SKIN_LINKS:08x}':
            if size < 20:
                raise FormatError('truncated skin links')
            field_0, field_4, buffer_ref, skeleton_ref, skin_ref = unpack(
                data, start, '<IiIII', 'skin links')
            skin_links.append({'section_index': section['index'], 'field_4_raw': field_4,
                               'field_0_reference': reference_info(field_0, sections),
                               'matrix_buffer_reference': reference_info(buffer_ref, sections),
                               'skeleton_reference': reference_info(skeleton_ref, sections),
                               'animation_skin_reference': reference_info(skin_ref, sections)})
        elif section['type'] == f'0x{KEYFRAME:08x}':
            if size < 48:
                raise FormatError('truncated keyframe header')
            names, channels, skeleton_id, field_c, ignored_data, padding_end, duplicate, field_1c, length, field_24, flags, info = unpack(
                data, start, '<IIiiIIiifiiI', 'keyframe header')
            if channels > len(data) // 12 or not math.isfinite(length):
                raise FormatError('invalid keyframe channel count or length')
            span(data, names, channels * 4, 'channel names')
            span(data, info, channels * 12, 'channel directory')
            rows = []
            for ordinal in range(channels):
                channel_id, = unpack(data, names + ordinal * 4, '<I', 'channel name')
                relative, pose_size, components = unpack(data, info + ordinal * 12, '<Iii', 'channel entry')
                if pose_size <= 0:
                    raise FormatError('invalid pose size')
                first = start + relative
                span(data, first, pose_size, 'first pose range')
                rows.append({'ordinal': ordinal, 'channel_id': f'0x{channel_id:08x}',
                             'relative_key_position': relative, 'first_key_offset': first,
                             'pose_size': pose_size, 'components': f'0x{components:08x}',
                             'key_payload_read': False})
            animations.append({'section_index': section['index'],
                               'channel_count': channels, 'skeleton_id': f'0x{skeleton_id & 0xffffffff:08x}',
                               'raw_duplicate_count_ignored_by_source': duplicate,
                               'length_raw': length, 'channels': rows,
                               'uninterpreted_header_fields': {'field_c': field_c,
                                   'data_pointer': ignored_data, 'padding_end': padding_end,
                                   'field_1c': field_1c, 'field_24': field_24, 'flags': flags}})
            # Read two explicit channel prefixes with next-entry boundaries.
            # Do not emulate the community reader's time-based last-channel loop.
            selected_samples = []
            for selected in range(min(2, len(rows) - 1)):
                if rows[selected]['components'] != '0x00000101' or rows[selected]['pose_size'] != 32:
                    continue
                begin, end = rows[selected]['first_key_offset'], rows[selected + 1]['first_key_offset']
                amount = end - begin
                if begin < start or end > start + size or amount <= 0 or amount % 32 or amount > 64 * 32:
                    raise FormatError('selected first-channel key span invalid or over budget')
                samples = []
                for key_offset in range(begin, end, 32):
                    values = unpack(data, key_offset, '<8f', 'selected LocRot key')
                    if any(not math.isfinite(v) for v in values):
                        raise FormatError('non-finite selected LocRot key')
                    samples.append({'offset': key_offset, 'rotation_raw': values[:4],
                                    'location_raw': values[4:7], 'time_raw': values[7]})
                rows[selected]['key_payload_read'] = True
                selected_samples.append({'ordinal': selected,
                                         'channel_id': rows[selected]['channel_id'],
                                         'samples': samples})
            animations[-1]['selected_channel_samples'] = selected_samples
    return {'rw4_kind': kind, 'section_count': count, 'section_table_offset': table,
            'base_buffer_offset': base, 'sections': sections,
            'handles': handles, 'skeletons': skeletons, 'animations': animations,
            'skin_links': skin_links,
            'coverage': 'Section metadata; 64-byte selected handles if present; skeleton headers/name-parent-flag arrays, skin object links, keyframe headers/channel directories; first two LocRot channels per animation with next-entry boundaries. No bind matrix decoding, interpolation, geometry, materials or textures.'}


def capture(package, output):
    # One known key located by the separate DBPF inventory; recheck index identity.
    expected_bytes = 942881325
    # The index location is measured again from the header, not selected by filename.
    with package.open('rb') as stream:
        header = stream.read(96)
        if header[:4] != b'DBPF' or struct.unpack_from('<II', header, 4) != (3, 0):
            raise FormatError('expected selected DBPF 3.0')
        index_size, = struct.unpack_from('<I', header, 44)
        index_offset, = struct.unpack_from('<I', header, 64)
        if package.stat().st_size != expected_bytes:
            raise FormatError('selected Graphics package size changed')
        if index_offset < 96 or index_size > expected_bytes - index_offset:
            raise FormatError('index outside Graphics package')
        if index_size > 8 * 1024 * 1024:
            raise FormatError('selected investigation index budget exceeded')
        stream.seek(index_offset)
        index = stream.read(index_size)
        if digest(header) != '0ab1f43303b6d32436d919419b57db9656df67f077790d58a3f190448d8fbd97' or digest(index) != 'bfc7feb82d2d3a17a828f20e0d1ad924fea94426808490e586ee3225c1240595':
            raise FormatError('selected package header/index identity changed')
        stream.seek(152564158)
        stored = stream.read(33479)
        if len(stored) != 33479:
            raise FormatError('truncated selected stored resource')
        stream.seek(0)
        package_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    decoded = refpack(stored, 55388)
    metadata = read_metadata(decoded)
    result = {'kind': 'local-selected-RW4-metadata-not-runtime',
              'reader': {'path': str(Path(__file__).resolve()),
                         'sha256': digest(Path(__file__).read_bytes()),
                         'format_manifest': 'public-part-definition-contracts.json'},
              'package': {'path': str(package.resolve()), 'bytes': expected_bytes,
                          'sha256': package_hash, 'header_sha256': digest(header),
                          'index_sha256': digest(index)},
              'key': {'type': '0x2f4e681b', 'group': '0x40606000', 'instance': '0x0df11468'},
              'resource': {'offset': 152564158, 'stored_bytes': 33479,
                           'memory_bytes': 55388, 'compression': '0xffff',
                           'stored_sha256': digest(stored), 'decoded_sha256': digest(decoded)},
              'metadata': metadata,
              'limits': ['Package/header/index hashes are observations, not load order.',
                         'Default-time units, mouse mapping and execution not recovered.',
                         'No model, texture or complete animation blob exported.',
                         'Encoded subreferences are preserved but not resolved.']}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.package, args.output)
    print(json.dumps({'sections': result['metadata']['section_count'],
                      'handles': len(result['metadata']['handles']),
                      'skeletons': result['metadata']['skeletons']}, ensure_ascii=False))
