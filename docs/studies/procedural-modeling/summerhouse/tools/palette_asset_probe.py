"""Read selected shipped SUMMERHOUSE palettes and their scene manager offline.

Narrow 2023.2.22f1 / Assembly-CSharp MVID profile. No target execution or digests.
Only parameter values, references and native Material/MonoScript facts are saved.
"""
import argparse
import json
import math
import struct
from pathlib import Path

from mask_target_probe import ROOT, VERSION, load

MVID = '84569538-a19f-4c17-8ccf-f40b95e99253'
METADATA = {'ColorPalette': 'color-palette.json', 'ColorManager': 'color-manager.json',
            **{'ColorPalette+' + n: n + '.json' for n in
               ['MaterialColorPair', 'AdditionalMaterialSetup', 'TerrainDetailColorPair',
                'TerrainLayerTintPair', 'DirectionalLightSettings', 'SharedVariableSettings']}}
REFERENCES = {'UnityEngine.Material', 'UnityEngine.TerrainData', 'UnityEngine.Rendering.VolumeProfile',
              'SharedVariable', 'ColorPalette', 'ColorBlendingCurves'}


def probe(game_data, schema_path, metadata_dir):
    unity = load('palette_resource_index', ROOT / 'tools/unity22-compute-probe.py')
    Reader = load('palette_native_reader', ROOT / 'sandcastle/tools/player_color_space_probe.py').ObjectReader
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    if schema['Version'] != VERSION:
        raise ValueError('Expected exact 2023.2.22f1 schema')
    classes = {x['TypeID']: x['ReleaseRootNode'] for x in schema['Classes']}
    fields = {}
    for type_name, filename in METADATA.items():
        metadata = json.loads((metadata_dir / filename).read_text(encoding='utf-8-sig'))
        if (metadata['type'], metadata['mvid']) != (type_name, MVID):
            raise ValueError('Selected type/MVID does not match metadata: ' + type_name)
        fields[type_name] = [f for f in metadata['declared_fields'] if not f['flags'] & (0x10 | 0x80)
                             and (f['flags'] & 7 == 6 or any(a['constructor'] == 'UnityEngine.SerializeField::.ctor'
                                                           for a in f['custom_attributes']))]
    # A different serializer layout must not silently become a new supported profile.
    if (len(fields['ColorPalette']), len(fields['ColorManager'])) != (29, 7):
        raise ValueError('Selected serialized field count changed')
    loaded = {}

    def resource(name):
        path = (game_data / name).resolve(strict=True)
        if path.parent != game_data:
            raise ValueError('Selected resource leaves data directory')
        if path not in loaded:
            raw, index = unity.resource_index(path, include_externals=True)
            if (index['unity'], index['format'], index['type_trees']) != (VERSION, 22, False):
                raise ValueError('Unsupported resource profile')
            loaded[path] = (raw, index, {x['path_id']: x for x in index['objects']})
        return path, loaded[path]

    def resolve(source, pointer, class_id=None):
        if pointer['m_PathID'] == 0:
            return None
        target = source
        if pointer['m_FileID']:
            _, (_, index, _) = resource(source.name)
            matches = [x for x in index['externals'] if x['file_id'] == pointer['m_FileID']]
            if len(matches) != 1 or Path(matches[0]['path']).name != matches[0]['path']:
                raise ValueError('Unsupported selected external reference')
            target = source.parent / matches[0]['path']
        path, (raw, _, objects) = resource(target.name)
        obj = objects[pointer['m_PathID']]
        if class_id is not None and obj['class_id'] != class_id:
            raise ValueError('Referenced class differs')
        return path, raw[obj['offset']:obj['offset']+obj['bytes']], obj

    def native(source, pointer, class_id):
        selected = resolve(source, pointer, class_id)
        if selected is None:
            return None
        path, payload, obj = selected
        reader = Reader(payload)
        value = reader.parse(classes[class_id])
        if reader.pos != len(payload):
            raise ValueError('Native object was not completely consumed')
        if class_id == 21:
            value = {key: value[key] for key in ['m_Name', 'm_Shader']}
        return {'resource': str(path), 'object': obj, 'bytes_consumed': reader.pos, 'value': value,
                'projection': 'Material name/shader only' if class_id == 21 else 'complete native fields'}

    class CustomReader:
        def __init__(self, payload, offset):
            self.payload, self.pos, self.locations = payload, offset, []

        def take(self, count):
            if count < 0 or self.pos + count > len(self.payload):
                raise ValueError('Custom field exceeds selected object')
            value = self.payload[self.pos:self.pos+count]
            self.pos += count
            return value

        def unpack(self, kind, count):
            return struct.unpack(kind, self.take(count))

        def field(self, name, kind):
            start = self.pos
            value = self.value(kind)
            self.locations.append({'name': name, 'field_type': kind, 'offset': start, 'end': self.pos})
            return value

        def value(self, kind):
            if kind == 'String':
                length, = self.unpack('<i', 4)
                value = self.take(length).decode('utf-8', errors='strict')
                padding = self.take((-self.pos) % 4)
                if any(padding):
                    raise ValueError('Nonzero selected string padding')
                return value
            if kind in ['Int32', 'ColorManager+SavePalette']:
                return self.unpack('<i', 4)[0]
            if kind == 'Single' or kind == 'UnityEngine.Color':
                values = self.unpack('<f' if kind == 'Single' else '<4f', 4 if kind == 'Single' else 16)
                if not all(math.isfinite(v) for v in values):
                    raise ValueError('Nonfinite selected color/parameter')
                return values[0] if kind == 'Single' else list(values)
            if kind in REFERENCES:
                file_id, path_id = self.unpack('<iq', 12)
                if file_id < 0:
                    raise ValueError('Negative external reference index')
                return {'m_FileID': file_id, 'm_PathID': path_id}
            if kind.startswith('System.Collections.Generic.List`1<') and kind.endswith('>'):
                element = kind[len('System.Collections.Generic.List`1<'):-1]
                count, = self.unpack('<i', 4)
                if count < 0 or count > (len(self.payload) - self.pos) // 4:
                    raise ValueError('Selected list count exceeds payload bound')
                return [self.value(element) for _ in range(count)]
            if kind in fields:
                return {f['name']: self.field(f['name'], f['field_type']) for f in fields[kind]}
            raise ValueError('Unsupported selected field type: ' + kind)

    def custom(source, pointer, expected_type):
        selected = resolve(source, pointer, 114)
        if selected is None:
            raise ValueError('Expected nonnull custom object')
        path, payload, obj = selected
        base_reader = Reader(payload)
        base = base_reader.parse(classes[114])
        script = native(path, base['m_Script'], 115)
        if (script['value']['m_ClassName'], script['value']['m_AssemblyName']) != (expected_type, 'Assembly-CSharp'):
            raise ValueError('Selected MonoScript identity changed')
        reader = CustomReader(payload, base_reader.pos)
        value = {f['name']: reader.field(f['name'], f['field_type']) for f in fields[expected_type]}
        if reader.pos != len(payload):
            raise ValueError(f'Custom object not completely consumed: {reader.pos}/{len(payload)}')
        return {'resource': str(path), 'object': obj, 'name': base['m_Name'], 'base': base,
                'base_bytes': base_reader.pos, 'bytes_consumed': reader.pos,
                'script': script, 'fields': reader.locations, 'value': value}

    palette_path, _ = resource('sharedassets1.assets')
    palettes = []
    for path_id, name in [(107, 'Night'), (108, 'Rain'), (109, 'Sun')]:
        item = custom(palette_path, {'m_FileID': 0, 'm_PathID': path_id}, 'ColorPalette')
        if item['name'] != 'ColorPalette Lake ' + name + ' 01':
            raise ValueError('Selected palette name changed')
        item['materials'] = [native(palette_path, pair['Material'], 21) for pair in item['value']['materialColors']]
        item['additional_materials'] = [native(palette_path, pair['material'], 21)
                                        for pair in item['value']['additionalMaterialSetups']]
        item['skybox_material'] = native(palette_path, item['value']['proceduralSkyboxMaterial'], 21)
        palettes.append(item)
    scene, (raw, _, objects) = resource('level1')
    managers = []
    for obj in objects.values():
        if obj['class_id'] != 114:
            continue
        reader = Reader(raw[obj['offset']:obj['offset']+obj['bytes']])
        base = reader.parse(classes[114])
        script = native(scene, base['m_Script'], 115)
        if script and script['value']['m_ClassName'] == 'ColorManager':
            managers.append(custom(scene, {'m_FileID': 0, 'm_PathID': obj['path_id']}, 'ColorManager'))
    if len(managers) != 1:
        raise ValueError('Expected exactly one selected scene ColorManager')
    managers[0]['resolved_palettes'] = {}
    for field, path_id in [('colorPaletteSun', 109), ('colorPaletteRain', 108), ('colorPaletteNight', 107)]:
        target_path, _, obj = resolve(scene, managers[0]['value'][field], 114)
        if target_path != palette_path or obj['path_id'] != path_id:
            raise ValueError('Selected manager palette connection changed')
        managers[0]['resolved_palettes'][field] = {'resource': str(target_path), 'object': obj}
    settings_path, (_, _, settings_objects) = resource('globalgamemanagers')
    build_objects = [obj for obj in settings_objects.values() if obj['class_id'] == 141]
    if len(build_objects) != 1:
        raise ValueError('Expected exactly one native BuildSettings')
    build = native(settings_path, {'m_FileID': 0, 'm_PathID': build_objects[0]['path_id']}, 141)
    if build['value']['scenes']['Array'][1] != 'Assets/Scenes/Environment Lake/Environment Lake.unity':
        raise ValueError('Selected level1 scene identity changed')
    return {'game_data': str(game_data), 'schema_version': VERSION, 'metadata_mvid': MVID,
            'palettes': palettes, 'managers': managers, 'build_settings': build,
            'files': [{'path': str(p), 'externals': index['externals']} for p, (_, index, _) in loaded.items()],
            'scope': 'selected palettes/manager and referenced native materials complete; no runtime',
            'runtime': 'Not Run', 'digests': 'Not computed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['game-data', 'schema', 'metadata-dir', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists')
    result = probe(args.game_data.resolve(strict=True), args.schema.resolve(strict=True), args.metadata_dir.resolve(strict=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'palettes': len(result['palettes']), 'scene_managers': len(result['managers'])}))


if __name__ == '__main__':
    main()
