"""Bounded recipe/gaze metadata research, not complete game asset extraction."""
import collections
from datetime import datetime, timezone
import json
import mmap
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from read_selected_ability_properties import read_index, digest, refpack, key_json, FormatError

BASE = Path(__file__).resolve().parent.parent
DATA = Path('E:/Steam/steamapps/common/Spore/Data')
PACKAGES = ['Spore_Game.package', 'PatchData.package', 'Spore_Content.package',
            'Spore_Graphics.package', 'Spore_Pack_03.package', 'Spore_Audio1.package', 'Spore_Audio2.package']
SELECTED = {'Spore_Game.package': [(0x2B978C46, 0x40626200, 0x135FF099)],
            'PatchData.package': [(0x2B978C46, 0x40626200, 0x135FF099)],
            'Spore_Content.package': [(0x0F43029A, 0x406B6200, 0x2A56398B),
                                      (0x0F43029A, 0x40626200, 0x067B1055)]}
EXPECTED = {'Spore_Game.package':'9d085118c649d211a86723d363592fd66ad655fd24497289b3eab96bb07db329',
            'PatchData.package':'cadbff237076b441e6981503f80538705aefa5863bb4c8d1b869f9db98d1adff'}


def xml_observations(data):
    if len(data) > 32768 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise FormatError('XML research budget or forbidden declaration')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise FormatError('XML syntax: ' + str(error)) from error
    if root.tag != 'sporemodel':
        raise FormatError('unexpected XML root')
    blocks = root.find('blocks')
    if blocks is None or int(blocks.get('count', '-1')) != len(blocks):
        raise FormatError('XML declared block count mismatch')
    rows = []
    for index, block in enumerate(blocks):
        children = block.find('childlist')
        child_ids = [] if children is None else [int(n.text) for n in children]
        if children is not None and int(children.get('count', '-1')) != len(child_ids):
            raise FormatError('XML child count mismatch')
        if any(c < 0 or c >= len(blocks) for c in child_ids):
            raise FormatError('XML child reference outside block array')
        rows.append(dict(block_array_index=index, blockid_raw=block.findtext('blockid'),
                         child_array_indices=child_ids, transform_fields=[n.tag for n in block.find('transform')],
                         scale_raw=block.findtext('transform/scale'),
                         position_raw=block.findtext('transform/position'), snapped_raw=block.findtext('snapped')))
    return dict(root_tag=root.tag, formatversion_raw=root.findtext('formatversion'),
                modeltype_raw=root.findtext('properties/modeltype'), declared_blocks=len(blocks), blocks=rows,
                inspected_XML_nodes=sum(1 for _ in root.iter()),
                classification=('Three vertebra asset references only; not a full multi-organ Creature proof.'
                                if len(rows)==3 and all(r['blockid_raw'].replace(' ','')=='0x40626000,0xd05c53a3' for r in rows)
                                else 'Unclassified sporemodel; runtime/organ semantics not established.'),
                full_XML_exported=False, runtime_bones_derived=False)


