"""Bounded research reader for selected effect component sections.

Not a game executor, general effect exporter, or production skin generator.
The section envelope is pinned by public-selected-skin-recipe-container-format.json.
Opaque sections retain hashes; only the normal component prefix is inspected.
"""
import hashlib
import math
import struct
from dataclasses import dataclass


class FormatError(ValueError):
    pass


@dataclass(frozen=True)
class Section:
    type_id: int
    version: int
    header_offset: int
    body_start: int
    body_end: int
    count: int
    sha256: str


def read_component_sections(data):
    if len(data) < 4:
        raise FormatError('TruncatedEffectHeader')
    version = struct.unpack_from('>H', data, 0)[0]
    if version != 4:
        raise FormatError(f'UnsupportedEffectVersion:{version}')
    return read_sections_at(data, 2)


def read_sections_at(data, pos):
    sections = []
    seen = set()
    while True:
        if pos+2 > len(data):
            raise FormatError(f'MissingComponentTerminator:{pos}')
        type_id = struct.unpack_from('>H', data, pos)[0]
        if type_id == 0xffff:
            return sections, pos+2
        if pos+8 > len(data):
            raise FormatError(f'TruncatedSectionHeader:{pos}')
        type_id, version, size = struct.unpack_from('>HHI', data, pos)
        if type_id in seen:
            raise FormatError(f'DuplicateComponentType:{type_id:#x}')
        seen.add(type_id)
        body_start = pos+8
        if size < 4 or size > len(data)-body_start:
            raise FormatError(f'InvalidSectionSize:{type_id:#x}:{size}')
        body_end = body_start+size
        count = struct.unpack_from('>I', data, body_start)[0]
        sections.append(Section(type_id, version, pos, body_start, body_end, count,
                                hashlib.sha256(data[body_start:body_end]).hexdigest()))
        pos = body_end


def section_payload(data, section):
    if not 0 <= section.body_start < section.body_end <= len(data):
        raise FormatError('StaleSectionRange')
    payload = data[section.body_start:section.body_end]
    if hashlib.sha256(payload).hexdigest() != section.sha256:
        raise FormatError('SectionIdentityMismatch')
    return payload


