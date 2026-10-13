"""Read one fixed hand RW4 and small pose prefixes; no geometry/asset export."""
from datetime import datetime, timezone
import json
import math
import mmap
from pathlib import Path
import struct
from zoneinfo import ZoneInfo

from read_selected_ability_properties import read_index, digest, refpack, FormatError
from read_selected_rigblock_metadata import read_metadata, span, unpack

BASE = Path(__file__).resolve().parent.parent


def read_skin_pose_prefix(data, section, selected_count=4):
    start, size = section['data_offset'], section['size']
    if selected_count < 0 or selected_count > 4:
        raise FormatError('pose prefix budget is0..4')
    if size < 16:raise FormatError('skin pose header truncated')
    pointer,count,field8,fieldc=unpack(data,start,'<Iiii','skin pose header')
    if count < 0 or count > 1024:raise FormatError('skin pose count budget')
    if pointer < start+16 or pointer+count*64 > start+size:raise FormatError('skin pose array outside section')
    span(data,pointer,count*64,'skin pose array')
    rows=[]
    for i in range(min(count,selected_count)):
        pos=pointer+i*64;raw=span(data,pos,64,'skin pose row');values=struct.unpack('<16f',raw)
        if any(not math.isfinite(v) for v in values[:15]):raise FormatError('nonfinite skin pose')
        rows.append(dict(pose_ordinal=i,decoded_offset=pos,raw_64_bytes=raw.hex(),
            matrix3x4_rows_raw=[list(values[j:j+4]) for j in (0,4,8)],
            community_invPoseTranslation_raw=list(values[12:15]),padding_word_raw=raw[60:64].hex(),
            interpretation='Tool BonePose labels only; edited rest pose, space and consumer multiplication remain unknown.'))
    return dict(section_index=section['index'],header_decoded_offset=start,
                pointer=pointer,count=count,raw_header16=span(data,start,16,'header').hex(),
                field8_raw=field8,fieldc_raw=fieldc,rows=rows,rows_not_read=count-len(rows))


def rotation_diagnostic(first,second):
    if len(first)!=4 or len(second)!=4:
        raise FormatError('rotation diagnostic requires two Vector4 fields')
    n0=math.sqrt(sum(v*v for v in first));n1=math.sqrt(sum(v*v for v in second))
    if not all(math.isfinite(v) for v in (*first,*second)) or min(n0,n1)<=1e-12:
        raise FormatError('degenerate rotation diagnostic')
    dot=sum(a*b for a,b in zip(first,second))/(n0*n1)
    angle=math.degrees(2*math.acos(min(1,abs(dot))))
    return dict(norm0=n0,norm1=n1,normalized_abs_dot=abs(dot),
                quaternion_geodesic_candidate_degrees=angle,
                assumption='Both four-component rotations are quaternions in one consistent ordering; diagnostic only, not joint-limit or reference-bend measurement.')