def creaturedata_header(data):
    if len(data) < 20:
        raise FormatError('creaturedata header truncated')
    magic, version = struct.unpack_from('<II', data)
    if magic != 0xABB455B7 or version not in (9, 10):
        raise FormatError('unsupported creaturedata header')
    count_length = 3 if version == 9 else 4
    size = 8 + 4 * count_length
    if len(data) < size + 2:
        raise FormatError('creaturedata counts truncated')
    counts = list(struct.unpack_from('<' + 'I' * count_length, data, 8))
    if any(n > 10000 for n in counts):
        raise FormatError('creaturedata count budget')
    chunk_size = struct.unpack_from('<H', data, size)[0]
    if not 1 <= chunk_size <= 0x800 or size + 2 + chunk_size > len(data):
        raise FormatError('creaturedata first-buffer bounds')
    chunk = data[size + 2:size + 2 + chunk_size]
    produced = 0
    pos = 0
    while pos < len(chunk):
        value = chunk[pos]; pos += 1
        if value == 254:
            if pos == len(chunk):
                raise FormatError('buffer escape at chunk end; no guessed continuation')
            number = chunk[pos]; pos += 1
            produced += number or 1
        else:
            produced += 1
    result = dict(magic_raw='0xabb455b7', version=version, count_words=counts,
                  header_decoded_offset=0, raw_header_bytes=data[:size].hex(),
                  first_buffer_size_word_offset=size, first_buffer_bytes=chunk_size,
                  first_buffer_token_output_count=produced,
                  community_expected_properties_bytes=0x80 - 0x3C,
                  complete_decode_status='not-established',
                  diagnostic='FX expected68bytes differs from first chunk token output; literal read uses buffer[0]. No original full decoder inferred.')
    # Conditional alignment inventory, not a validated decode or runtime binding.
    start = size + 2 + chunk_size
    cap_offset = start + counts[0] * 0x8C
    final_offset = cap_offset + counts[1] * 5 + counts[2] * 12 + 4
    if version == 10:
        final_offset += counts[3] * 0x38
    result['conditional_alignment'] = dict(assumption='First whole chunk ends properties; no reliable properties decode established.',
        rigblock_bytes_start=start, capability_bytes_start=cap_offset,
        calculated_end=final_offset, actual_bytes=len(data), end_matches=final_offset == len(data))
    if final_offset == len(data):
        tags = [data[cap_offset + i*4:cap_offset + i*4 + 4] for i in range(counts[1])]
        result['conditional_alignment']['tag_byte_candidates'] = [dict(offset=cap_offset+i*4, raw=t.hex(),
                ascii_candidate=t.rstrip(b'\0').decode('ascii') if all(c<128 for c in t) else None)
                for i,t in enumerate(tags)]
    return result


