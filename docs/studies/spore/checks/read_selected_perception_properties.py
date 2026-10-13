"""Read only CreatureGameTuning PROP variants; export selected AI names, not assets.

Registry identifiers and package records are observations. Do not merge variants
or infer their runtime owners, defaults, units, or package load precedence.
"""
import argparse
import json
from pathlib import Path

from read_selected_ability_properties import FormatError, digest, fnv, key_json, read_index, read_prop, refpack


def names_from_registry(registry):
    names = {0x00B2CCCB: 'parent'}
    for row in registry['selected_declarations']:
        tokens = row['text'].split()
        name = tokens[0]
        if not name.lower().startswith('creature') or 'scenario' in name.lower():
            continue
        ident = int(tokens[1], 16) if len(tokens) == 2 else fnv(name)
        if ident in names and names[ident] != name:
            raise FormatError('conflicting selected property names')
        names[ident] = name
    # Bare registered name already pinned by module 26: lowercase FNV1 identifier.
    names[fnv('creatureHitPointsTurnAndFightPercentage')] = 'creatureHitPointsTurnAndFightPercentage'
    return names


def observe(data, package_name, names):
    entries, index_info = read_index(data)
    records = []
    for k, entry in sorted(entries.items()):
        if k[0] != 0x00B1B104 or k[2] != fnv('CreatureGameTuning'):
            continue
        if entry['memory_bytes'] > 2 * 1024 * 1024:
            raise FormatError('selected resource exceeds 2 MiB research budget')
        raw = data[entry['offset']:entry['offset'] + entry['stored_bytes']]
        decoded = refpack(raw, entry['memory_bytes']) if entry['compression'] else raw
        if len(decoded) != entry['memory_bytes']:
            raise FormatError('selected resource size mismatch')
        props = read_prop(decoded)
        records.append(dict(package=package_name, key=key_json(k), **entry,
                            stored_sha256=digest(raw), decoded_sha256=digest(decoded),
                            property_count=len(props),
                            selected_properties={names[i]: dict(id=f'0x{i:08x}', **p)
                                                 for i, p in props.items() if i in names},
                            not_written_here=[n for i, n in names.items() if i not in props]))
    return records, index_info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent.parent / 'evidence'
    registry = json.loads((evidence / 'public-perception-motive-registry.json').read_text(encoding='utf-8'))
    names = names_from_registry(registry)
    records, packages = [], []
    for filename in ('Spore_Game.package', 'PatchData.package'):
        path = args.data / filename
        data = path.read_bytes()
        rows, info = observe(data, filename, names)
        records.extend(rows)
        packages.append(dict(path=str(path.resolve()), bytes=len(data), sha256=digest(data), **info))
    if not records:
        raise FormatError('no selected CreatureGameTuning PROP resources found')
    output = dict(kind='local-config-observation-not-REA-Evidence',
                  scope='CreatureGameTuning PROP variants only; selected perception/hunger/flee/target names',
                  package_load_order='unknown; variants remain separate',
                  absence_semantics='not written in this record, not a claim of absent runtime/default/inherited behavior',
                  registry_commit=registry['commit'], registry_sha256=registry['sha256'],
                  reader_sha256=digest(Path(__file__).read_bytes()),
                  shared_reader_sha256=digest(Path(__file__).with_name('read_selected_ability_properties.py').read_bytes()),
                  packages=packages, records=records)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(records=len(records), output=str(args.output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
