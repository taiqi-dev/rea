"""Read Shader622 forward vertex projection inputs and instructions offline.

Uses the exact shipped schema and existing bounded shader decoders. D3DDisassemble
decodes bytes; it does not create a graphics device or execute the target shader.
"""
import argparse
import json
from pathlib import Path

from material_shader_inputs_probe import parameter_record
from mask_render_route_probe import ROOT, VERSION, load, program_dxbc, program_records


def probe(resource, schema_path, output):
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    if schema['Version'] != VERSION:
        raise ValueError('Expected exact 2023.2.22f1 schema')
    indexer = load('projection_index', ROOT / 'tools/unity22-compute-probe.py')
    Reader = load('projection_reader', ROOT / 'sandcastle/tools/player_color_space_probe.py').ObjectReader
    shader = load('projection_shader_decode', ROOT / 'tools/unity22-shader-probe.py')
    data, index = indexer.resource_index(resource)
    if (index['unity'], index['format'], index['type_trees']) != (VERSION, 22, False):
        raise ValueError('Unsupported selected SerializedFile profile')
    matches = [x for x in index['objects'] if x['path_id'] == 622 and x['class_id'] == 48]
    if len(matches) != 1:
        raise ValueError('Expected one selected Shader622 object')
    obj = matches[0]
    node = next(x['ReleaseRootNode'] for x in schema['Classes'] if x['TypeID'] == 48)
    reader = Reader(data[obj['offset']:obj['offset'] + obj['bytes']])
    value = reader.parse(node)
    if reader.pos != obj['bytes']:
        raise ValueError('Selected Shader not completely consumed')
    parsed = value['m_ParsedForm']
    if parsed['m_Name'] != 'Shader Graphs/LitColorTriplanarNormalAnimatedShimmer':
        raise ValueError('Selected Shader identity changed')
    selected_pass = parsed['m_SubShaders']['Array'][0]['m_Passes']['Array'][0]
    names = {x['second']: x['first'] for x in selected_pass['m_NameIndices']['Array']}
    program = selected_pass['progVertex']
    common = program['m_CommonParameters']
    buffers = []
    for buffer in common['m_ConstantBuffers']['Array']:
        record = {'name': names[buffer['m_NameIndex']], 'bytes': buffer['m_Size'],
                  'partial': buffer['m_IsPartialCB'], 'matrices': [], 'vectors': []}
        for source, dest in [('m_MatrixParams', 'matrices'), ('m_VectorParams', 'vectors')]:
            record[dest] = [{'name': names[x['m_NameIndex']], **x} for x in buffer[source]['Array']]
        buffers.append(record)
    decoded, records = program_records(value, shader)
    variants = []
    keywords = parsed['m_KeywordNames']['Array']
    for group, parameters in zip(program['m_PlayerSubPrograms']['Array'],
                                 program['m_ParameterBlobIndices']['Array'], strict=True):
        for subprogram, parameter_index in zip(group['Array'], parameters['Array'], strict=True):
            blob = subprogram['m_BlobIndex']
            if not 0 <= blob < len(records) or not 0 <= parameter_index < len(records):
                raise ValueError('Selected vertex record exceeds table')
            at, code = program_dxbc(decoded, records[blob])
            text = indexer.disassemble(code)
            if 'vs_4_0' not in text:
                raise ValueError('Expected selected vertex shader model')
            filename = f'shader622-vertex-{blob}.asm.txt'
            with (output / filename).open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
            variants.append({'blob_index': blob, 'record': records[blob],
                             'keywords': [keywords[x] for x in subprogram['m_KeywordIndices']['Array']],
                             'parameters': parameter_record(decoded, records[parameter_index]),
                             'dxbc_record_offset': at, 'dxbc_bytes': len(code), 'disassembly': filename})
    if len(variants) != 2:
        raise ValueError('Selected forward vertex variant coverage changed')
    return {'resource': str(resource), 'resource_bytes': len(data), 'schema_version': VERSION,
            'object': obj, 'bytes_consumed': reader.pos, 'shader_name': parsed['m_Name'],
            'pass_name': selected_pass['m_State']['m_Name'], 'common_buffers': buffers,
            'variants': variants, 'runtime': 'Not Run', 'digests': 'Not computed',
            'scope': 'complete selected Shader object; forward common CB parameters and two vertex variants only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resource', type=Path)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output directory already exists')
    args.output.mkdir(parents=True)
    result = probe(args.resource.resolve(strict=True), args.schema.resolve(strict=True), args.output)
    with (args.output / 'projection-inputs.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'vertex_variants': len(result['variants']), 'bytes_consumed': result['bytes_consumed']}))


if __name__ == '__main__':
    main()
