"""Read one previously selected Patch ANIM mouthMorphs channel's scalar keys.

Research observations only: no playback, interpolation evaluation, geometry,
runtime ID semantics or legacy fixup. No complete animation asset exported.
"""
import json
import math
from pathlib import Path
import struct

from read_selected_ability_properties import FormatError, digest, refpack
from read_selected_action_channels import read_anim_metadata


def read_scalar_keys(data, channel_index):
    meta=read_anim_metadata(data)
    if meta['version']!=25:
        raise FormatError('scalar study only supports selected version25; no legacy fixup')
    if not 0<=channel_index<len(meta['channels']):
        raise FormatError('selected channel index outside metadata')
    channel=meta['channels'][channel_index]
    if channel['name']!='mouthMorphs' or channel['primaryContext']['capability_ascii']!='mout':
        raise FormatError('selected channel is not mouthMorphs/mout')
    if channel['keyframe_count']>32:
        raise FormatError('selected scalar key study budget exceeded')
    def u(off):
        if not 0<=off<=len(data)-4:raise FormatError('scalar pointer outside resource')
        return struct.unpack_from('<I',data,off)[0]
    pointer_table=u(0x148);base=u(pointer_table+4*channel_index);key_pointer=u(base+0xd8)
    def region(off,size):
        if off<0 or off+size>len(data):raise FormatError('scalar key outside resource')
        return data[off:off+size]
    infos=[c for c in channel['components'] if c['type']==0]
    if len(infos)!=1:raise FormatError('selected scalar channel needs exactly one info component')
    times=[]
    for k in range(channel['keyframe_count']):
        off=key_pointer+infos[0]['keyframe_offset']+k*infos[0]['keyframe_stride']
        times.append(struct.unpack('<i',region(off,4))[0])
    components=[]
    for c in (c for c in channel['components'] if c['type']==3):
        if c['keyframe_stride']<40:raise FormatError('scalar stride cannot fit 40-byte component')
        samples=[]
        for k,time in enumerate(times):
            off=key_pointer+c['keyframe_offset']+k*c['keyframe_stride']
            raw=region(off,40);value,weight=struct.unpack_from('<ff',raw)
            interpolators=[]
            for p in (8,24):
                next_factor,prev_factor,next_mode,prev_mode=struct.unpack_from('<ffBB',raw,p)
                interpolators.append(dict(nextFactor=next_factor,previousFactor=prev_factor,
                                          nextMode=next_mode,previousMode=prev_mode))
            if any(not math.isfinite(v) for v in [value,weight]+[
                    v for i in interpolators for v in (i['nextFactor'],i['previousFactor'])]):
                raise FormatError('nonfinite scalar key value')
            samples.append(dict(time_raw=time,value_raw=value,weight_raw=weight,
                                interpolators_raw=interpolators))
        components.append(dict(metadata=c,samples=samples))
    if not components:raise FormatError('selected channel has no scalar deform components')
    return dict(version=25,channel_metadata=channel,info_times_raw=times,components=components,
                coverage='selected scalar value/weight/interpolator bytes; no evaluation, events or effective runtime binding')


def main():
    study=Path(__file__).resolve().parent.parent;source=study/'evidence/local-selected-action-channels.json'
    records=json.loads(source.read_text(encoding='utf8'))
    selected=[r for r in records['records'] if r['package']=='PatchData.package'
              and r.get('key',{}).get('instance')=='0x0af13430' and 'anim' in r]
    if len(selected)!=1:raise FormatError('selected prior ANIM record is not unique')
    record=selected[0];package=Path('E:/Steam/steamapps/common/Spore/Data/PatchData.package')
    expected=next(p for p in records['packages'] if Path(p['path']).name=='PatchData.package')
    data=package.read_bytes()
    if len(data)!=expected['bytes'] or digest(data)!=expected['sha256']:
        raise FormatError('selected package identity changed')
    raw=data[record['offset']:record['offset']+record['stored_bytes']]
    if digest(raw)!=record['stored_sha256']:raise FormatError('selected stored resource changed')
    dec=refpack(raw,record['memory_bytes']) if record['compression'] else raw
    if digest(dec)!=record['decoded_sha256']:raise FormatError('selected decoded resource changed')
    selected_channel=next(c for c in record['anim']['channels'] if c['name']=='mouthMorphs')
    result=read_scalar_keys(dec,selected_channel['resource_channel_index'])
    out={'kind':'local-selected-scalar-config-observation-not-runtime','source_metadata_sha256':digest(source.read_bytes()),
         'reader_sha256':digest(Path(__file__).read_bytes()),'format_commit':records['format_commit'],
         'package':expected,'resource_key':record['key'],'file_offset':record['offset'],
         'stored_bytes':record['stored_bytes'],'stored_sha256':digest(raw),'decoded_sha256':digest(dec),
         'embedded_path':record['anim']['embedded_path'],'scalar_keys':result,
         'limits':['Package load priority not established; selected Patch record is not a runtime selection.',
                   'Deform IDs not assigned names such as mouth-open; units/endpoints unknown.',
                   'No interpolation evaluated or Creature recipe selected; no curve retargeting/composition recovered.']}
    (study/'evidence/local-selected-part-deform-keys.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'components':len(result['components']),'times_raw':result['info_times_raw'],
                      'samples':{c['metadata']['id']:[[s['value_raw'],s['weight_raw']] for s in c['samples']]
                                 for c in result['components']}},indent=2))


if __name__=='__main__':main()
