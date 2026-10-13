"""Observe selected attack TLSA groups and referenced ANIM channel metadata.

Independent research reader. No animation curves/assets are exported; no
runtime binding, precedence, effective package resolution or ABI is inferred.
"""
import argparse
import json
import math
from pathlib import Path
import struct

from read_selected_ability_properties import Cursor, FormatError, digest, key_json, read_index, refpack


def read_tlsa(data, selected_ids):
    c=Cursor(data)
    magic,version,count=c.unpack('>III')
    if magic != 0x74736c61 or version not in (7,8,9,10):
        raise FormatError('unsupported TLSA magic/version')
    if count > 10000: raise FormatError('TLSA group budget exceeded')
    def integer(): return c.unpack('>I')[0]
    def number():
        value=c.unpack('>f')[0]
        if not math.isfinite(value):raise FormatError('nonfinite TLSA value')
        return value
    def boolean():
        value=c.unpack('>B')[0]
        if value not in (0,1):raise FormatError('invalid TLSA boolean')
        return bool(value)
    def text():
        n=integer()
        if n>4096:raise FormatError('TLSA string budget exceeded')
        try:return c.take(n*2).decode('utf-16-le')
        except UnicodeError as exc:raise FormatError('invalid TLSA UTF16') from exc
    def limited(n):
        if n>10000:raise FormatError('TLSA nested count budget exceeded')
        return range(n)
    groups=[]
    for _ in range(count):
        ident=integer(); name=None; priority=None; randomize=None
        choices=[]
        if version<=8:
            if version==8:priority=number()
            n=integer(); descriptions=[text() for _ in limited(n)]
            ids=[integer() for _ in limited(n)]
            scale,duration=number(),number()
            animations=[dict(id=f'0x{i:08x}',description=s,durationScale=scale,duration=duration)
                        for i,s in zip(ids,descriptions)]
            choices=[dict(probabilityThreshold=None,animations=animations)]
            idle=boolean(); blend=number(); allow=boolean()
            disable,match,end=integer(),integer(),integer()
        else:
            name=text(); priority,blend=number(),number();idle,allow=boolean(),boolean()
            if version==10:randomize=boolean()
            match,disable,end=integer(),integer(),integer()
            for _ in limited(integer()):
                threshold=number(); animations=[]
                for _ in limited(integer()):
                    scale,duration=number(),number();anim_id=integer();description=text()
                    animations.append(dict(id=f'0x{anim_id:08x}',description=description,
                                           durationScale=scale,duration=duration))
                choices.append(dict(probabilityThreshold=threshold,animations=animations))
        if ident in selected_ids:
            groups.append(dict(id=f'0x{ident:08x}',name=name,priorityOverride=priority,
                               blendInTime=blend,idle=idle,allowLocomotion=allow,
                               randomizeChoicePerLoop=randomize,matchVariantForToolMask=f'0x{match:08x}',
                               disableToolOverlayMask=f'0x{disable:08x}',endMode=end,choices=choices))
    if c.pos != len(data):raise FormatError('TLSA trailing bytes')
    return dict(version=version,groups_examined=count,fully_consumed_bytes=c.pos,selected_groups=groups)


