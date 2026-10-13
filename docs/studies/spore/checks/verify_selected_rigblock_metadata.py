"""Research-reader boundary checks and selected local metadata replay; not gameplay."""
import json
from pathlib import Path
import struct
import unittest

from read_selected_rigblock_metadata import MAGIC, HANDLE, SKELETON, KEYFRAME, BASE, SKIN_LINKS
from read_selected_rigblock_metadata import FormatError, read_metadata, reference_info


def fixture(parts):
    table = 0xa0
    position = table + 24 * len(parts)
    result = bytearray(position)
    result[:28] = MAGIC
    struct.pack_into('<I', result, 0x1c, 1)
    struct.pack_into('<I', result, 0x24, len(parts))
    struct.pack_into('<I', result, 0x30, table)
    for index, (code, body) in enumerate(parts):
        struct.pack_into('<Iiiiii', result, table + index * 24,
                         position, 0, len(body), 4, 0, code)
        result.extend(body)
        position += len(body)
    return result


def keyframe_fixture():
    # Single animation; two channels, each with one LocRot key.
    start = 0xa0 + 24
    body = bytearray(144)
    struct.pack_into('<IIiiIIiifiiI', body, 0, start + 48, 2, 17, 0,
                     start + 80, start + 144, 2, 0, 1.25, 0, 1, start + 56)
    struct.pack_into('<II', body, 48, 100, 101)
    struct.pack_into('<IiiIii', body, 56, 80, 32, 0x101, 112, 32, 0x101)
    struct.pack_into('<8f', body, 80, 0, 0, 0, 1, 2, 3, 4, .625)
    struct.pack_into('<8f', body, 112, 0, 0, 0, 1, 2, 3, 4, 1.25)
    return fixture([(KEYFRAME, body)])


