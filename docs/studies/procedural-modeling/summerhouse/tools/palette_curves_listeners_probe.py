"""Read shipped SUMMERHOUSE blend curves and particle listener instances offline.

Exact Unity 2023.2.22f1 metadata profile. Curve keyframes reuse the native float
AnimationCurve tree; target Evaluate, lifecycle methods and ParticleSystems never run.
"""
import argparse
import copy
import json
from pathlib import Path

from mask_target_probe import ROOT, VERSION, load

MVID = '84569538-a19f-4c17-8ccf-f40b95e99253'
METADATA = {'ColorBlendingCurves': ('blending-curves-metadata.json', 10),
            'ColorManager': ('manager-metadata.json', 7),
            'SharedVariable': ('variable-metadata.json', 3),
            'SharedVariableListener': ('listener-metadata.json', 1)}


def probe(game_data, schema_path, metadata_dir):
    indexer = load('curve_resource_index', ROOT / 'tools/unity22-compute-probe.py')
    Reader = load('curve_native_reader', ROOT / 'sandcastle/tools/player_color_space_probe.py').ObjectReader
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    if schema['Version'] != VERSION:
        raise ValueError('Expected exact 2023.2.22f1 schema')
    classes = {x['TypeID']: x['ReleaseRootNode'] for x in schema['Classes']}
    float_curves = []

    def collect(node):
        if node['TypeName'] == 'AnimationCurve':
            key = node['SubNodes'][0]['SubNodes'][0]['SubNodes'][1]
            value = next((x for x in key['SubNodes'] if x['Name'] == 'value'), None)
            if value and value['TypeName'] == 'float':
                float_curves.append(node)
        for child in node['SubNodes']:
            collect(child)
    collect(classes[74])
    if len(float_curves) != 1:
        raise ValueError('Expected one native AnimationClip float-curve template')
    fields = {}
    for name, (filename, count) in METADATA.items():
        source = json.loads((metadata_dir / filename).read_text(encoding='utf-8-sig'))
        if (source['mvid'], source['type']) != (MVID, name):
            raise ValueError('Selected script metadata identity changed: ' + name)
        fields[name] = [f for f in source['declared_fields'] if not f['flags'] & (0x10 | 0x80)
                        and ((f['flags'] & 7) == 6 or any(a['constructor'] == 'UnityEngine.SerializeField::.ctor'
                                                        for a in f['custom_attributes']))]
        if len(fields[name]) != count:
            raise ValueError('Selected serialized field count changed: ' + name)

    def leaf(name, kind):
        return {'Name': name, 'TypeName': kind, 'ByteSize': 4, 'MetaFlag': 0, 'SubNodes': []}

    def field_node(name, kind):
        if kind == 'UnityEngine.AnimationCurve':
            node = copy.deepcopy(float_curves[0])
        elif kind in ['ColorPalette', 'ColorBlendingCurves', 'SharedVariable', 'UnityEngine.Material']:
            node = copy.deepcopy(next(x for x in classes[114]['SubNodes'] if x['Name'] == 'm_Script'))
            node['TypeName'] = 'PPtr<' + kind + '>'
        elif kind == 'UnityEngine.Material[]':
            node = {'TypeName': 'vector', 'Name': name, 'ByteSize': -1, 'MetaFlag': 0,
                    'SubNodes': [{'TypeName': 'Array', 'Name': 'Array', 'ByteSize': -1, 'MetaFlag': 0,
                                  'SubNodes': [leaf('size', 'int'), field_node('data', 'UnityEngine.Material')]}]}
        elif kind in ['ColorManager+SavePalette', 'SharedVariable+VariableType']:
            node = leaf(name, 'int')
        elif kind == 'Single':
            node = leaf(name, 'float')
        elif kind == 'UnityEngine.Color':
            node = {'Name': name, 'TypeName': 'ColorRGBA', 'ByteSize': 16, 'MetaFlag': 0,
                    'SubNodes': [leaf(c, 'float') for c in ['r', 'g', 'b', 'a']]}
        else:
            raise ValueError('Unsupported selected custom field type: ' + kind)
        node['Name'] = name
        return node
    custom_nodes = {}
    for name, members in fields.items():
        node = copy.deepcopy(classes[114])
        node['SubNodes'].extend(field_node(f['name'], f['field_type']) for f in members)
        custom_nodes[name] = node
    files = {}
    decoded = {}

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

    def resolve(source, pointer, class_id=None):
        if pointer['m_PathID'] == 0:
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
        if class_id is not None and obj['class_id'] != class_id:
            raise ValueError('Selected referenced class changed')
        return path, raw[obj['offset']:obj['offset']+obj['bytes']], obj

    def decode(source, pointer, class_id, custom=None):
        selected = resolve(source, pointer, class_id)
        if selected is None:
            return None
        path, payload, obj = selected
        key = (path, obj['path_id'], custom)
        if key not in decoded:
            reader = Reader(payload)
            value = reader.parse(custom_nodes[custom] if custom else classes[class_id])
            if reader.pos != len(payload):
                raise ValueError(f'Object not fully consumed: {path.name}/{obj["path_id"]} {reader.pos}/{len(payload)}')
            if custom:
                script = decode(path, value['m_Script'], 115)
                if (script['value']['m_ClassName'], script['value']['m_AssemblyName']) != (custom, 'Assembly-CSharp'):
                    raise ValueError('Selected MonoScript identity changed')
            decoded[key] = {'resource': str(path), 'object': obj, 'value': value,
                            'bytes_consumed': reader.pos, 'fields': reader.fields}
        return decoded[key]

    def local(path_id):
        return {'m_FileID': 0, 'm_PathID': path_id}

    def hierarchy(scene, pointer):
        chain, seen = [], set()
        current = pointer
        while current['m_PathID']:
            go = decode(scene, current, 1)
            key = (go['resource'], go['object']['path_id'])
            if key in seen:
                raise ValueError('Transform hierarchy cycle')
            seen.add(key)
            chain.append({'path_id': go['object']['path_id'], 'name': go['value']['m_Name'],
                          'activeSelf': go['value']['m_IsActive']})
            transforms = []
            for comp in go['value']['m_Component']['Array']:
                selected = resolve(Path(go['resource']), comp['component'])
                if selected and selected[2]['class_id'] == 4:
                    transforms.append(decode(Path(go['resource']), comp['component'], 4))
            if len(transforms) != 1:
                raise ValueError('Expected one Transform on selected listener ancestor')
            parent = transforms[0]['value']['m_Father']
            if not parent['m_PathID']:
                break
            transform = decode(scene, parent, 4)
            current = transform['value']['m_GameObject']
        return chain

    managers, listeners = [], []
    curve_assets, variables = {}, {}
    for name in ['level0', 'level1', 'level2', 'level3', 'level4']:
        scene, (raw, _, objects) = resource(name)
        for obj in objects.values():
            if obj['class_id'] != 114:
                continue
            reader = Reader(raw[obj['offset']:obj['offset']+obj['bytes']])
            base = reader.parse(classes[114])
            script = decode(scene, base['m_Script'], 115)
            class_name = script['value']['m_ClassName'] if script else None
            if class_name == 'ColorManager':
                manager = decode(scene, local(obj['path_id']), 114, class_name)
                curves = decode(scene, manager['value']['colorBlendingCurves'], 114, 'ColorBlendingCurves')
                curve_key = Path(curves['resource']).name + ':' + str(curves['object']['path_id'])
                if curve_key not in curve_assets:
                    curves = copy.deepcopy(curves)
                    curves['exception_materials'] = []
                    for ref in curves['value']['exceptionMaterials']['Array']:
                        material = decode(Path(curves['resource']), ref, 21)
                        curves['exception_materials'].append(None if material is None else
                            {'resource': material['resource'], 'object': material['object'],
                             'bytes_consumed': material['bytes_consumed'], 'name': material['value']['m_Name']})
                    curve_assets[curve_key] = curves
                manager['curve_key'] = curve_key
                managers.append(manager)
            elif class_name == 'SharedVariableListener':
                listener = copy.deepcopy(decode(scene, local(obj['path_id']), 114, class_name))
                variable = decode(scene, listener['value']['variable'], 114, 'SharedVariable')
                if variable is None or variable['value']['type'] not in (0, 1):
                    raise ValueError('Unsupported selected listener variable')
                variable_key = Path(variable['resource']).name + ':' + str(variable['object']['path_id'])
                variables[variable_key] = variable
                listener['variable_key'] = variable_key
                listener['hierarchy'] = hierarchy(scene, listener['value']['m_GameObject'])
                listener['serialized_active_chain'] = all(x['activeSelf'] for x in listener['hierarchy'])
                go = decode(scene, listener['value']['m_GameObject'], 1)
                targets = [resolve(scene, c['component']) for c in go['value']['m_Component']['Array']]
                listener['particle_systems'] = [item[2] for item in targets if item and item[2]['class_id'] == 198]
                listeners.append(listener)
    if len(managers) != 4 or not listeners:
        raise ValueError('Selected scene manager/listener coverage changed')
    return {'game_data': str(game_data), 'schema_version': VERSION, 'metadata_mvid': MVID,
            'curve_template': 'AnimationClip/m_FloatCurves/Array/data/curve; Keyframe version3, 28B',
            'managers': managers, 'curve_assets': curve_assets, 'listeners': listeners, 'variables': variables,
            'files': [{'path': str(p), 'externals': index['externals']} for p, (_, index, _) in files.items()],
            'scope': 'five shipped scenes; custom records/native GO/Transform complete; ParticleSystem identity only',
            'runtime': 'Not Run', 'digests': 'Not computed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['game-data', 'schema', 'metadata-dir', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists')
    result = probe(args.game_data.resolve(strict=True), args.schema.resolve(strict=True), args.metadata_dir.resolve(strict=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'managers': len(result['managers']), 'curves': len(result['curve_assets']),
                      'listeners': len(result['listeners']), 'variables': len(result['variables'])}))


if __name__ == '__main__':
    main()