def read_anim_metadata(data):
    def u(off):
        if off<0 or off+4>len(data):raise FormatError('ANIM offset outside resource')
        return struct.unpack_from('<I',data,off)[0]
    def region(off,size):
        if off<0 or size<0 or off+size>len(data):raise FormatError('ANIM region outside resource')
        return data[off:off+size]
    def ascii_z(raw):
        if b'\0' not in raw:raise FormatError('ANIM fixed text missing terminator')
        try:return raw.split(b'\0',1)[0].decode('ascii')
        except UnicodeError as exc:raise FormatError('ANIM non-ASCII metadata') from exc
    if len(data)<0x15c or u(0)!=0x4d494e41 or not 0x14<=u(8)<=0x19:
        raise FormatError('unsupported ANIM header/version')
    if u(4)!=len(data):raise FormatError('ANIM declared size mismatch')
    count,ptr=u(0x144),u(0x148)
    if count>1024:raise FormatError('ANIM channel budget exceeded')
    region(ptr,count*4); channels=[]
    for i in range(count):
        base=u(ptr+4*i);region(base,0xe4)
        if u(base)!=0x4e414843:raise FormatError('invalid CHAN magic')
        keys,key_ptr,components,comp_ptr=(u(base+x) for x in (0xd4,0xd8,0xdc,0xe0))
        if keys>100000 or components>64:raise FormatError('ANIM component/key budget exceeded')
        region(comp_ptr,32*components);items=[]
        for j in range(components):
            flags,ident,offset,stride,index=(u(comp_ptr+j*32+x) for x in (0,4,8,12,16))
            if keys and not stride:raise FormatError('ANIM zero key stride')
            if keys:region(key_ptr+offset+(keys-1)*stride,4)
            items.append(dict(type=flags&15,flags=f'0x{flags:08x}',id=f'0x{ident:08x}',
                              keyframe_offset=offset,keyframe_stride=stride,index=index))
        bind=u(base+0xac)
        contexts=[]
        for off in (0x8c,0x9c):
            cap=region(base+off+4,4)
            contexts.append(dict(flags=f'0x{u(base+off):08x}',capability_bytes=cap.hex(),
                                 capability_ascii=cap.rstrip(b'\0').decode('ascii') if all(v<128 for v in cap) else None,
                                 field_8=f'0x{u(base+off+8):08x}',field_C=f'0x{u(base+off+12):08x}'))
        channels.append(dict(resource_channel_index=i,name=ascii_z(region(base+8,128)),
                             movementFlags=f'0x{u(base+0x88):08x}',bindFlags=f'0x{bind:08x}',
                             community_blendGroup=(bind>>16)&255,community_variantGroup=(bind>>24)&255,
                             primaryContext=contexts[0],secondaryContext=contexts[1],
                             keyframe_count=keys,components=items))
    length=struct.unpack_from('<f',data,0x120)[0]
    if not math.isfinite(length):raise FormatError('nonfinite ANIM length')
    return dict(version=u(8),declared_bytes=u(4),embedded_path=ascii_z(region(12,256)),
                animation_id=f'0x{u(0x110):08x}',length_raw=length,channels=channels,
                coverage='header/channel/component metadata only; curves, events, predicates and relocation table not decoded',
                version_semantics='raw fields; no old-version fixup or runtime binding applied')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    ev=Path(__file__).resolve().parent.parent/'evidence'
    skills=json.loads((ev/'local-selected-attack-properties.json').read_text(encoding='utf-8'))
    selected_ids=set();sources=[]
    for r in skills['records']:
        for name,p in r['selected_properties'].items():
            if name in ('creatureAbilityAnimationIDs','creatureAbilityRushingAnimationID'):
                selected_ids.update(p['values'])
                sources.append(dict(package=r['package'],ability_record=r['name'],field=name,values=p['values']))
    packages=[];records=[];anim_ids=set()
    for name in ('Spore_Game.package','PatchData.package'):
        path=args.data/name;data=path.read_bytes();entries,info=read_index(data)
        packages.append((data,entries,dict(path=str(path.resolve()),bytes=len(data),sha256=digest(data),**info)))
        for k,e in sorted(entries.items()):
            if k[0]!=0x4aeb6bc6:continue
            if e['memory_bytes']>2*1024*1024:raise FormatError('TLSA research size budget exceeded')
            raw=data[e['offset']:e['offset']+e['stored_bytes']]
            dec=refpack(raw,e['memory_bytes']) if e['compression'] else raw
            if len(dec)!=e['memory_bytes']:raise FormatError('TLSA uncompressed size mismatch')
            result=read_tlsa(dec,selected_ids)
            records.append(dict(package=name,key=key_json(k),**e,stored_sha256=digest(raw),decoded_sha256=digest(dec),tlsa=result))
            for group in result['selected_groups']:
                for choice in group['choices']:
                    anim_ids.update(int(a['id'],16) for a in choice['animations'])
    if not anim_ids:raise FormatError('no selected attack groups matched TLSA')
    if len(anim_ids)>128:raise FormatError('selected animation research budget exceeded')
    missing=[]
    for anim_id in sorted(anim_ids):
        found=False
        for data,entries,info in packages:
            for k,e in sorted(entries.items()):
                if k[0]!=0xee17c6ad or k[2]!=anim_id:continue
                found=True
                if e['memory_bytes']>2*1024*1024:raise FormatError('ANIM research size budget exceeded')
                raw=data[e['offset']:e['offset']+e['stored_bytes']]
                dec=refpack(raw,e['memory_bytes']) if e['compression'] else raw
                if len(dec)!=e['memory_bytes']:raise FormatError('ANIM uncompressed size mismatch')
                meta=read_anim_metadata(dec)
                if '\\creature\\' not in meta['embedded_path'].lower():
                    raise FormatError('selected animation not labeled Creature path; review scope before continuing')
                records.append(dict(package=Path(info['path']).name,key=key_json(k),**e,
                                    stored_sha256=digest(raw),decoded_sha256=digest(dec),anim=meta))
        if not found:missing.append(f'0x{anim_id:08x}')
    output=dict(kind='local-action-config-observation-not-REA-Evidence',
                scope='existing four attack families levels1..5 normal/rushing animation IDs -> selected TLSA groups -> referenced Creature-labeled ANIM metadata',
                package_load_order='unknown; separate resource keys/versions preserved',
                format_commit='a482c51d8d37fc8cf416acecc3c00a5b0723f2e5',
                ability_evidence_sha256=digest((ev/'local-selected-attack-properties.json').read_bytes()),
                reader_sha256=digest(Path(__file__).read_bytes()),
                packages=[p[2] for p in packages],selected_group_ids=[f'0x{i:08x}' for i in sorted(selected_ids)],
                selection_sources=sources,missing_animation_ids=missing,records=records)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(tlsa_records=sum('tlsa' in r for r in records),anim_records=sum('anim' in r for r in records),missing=len(missing))))


if __name__=='__main__':main()
