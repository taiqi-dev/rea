"""Bounded, read-only probe for cooked Unreal Kismet calls in a Zen export.

This is a narrow evidence tool, not a general Blueprint decompiler. Unknown
tokens stop at their first byte; no speculative resynchronization is attempted.
"""

import argparse
import json
import pathlib
import struct


class DecodeError(Exception):
    pass


def read_int(buf, pos, size=4, signed=True):
    if pos + size > len(buf):
        raise DecodeError(f"truncated at {pos}")
    return int.from_bytes(buf[pos:pos + size], "little", signed=signed), pos + size


class Decoder:
    def __init__(self, code, names, imports, exports, absolute_start, max_nodes):
        self.code = code
        self.names = names
        self.imports = {x['package_index']: x.get('script_object') for x in imports}
        self.exports = {x['package_index']: x['name'] for x in exports}
        self.absolute_start = absolute_start
        self.max_nodes = max_nodes
        self.nodes = 0
        self.logical = 0
        self.calls = []

    def read(self, pos, size=4, signed=True):
        value, end = read_int(self.code, pos, size, signed)
        self.logical += size
        return value, end

    def name(self, pos):
        idx, pos = read_int(self.code, pos)
        num, pos = read_int(self.code, pos)
        self.logical += 12  # FName occupies 12 Kismet code-offset bytes.
        if not 0 <= idx < len(self.names):
            raise DecodeError(f"bad FName {idx} at {pos - 8}")
        return self.names[idx] + (f"_{num - 1}" if num else ""), pos

    def field(self, pos):
        count, pos = read_int(self.code, pos)
        if not 0 <= count <= 16:
            raise DecodeError(f"bad field path length {count} at {pos - 4}")
        path = []
        for _ in range(count):
            idx, pos = read_int(self.code, pos)
            num, pos = read_int(self.code, pos)
            if not 0 <= idx < len(self.names):
                raise DecodeError(f"bad field FName {idx} at {pos - 8}")
            path.append(self.names[idx] + (f"_{num - 1}" if num else ""))
        owner, pos = read_int(self.code, pos)
        self.logical += 8  # Cooked FFieldPath logical code-offset width.
        return {'path': '.'.join(path), 'owner_index': owner}, pos

    def array(self, pos, end_token, depth):
        args = []
        while True:
            if len(args) > 128:
                raise DecodeError('expression array over 128 entries')
            node, pos = self.expr(pos, depth + 1)
            if node['token'] == end_token:
                return args, pos
            args.append(node)

    def expr(self, pos, depth=0):
        if depth > 64 or self.nodes >= self.max_nodes:
            raise DecodeError('decode budget exceeded')
        if pos >= len(self.code):
            raise DecodeError('script end before expression')
        physical = pos
        logical = self.logical
        token = self.code[pos]
        pos += 1
        self.logical += 1
        self.nodes += 1
        node = {'token': f'0x{token:02x}', 'code_offset': logical,
                'file_offset': self.absolute_start + physical}
        if token in (0x00, 0x01, 0x02, 0x48, 0x6c):
            node['field'], pos = self.field(pos)
        elif token == 0x11:
            node['field'], pos = self.field(pos)
            node['value'], pos = self.read(pos, 1, False)
        elif token in (0x1c, 0x46, 0x68):
            idx, pos = self.read(pos)
            self.logical += 4  # FPackageIndex uses eight logical offset bytes.
            node['function_index'] = idx
            node['function'] = self.imports.get(idx) or self.exports.get(idx) or f'unknown:{idx}'
            node['args'], pos = self.array(pos, '0x16', depth)
            self.calls.append(node)
        elif token in (0x1b, 0x45):
            node['function'], pos = self.name(pos)
            node['args'], pos = self.array(pos, '0x16', depth)
            self.calls.append(node)
        elif token in (0x1d, 0x0c, 0x06, 0x4c, 0x5b):
            node['value'], pos = self.read(pos)
        elif token in (0x1e,):
            bits, pos = self.read(pos, 4, False)
            node['value'] = struct.unpack('<f',bits.to_bytes(4,'little',signed=False))[0]
        elif token == 0x37:
            bits, pos = self.read(pos, 8, False)
            node['value'] = struct.unpack('<d',bits.to_bytes(8,'little'))[0]
        elif token in (0x22, 0x23, 0x41):
            width = 24 if token in (0x22, 0x23) else 12
            if pos + width > len(self.code):
                raise DecodeError('truncated vector')
            node['value'] = list(struct.unpack('<ddd' if width == 24 else '<fff', self.code[pos:pos+width]))
            self.logical += width
            pos += width
        elif token in (0x20,):
            idx, pos = self.read(pos)
            self.logical += 4
            node['object_index'] = idx
            node['object'] = self.imports.get(idx) or self.exports.get(idx)
        elif token in (0x13, 0x2e, 0x52, 0x54, 0x55):
            idx, pos = self.read(pos)
            self.logical += 4
            node['class_index'] = idx
            node['class'] = self.imports.get(idx) or self.exports.get(idx)
            node['arg'], pos = self.expr(pos, depth + 1)
        elif token == 0x38:
            node['cast_type'], pos = self.read(pos, 1, False)
            node['arg'], pos = self.expr(pos, depth + 1)
        elif token in (0x21, 0x4b):
            node['value'], pos = self.name(pos)
        elif token == 0x61:
            node['function'], pos = self.name(pos)
            node['delegate'], pos = self.expr(pos, depth + 1)
            node['object'], pos = self.expr(pos, depth + 1)
        elif token in (0x24, 0x2c, 0x6a):
            node['value'], pos = self.read(pos, 1, False)
        elif token in (0x1f,):
            end = self.code.find(b'\x00', pos)
            if end < 0 or end - pos > 4096:
                raise DecodeError('unbounded string')
            node['value'] = self.code[pos:end].decode('utf-8', errors='replace')
            self.logical += end + 1 - pos
            pos = end + 1
        elif token == 0x29:
            kind, pos = self.read(pos, 1, False)
            node['text_kind'] = kind
            if kind == 1:
                node['source'], pos = self.expr(pos, depth + 1)
                node['key'], pos = self.expr(pos, depth + 1)
                node['namespace'], pos = self.expr(pos, depth + 1)
            elif kind in (2, 3):
                node['source'], pos = self.expr(pos, depth + 1)
            elif kind == 4:
                idx, pos = self.read(pos)
                self.logical += 4
                node['string_table_index'] = idx
                node['table_id'], pos = self.expr(pos, depth + 1)
                node['key'], pos = self.expr(pos, depth + 1)
            elif kind != 0:
                raise DecodeError(f'unsupported text kind {kind}')
        elif token in (0x04, 0x4e, 0x4f, 0x51, 0x6d):
            node['arg'], pos = self.expr(pos, depth + 1)
        elif token in (0x07,):
            node['target'], pos = self.read(pos)
            node['condition'], pos = self.expr(pos, depth + 1)
        elif token in (0x0f,):
            node['field'], pos = self.field(pos)
            node['target'], pos = self.expr(pos, depth + 1)
            node['value'], pos = self.expr(pos, depth + 1)
        elif token in (0x14, 0x43, 0x44, 0x5f, 0x60, 0x5c, 0x62, 0x6b):
            node['target'], pos = self.expr(pos, depth + 1)
            node['value'], pos = self.expr(pos, depth + 1)
        elif token == 0x31:
            node['target'], pos = self.expr(pos, depth + 1)
            node['elements'], pos = self.array(pos, '0x32', depth)
        elif token == 0x2f:
            idx, pos = self.read(pos)
            self.logical += 4
            node['struct_index'] = idx
            node['struct'] = self.imports.get(idx) or self.exports.get(idx)
            node['struct_size'], pos = self.read(pos)
            node['properties'], pos = self.array(pos, '0x30', depth)
        elif token == 0x42:
            node['field'], pos = self.field(pos)
            node['arg'], pos = self.expr(pos, depth + 1)
        elif token == 0x69:
            count, pos = self.read(pos, 2, False)
            if count > 128:
                raise DecodeError('switch has over 128 cases')
            node['end_offset'], pos = self.read(pos, 4, False)
            node['index'], pos = self.expr(pos, depth + 1)
            cases = []
            for _ in range(count):
                key, pos = self.expr(pos, depth + 1)
                next_offset, pos = self.read(pos, 4, False)
                value, pos = self.expr(pos, depth + 1)
                cases.append({'key': key, 'next_offset': next_offset, 'value': value})
            node['cases'] = cases
            node['default'], pos = self.expr(pos, depth + 1)
        elif token in (0x19, 0x1a, 0x12):
            node['object'], pos = self.expr(pos, depth + 1)
            node['skip'], pos = self.read(pos)
            node['field'], pos = self.field(pos)
            node['context'], pos = self.expr(pos, depth + 1)
        elif token in (0x0b, 0x16, 0x17, 0x25, 0x26, 0x27, 0x28, 0x2a,
                       0x2d, 0x30, 0x32, 0x4d, 0x53):
            pass
        else:
            raise DecodeError(f"unsupported token 0x{token:02x} at file offset {self.absolute_start + physical}")
        return node, pos


