"""Read lifecycle settings and ancestor components for shipped palette listeners.

Reuses the exact-version curve/listener reader to select instances afresh. Native
ParticleSystem, GameObject and Transform records are consumed completely; other
MonoBehaviours are read only through the script-reference prefix. No Unity code runs.
"""
import argparse
import json
from pathlib import Path

from mask_target_probe import ROOT, VERSION, load
from palette_curves_listeners_probe import probe as palette_probe


def probe(game_data, schema_path, metadata_dir):
    selected = palette_probe(game_data, schema_path, metadata_dir)
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    classes = {x['TypeID']: x['ReleaseRootNode'] for x in schema['Classes']}
    indexer = load('lifecycle_resource_index', ROOT / 'tools/unity22-compute-probe.py')
    Reader = load('lifecycle_native_reader', ROOT / 'sandcastle/tools/player_color_space_probe.py').ObjectReader
    files = {}

    def resource(name):
        path = (game_data / name).resolve(strict=True)
        if path.parent != game_data:
            raise ValueError('Resource leaves selected data directory')
        if path not in files:
            raw, index = indexer.resource_index(path, include_externals=True)
            if (index['unity'], index['format'], index['type_trees']) != (VERSION, 22, False):
                raise ValueError('Unsupported selected resource profile')
            files[path] = raw, index, {x['path_id']: x for x in index['objects']}
        return path, files[path]

    def resolve(source, pointer):
        if not pointer['m_PathID']:
            return None
        name = source.name
        if pointer['m_FileID']:
            _, (_, index, _) = resource(name)
            refs = [x for x in index['externals'] if x['file_id'] == pointer['m_FileID']]
            if len(refs) != 1 or Path(refs[0]['path']).name != refs[0]['path']:
                raise ValueError('Unsupported selected external reference')
            name = refs[0]['path']
        path, (raw, _, objects) = resource(name)
        obj = objects[pointer['m_PathID']]
        return path, raw[obj['offset']:obj['offset'] + obj['bytes']], obj

    def decode(source, pointer, class_id):
        item = resolve(source, pointer)
        if item is None or item[2]['class_id'] != class_id:
            raise ValueError('Selected referenced class changed')
        path, payload, obj = item
        reader = Reader(payload)
        value = reader.parse(classes[class_id])
        if reader.pos != len(payload) and class_id != 114:
            raise ValueError(f'Object not fully consumed: {path.name}/{obj["path_id"]}')
        return path, obj, value, reader.pos

    def local(path_id):
        return {'m_FileID': 0, 'm_PathID': path_id}

    ancestors, listeners = {}, []
    for listener in selected['listeners']:
        scene = Path(listener['resource'])
        particles = []
        for obj in listener['particle_systems']:
            path, actual, value, end = decode(scene, local(obj['path_id']), 198)
            if actual != obj:
                raise ValueError('Selected ParticleSystem identity changed')
            settings = {k: v for k, v in value.items() if not isinstance(v, (dict, list))}
            particles.append({'resource': path.name, 'object': obj, 'bytes_consumed': end,
                              'settings': settings})
        ancestor_keys = []
        for ancestor in listener['hierarchy']:
            key = scene.name + ':' + str(ancestor['path_id'])
            ancestor_keys.append(key)
            if key in ancestors:
                continue
            path, obj, go, end = decode(scene, local(ancestor['path_id']), 1)
            components = []
            for ref in go['m_Component']['Array']:
                component = resolve(path, ref['component'])
                if component is None:
                    components.append(None)
                    continue
                comp_path, _, comp_obj = component
                record = {'resource': comp_path.name, 'object': comp_obj}
                if comp_obj['class_id'] == 114:
                    _, _, base, prefix = decode(comp_path, local(comp_obj['path_id']), 114)
                    script_path, script_obj, script, script_end = decode(comp_path, base['m_Script'], 115)
                    record.update({'enabled': base['m_Enabled'], 'prefix_bytes_consumed': prefix,
                                   'script': {'resource': script_path.name, 'object': script_obj,
                                              'class': script['m_ClassName'],
                                              'assembly': script['m_AssemblyName'],
                                              'bytes_consumed': script_end}})
                components.append(record)
            ancestors[key] = {'resource': path.name, 'object': obj, 'bytes_consumed': end,
                              'name': go['m_Name'], 'activeSelf': go['m_IsActive'],
                              'components': components}
        listeners.append({'resource': scene.name, 'listener': listener['object'],
                          'variable_key': listener['variable_key'], 'enabled': listener['value']['m_Enabled'],
                          'ancestor_keys': ancestor_keys, 'particles': particles})
    return {'game_data': str(game_data), 'schema_version': VERSION, 'metadata_mvid': selected['metadata_mvid'],
            'listeners': listeners, 'ancestors': ancestors,
            'scope': 'five shipped scenes; complete selected native records; other MonoBehaviour script prefix only',
            'runtime': 'Not Run', 'digests': 'Not computed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['game-data', 'schema', 'metadata-dir', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists')
    result = probe(args.game_data.resolve(strict=True), args.schema.resolve(strict=True),
                   args.metadata_dir.resolve(strict=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'listeners': len(result['listeners']), 'ancestor_objects': len(result['ancestors']),
                      'particles': sum(len(x['particles']) for x in result['listeners'])}))


if __name__ == '__main__':
    main()
