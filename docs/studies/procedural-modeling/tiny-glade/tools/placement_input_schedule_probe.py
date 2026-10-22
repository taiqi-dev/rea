"""Read the measured Tiny Glade input and placement-schedule anchors.

Version-specific, read-only file evidence. Does not execute target code, emulate
input, calculate digests, or establish the built ECS graph or displayed frames.
Use with study topics 133 and 134; PDB and disassembly supply the interpretation.
"""

import argparse
import json
from pathlib import Path
import re
import struct

from atlas_budget_probe import PeReader


CALLS = {
    "main_registers_stages": (0x140654EF3, 0x14093E620),
    "enumerate_stages": (0x14093E74F, 0x1415EB150),
    "configure_update_sets": (0x14093E7A5, 0x140C97EF0),
    "normal_chain_metadata": (0x1404EF20E, 0x140F23D60),
    "translate_input": (0x14181E6DC, 0x140B6B330),
    "calculate_input_states": (0x141A09A6F, 0x1419ADF30),
    "ui_update": (0x141A5CBC5, 0x140BF00B0),
    "default_keybindings_v2": (0x140A1EDD0, 0x140A1F3F0),
    "escape_menu": (0x1401C185A, 0x14033DFA0),
    "escape_default_mode": (0x14033E68E, 0x140B4B6A0),
    "request_mode_gate": (0x140B42B33, 0x141B6B0B0),
    "rectangle_ui": (0x140AA9080, 0x140ADC7A0),
    "rectangle_submit": (0x140ADD67A, 0x141B75220),
    "rectangle_consumer": (0x141A74986, 0x140A4BB50),
    "roof_consumer": (0x141F37F1F, 0x14280DD10),
    "roof_assemble_registration": (0x1406C32DF, 0x140FDED70),
    "roof_prepare_registration": (0x1406C3347, 0x140FE0CA0),
    "roof_tile_flush": (0x140FE09F0, 0x141F482C0),
}

ANCHORS = {
    "digital_just_released_3": (0x140938B90, "83f9030f94c0"),
    "drag_started_3": (0x140901020, "803903"),
    "drag_finished_below_2": (0x140901030, "803902"),
    "drag_distance_mark": (0x140ADCB4C, "41c6400c01"),
    "confirmation_reads_moved_flag": (0x140ADD3BE, "80780c00"),
    "mode_clears_preview": (0x140ADCDCA, "41c7042400000000"),
    "default_mode_tag_zero": (0x140B4B6AA, "c60100"),
    "accepted_request_copies_mode": (0x141B6B14A, "0f1100"),
    "iterator_starts_zero": (0x14093E74D, "31d2"),
    "iterator_bound_45": (0x1415EB179, "80fa2d"),
    "iterator_increment_bound": (0x1415EB30C, "fec380fb2d"),
    "wall_shape_ux_tag_17": (0x140947109, "c6851007000011"),
    "timberframe_tag_27": (0x1406C44B3, "c685870000001b"),
    "roof_systems_tag_20": (0x1406C3230, "c6851007000014"),
    "roof_assemble_tag_29": (0x1406C32DD, "b21d"),
    "prepare_rendering_tag_44": (0x1406C3345, "b22c"),
}

# Registration lea -> measured System trait vtable -> run_unsafe, offset 0x48.
VTABLES = {
    "rectangle_ui": (0x1417E6912, 0x143048F78, 0x140AA8370),
    "rectangle_consumer": (0x1417E69B0, 0x143381AF8, 0x141A73D80),
    "roof_consumer": (0x140FD526C, 0x14342CCD0, 0x141F37C40),
    "spire_assemble": (0x140FDEE73, 0x143429620, 0x141F0FBE0),
    "roof_tile_prepare": (0x140FE0CEE, 0x14326DDC0, 0x140FE08E0),
}

STAGES = """Watchers InputReplayControl TimeUpdate InputReset InputGather
InputTranslate ImuiUpdate RmuiUpdate UiClientLogic CameraUpdate MainPreUpdate
Tutorial LoadGame SpawnPreplacedTrees HistoryStart TerrainGenerators
PathGenerators WallShapeUx RoofUiSystems WallGenerators RoofSystems
RoofDeleteEntities WallRoofHashmap IntersectWalls ElevatedShapesSupports1
DecoratorSystems ElevatedShapesSupports2 Timberframe WallVisualGenerators
RoofAssemble InitRaycastAccel ColorSystems Plaster ClearCanvas
HistoryDeferredRecord HistoryEnd PostGeneratorGameplay MaintainPrefabs Audio
DebugGui ReplaySystems ReplaySystemsCleanup RestoreArchivedData SaveGame
PrepareRendering""".split()