def main():
    now=datetime.now(timezone.utc);ev=BASE/'evidence';oldpath=ev/'local-selected-rigblock-metadata.json'
    oldraw=oldpath.read_bytes();old=json.loads(oldraw.decode('utf8'))
    package=Path(old['package']['path']);key=tuple(int(old['key'][n],16) for n in ('type','group','instance'))
    with package.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as data:
        entries,index=read_index(data);e=entries[key]
        for n in ('offset','stored_bytes','memory_bytes'):
            if e[n]!=old['resource'][n]:raise FormatError('selected index entry mismatch')
        header_sha=digest(data[:96]);index_sha=digest(data[index['index_offset']:index['index_offset']+index['index_bytes']])
        if header_sha!=old['package']['header_sha256'] or index_sha!=old['package']['index_sha256']:
            raise FormatError('Graphics header/index mismatch')
        if e['memory_bytes']>65536:raise FormatError('selected RW4 memory budget')
        stored=data[e['offset']:e['offset']+e['stored_bytes']];decoded=refpack(stored,e['memory_bytes']) if e['compression'] else stored
        if digest(stored)!=old['resource']['stored_sha256'] or digest(decoded)!=old['resource']['decoded_sha256']:
            raise FormatError('selected RW4 identity mismatch')
        metadata=read_metadata(decoded)
        if metadata['section_count']!=21:raise FormatError('selected section count mismatch')
        pose_sections=[s for s in metadata['sections'] if s['type']=='0x00070003']
        poses=[read_skin_pose_prefix(decoded,s) for s in pose_sections]
        tracks=[]
        for animation in metadata['animations']:
            for channel in animation['selected_channel_samples']:
                samples=[]
                for sample in channel['samples']:
                    samples.append(dict(**sample,raw32=span(decoded,sample['offset'],32,'track sample').hex()))
                tracks.append(dict(section_index=animation['section_index'],channel_id=channel['channel_id'],
                    channel_ordinal=channel['ordinal'],samples=samples,
                    rotation_diagnostic=rotation_diagnostic(samples[0]['rotation_raw'],samples[-1]['rotation_raw'])))
        resource=dict(key=old['key'],**e,stored_sha256=digest(stored),decoded_sha256=digest(decoded))
    path=ev/'joint-limits-shape-feasibility-observations.json';output=json.loads(path.read_text(encoding='utf8'))
    prop_path=ev/'local-part-definition-observations.json';prop_raw=prop_path.read_bytes();props=json.loads(prop_raw.decode('utf8'))
    selected=[]
    for r in props['records']:
        if r['key']['instance']!='0x0df11468':continue
        for p in r.get('properties',[]):
            names=[n['name'] for n in p.get('labels',[])]
            if set(names)&{'modelMinScale','modelMaxScale','modelScale','modelRotation','modelEditorInitialRotation','modelRunTimeBoneCount'}:
                selected.append(dict(package=r['package'],key=r['key'],stored_offset=r['offset'],
                                     decoded_sha256=r['decoded_sha256'],property=p,reused_not_reread=True))
    output.update(timestamp_utc=now.strftime('%Y-%m-%d %H:%M:%S UTC'),
        timestamp_pacific=now.astimezone(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d %H:%M:%S %Z'),
        target_executable_identity=dict(path='E:/Steam/steamapps/common/Spore/SporeBin/SporeApp.exe',
            sha256='f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d',
            scope='reused fixed identity; EXE not reread or executed in55'),
        package=dict(path=str(package.resolve()),bytes=old['package']['bytes'],header96_sha256=header_sha,
            index_sha256=index_sha,full_sha256_reused=old['package']['sha256'],full_file_digest_fresh=False,**index),
        resource=resource,skin_pose_prefixes=poses,local_track_prefixes=tracks,
        handle_section_count=len(metadata['handles']),skeletons=metadata['skeletons'],skin_links=metadata['skin_links'],
        reused_properties=selected,reused_sources=[dict(path=str(oldpath.resolve()),sha256=digest(oldraw)),
            dict(path=str(prop_path.resolve()),sha256=digest(prop_raw))],reader_sha256=digest(Path(__file__).read_bytes()),
        coverage=dict(fresh_stored_bytes=e['stored_bytes'],fresh_decoded_bytes=e['memory_bytes'],
            skeleton_metadata=True,local_LocRot_key_samples=sum(len(t['samples']) for t in tracks),
            skin_pose_rows=sum(len(p['rows']) for p in poses),models_vertices_textures_exported=False,
            angular_limit_configuration_obtained=False,native_shape_to_motion_consumer_recovered=False),
        unknowns=['Which local tracks correspond to edit handles or runtime semantic deforms',
                  'Global/local bind pose convention and reference bend extraction',
                  'Original swing/twist limits, post-edit recalculation and muscle physics',
                  'Shape-to-action feasibility and collision consumers'])
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(coverage=output['coverage'],track_diagnostics=[dict(section=t['section_index'],channel=t['channel_ordinal'],degrees=t['rotation_diagnostic']['quaternion_geodesic_candidate_degrees']) for t in tracks])))


if __name__=='__main__':main()
