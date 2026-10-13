"""Synthetic boundary fixtures; these do not verify game execution or damage."""
import json
import struct
import unittest

from read_selected_action_events import FormatError, read_action_events


def fixture():
    # Explicit documented wire layout, with two events and three INFO references.
    data = bytearray(0x900)
    def word(offset, value):
        struct.pack_into('<I', data, offset, value)
    word(0, 0x4D494E41)
    word(4, len(data))
    word(8, 0x19)
    struct.pack_into('<f', data, 0x11C, 1 / 30)
    struct.pack_into('<f', data, 0x120, 10)
    word(0x13C, 2)
    word(0x140, 0x500)
    word(0x144, 2)
    word(0x148, 0x200)
    word(0x200, 0x240)
    word(0x204, 0x340)
    for base, comp, keys, count in [(0x240, 0x440, 0x480, 2), (0x340, 0x460, 0x4C0, 1)]:
        word(base, 0x4E414843)
        data[base + 8:base + 13] = b'hand\0'
        word(base + 0x90, 0x70737267)  # grsp
        word(base + 0x9C, 2)
        word(base + 0xD4, count)
        word(base + 0xD8, keys)
        word(base + 0xDC, 1)
        word(base + 0xE0, comp)
        word(comp, 0)
        word(comp + 4, 0x4F464E49)
        word(comp + 8, 0)
        word(comp + 12, 20)
        word(comp + 16, 0)
    for offset, time, start, count in [(0x480, 0, 0, 2), (0x494, 4, 1, 1), (0x4C0, 4, 1, 1)]:
        struct.pack_into('<iIHBBII', data, offset, time, 0xAABBCCDD, start, count, 0xCC, 0x11223344, 0xDDDDDDDD)
    for offset, ident, nameptr in [(0x500, 0x11, 0x800), (0x560, 0x22, 0x820)]:
        word(offset, 1)
        for relative in (4, 0x10, 0x1C):
            word(offset + relative, 2)
        word(offset + 0x3C, ident)
        word(offset + 0x40, nameptr)
        struct.pack_into('<f', data, offset + 0x48, 16)
        data[offset + 0x58:offset + 0x60] = bytes.fromhex('cdcdcdcdcdcdcdcd')
    data[0x800:0x80F] = b'fixture_effect\0'
    data[0x820:0x830] = b'fixture_message\0'
    word(0x560, 0xA0001)  # message and float parameter1
    word(0x564, 0x12)  # default plus firstOnly
    word(0x5AC, 0x3F000000)
    return data


def word(data, offset, value):
    struct.pack_into('<I', data, offset, value)


class EventReaderTests(unittest.TestCase):
    def test_little_endian_layout_and_links(self):
        parsed = read_action_events(fixture())
        self.assertEqual(parsed['header']['eventCount'], 2)
        self.assertEqual(parsed['info_event_references'][0]['event_indices'], [0, 1])
        self.assertEqual(parsed['events'][0]['name']['name'], 'fixture_effect')
        self.assertEqual(parsed['events'][1]['community_event_type'], 'message')

    def test_bad_magic(self):
        data = fixture(); word(data, 0, 0)
        with self.assertRaises(FormatError): read_action_events(data)

    def test_unsupported_version(self):
        data = fixture(); word(data, 8, 0x13)
        with self.assertRaises(FormatError): read_action_events(data)

    def test_size_mismatch(self):
        data = fixture(); word(data, 4, len(data) + 1)
        with self.assertRaises(FormatError): read_action_events(data)

    def test_event_table_bounds(self):
        data = fixture(); word(data, 0x140, len(data) - 32)
        with self.assertRaisesRegex(FormatError, 'event table'): read_action_events(data)

    def test_name_pointer_bounds(self):
        data = fixture(); word(data, 0x540, len(data))
        with self.assertRaisesRegex(FormatError, 'name pointer'): read_action_events(data)

    def test_unterminated_name(self):
        data = fixture(); word(data, 0x540, len(data) - 4); data[-4:] = b'abcd'
        with self.assertRaisesRegex(FormatError, 'terminator'): read_action_events(data)

    def test_nonascii_name(self):
        data = fixture(); data[0x800] = 0xFF
        with self.assertRaisesRegex(FormatError, 'ASCII'): read_action_events(data)

    def test_nonzero_event_range_overflow(self):
        data = fixture(); struct.pack_into('<HB', data, 0x488, 1, 2)
        with self.assertRaisesRegex(FormatError, 'event range'): read_action_events(data)

    def test_zero_count_does_not_dereference_start_sentinel(self):
        data = fixture(); struct.pack_into('<HB', data, 0x488, 65535, 0)
        result = read_action_events(data)
        self.assertEqual(result['zero_count_start_histogram'], [{'eventStartIndex': 65535, 'rows': 1}])

    def test_short_INFO_stride(self):
        data = fixture(); word(data, 0x44C, 16)
        with self.assertRaisesRegex(FormatError, 'stride'): read_action_events(data)

    def test_truncated_INFO_span(self):
        data = fixture(); word(data, 0x240 + 0xD4, 1); word(data, 0x240 + 0xD8, len(data) - 4)
        with self.assertRaisesRegex(FormatError, 'INFO keyframe'): read_action_events(data)

    def test_unexpected_INFO_identifier(self):
        data = fixture(); word(data, 0x444, 0)
        with self.assertRaisesRegex(FormatError, 'identifier'): read_action_events(data)

    def test_research_budget_rejection(self):
        data = fixture(); word(data, 0x13C, 4097)
        with self.assertRaisesRegex(FormatError, 'budget'): read_action_events(data)

    def test_signed_and_float_parameters(self):
        data = fixture(); word(data, 0x500, 0x101); word(data, 0x544, 0xFFFFFFFD)
        result = read_action_events(data)
        self.assertEqual(result['events'][0]['parameter0']['value'], -3)
        self.assertEqual(result['events'][1]['parameter1']['float']['value'], 0.5)

    def test_unused_nonfinite_float_keeps_diagnostic_class(self):
        data = fixture(); word(data, 0x548, 0x7FC00000)
        event = read_action_events(data)['events'][0]
        self.assertIsNone(event['maxSqrDist']['value'])
        self.assertEqual(event['maxSqrDist']['classification'], 'nan')
        json.dumps(event, allow_nan=False)

    def test_repeated_references_are_preserved(self):
        result = read_action_events(fixture())
        self.assertEqual(result['repeated_event_index_references'][0]['event_index'], 1)
        self.assertEqual(result['repeated_event_index_references'][0]['reference_count'], 3)

    def test_reused_id_does_not_merge_table_entries(self):
        data = fixture(); word(data, 0x59C, 0x11)
        result = read_action_events(data)
        self.assertEqual(result['same_id_multiple_table_entries'], [{'id': '0x00000011', 'event_indices': [0, 1]}])
        self.assertEqual(result['info_event_references'][0]['event_indices'], [0, 1])

    def test_selector_filter_is_event_specific(self):
        selector = read_action_events(fixture())['events'][1]['selectors'][0]
        self.assertEqual(selector['community_type'], 'default')
        self.assertEqual(selector['community_filter'], 'firstOnly')

    def test_fourth_source_and_unknown_tail_preserved(self):
        event = read_action_events(fixture())['events'][0]
        self.assertEqual(event['selectors'][3]['role'], 'source4')
        self.assertEqual(event['unknown_tail_8_bytes'], 'cdcdcdcdcdcdcdcd')


if __name__ == '__main__':
    unittest.main(verbosity=2)