class ReaderChecks(unittest.TestCase):
    def test_opaque_section_bounds(self):
        value = read_metadata(fixture([(0x1234, b'abcd')]))
        self.assertEqual(value['section_count'], 1)
        self.assertEqual(value['handles'], [])

    def test_signature_and_header(self):
        with self.assertRaisesRegex(FormatError, 'header'):
            read_metadata(b'RW4')
        value = fixture([(0x1234, b'abcd')]); value[0] = 0
        with self.assertRaisesRegex(FormatError, 'signature'):
            read_metadata(value)

    def test_section_count_table_range(self):
        value = fixture([(0x1234, b'abcd')])
        struct.pack_into('<I', value, 0x24, 0xffffffff)
        with self.assertRaisesRegex(FormatError, 'count'):
            read_metadata(value)

    def test_negative_section_size(self):
        value = fixture([(0x1234, b'abcd')])
        struct.pack_into('<i', value, 0xa0 + 8, -1)
        with self.assertRaisesRegex(FormatError, 'outside'):
            read_metadata(value)

    def test_base_pointer_conversion(self):
        value = fixture([(BASE, b'abcd')])
        struct.pack_into('<I', value, 0x44, 4)
        struct.pack_into('<I', value, 0xa0, 0xb8 - 4)
        self.assertEqual(read_metadata(value)['sections'][0]['data_offset'], 0xb8)

    def test_morph_null_and_raw_default(self):
        body = struct.pack('<ii6dfI', 55, 7, 0, 0, 0, 1, 2, 3, 1.25, 0x00400000)
        handle = read_metadata(fixture([(HANDLE, body)]))['handles'][0]
        self.assertEqual(handle['default_time_raw'], 1.25)
        self.assertEqual(handle['animation_reference']['kind'], 'null-encoding')

    def test_morph_size_and_nonfinite(self):
        with self.assertRaisesRegex(FormatError, 'truncated morph'):
            read_metadata(fixture([(HANDLE, bytes(63))]))
        body = struct.pack('<ii6dfI', 55, 7, 0, 0, 0, 1, 2, 3, float('nan'), 0x00400000)
        with self.assertRaisesRegex(FormatError, 'non-finite'):
            read_metadata(fixture([(HANDLE, body)]))

    def test_reference_namespaces(self):
        sections = [{'type': '0x00070001'}]
        self.assertEqual(reference_info(0, sections)['section_index'], 0)
        self.assertEqual(reference_info(0x00800001, sections)['kind'], 'unresolved-subreference')
        self.assertEqual(reference_info(0x00c00000, sections)['kind'], 'unsupported-reference-encoding')
        with self.assertRaisesRegex(FormatError, 'out of bounds'):
            reference_info(1, sections)

    def test_wrong_morph_reference_type(self):
        body = struct.pack('<ii6dfI', 55, 7, 0, 0, 0, 1, 2, 3, 0, 0)
        with self.assertRaisesRegex(FormatError, 'non-animation'):
            read_metadata(fixture([(HANDLE, body)]))

    def test_skeleton_count_and_array_range(self):
        start = 0xb8
        body = struct.pack('<IIIiIi3i', start + 24, start + 28, start + 32,
                           1, 17, 1, 0, -1, 55)
        self.assertEqual(read_metadata(fixture([(SKELETON, body)]))['skeletons'][0]['bone_count'], 1)
        bad = bytearray(body); struct.pack_into('<i', bad, 20, 2)
        with self.assertRaisesRegex(FormatError, 'count'):
            read_metadata(fixture([(SKELETON, bad)]))

    def test_keyframe_directory_and_selected_key(self):
        animation = read_metadata(keyframe_fixture())['animations'][0]
        self.assertEqual(animation['channel_count'], 2)
        self.assertEqual(animation['selected_channel_samples'][0]['samples'][0]['time_raw'], .625)

    def test_keyframe_directory_bad_size(self):
        value = keyframe_fixture()
        struct.pack_into('<i', value, 0xb8 + 60, 0)
        with self.assertRaisesRegex(FormatError, 'pose size'):
            read_metadata(value)

    def test_selected_channel_span_budget(self):
        value = keyframe_fixture()
        struct.pack_into('<I', value, 0xb8 + 68, 111)
        with self.assertRaisesRegex(FormatError, 'span invalid'):
            read_metadata(value)

    def test_local_capture_is_bounded_observation(self):
        path = Path(__file__).resolve().parents[1] / 'evidence/local-selected-rigblock-metadata.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        metadata = data['metadata']
        self.assertEqual(metadata['section_count'], 21)
        self.assertEqual(metadata['handles'], [])
        self.assertEqual([s['bone_count'] for s in metadata['skeletons']], [1, 10])
        self.assertEqual([a['channel_count'] for a in metadata['animations']], [10, 10])
        samples = [sample for a in metadata['animations']
                   for c in a['selected_channel_samples'] for sample in c['samples']]
        self.assertEqual(len(samples), 10)
        self.assertNotEqual(samples[3]['rotation_raw'], samples[4]['rotation_raw'])

    def test_skin_link_encoding_and_size(self):
        body = struct.pack('<IiIII', 0x00400000, 123, 0x00400000, 0x00400000, 0x00400000)
        links = read_metadata(fixture([(SKIN_LINKS, body)]))['skin_links'][0]
        self.assertEqual(links['skeleton_reference']['kind'], 'null-encoding')
        with self.assertRaisesRegex(FormatError, 'truncated skin links'):
            read_metadata(fixture([(SKIN_LINKS, body[:19])]))

    def test_local_hierarchy_and_pose_links(self):
        path = Path(__file__).resolve().parents[1] / 'evidence/local-selected-rigblock-metadata.json'
        m = json.loads(path.read_text(encoding='utf-8'))['metadata']
        bones = m['skeletons'][1]['bones']
        self.assertEqual([b['parent_index_raw'] for b in bones], [-1, 0, 1, 2, 0, 4, 5, 0, 7, 8])
        self.assertEqual(m['skin_links'][0]['skeleton_reference']['section_index'], 16)
        self.assertEqual(m['skin_links'][0]['animation_skin_reference']['section_index'], 6)
        for animation in m['animations']:
            self.assertEqual([c['channel_id'] for c in animation['channels']],
                             [b['name_id'] for b in bones])


if __name__ == '__main__':
    unittest.main(verbosity=2)
