"""Read selected CreatureGameTuning keys and LOD properties only; no runtime."""
import hashlib
import json
import mmap
from pathlib import Path

from read_selected_ability_properties import FormatError,fnv,key,read_index,read_prop,refpack


NAMES=['parent','creatureSimulationLOD_MinDistanceLow','creatureSimulationLOD_MinDistanceMed',
       'creatureSpeedMediumLODMultiplier','modelLODDistances','modelLODDistanceScale',
       'modelMeshLOD0','modelMeshLOD1','modelMeshLOD2','modelMeshLOD3',
       'useHighModelLOD','useHighAnimLOD','TintCreaturesByAnimLOD',
       'LODMaxHigh','LODMaxMedium','LODMaxLow','LODCutoffHigh','LODCutoffMedium',
       'characterLODDistance','objectLODDeactivationDistance']


def property_ids(manifest):
    declarations=next(r for r in manifest['sources'] if r['path']=='reg_property.txt')['selected_declarations']
    entries={r['text'].split()[0]:r['text'].split()[1:] for r in declarations}
    out={}
    for name in NAMES:
        if name=='parent':out[name]=0x00B2CCCB;continue
        if name not in entries:raise FormatError(f'LOD registry declaration missing: {name}')
        bits=entries[name]
        out[name]=int(bits[0],16) if bits else fnv(name)
    return out


def select_properties(props,ids):
    return {name:{'id':f'0x{ident:08x}',**props[ident]} for name,ident in ids.items() if ident in props}


def main():
    evidence=Path(__file__).resolve().parent.parent/'evidence'
    manifest=json.loads((evidence/'public-creature-lod-contracts.json').read_text(encoding='utf-8'))
    prior=json.loads((evidence/'local-selected-movement-resources.json').read_text(encoding='utf-8'))
    ids=property_ids(manifest);records=[];packages=[]
    for filename in ('Spore_Game.package','PatchData.package'):
        selected=[r for r in prior['records'] if r['package']==filename and r['name']=='CreatureGameTuning']
        path=Path('E:/Steam/steamapps/common/Spore/Data')/filename
        with path.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as data:
            entries,index=read_index(data)
            package_hash=hashlib.sha256(data).hexdigest()
            expected=next(p['sha256'] for p in prior['packages'] if Path(p['path']).name==filename)
            if package_hash!=expected:raise FormatError(f'Package identity changed: {filename}')
            packages.append({'path':str(path),'bytes':len(data),'sha256':package_hash,**index})
            for r in selected:
                k=key(*(int(r['key'][x],16) for x in ('type','group','instance')))
                if k not in entries:raise FormatError(f'Selected key missing: {r["key"]}')
                e=entries[k];stored=data[e['offset']:e['offset']+e['stored_bytes']]
                decoded=refpack(stored,e['memory_bytes']) if e['compression']==0xFFFF else stored
                stored_hash=hashlib.sha256(stored).hexdigest();decoded_hash=hashlib.sha256(decoded).hexdigest()
                if stored_hash!=r['stored_sha256'] or decoded_hash!=r['decoded_sha256']:
                    raise FormatError(f'Selected resource identity changed: {filename} {r["key"]}')
                props=read_prop(decoded);values=select_properties(props,ids)
                records.append({'package':filename,'name':'CreatureGameTuning','key':r['key'],**e,
                                'stored_sha256':stored_hash,'decoded_sha256':decoded_hash,
                                'prior_identity_matched':True,'property_count':len(props),
                                'selected_properties':values,
                                'absent_direct_properties':[n for n in NAMES if n not in values]})
    result={'kind':'bounded-local-selected-creature-lod-properties-not-runtime',
            'scope':'Previously selected CreatureGameTuning four group variants, two packages; direct fields only',
            'reader_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'shared_reader_sha256':hashlib.sha256((Path(__file__).parent/'read_selected_ability_properties.py').read_bytes()).hexdigest(),
            'registry_commit':manifest['fx_commit'],'packages':packages,
            'query_ids':{n:f'0x{i:08x}' for n,i in ids.items()},'records':records,
            'limitations':['Direct absence is not an effective inherited default',
                           'Package override/load activation and native consumers not recovered',
                           'Distance units, origin, inclusivity and final multipliers unknown',
                           'No other packages or CreatureGameTuning variants searched']}
    (evidence/'local-selected-creature-lod-properties.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'records':len(records),'values':[{ 'package':r['package'],'group':r['key']['group'],'fields':r['selected_properties']} for r in records]},ensure_ascii=False))


if __name__=='__main__':main()
