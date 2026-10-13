"""Bounded PCTP v4 research reader. Scalar/identity metadata only, no game execution.

The v3 writer/reader discrepancy is preserved as an explicit unsupported profile.
Provenance: ../evidence/public-capability-binding-format-contracts.json.
"""
import argparse
import hashlib
import json
import math
import mmap
from pathlib import Path
import struct

from read_selected_ability_properties import Cursor, FormatError, read_index, refpack, key_json, fnv


TYPE = 0x7c19aa7a
SELECTED = (("Spore_Game.package", (TYPE, 0x6f14, 0xf8ccfe08)),
            ("PatchData.package", (TYPE, 0x82d0, 0x142d3338)))
ROLES = ('mout', 'grsp')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tag(cursor):
    stored = cursor.take(4)
    logical = stored[::-1]
    if any(value > 127 for value in logical):
        raise FormatError('non-ASCII role identifier')
    return {'stored_hex': stored.hex(), 'logical_hex': logical.hex(),
            'display': logical.replace(b'\0', b' ').decode('ascii')}


def count(cursor, minimum, label):
    value, = cursor.unpack('>i')
    if value < 0 or value > (len(cursor.data) - cursor.pos) // minimum:
        raise FormatError(f'impossible {label} count at {cursor.pos - 4}')
    return value


def read_pctp_v4(data):
    c = Cursor(data)
    magic, version = c.unpack('>Ii')
    if magic != 0x70637470:
        raise FormatError('PCTP magic mismatch')
    if version != 4:
        raise FormatError(f'unsupported PCTP profile version {version}; version3 is not assumed symmetric')
    priority, = c.unpack('>f')
    if not math.isfinite(priority):
        raise FormatError('non-finite PCTP priority')
    names, remaps, aggregates, deforms = [], [], [], []
    for _ in range(count(c, 8, 'name')):
        start = c.pos
        size, = c.unpack('>i')
        if size < 0 or size > len(c.data) - c.pos - 4:
            raise FormatError('invalid capability name length')
        raw = c.take(size)
        if any(value > 127 for value in raw):
            raise FormatError('non-ASCII capability name')
        name = raw.decode('ascii')
        names.append({'offset': start, 'name': name, 'name_ascii_hex': raw.hex(),
                      'name_fnv1_candidate': f'0x{fnv(name):08x}', 'role': tag(c)})
    for _ in range(count(c, 12, 'remap')):
        start = c.pos
        hash_id, = c.unpack('>I')
        role = tag(c)
        index, = c.unpack('>i')
        remaps.append({'offset': start, 'hash': f'0x{hash_id:08x}', 'role': role,
                       'index_raw': index})
    for _ in range(count(c, 8, 'aggregate')):
        start, role = c.pos, tag(c)
        children = [tag(c) for _ in range(count(c, 4, 'aggregate child'))]
        aggregates.append({'offset': start, 'role': role, 'children': children})
    for _ in range(count(c, 8, 'deform role')):
        start, role = c.pos, tag(c)
        entries = []
        for _ in range(count(c, 16, 'deform entry')):
            offset = c.pos
            deform_id, raw0, raw1, flags = c.unpack('>IffI')
            if not math.isfinite(raw0) or not math.isfinite(raw1):
                raise FormatError('non-finite deform parameter')
            entries.append({'offset': offset, 'deform_id': f'0x{deform_id:08x}',
                            'raw_float_0': raw0, 'raw_float_1': raw1,
                            'flags_raw': f'0x{flags:08x}'})
        deforms.append({'offset': start, 'role': role, 'entries': entries})
    if c.pos != len(data):
        raise FormatError(f'PCTP trailing bytes: {len(data) - c.pos}')
    return {'version': version, 'priority_raw': priority, 'names': names, 'remaps': remaps,
            'aggregates': aggregates, 'deforms': deforms, 'exact_end': c.pos}


def select_roles(parsed):
    exact = {role.encode('ascii').hex(): role for role in ROLES}
    result = []
    for raw, role in exact.items():
        selected_names = [n for n in parsed['names'] if n['role']['logical_hex'] == raw]
        selected_remaps = [r for r in parsed['remaps'] if r['role']['logical_hex'] == raw]
        selected_deforms = [d for d in parsed['deforms'] if d['role']['logical_hex'] == raw]
        candidate_hashes = {n['name_fnv1_candidate'] for n in selected_names}
        hash_matches = [r for r in selected_remaps if r['hash'] in candidate_hashes]
        result.append({'role': role, 'names': selected_names, 'remaps': selected_remaps,
                       'aggregates': [a for a in parsed['aggregates'] if a['role']['logical_hex'] == raw],
                       'deforms': selected_deforms,
                       'name_fnv1_to_stored_hash_matches': hash_matches})
    return result


def capture(data_directory, output):
    packages, records = [], []
    for filename, resource_key in SELECTED:
        path = data_directory / filename
        with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            entries, info = read_index(data)
            stream.seek(0)
            packages.append({'path': str(path.resolve()), 'bytes': len(data),
                             'sha256': hashlib.file_digest(stream, 'sha256').hexdigest(), **info})
            if resource_key not in entries:
                raise FormatError('previously selected PCTP key no longer present')
            entry = entries[resource_key]
            if entry['memory_bytes'] > 64 * 1024:
                raise FormatError('selected PCTP research budget exceeded')
            stored = data[entry['offset']:entry['offset'] + entry['stored_bytes']]
            decoded = refpack(stored, entry['memory_bytes']) if entry['compression'] else stored
            if len(decoded) != entry['memory_bytes']:
                raise FormatError('selected resource length mismatch')
            magic, version = struct.unpack('>Ii', decoded[:8])
            if magic != 0x70637470:
                raise FormatError('selected PCTP magic mismatch')
            record = {'package': filename, 'key': key_json(resource_key), **entry,
                      'stored_sha256': digest(stored), 'decoded_sha256': digest(decoded),
                      'version': version}
            if version == 4:
                parsed = read_pctp_v4(decoded)
                record.update({'status': 'parsed-v4-exact-end',
                               'counts': {n: len(parsed[n]) for n in ('names','remaps','aggregates','deforms')},
                               'priority_raw': parsed['priority_raw'], 'exact_end': parsed['exact_end'],
                               'selected_roles': select_roles(parsed)})
            else:
                record.update({'status': 'unsupported-profile-header-only',
                               'diagnostic': 'v3 read/write conditions differ; no effective mapping decoded',
                               'word_at_8_raw': f'0x{struct.unpack_from(">I",decoded,8)[0]:08x}',
                               'word_at_8_format_candidate': 'v3 name count, not a priority float'})
            records.append(record)
    result = {'kind': 'local-selected-PCTP-identities-and-fields-not-runtime',
              'reader_sha256': digest(Path(__file__).read_bytes()), 'packages': packages,
              'records': records, 'selected_role_policy': 'Exact logical role bytes mout/grsp; all sections traversed for boundaries, only these role records exported.',
              'limits': ['Two resource keys differ; not an override pair.',
                         'Shared PCTP context not proven to be Creature runtime.',
                         'Priority, remap index and deform floats are preserved, not executed.',
                         'FNV candidates are not PROP field IDs or bone indices.',
                         'No game/process/save/model/texture execution or export.']}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps([{'package': r['package'], 'status': r['status'],
                       'counts': r.get('counts'), 'roles': [x['role'] for x in r.get('selected_roles',[])]}
                      for r in records], ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-directory', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    capture(args.data_directory, args.output)
