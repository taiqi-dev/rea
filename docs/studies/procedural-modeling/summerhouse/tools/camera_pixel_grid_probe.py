"""Read shipped camera-controller curves and linked pixel-grid configuration offline.

Exact 2023.2.22f1 native schema and selected assembly MVIDs only. Consumes the
selected controller/feature/native objects completely; never evaluates Unity code.
"""
import argparse
import copy
import json
from pathlib import Path

from mask_target_probe import ROOT, VERSION, load

MVID = '84569538-a19f-4c17-8ccf-f40b95e99253'
TYPES = {'CameraController': ('camera-controller.json', MVID, 17),
         'Rendering.PixelateRendererFeature.PixelateLayer': ('pixelate-layer.json', MVID, 1),
         'Rendering.PixelateRendererFeature.PixelateLayer+Settings': ('pixelate-settings.json', MVID, 4),
         'UnityEngine.Rendering.Universal.ScriptableRendererFeature':
             ('feature-base.json', '441516f4-c7ab-401e-840b-a71a7013b536', 1)}


def probe(game_data, schema_path, metadata_dir):
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    if schema['Version'] != VERSION:
        raise ValueError('Expected exact 2023.2.22f1 schema')
    classes = {x['TypeID']: x['ReleaseRootNode'] for x in schema['Classes']}
    indexer = load('grid_resource_index', ROOT / 'tools/unity22-compute-probe.py')
    Reader = load('grid_native_reader', ROOT / 'sandcastle/tools/player_color_space_probe.py').ObjectReader
    fields = {}
    for kind, (filename, mvid, count) in TYPES.items():
        metadata = json.loads((metadata_dir / filename).read_text(encoding='utf-8-sig'))
        if (metadata['mvid'], metadata['type']) != (mvid, kind):
            raise ValueError('Selected type/MVID does not match metadata: ' + kind)
        selected = [f for f in metadata['declared_fields'] if not f['flags'] & (0x10 | 0x80)
                    and ((f['flags'] & 7) == 6 or any(a['constructor'] == 'UnityEngine.SerializeField::.ctor'
                                                    for a in f['custom_attributes']))]
        if len(selected) != count:
            raise ValueError('Selected serialized field count changed: ' + kind)
        fields[kind] = selected
    curve_nodes = []
    def find_curve(node):
        if node['TypeName'] == 'AnimationCurve':
            key = node['SubNodes'][0]['SubNodes'][0]['SubNodes'][1]
            if any(x['Name'] == 'value' and x['TypeName'] == 'float' for x in key['SubNodes']):
                curve_nodes.append(node)
        for sub in node['SubNodes']:
            find_curve(sub)
    find_curve(classes[74])
    if len(curve_nodes) != 1:
        raise ValueError('Expected one float AnimationCurve template')
    references = {'Rendering.PixelateRendererFeature.PixelateLayer', 'UnityEngine.Transform', 'UnityEngine.Shader'}

    def leaf(name, kind):
        return {'Name': name, 'TypeName': kind, 'ByteSize': 4, 'MetaFlag': 0, 'SubNodes': []}

    def node(name, kind):
        if kind == 'UnityEngine.AnimationCurve':
            value = copy.deepcopy(curve_nodes[0])
        elif kind in references:
            value = copy.deepcopy(next(x for x in classes[114]['SubNodes'] if x['Name'] == 'm_Script'))
        elif kind in ('Single', 'Int32'):
            value = leaf(name, 'float' if kind == 'Single' else 'int')
        elif kind == 'Boolean':
            value = {'Name': name, 'TypeName': 'bool', 'ByteSize': 1, 'MetaFlag': 0x4000, 'SubNodes': []}
        elif kind in ('UnityEngine.Vector2', 'UnityEngine.Vector3', 'UnityEngine.Vector2Int'):
            axes = 'xyz' if kind == 'UnityEngine.Vector3' else 'xy'
            value = {'Name': name, 'TypeName': kind, 'ByteSize': 4 * len(axes), 'MetaFlag': 0,
                     'SubNodes': [leaf(c, 'int' if kind.endswith('Int') else 'float') for c in axes]}
        elif kind == 'UnityEngine.LayerMask':
            value = {'Name': name, 'TypeName': kind, 'ByteSize': 4, 'MetaFlag': 0,
                     'SubNodes': [leaf('m_Bits', 'unsigned int')]}
        elif kind == 'Rendering.PixelateRendererFeature.PixelateLayer+Settings':
            value = {'Name': name, 'TypeName': kind, 'ByteSize': -1, 'MetaFlag': 0,
                     'SubNodes': [node(f['name'], f['field_type']) for f in fields[kind]]}
        else:
            raise ValueError('Unsupported selected field type: ' + kind)
        value['Name'] = name
        return value

    custom = {}
    for kind in ['CameraController', 'Rendering.PixelateRendererFeature.PixelateLayer']:
        value = copy.deepcopy(classes[114])
        members = fields[kind]
        if kind.endswith('PixelateLayer'):
            members = fields['UnityEngine.Rendering.Universal.ScriptableRendererFeature'] + members
        value['SubNodes'].extend(node(f['name'], f['field_type']) for f in members)
        custom[kind] = value
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

    def decode(source, pointer, expected, kind=None):
        if not pointer['m_PathID']:
            raise ValueError('Selected required reference is null')
        name = source.name
        if pointer['m_FileID']:
            _, (_, index, _) = resource(name)
            refs = [x for x in index['externals'] if x['file_id'] == pointer['m_FileID']]
            if len(refs) != 1 or Path(refs[0]['path']).name != refs[0]['path']:
                raise ValueError('Unsupported selected external reference')
            name = refs[0]['path']
        path, (raw, _, objects) = resource(name)
        obj = objects[pointer['m_PathID']]
        if obj['class_id'] != expected:
            raise ValueError('Selected referenced class changed')
        reader = Reader(raw[obj['offset']:obj['offset'] + obj['bytes']])
        value = reader.parse(custom[kind] if kind else classes[expected])
        if reader.pos != obj['bytes']:
            raise ValueError(f'Object not fully consumed: {path.name}/{obj["path_id"]} {reader.pos}/{obj["bytes"]}')
        if kind:
            script = decode(path, value['m_Script'], 115)
            if script['value']['m_ClassName'] != kind.split('.')[-1] or script['value']['m_AssemblyName'] != 'Assembly-CSharp':
                raise ValueError('Selected MonoScript identity changed')
        return {'resource': str(path), 'object': obj, 'bytes_consumed': reader.pos,
                'value': value, 'fields': reader.fields}

    controllers = []
    for name in ['level0', 'level1', 'level2', 'level3', 'level4']:
        scene, (raw, _, objects) = resource(name)
        for obj in objects.values():
            if obj['class_id'] != 114:
                continue
            base = Reader(raw[obj['offset']:obj['offset'] + obj['bytes']]).parse(classes[114])
            if not base['m_Script']['m_PathID']:
                continue
            script = decode(scene, base['m_Script'], 115)
            if script['value']['m_ClassName'] != 'CameraController' or script['value']['m_AssemblyName'] != 'Assembly-CSharp':
                continue
            controller = decode(scene, {'m_FileID': 0, 'm_PathID': obj['path_id']}, 114, 'CameraController')
            controller_go = decode(scene, controller['value']['m_GameObject'], 1)
            rig_transforms = [ref['component'] for ref in controller_go['value']['m_Component']['Array']
                              if ref['component']['m_FileID'] == 0
                              and objects[ref['component']['m_PathID']]['class_id'] == 4]
            if len(rig_transforms) != 1:
                raise ValueError('Expected one controller Transform')
            rig_transform = decode(scene, rig_transforms[0], 4)
            feature = decode(scene, controller['value']['pixelizeRenderFeature'], 114,
                             'Rendering.PixelateRendererFeature.PixelateLayer')
            camera_transform = decode(scene, controller['value']['cameraObject'], 4)
            go = decode(Path(camera_transform['resource']), camera_transform['value']['m_GameObject'], 1)
            cameras = []
            for ref in go['value']['m_Component']['Array']:
                # The selected native camera object is local in this shipped scene.
                if ref['component']['m_FileID'] != 0:
                    raise ValueError('Unexpected external camera component')
                if objects[ref['component']['m_PathID']]['class_id'] == 20:
                    cameras.append(decode(scene, ref['component'], 20))
            if len(cameras) != 1:
                raise ValueError('Expected one Camera on selected cameraObject')
            ancestry, seen = [], set()
            current = camera_transform
            while True:
                identity = (current['resource'], current['object']['path_id'])
                if identity in seen:
                    raise ValueError('Transform hierarchy cycle')
                seen.add(identity)
                native_go = decode(scene, current['value']['m_GameObject'], 1)
                components = []
                for ref in native_go['value']['m_Component']['Array']:
                    pointer = ref['component']
                    if pointer['m_FileID'] != 0:
                        raise ValueError('Unexpected external ancestor component')
                    comp_obj = objects[pointer['m_PathID']]
                    item = {'object': comp_obj}
                    if comp_obj['class_id'] == 114:
                        prefix_reader = Reader(raw[comp_obj['offset']:comp_obj['offset'] + comp_obj['bytes']])
                        base = prefix_reader.parse(classes[114])
                        script = decode(scene, base['m_Script'], 115)
                        item.update({'prefix_bytes_consumed': prefix_reader.pos,
                                     'script_class': script['value']['m_ClassName'],
                                     'script_assembly': script['value']['m_AssemblyName']})
                    components.append(item)
                ancestry.append({'transform': current, 'game_object': native_go, 'components': components})
                parent = current['value']['m_Father']
                if not parent['m_PathID']:
                    break
                current = decode(scene, parent, 4)
            controllers.append({'controller': controller, 'controller_game_object': controller_go,
                                'controller_transform': rig_transform, 'feature': feature,
                                'camera_transform': camera_transform, 'camera_game_object': go,
                                'camera': cameras[0], 'camera_ancestry': ancestry})
    if not controllers:
        raise ValueError('No selected CameraController instances')
    return {'game_data': str(game_data), 'schema_version': VERSION, 'metadata_mvid': MVID,
            'controllers': controllers, 'scope': 'five scenes; selected custom/native records fully consumed',
            'runtime': 'Not Run', 'digests': 'Not computed by this reader'}


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
    print(json.dumps({'controllers': len(result['controllers'])}))


if __name__ == '__main__':
    main()
