"""Read-only, bounded research reader; not a general DBPF tool or REA provider.

Format references are pinned in ../evidence/public-dbpf-prop-format-sources.json.
Only four named attack families (levels 1..5), their templates, and referenced
parents are decoded. No executable, package, asset or save is modified.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


class FormatError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fnv(name):
    value = 0x811C9DC5
    for char in name.lower():
        value = ((value * 0x1000193) & 0xFFFFFFFF) ^ ord(char)
    return value


def key(type_id, group_id, instance_id):
    return tuple((type_id, group_id, instance_id))


def key_json(value):
    return dict(zip(('type', 'group', 'instance'), (f'0x{x:08x}' for x in value)))


class Cursor:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, size):
        if size < 0 or size > len(self.data) - self.pos:
            raise FormatError(f'truncated input: offset={self.pos}, needed={size}')
        result = self.data[self.pos:self.pos + size]
        self.pos += size
        return result

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))


def refpack(data, expected):
    c = Cursor(data)
    first, marker = c.unpack('BB')
    if first not in (0x10, 0x50) or marker != 0xFB:
        raise FormatError('unsupported RefPack header')
    declared = int.from_bytes(c.take(3), 'big')
    if declared != expected:
        raise FormatError('RefPack length differs from DBPF memory size')
    out = bytearray()
    terminated = False
    while c.pos < len(data):
        control = c.take(1)[0]
        length, offset = 0, 0
        if control >= 0xFC:
            literals = control & 3
            terminated = True
        elif control >= 0xE0:
            literals = ((control & 31) << 2) + 4
        elif control >= 0xC0:
            a, b, d = c.unpack('BBB')
            literals = control & 3
            length = ((control & 12) << 6) + d + 5
            offset = ((control & 16) << 12) + (a << 8) + b + 1
        elif control >= 0x80:
            a, b = c.unpack('BB')
            literals = a >> 6
            length = (control & 63) + 4
            offset = ((a & 63) << 8) + b + 1
        else:
            a = c.take(1)[0]
            literals = control & 3
            length = ((control & 28) >> 2) + 3
            offset = ((control & 96) << 3) + a + 1
        if len(out) + literals + length > expected:
            raise FormatError('RefPack output exceeds declared length')
        out.extend(c.take(literals))
        if length and (offset == 0 or offset > len(out)):
            raise FormatError('invalid RefPack back reference')
        for _ in range(length):
            out.append(out[-offset])  # Overlapping references are intentional.
        if terminated:
            break
    if not terminated or len(out) != expected or c.pos != len(data):
        raise FormatError('RefPack missing terminator, length mismatch or trailing bytes')
    return bytes(out)


def read_index(data):
    if len(data) < 96 or data[:4] != b'DBPF' or struct.unpack_from('<II', data, 4) != (3, 0):
        raise FormatError('expected DBPF 3.0')
    count = struct.unpack_from('<I', data, 36)[0]
    size, offset = (struct.unpack_from('<I', data, i)[0] for i in (44, 64))
    if offset < 96 or size > len(data) - offset:
        raise FormatError('index outside package')
    c = Cursor(data[offset:offset + size])
    flags, = c.unpack('<I')
    if flags & ~7 or not flags & 4:
        raise FormatError('unsupported index flags; reader requires common high-ID slot')
    common_type = c.unpack('<I')[0] if flags & 1 else None
    common_group = c.unpack('<I')[0] if flags & 2 else None
    if c.unpack('<I')[0] != 0:
        raise FormatError('nonzero high-ID slot unsupported')
    record_size = 20 + (4 if common_type is None else 0) + (4 if common_group is None else 0)
    if count * record_size != len(c.data) - c.pos:
        raise FormatError('index count/size mismatch')
    entries = {}
    for _ in range(count):
        type_id = c.unpack('<I')[0] if common_type is None else common_type
        group_id = c.unpack('<I')[0] if common_group is None else common_group
        instance, start, stored, memory, compression, saved, pad = c.unpack('<IIIIHBB')
        stored &= 0x7FFFFFFF
        resource_key = key(type_id, group_id, instance)
        if resource_key in entries or start < 96 or stored > len(data) - start:
            raise FormatError('duplicate key or resource outside package')
        if compression not in (0, 0xFFFF):
            raise FormatError(f'unsupported compression: {compression:#x}')
        entries[resource_key] = dict(offset=start, stored_bytes=stored,
                                     memory_bytes=memory, compression=compression)
    return entries, dict(index_count=count, index_offset=offset,
                         index_bytes=size, index_flags=flags, examined_entries=count)


def read_prop(data):
    c = Cursor(data)
    count, = c.unpack('>I')
    if count > (len(data) - 4) // 8:
        raise FormatError('impossible property count')
    properties = {}
    numeric = {1: '?', 2: 'B', 3: 'H', 5: 'b', 6: 'B', 7: 'h',
               8: 'H', 9: 'i', 10: 'I', 11: 'q', 12: 'Q', 13: 'f', 14: 'd'}
    vectors = {0x30: 2, 0x31: 3, 0x32: 3, 0x33: 4, 0x34: 4}
    for _ in range(count):
        prop_id, type_id, flags = c.unpack('>IHH')
        if prop_id in properties or flags & 0x40:
            raise FormatError('duplicate property or unsupported flag 0x40')
        array = bool(flags & 0x30)
        items, item_size = c.unpack('>II') if array else (1, None)
        if items > len(data):
            raise FormatError('impossible array count')
        values = []
        for _ in range(items):
            if type_id in numeric:
                fmt = '>' + numeric[type_id]
                if array and item_size != struct.calcsize(fmt):
                    raise FormatError('numeric array item-size mismatch')
                value, = c.unpack(fmt)
                if isinstance(value, float) and not math.isfinite(value):
                    raise FormatError('nonfinite property value')
            elif type_id == 0x20:
                instance, resource_type, group = c.unpack('<III')
                value = key_json(key(resource_type, group, instance))
                if not array:
                    c.take(4)
                elif item_size != 12:
                    raise FormatError('key array item-size mismatch')
            elif type_id in (0x12, 0x13):
                length, = c.unpack('>I')
                value = c.take(length * (2 if type_id == 0x13 else 1)).decode(
                    'utf-16-le' if type_id == 0x13 else 'ascii')
            elif type_id == 0x22:
                table, instance = c.unpack('<II')
                c.take(512)  # Text itself is irrelevant to this study and not exported.
                value = {'table': f'0x{table:08x}', 'instance': f'0x{instance:08x}'}
                if array and item_size != 520:
                    raise FormatError('localized text item-size mismatch')
            elif type_id in vectors:
                n = vectors[type_id]
                value = list(c.unpack('<' + 'f' * n))
                if not all(math.isfinite(v) for v in value):
                    raise FormatError('nonfinite vector')
                if not array:
                    c.take(16 - n * 4)
                elif item_size != n * 4:
                    raise FormatError('vector item-size mismatch')
            else:
                raise FormatError(f'unsupported property type {type_id:#x} at {c.pos}')
            values.append(value)
        properties[prop_id] = dict(type=f'0x{type_id:04x}', flags=f'0x{flags:04x}',
                                   array=array, values=values)
    if c.pos != len(data):
        raise FormatError(f'PROP trailing bytes: {len(data) - c.pos}')
    return properties


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent.parent / 'evidence'
    registry = json.loads((evidence / 'public-ability-name-and-type-registry.json').read_text(encoding='utf-8'))
    prop_names = {0x00B2CCCB: 'parent', 0x06838638: 'creatureExtentsContributionScale'}
    for source in registry['files']:
        if source['path'] == 'reg_property.txt':
            for item in source['selected_declarations']:
                bits = item['text'].split()
                if len(bits) == 2 and bits[1].startswith('0x'):
                    prop_names[int(bits[1], 16)] = bits[0]
    names = [a + str(i) for a in ('bite', 'strike', 'charge', 'spit') for i in range(1, 6)]
    names += ['BiteTemplate', 'StrikeTemplate', 'ChargeTemplate', 'SpitTemplate']
    names_by_id = {fnv(name): name for name in names + ['CreatureAbilityTemplate']}
    selected = set(key(0xB1B104, 0xD2FCB262 if name.endswith('Template') else fnv('CreatureAbilities'), fnv(name)) for name in names)
    packages = []
    for filename in ('Spore_Game.package', 'PatchData.package'):
        path = args.data / filename
        data = path.read_bytes()
        entries, info = read_index(data)
        packages.append((data, entries, dict(path=str(path.resolve()), sha256=digest(data),
                                             bytes=len(data), **info)))
    records, missing, done = [], [], set()
    pending = list(sorted(selected))
    while pending:
        resource_key = pending.pop()
        if resource_key in done:
            continue
        done.add(resource_key)
        if len(done) > 128:
            raise FormatError('research budget exceeded: selected plus parents >128')
        present = False
        for data, entries, info in packages:
            if resource_key not in entries:
                continue
            present = True
            entry = entries[resource_key]
            if entry['memory_bytes'] > 2 * 1024 * 1024:
                raise FormatError('selected resource exceeds 2 MiB research budget')
            raw = data[entry['offset']:entry['offset'] + entry['stored_bytes']]
            decoded = refpack(raw, entry['memory_bytes']) if entry['compression'] else raw
            if len(decoded) != entry['memory_bytes']:
                raise FormatError('uncompressed resource size mismatch')
            props = read_prop(decoded)
            selected_props = {prop_names[i]: dict(id=f'0x{i:08x}', **p)
                              for i, p in props.items() if i in prop_names}
            record = dict(package=Path(info['path']).name,
                                name=names_by_id.get(resource_key[2]), key=key_json(resource_key),
                                **entry, stored_sha256=digest(raw), decoded_sha256=digest(decoded),
                                property_count=len(props),
                                property_ids=[f'0x{i:08x}' for i in props],
                                selected_properties=selected_props)
            records.append(record)
            if 0x00B2CCCB in props:
                parent = props[0x00B2CCCB]['values']
                if len(parent) != 1 or not isinstance(parent[0], dict) or 'type' not in parent[0]:
                    raise FormatError('unexpected parent representation')
                parent_key = tuple(int(parent[0][field], 16) for field in ('type', 'group', 'instance'))
                if any(parent_key):
                    if parent_key[0] == 0:
                        # Keep the source key intact. This is a PROP-only research
                        # lookup candidate, not a claim about the engine resolver.
                        candidate = key(0xB1B104, parent_key[1], parent_key[2])
                        record['parent_lookup_candidate'] = dict(
                            raw=key_json(parent_key), candidate=key_json(candidate),
                            status='inferred PROP candidate by group/instance; runtime resolution unverified')
                        pending.append(candidate)
                    else:
                        pending.append(parent_key)
        if not present:
            missing.append(key_json(resource_key))
    output = dict(kind='local-read-only-config-observation-not-REA-Evidence',
                  scope='four attack families levels 1..5, templates and referenced parents only',
                  package_load_order='unknown; records kept separately; no effective override claim',
                  format_source_commit=registry['commit'], reader_sha256=digest(Path(__file__).read_bytes()),
                  packages=[p[2] for p in packages], selected_keys=[key_json(k) for k in sorted(selected)],
                  missing_keys=missing, records=records)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(records=len(records), distinct_keys=len(done), missing=len(missing),
                          output=str(args.output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