def find_script(export_bytes):
    # UFunction stores logical code size, serialized byte length, bytes, then
    # 12-byte flags/event-graph suffix. Require both exact boundary and 0x53.
    candidates = []
    for pos in range(len(export_bytes) - 20):
        logical, serialized = struct.unpack_from('<II', export_bytes, pos)
        start, end = pos + 8, pos + 8 + serialized
        if not (0 < logical < 10000000 and 0 < serialized < 10000000):
            continue
        if end == len(export_bytes) - 12 and export_bytes[end - 1] == 0x53:
            candidates.append((pos, start, end, logical))
    if len(candidates) == 1 and export_bytes[candidates[0][1]] in (0x46, 0x68, 0x14, 0x0f, 0x04, 0x06, 0x4c):
        return (*candidates[0], 'size_fields')
    # Cooked one-argument UFunctions may have inline property metadata whose
    # length pair masquerades as script sizes. Their 14-byte graph trampoline
    # is unambiguous when anchored at the 12-byte UFunction suffix.
    start = len(export_bytes) - 26
    code = export_bytes[start:start + 14]
    if (start >= 0 and code[0] == 0x46 and code[5] == 0x1d and
            code[10:] == b'\x16\x04\x0b\x53'):
        return (None, start, start + 14, 18, 'graph_trampoline')
    raise DecodeError(f'expected one exact script boundary, found {candidates[:8]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=pathlib.Path)
    parser.add_argument('zen_json', type=pathlib.Path)
    parser.add_argument('--function', required=True)
    parser.add_argument('--max-nodes', type=int, default=20000)
    parser.add_argument('--max-top-level', type=int, default=20000)
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    if not 1 <= args.max_nodes <= 100000 or not 1 <= args.max_top_level <= 100000:
        parser.error('budgets must be between 1 and 100000')
    meta = json.loads(args.zen_json.read_text(encoding='utf-8'))
    blob = args.package.read_bytes()
    matches = [x for x in meta['exports'] if x['name'] == args.function]
    if len(matches) != 1:
        parser.error(f'function name matched {len(matches)} exports')
    exp = matches[0]
    payload = blob[exp['data_offset']:exp['data_offset'] + exp['size']]
    pair, start, end, logical_size, boundary_source = find_script(payload)
    decoder = Decoder(payload[start:end], meta['names'], meta['imports'],
                      meta['exports'], exp['data_offset'] + start, args.max_nodes)
    statements = []
    error = None
    pos = 0
    for _ in range(args.max_top_level):
        if pos >= end - start:
            break
        try:
            node, pos = decoder.expr(pos)
        except DecodeError as exc:
            error = str(exc)
            break
        statements.append(node)
        if node['token'] == '0x53':
            break
    result = {'package': str(args.package), 'function': args.function,
              'export_offset': exp['data_offset'], 'script_size_field_offset': exp['data_offset'] + pair if pair is not None else None,
              'script_boundary_source': boundary_source,
              'script_file_offset': exp['data_offset'] + start,
              'serialized_size': end - start, 'logical_size': logical_size,
              'decoded_serialized_bytes': pos, 'decoded_logical_bytes': decoder.logical,
              'top_level_count': len(statements), 'node_count': decoder.nodes,
              'complete': error is None and pos == end - start and decoder.logical == logical_size,
              'error': error, 'calls': decoder.calls, 'statements': statements}
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + '\n', encoding='utf-8')
    else:
        print(encoded)


if __name__ == '__main__':
    main()
