"""Read only five named Creature editor animation PROP records per package."""
import hashlib
import json
import mmap
from pathlib import Path

from read_selected_ability_properties import read_index,read_prop,refpack,FormatError

SELECTED={'creature_button_attack_1','creature_button_attack_2','creature_button_dance_1',
          'creature_idle','creature_rest_pose'}


def main():
    evidence=Path(__file__).resolve().parent.parent/'evidence'
    manifest=json.loads((evidence/'public-editor-preview-subtree-contracts.json').read_text(encoding='utf-8'))
    registry=next(r for r in manifest['sources'] if r['path']=='reg_property.txt')
    names={int(r['text'].split()[1],16):r['text'].split()[0] for r in registry['selected_declarations']
           if len(r['text'].split())==2}
    prior=json.loads((evidence/'local-selected-movement-resources.json').read_text(encoding='utf-8'))
    inventory=manifest['preview_resource_inventory']['records'];records=[];packages=[]
    for filename in ('Spore_Game.package','PatchData.package'):
        path=Path('E:/Steam/steamapps/common/Spore/Data')/filename
        with path.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as data:
            entries,index=read_index(data);sha=hashlib.sha256(data).hexdigest()
            if sha!=next(r['sha256'] for r in prior['packages'] if Path(r['path']).name==filename):
                raise FormatError(f'Package identity changed: {filename}')
            packages.append({'path':str(path),'bytes':len(data),'sha256':sha,**index})
            selected=[r for r in inventory if r['package']==filename and
                      any(n['name'] in SELECTED for n in r['instance_names'])]
            if len(selected)!=5:raise FormatError('Selected five editor records not uniquely located')
            for r in selected:
                k=tuple(int(r['key'][x],16) for x in ('type','group','instance'));e=entries[k]
                stored=data[e['offset']:e['offset']+e['stored_bytes']]
                decoded=refpack(stored,e['memory_bytes']) if e['compression']==0xFFFF else stored
                props=read_prop(decoded)
                fields={names[pid]:{'id':f'0x{pid:08x}',**v} for pid,v in props.items() if pid in names}
                records.append({'package':filename,'key':r['key'],'instance_names':r['instance_names'],**e,
                                'stored_sha256':hashlib.sha256(stored).hexdigest(),
                                'decoded_sha256':hashlib.sha256(decoded).hexdigest(),
                                'property_count':len(props),'property_ids':[f'0x{x:08x}' for x in sorted(props)],
                                'selected_fields':fields,
                                'uninterpreted_property_ids':[f'0x{x:08x}' for x in sorted(props) if x not in names]})
    result={'kind':'bounded-local-editor-preview-prop-fields-not-runtime',
            'scope':'Five Creature editor animation config names in group40606300, two packages; panels/buttons groups checked only at index level',
            'reader_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'shared_reader_sha256':hashlib.sha256((Path(__file__).parent/'read_selected_ability_properties.py').read_bytes()).hexdigest(),
            'packages':packages,'records':records,
            'limitations':['No animation bodies decoded from these links','Name/field strings do not prove actual button availability or gameplay damage',
                           'EditorAnimInfo schema and native consumer unknown','No original preview test outcome or subtree copy behavior observed']}
    (evidence/'local-selected-editor-preview-properties.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'records':len(records),'selected_fields':[{'package':r['package'],'name':r['instance_names'][0]['name'],'fields':r['selected_fields']} for r in records]},ensure_ascii=False))


if __name__=='__main__':main()