def controller_bindings(path):
    source = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(r'\s+|//[^\n]*|"(?:\\.|[^"\\])*"|[{}]')
    tokens = []
    position = 0
    while position < len(source):
        match = pattern.match(source, position)
        if match is None:
            raise ValueError(f"Unparsed VDF at character {position}")
        value = match.group()
        if not value.isspace() and not value.startswith("//"):
            tokens.append(json.loads(value) if value.startswith('"') else value)
        position = match.end()

    def block(index, nested):
        pairs = []
        while index < len(tokens):
            key = tokens[index]
            if key == "}":
                if not nested:
                    raise ValueError("Unexpected VDF closing brace")
                return pairs, index + 1
            if key == "{" or index + 1 >= len(tokens):
                raise ValueError("Expected VDF key/value")
            value = tokens[index + 1]
            index += 2
            if value == "{":
                value, index = block(index, True)
            elif value == "}":
                raise ValueError("Expected VDF value")
            pairs.append((key, value))
        if nested:
            raise ValueError("Unclosed VDF block")
        return pairs, index

    def values(pairs, key):
        return [value for name, value in pairs if name == key]

    def all_bindings(pairs):
        found = []
        for key, value in pairs:
            if isinstance(value, list):
                found.extend(all_bindings(value))
            elif key == "binding":
                found.append(value)
        return found

    tree, consumed = block(0, False)
    if consumed != len(tokens):
        raise ValueError("Trailing VDF tokens")
    roots = values(tree, "controller_mappings")
    if len(roots) != 1 or not isinstance(roots[0], list):
        raise ValueError("Expected one controller_mappings root")
    groups = [value for key, value in roots[0] if key == "group"]
    selected = [group for group in groups if values(group, "id") == ["1"]]
    if len(selected) != 1:
        raise ValueError("Expected unique controller group 1")
    inputs = values(selected[0], "inputs")
    if len(inputs) != 1:
        raise ValueError("Expected one group input block")
    result = {}
    for button, action in (("button_a", "ui_confirm"), ("button_b", "ui_cancel")):
        subtrees = values(inputs[0], button)
        if len(subtrees) != 1:
            raise ValueError(f"Expected one {button} block")
        result[button] = all_bindings(subtrees[0])
        if result[button] != [f"game_action GameControls {action}, , "]:
            raise ValueError(f"Unexpected shipped {button} binding")
    return result


def inspect(binary, controller):
    pe = PeReader(binary)
    if pe.base != 0x140000000:
        raise ValueError("Unexpected image base")
    for name, (site, target) in CALLS.items():
        raw = pe.read(site, 5)
        if raw[0] != 0xE8 or site + 5 + struct.unpack_from("<i", raw, 1)[0] != target:
            raise ValueError(f"Call mismatch: {name}")
    for name, (site, expected) in ANCHORS.items():
        if pe.read(site, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f"Anchor mismatch: {name}")
    for name, (site, table, wrapper) in VTABLES.items():
        raw = pe.read(site, 7)
        if raw[:3].hex() != "4c8d05" or site + 7 + struct.unpack_from("<i", raw, 3)[0] != table:
            raise ValueError(f"Registration lea mismatch: {name}")
        if struct.unpack("<Q", pe.read(table + 0x48, 8))[0] != wrapper:
            raise ValueError(f"System vtable mismatch: {name}")
    names = []
    for index in range(45):
        length = struct.unpack("<Q", pe.read(0x14326E848 + index * 8, 8))[0]
        relative = struct.unpack("<i", pe.read(0x14326E9B0 + index * 4, 4))[0]
        if not 0 < length <= 64:
            raise ValueError("Unexpected stage name length")
        names.append(pe.read(0x14326E9B0 + relative, length).decode("ascii"))
    if names != STAGES:
        raise ValueError("Stage names differ")
    for address in (0x143333D50, 0x143400670):
        control, *counts = struct.unpack("<QQQQ", pe.read(address, 32))
        if counts != [0, 0, 0] or pe.read(control, 16) != b"\xff" * 16:
            raise ValueError("Expected measured normal chained empty-map metadata")
    comparison = pe.read(0x140ADCB40, 7)
    if comparison[:3].hex() != "0f2e05":
        raise ValueError("Expected drag threshold RIP comparison")
    threshold_address = 0x140ADCB47 + struct.unpack_from("<i", comparison, 3)[0]
    threshold = struct.unpack("<f", pe.read(threshold_address, 4))[0]
    if threshold != 4.0:
        raise ValueError("Unexpected drag threshold")
    keys = {}
    for raw, expected in ((0x3A, "Enter"), (0x73, "Escape")):
        index = (raw + 0x80) & 0xFF
        length = struct.unpack("<Q", pe.read(0x1430377D8 + index * 8, 8))[0]
        address = struct.unpack("<Q", pe.read(0x143037FD8 + index * 8, 8))[0]
        if not 0 < length <= 32 or pe.read(address, length).decode("utf-8") != expected:
            raise ValueError("Key-name table mismatch")
        keys[hex(raw)] = expected
    return {
        "binary": str(binary.resolve()), "binary_bytes": len(pe.data),
        "calls_checked": len(CALLS), "anchors_checked": len(ANCHORS),
        "registration_vtables_checked": len(VTABLES),
        "stages": [{"raw": index, "name": name} for index, name in enumerate(names)],
        "normal_chain_empty_maps_checked": 2,
        "drag_threshold": {"address": hex(threshold_address), "value": threshold},
        "key_names": keys, "controller_bindings": controller_bindings(controller),
        "limitations": ["Ordinary file evidence, not REA provider Evidence.",
                        "Selected anchors do not prove complete control flow or all bindings.",
                        "No built schedule graph, input simulation, target execution, or frame acceptance."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--controller", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.binary, args.controller)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("calls_checked", "anchors_checked",
                                                "registration_vtables_checked")}))


if __name__ == "__main__":
    main()
