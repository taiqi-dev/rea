"""Capture only the selected skin PROP metadata and two effect-reference graphs.

Read-only inputs; no asset files or decoded effect blobs are exported.
Parser provenance is documented by module 36's pinned format manifests.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from read_selected_ability_properties import read_index, read_prop, refpack
from read_selected_skinpaint_sections import (read_component_sections, read_sections_at,
    read_visual_exports, read_sequences, read_distribute, trace_selected_visual)


PROP_NAMES={0x00f3892f:'ce_skinpaint_detail_stripesML',
            0x05475ea3:'ce_skinpaint_theme_giraffeArmor',
            0x085b9de0:'ce_skinpaint_base_melt'}
EXPORT_NAMES={0x103691ce:'skinpaint_detail_stripesML',0x8c7aa8c3:'skinpaint_base_melt',
              0x32fe45f6:'skinpaint_base_zebroid',0x8ac01a79:'skinpaint_coat_giraffe',
              0x203219f6:'skinpaint_detail_giraffeLimbs'}
PROPERTY_NAMES={11717834:'description',11717835:'parent',
                2967496359:'paintThemePaints',2967496360:'paintThemeColor1s'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def key_json(key):
    return dict(zip(('type','group','instance'),(f'0x{x:08x}' for x in key)))


def decoded_payload(raw, meta):
    stored=raw[meta['offset']:meta['offset']+meta['stored_bytes']]
    blob=refpack(stored,meta['memory_bytes']) if meta['compression']==0xffff else stored
    if len(blob)!=meta['memory_bytes']:
        raise ValueError('DecodedSizeMismatch')
    return blob,dict(stored_sha256=digest(stored),decoded_sha256=digest(blob),**meta)


def capture(directory):
    report=dict(kind='selected-local-config-and-reference-graph-observations-not-runtime',
                packages=[],selected_properties=[],effect_prefix_candidates=[],selected_effect_directories=[],
                limits={'prefix_budget_bytes':1048576,'prefix_scope':'12 normal-component envelopes only, six oversized effect candidates not decompressed',
                        'complete_directory_scope':'Two explicit Patch group40450200 csa/editors candidates; component payloads opaque except Distribute and Sequence',
                        'particle_settings_transform_payloads':'Particle, Settings, non-skin components, resources and most Visual fields remain opaque/skipped; not a complete effects exporter'})
    comparison_cache={}
    report['property_pair_comparisons']=[]
    for package in ('Spore_Game.package','PatchData.package'):
        path=directory/package
        raw=path.read_bytes();entries,stats=read_index(raw)
        report['packages'].append(dict(path=path.as_posix(),bytes=len(raw),sha256=digest(raw),index=stats))
        for instance,name in PROP_NAMES.items():
            key=(0x00b1b104,0x406a0200,instance);meta=entries[key]
            blob,identity=decoded_payload(raw,meta);props=read_prop(blob)
            if package=='Spore_Game.package':
                comparison_cache[instance]=(blob,props)
            else:
                original,old_props=comparison_cache[instance]
                report['property_pair_comparisons'].append(dict(instance=f'0x{instance:08x}',
                    interpreted_properties_equal=old_props==props,decoded_bytes_equal=original==blob,
                    same_decoded_length=len(original)==len(blob),
                    differing_bytes=[dict(decoded_offset=i,game_byte=a,patch_byte=b)
                                     for i,(a,b) in enumerate(zip(original,blob)) if a!=b],
                    interpretation='Differences are not interpreted; equal parsed fields do not mean identical bytes or proven load precedence.'))
            report['selected_properties'].append(dict(package=package,name_candidate=name,key=key_json(key),
                **identity,properties=[dict(id=f'0x{int(k):08x}',registered_name=PROPERTY_NAMES.get(int(k)),**v) for k,v in props.items()]))
        if package!='PatchData.package':
            continue
        for key,meta in entries.items():
            if key[0]!=0xea5118b0:
                continue
            row=dict(key=key_json(key),**meta)
            if meta['memory_bytes']>1048576:
                row['status']='NotDecompressedAboveDeclaredResearchBudget'
            else:
                blob,identity=decoded_payload(raw,meta);sections,prefix_end=read_component_sections(blob)
                row.update(identity)
                row.update(status='NormalComponentEnvelopesExamined',normal_prefix_end=prefix_end,
                           skin_sections=[asdict(s) for s in sections if s.type_id in (0x22,0x23,0x26)])
            report['effect_prefix_candidates'].append(row)
        for instance in (0x2c978da4,0xbafc5ca1):
            key=(0xea5118b0,0x40450200,instance);blob,identity=decoded_payload(raw,entries[key])
            sections,pos=read_component_sections(blob);resources,pos=read_sections_at(blob,pos)
            visual=read_visual_exports(blob,pos)
            sequences=read_sequences(blob,next(s for s in sections if s.type_id==4),len(visual['visuals']))
            particle_count=next(s.count for s in sections if s.type_id==0x26)
            distributions=read_distribute(blob,next(s for s in sections if s.type_id==0x23),particle_count)
            traces=[];selected_rows=set()
            for export in visual['exports']:
                name_hash=int(export['name_hash'],16)
                if name_hash not in EXPORT_NAMES:
                    continue
                if export['effect_index_raw']<0:
                    raise ValueError('SelectedExportUsesUnresolvedImport')
                trace=trace_selected_visual(export['effect_index_raw'],visual['visuals'],sequences,{s.type_id:s.count for s in sections})
                for leaf in trace:
                    last=leaf['path'][-1]
                    if last[0]=='component' and last[1]==0x23:
                        selected_rows.add(last[2])
                traces.append(dict(name_candidate=EXPORT_NAMES[name_hash],export=export,paths=trace))
            report['selected_effect_directories'].append(dict(key=key_json(key),**identity,
                normal_sections=[asdict(s) for s in sections],resource_sections=[asdict(s) for s in resources],
                visual_count=len(visual['visuals']),export_count=len(visual['exports']),import_count=len(visual['imports']),
                string_assignments_raw=visual['string_assignments_raw'],exact_directory_end=visual['decoded_end'],
                sequence_records_validated=len(sequences),distribute_records_validated=len(distributions),
                selected_traces=traces,selected_distributions=[distributions[i] for i in sorted(selected_rows)]))
    report['unknowns']=['Package/variant loading precedence and actual Creature-stage caller',
        'Particle brush contents/directions/variables and Settings map initialization',
        'Spacing units, sequence time semantics, execution order and conditional block flags',
        'Theme slot lookup/colour conversion and default/inheritance application',
        'Edit redraw/reprojection, precise stripe/spot density and cross-part seams']
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-directory',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=capture(args.data_directory)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(property_records=len(result['selected_properties']),
                         prefix_candidates=len(result['effect_prefix_candidates']),
                         complete_directories=len(result['selected_effect_directories']),
                         selected_export_traces=sum(len(d['selected_traces']) for d in result['selected_effect_directories']),
                         output=args.output.as_posix())))