def main():
    now = datetime.now(timezone.utc)
    packages, observations = [], []
    for name in PACKAGES:
        path = DATA / name
        with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            entries, index = read_index(data)
            identity = dict(path=str(path.resolve()), bytes=len(data), **index,
                header96_sha256=digest(data[:96]),
                index_sha256=digest(data[index['index_offset']:index['index_offset']+index['index_bytes']]),
                full_file_sha256=None, full_file_digest_fresh=False)
            if name in EXPECTED:
                sha = digest(data)
                if sha != EXPECTED[name]:raise FormatError('package hash mismatch: '+name)
                identity.update(full_file_sha256=sha, full_file_digest_fresh=True)
            counts = collections.Counter(k[0] for k in entries)
            identity['exact_type_counts'] = {'crt_2b978c46':counts[0x2B978C46], 'creaturedata_0f43029a':counts[0x0F43029A]}
            groups = collections.Counter(k[1] for k in entries if k[0] == 0x0F43029A)
            identity['creaturedata_groups'] = [{ 'group':f'0x{k:08x}', 'entries':n} for k,n in sorted(groups.items())]
            packages.append(identity)
            for key in SELECTED.get(name, []):
                e = entries[key]
                if e['memory_bytes'] > 32768:raise FormatError('selected metadata memory budget')
                stored = data[e['offset']:e['offset'] + e['stored_bytes']]
                decoded = refpack(stored, e['memory_bytes']) if e['compression'] else stored
                record = dict(package=name, key=key_json(key), **e, stored_sha256=digest(stored),
                              decoded_sha256=digest(decoded), raw_prefix64=decoded[:64].hex())
                record['metadata'] = xml_observations(decoded) if key[0]==0x2B978C46 else creaturedata_header(decoded)
                observations.append(record)
    fifty_path=BASE/'evidence/complete-creature-recipe-observations.json'
    fifty=json.loads(fifty_path.read_text(encoding='utf8'))
    reused=[]
    for name in ['local-part-definition-observations.json','local-selected-rigblock-metadata.json',
                 'local-selected-capability-mappings.json','local-same-role-selector-observations.json']:
        p=BASE/'evidence'/name
        reused.append(dict(path=str(p.resolve()),sha256=digest(p.read_bytes()),read_scope='Identity and existing evidence summary; no original payload re-read here.'))
    fifty.update(timestamp_utc=now.strftime('%Y-%m-%d %H:%M:%S UTC'),
                 timestamp_pacific=now.astimezone(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d %H:%M:%S %Z'),
                 target_executable_identity={'path':'E:/Steam/steamapps/common/Spore/SporeBin/SporeApp.exe',
                    'sha256':'f9716458cdc232a507686dcb490e75680c514e31a5b1f33601b0dfcd05baf75d',
                    'identity_scope':'reused45; EXE not reread in50/52', 'executed':False},
                 packages=packages,selected_resources=observations,reused_evidence=reused,
                 coverage={'all_seven_DBPF_indexes_read':True,'selected_resource_versions':4,
                    'decoded_bytes_total':sum(r['memory_bytes'] for r in observations),
                    'complete_creature_recipe_to_runtime_chain_recovered':False,'models_curves_or_textures_exported':False},
                 reader_sha256=digest(Path(__file__).read_bytes()),
                 unknowns=['Native full creaturedata parsing', 'Editable complete Creature instance recipe linked to compiled counterpart',
                           'Stable instance identity and bone/weight/socket compiler', 'Effective package resolution and runtime binding'])
    fifty_path.write_text(json.dumps(fifty,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    prior_path=BASE/'evidence/local-selected-animation-predicates.json'
    prior_raw=prior_path.read_bytes();prior=json.loads(prior_raw.decode('utf8'))
    channels=[]
    for resource in prior['records']:
        for channel in resource['predicates']['channels']:
            channels.append(dict(package=resource['package'],key=resource['key'],
                version=resource['predicates']['version'],stored_offset=resource['offset'],
                stored_sha256=resource['stored_sha256'],decoded_sha256=resource['decoded_sha256'],**channel))
    if len(prior['records'])!=46 or len(channels)!=612:
        raise FormatError('expected45 scope of46 ANIM versions and612 channels')
    lookat=[c for c in channels if int(c['movementFlags'],16)&8]
    anatomical=[c for c in channels if c['primaryContext']['capability_ascii'] in ('mout','eye')]
    fiftytwo_path=BASE/'evidence/gaze-head-attention-observations.json'
    fiftytwo=json.loads(fiftytwo_path.read_text(encoding='utf8'))
    fiftytwo.update(timestamp_utc=fifty['timestamp_utc'],timestamp_pacific=fifty['timestamp_pacific'],
        reader_sha256=digest(Path(__file__).read_bytes()),
        target_executable_identity=fifty['target_executable_identity'],
        reused_animation_evidence=dict(path=str(prior_path.resolve()),sha256=digest(prior_raw),
            source_scope='45 freshly decompressed46selected ANIM versions;52 reuses metadata without new ANIM payload reading.'),
        coverage=dict(resources=46,channels=612,LOOKAT_bit_channels=len(lookat),
            anatomy_tag_channels=len(anatomical), primary_mout_count=sum(c['primaryContext']['capability_ascii']=='mout' for c in channels),
            primary_eye_count=sum(c['primaryContext']['capability_ascii']=='eye' for c in channels),
            independent_organ_targets_observed=False, native_gaze_solver_recovered=False),
        LOOKAT_samples=lookat, anatomy_samples=anatomical[:6],
        unknowns=['External target producer/coordinate frame and slot meaning', 'Per-eye or multi-head target allocation',
                  'Eye/neck/spine joint solver and constraints', 'Gaze/attack/locomotion priority',
                  'Target loss timing and controller change policy'])
    fiftytwo_path.write_text(json.dumps(fiftytwo,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'module50':fifty['coverage'],'module52':fiftytwo['coverage']}))


if __name__=='__main__':main()