class Cursor:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, length):
        if length < 0 or length > len(self.data)-self.pos:
            raise FormatError(f'TruncatedComponent:{self.pos}:{length}')
        value = self.data[self.pos:self.pos+length]
        self.pos += length
        return value

    def number(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def boolean(self):
        value = self.number('>B')
        if value not in (0, 1):
            raise FormatError(f'InvalidBoolean:{value}')
        return bool(value)

    def cstring(self):
        end = self.data.find(b'\0', self.pos)
        if end < 0:
            raise FormatError('UnterminatedComponentString')
        value = self.take(end-self.pos+1)[:-1]
        try:
            return value.decode('ascii')
        except UnicodeDecodeError as err:
            raise FormatError('NonAsciiComponentString') from err


def read_distribute(data, section, particle_count):
    if section.type_id != 0x23 or section.version not in (1, 2):
        raise FormatError('UnsupportedDistributeSection')
    payload = section_payload(data, section)
    c = Cursor(payload)
    count = c.number('>I')
    if count != section.count or count > (len(payload)-4)//42:
        raise FormatError('ImpossibleDistributeCount')
    result = []
    for ordinal in range(count):
        start = c.pos
        label = c.cstring()
        particle = c.number('>i')
        spacing = c.number('>f')
        limit, region = c.number('>i'), c.number('>i')
        raw_back, raw_belly, raw_body = c.take(4), c.take(4), c.take(8)
        back, belly = struct.unpack('>f', raw_back)[0], struct.unpack('>f', raw_belly)[0]
        body_range = list(struct.unpack('<ff', raw_body))
        flags = [c.boolean() for _ in range(4)]
        selection_count = c.number('>i')
        if selection_count < 0 or selection_count > (len(payload)-c.pos-1)//8:
            raise FormatError('ImpossibleParticleSelectionCount')
        selection = [dict(particle_index=c.number('>i'), stored_value=c.number('>f'))
                     for _ in range(selection_count)]
        select_all = c.boolean()
        for index in [particle]+[s['particle_index'] for s in selection]:
            if index != -1 and not 0 <= index < particle_count:
                raise FormatError(f'ParticleIndexOutOfRange:{index}:{particle_count}')
        if not all(math.isfinite(x) for x in [spacing, back, belly]+body_range+[s['stored_value'] for s in selection]):
            raise FormatError('NonFiniteDistributeValue')
        result.append(dict(ordinal=ordinal, decoded_byte_start=section.body_start+start,
                           decoded_byte_end=section.body_start+c.pos, label=label,
                           particle_index=particle, spacing=spacing, distribute_limit=limit,
                           region_raw=region, region_back_stored=back, region_belly_stored=belly,
                           body_range=body_range,
                           raw_float_fields=dict(back_hex=raw_back.hex(), belly_hex=raw_belly.hex(),
                                                 body_range_hex=raw_body.hex()),
                           flags=dict(zip(('inverse','center_only','cover','ordered'),flags)),
                           particle_select=selection, select_all=select_all))
    if c.pos != len(payload):
        raise FormatError(f'DistributeTrailingBytes:{len(payload)-c.pos}')
    return result


def read_visual_exports(data, start):
    c = Cursor(data)
    c.pos = start
    version = c.number('>h')
    if version != 1:
        raise FormatError(f'UnsupportedVisualVersion:{version}')
    count = c.number('>i')
    if count < 0 or count > (len(data)-c.pos)//49:
        raise FormatError('ImpossibleVisualCount')
    visuals = []
    for ordinal in range(count):
        begin = c.pos
        c.take(12+8+4+1)  # flags/application masks, LE range, scale, byte
        lod_count = c.number('>i')
        if lod_count < 0 or lod_count > (len(data)-c.pos)//4:
            raise FormatError('ImpossibleVisualLODCount')
        c.take(lod_count*4+12+4)  # BE LOD array, LE vector, BE seed
        block_count = c.number('>i')
        if block_count < 0 or block_count > (len(data)-c.pos)//109:
            raise FormatError('ImpossibleVisualBlockCount')
        blocks = []
        for block_ordinal in range(block_count):
            bstart = c.pos
            block_type = c.number('>B')
            flags = c.number('>I')
            c.take(54)  # Transform: u16 flags + f32 scale + LE 3x3 + LE offset
            lod_begin, lod_end = c.number('>B'), c.number('>B')
            scales = c.number('>i')
            if scales < 0 or scales > (len(data)-c.pos-40)//12:
                raise FormatError('ImpossibleBlockLODScaleCount')
            c.take(scales*12+24+8+4)  # LOD scales, 6 factors, masks, selection
            time_scale = c.number('>f')
            component_index = c.number('>i')
            blocks.append(dict(ordinal=block_ordinal, decoded_byte_start=bstart,
                               decoded_byte_end=c.pos, block_type=block_type,
                               flags_raw=flags, component_index_raw=component_index,
                               lod_begin=lod_begin, lod_end=lod_end, time_scale=time_scale))
        visuals.append(dict(ordinal=ordinal, decoded_byte_start=begin,
                            decoded_byte_end=c.pos, blocks=blocks))
    export_start = c.pos
    exports = []
    while True:
        index = c.number('>i')
        if index == -1:
            break
        group, name = c.number('>I'), c.number('>I')
        # Preserve high-bit/import references without guessing their indexing policy.
        if index >= count:
            raise FormatError(f'ExportVisualIndexOutOfRange:{index}:{count}')
        exports.append(dict(effect_index_raw=index, group=f'0x{group:08x}', name_hash=f'0x{name:08x}'))
    string_assignments = c.number('>i')
    import_count = c.number('>i')
    if import_count < 0 or import_count > (len(data)-c.pos)//8:
        raise FormatError('ImpossibleImportCount')
    imports = [dict(group=f'0x{c.number(">I"):08x}', name_hash=f'0x{c.number(">I"):08x}')
               for _ in range(import_count)]
    if c.pos != len(data):
        raise FormatError(f'EffectDirectoryTrailingBytes:{len(data)-c.pos}')
    return dict(visual_version=version, visuals=visuals, export_start=export_start,
                exports=exports, string_assignments_raw=string_assignments,
                imports=imports, decoded_end=c.pos)


def read_sequences(data, section, visual_count):
    if section.type_id != 4 or section.version != 1:
        raise FormatError('UnsupportedSequenceSection')
    payload=section_payload(data,section)
    c=Cursor(payload)
    count=c.number('>i')
    if count < 0 or count != section.count or count > (len(payload)-4)//8:
        raise FormatError('ImpossibleSequenceCount')
    result=[]
    for ordinal in range(count):
        begin=c.pos
        items=c.number('>i')
        if items < 0 or items > (len(payload)-c.pos-4)//12:
            raise FormatError('ImpossibleSequenceStepCount')
        steps=[]
        for step in range(items):
            time_range=list(struct.unpack('<ff',c.take(8)))
            visual=c.number('>i')
            if visual != -1 and not 0 <= visual < visual_count:
                raise FormatError('SequenceVisualIndexOutOfRange')
            if not all(math.isfinite(v) for v in time_range):
                raise FormatError('NonFiniteSequenceTimeRange')
            steps.append(dict(ordinal=step,time_range_stored=time_range,visual_index=visual))
        flags=c.number('>I')
        result.append(dict(ordinal=ordinal,decoded_byte_start=section.body_start+begin,
                           decoded_byte_end=section.body_start+c.pos,steps=steps,flags_raw=flags))
    if c.pos!=len(payload):
        raise FormatError('SequenceTrailingBytes')
    return result


def trace_selected_visual(index,visuals,sequences,section_counts,ancestry=()):
    if ('visual',index) in ancestry:
        raise FormatError(f'SelectedEffectCycle:{ancestry}:{index}')
    if not 0 <= index < len(visuals):
        raise FormatError('TraceVisualOutOfRange')
    ancestry=ancestry+(('visual',index),)
    trace=[]
    for block in visuals[index]['blocks']:
        kind,ref=block['block_type'],block['component_index_raw']
        if kind==4:
            if not 0<=ref<len(sequences):
                raise FormatError('TraceSequenceOutOfRange')
            seq=sequences[ref]
            for step in seq['steps']:
                if step['visual_index']==-1:
                    trace.append(dict(path=list(ancestry)+[('sequence',ref),('wait',step['ordinal'])],
                                      time_range_stored=step['time_range_stored']))
                else:
                    children=trace_selected_visual(step['visual_index'],visuals,sequences,section_counts,
                                                   ancestry+(('sequence',ref),))
                    for child in children:
                        child['sequence_time_ranges_stored']=[step['time_range_stored']]+child.get('sequence_time_ranges_stored',[])
                    trace.extend(children)
        elif kind==0:
            trace.extend(trace_selected_visual(ref,visuals,sequences,section_counts,ancestry))
        else:
            if kind not in section_counts or not 0<=ref<section_counts[kind]:
                raise FormatError(f'TraceComponentOutOfRange:{kind}:{ref}')
            trace.append(dict(path=list(ancestry)+[('component',kind,ref)],
                              block_decoded_byte_range=[block['decoded_byte_start'],block['decoded_byte_end']],
                              block_flags_raw=block['flags_raw']))
    return trace
