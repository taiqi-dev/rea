"""Bounded static contribution/requirement records; no original aggregation."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import struct
import urllib.request

from read_selected_ability_properties import Cursor, digest, fnv, key_json, read_index, read_prop, refpack, FormatError

SDK='2d71289adc71aa5c58f4516c6c835c99f5f9ca19'
FX='a482c51d8d37fc8cf416acecc3c00a5b0723f2e5'
SOURCES=(
    ('cSpeciesProfile.h',f'https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/{SDK}/Spore%20ModAPI/Spore/Simulator/cSpeciesProfile.h'),
    ('cCreatureAbility.h',f'https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/{SDK}/Spore%20ModAPI/Spore/Simulator/cCreatureAbility.h'),
    ('EditorRigblock.h',f'https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/{SDK}/Spore%20ModAPI/Spore/Editors/EditorRigblock.h'),
    ('cCreatureDataResource.h',f'https://raw.githubusercontent.com/Spore-Community/Spore-ModAPI/{SDK}/Spore%20ModAPI/Spore/Editors/cCreatureDataResource.h'),
    ('reg_property.txt',f'https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/{FX}/reg_property.txt'),
    ('reg_file.txt',f'https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/{FX}/reg_file.txt'),
    ('properties.txt',f'https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/{FX}/Documentation/properties.txt'),
    ('PropertyTransform.java',f'https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/{FX}/src/sporemodder/file/prop/PropertyTransform.java'),
    ('PropertyBBox.java',f'https://raw.githubusercontent.com/Spore-Community/SporeModder-FX/{FX}/src/sporemodder/file/prop/PropertyBBox.java'),
)


def fetch(item):
    name,url=item
    with urllib.request.urlopen(url,timeout=30) as response:
        raw=response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:
        raise FormatError(f'PublicSourceResearchBudget:{name}')
    encoding='utf-8'
    try:text=raw.decode(encoding)
    except UnicodeDecodeError:
        encoding='cp1252';text=raw.decode(encoding)
    return name,text,dict(name=name,url=url,bytes=len(raw),sha256=digest(raw),
                          encoding=encoding,line_count=len(text.splitlines()))


def registry_fields(text):
    result={}
    for n,line in enumerate(text.splitlines(),1):
        bits=line.strip().split()
        if len(bits)!=2:
            continue
        candidates=[(bits[0],bits[1]),(bits[1],bits[0])]
        for name,hex_id in candidates:
            if not re.fullmatch(r'0x[0-9a-fA-F]{1,8}',hex_id):continue
            if name.startswith('modelCapability') or name.startswith('creatureAbilityRequiredCAPs') or name in (
                'creatureAbilityExcludedCAPs','creatureAbilityAttackStatSumValueRange',
                'creatureAbilitySocialStatSumValueRange','creatureAbilityLevelMultiplier'):
                if name in result:raise FormatError(f'DuplicateRegistryName:{name}')
                result[name]=dict(id=f'0x{int(hex_id,16):08x}',line=n)
    if 'modelCapabilityStrike' not in result or 'creatureAbilityRequiredCAPs' not in result:
        raise FormatError('RequiredCapabilityRegistryFieldsMissing')
    return result


def read_capability_prop(data):
    """Walk known PROP boundaries; preserve BBox opaque24, decode others unchanged.

    This is an in-memory format projection, never a modified target file. The
    established helper is unchanged. TYPE38 Transform is still unsupported.
    """
    c=Cursor(data);count,=c.unpack('>I')
    if count>(len(data)-4)//8:raise FormatError('ImpossiblePropertyCount')
    records=[];boxes={};seen=set()
    numeric={1:1,2:1,3:2,5:1,6:1,7:2,8:2,9:4,10:4,11:8,12:8,13:4,14:8}
    vector_sizes={0x30:8,0x31:12,0x32:12,0x33:16,0x34:16}
    for _ in range(count):
        start=c.pos;ident,typ,flags=c.unpack('>IHH')
        if ident in seen or flags&0x40:raise FormatError('DuplicateOrUnsupportedPropertyFlag')
        seen.add(ident);array=bool(flags&0x30)
        n,size=c.unpack('>II') if array else (1,None)
        if n>len(data):raise FormatError('ImpossibleItemCount')
        bbox=[]
        for _ in range(n):
            if typ in numeric:
                if array and size!=numeric[typ]:raise FormatError('NumericItemSizeMismatch')
                c.take(numeric[typ])
            elif typ==0x20:
                if array and size!=12:raise FormatError('KeyItemSizeMismatch')
                c.take(12 if array else 16)
            elif typ in (0x12,0x13):
                length,=c.unpack('>I');c.take(length*(2 if typ==0x13 else 1))
            elif typ==0x22:
                if array and size!=520:raise FormatError('TextItemSizeMismatch')
                c.take(520)
            elif typ in vector_sizes:
                if array and size!=vector_sizes[typ]:raise FormatError('VectorItemSizeMismatch')
                c.take(vector_sizes[typ] if array else 16)
            elif typ==0x39:
                if array and size!=24:raise FormatError('BBoxItemSizeMismatch')
                bbox.append({'raw_24_bytes':c.take(24).hex(),'interpretation':'opaque fixed-format BBox; coordinate semantics not evaluated'})
            else:
                raise FormatError(f'UnsupportedCapabilityProfileType:{typ:#x}')
        if typ==0x39:
            boxes[ident]=dict(type='0x0039',flags=f'0x{flags:04x}',array=array,values=bbox)
        else:
            records.append(data[start:c.pos])
    if c.pos!=len(data):raise FormatError('CapabilityPROP_TrailingBytes')
    result=read_prop(struct.pack('>I',len(records))+b''.join(records))
    result.update(boxes)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=Path('E:/Steam/steamapps/common/Spore/Data'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--public-output',type=Path,required=True)
    args=parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fetched=list(pool.map(fetch,SOURCES))
    texts={name:text for name,text,row in fetched}
    rows={name:row for name,text,row in fetched}
    fields=registry_fields(texts['reg_property.txt'])
    sources=[]
    for name,text,row in fetched:
        pattern=(r'mAttack|mBite|mStrike|mSpit|mCharge|mSocial|mMouth|mHands|Capability|RequiredCAP|ExcludedCAP|StatSum|LevelMultiplier|GetMax|GetSum'
                 if name!='reg_file.txt' else r'^ce_(?:grasper|mouth)_')
        selected=[dict(line=n,text=line.strip()) for n,line in enumerate(text.splitlines(),1)
                  if re.search(pattern,line)]
        if name in ('PropertyTransform.java','PropertyBBox.java'):
            selected=[dict(line=n,text=line.strip()) for n,line in enumerate(text.splitlines(),1)
                      if re.search(r'import.*Transform|TYPE_CODE|ARRAY_SIZE|\.read|\.write|read\(|write\(|super\(',line)]
        sources.append(dict(**row,selected_declarations=selected,
                            scope='community declarations/registry/documentation, not local consumer'))
    public=dict(kind='pinned-capability-contribution-contracts-not-native-aggregation',
                commits={'SDK':SDK,'FX':FX},sources=sources,property_registry=fields,
                unknowns=['native contribution reducer','default/inheritance execution',
                          'range inclusivity and qualification consumer','selected gameplay executor relation'],
                network_fallback='Web reader cache miss; authorized fixed public URLs read directly; no config changes')
    args.public_output.write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    parts=[];packages=[];diagnostics=[]
    attack_evidence=Path(__file__).resolve().parent.parent/'evidence/local-selected-attack-properties.json'
    old=json.loads(attack_evidence.read_text(encoding='utf-8'))
    part_names=[]
    for n,line in enumerate(texts['reg_file.txt'].splitlines(),1):
        match=re.match(r'^(ce_(grasper|mouth)_[A-Za-z0-9_]+)\s*(?:0x[0-9a-fA-F]+)?$',line.strip())
        if match:
            name=match.group(1)
            if any(token in name.lower() for token in ('default','template','symmetric','cell','scc','registration','partner','flora','mech','_ga_','_null')):
                continue
            part_names.append((name,match.group(2),n))
    selected_cap_ids={int(item['id'],16):name for name,item in fields.items()}
    for package_name in ('Spore_Game.package','PatchData.package'):
        file=args.data/package_name;data=file.read_bytes();entries,info=read_index(data)
        packages.append(dict(path=str(file.resolve()),bytes=len(data),sha256=digest(data),**info))
        candidates={kind:[] for kind in ('grasper','mouth')}
        for name,kind,line in part_names:
            k=(0x00b1b104,0x40626000,fnv(name))
            if k in entries:
                candidates[kind].append((name,line,k))
        # At most two concrete definitions per kind in each package; same deterministic name rule.
        for kind in ('grasper','mouth'):
            chosen_candidates=(sorted(c for c in candidates[kind] if c[0] in ('ce_grasper_bird_01','ce_grasper_bird_02'))
                               if kind=='grasper' else sorted(candidates[kind])[:2])
            for name,line,k in chosen_candidates:
                e=entries[k]
                if e['memory_bytes']>128*1024:raise FormatError('SelectedPartResearchBudget')
                raw=data[e['offset']:e['offset']+e['stored_bytes']]
                decoded=refpack(raw,e['memory_bytes']) if e['compression'] else raw
                try:props=read_capability_prop(decoded)
                except FormatError as error:
                    diagnostics.append(dict(package=package_name,name=name,key=key_json(k),error=str(error)))
                    continue
                chosen={selected_cap_ids[ident]:value for ident,value in props.items() if ident in selected_cap_ids}
                parent=props.get(fnv('parent'))
                parts.append(dict(package=package_name,name=name,registry_line=line,key=key_json(k),**e,
                                  stored_sha256=digest(raw),decoded_sha256=digest(decoded),
                                  property_count=len(props),direct_capability_fields=chosen,parent_raw=parent,
                                  opaque_bbox_properties={f'0x{ident:08x}':value for ident,value in props.items() if value['type']=='0x0039'},
                                  omitted_fields='not directly present; defaults/ancestors not resolved'))
    output=dict(kind='selected-part-contributions-and-existing-ability-ranges-not-REA-Evidence',
                rea_evidence_id=None,reader=dict(path=str(Path(__file__).resolve()),sha256=digest(Path(__file__).read_bytes())),
                packages=packages,selected_parts=parts,diagnostics=diagnostics,
                existing_ability_evidence=dict(path=str(attack_evidence.resolve()),sha256=digest(attack_evidence.read_bytes())),
                selected_ability_requirements=[dict(package=r['package'],name=r['name'],key=r['key'],
                  fields={name:value for name,value in r['selected_properties'].items()
                          if name in fields and name.startswith('creatureAbility')}) for r in old['records']],
                coverage={'new_part_payload_records':len(parts)+len(diagnostics),'new_ability_payload_records':0},
                format_profile='Known PROP boundary projection plus unchanged primitive decoder; BBox39 preserves24bytes, Transform38 unsupported',
                resolved_profile_gap='Initial two ordinary mouth reads failed on type39. Fixed PropertyBBox declares39/24bytes; no byte-pattern skip or target modification.',
                unknowns=public['unknowns'],not_performed=['game execution/attach','private saves','complete asset export','provider setup'])
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'source_count':len(sources),'property_ids':len(fields),'part_records':len(parts),'diagnostics':len(diagnostics)}))
    print(json.dumps([{'package':r['package'],'name':r['name'],'capabilities':r['direct_capability_fields']} for r in parts]))
    print(json.dumps([{'source':r['name'],'declarations':r['selected_declarations'][:8]} for r in sources if r['name'] in ('cSpeciesProfile.h','reg_property.txt')]))
    print(json.dumps([r for r in sources if r['name']=='PropertyBBox.java']))


if __name__=='__main__':main()
