"""Bounded, read-only artifact anchors for Tiny Glade studies 140-142.

No target execution, hashing, downloads, GPU validation or resource extraction.
PDB identities and complete native control flow are separate retained evidence.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from spirv_probe import decode_module


MODULES = {
    "light": ("deferred/solid_light_sun_sky.precomp", 1243, 20348),
    "shadow": ("apply_screen_shadows.precomp", 112, 5463),
    "tree": ("clearing/tree_canopy.precomp", 159, 5605),
    "water": ("water_plane.precomp", 3098, 16301),
    "deferred_water": ("water/deferred_rt.precomp", 106, 21600),
}

NATIVE = {
    "weather_parameter_pointer": (0x1409253F6, "48 8b 02 48 89 85 10 11 00 00"),
    "weather_wind_load": (0x140925D8B, "48 8b 85 10 11 00 00 f3 0f 10 48 0c"),
    "frame_wind_store": (0x1409263BA, "f3 0f 10 85 38 11 00 00 f3 0f 11 81 34 01 00 00"),
    "settings_to_weather": (0x1408F9D10, "4d 8b 45 00 f3 41 0f 10 40 10 89 01 f3 0f 11 42 0c"),
    "settings_default_wind": (0x140C5D3EB, "c7 46 10 00 00 80 3f"),
    "wind_key_to_enum7": (0x141C6F698, "48 b9 77 69 6e 64 5f 73 74 72 48 33 0a 49 b8 73 74 72 65 6e 67 74 68 4c 33 42 05 49 09 c8 0f 85 96 00 00 00 b1 07"),
    "wind_value_read": (0x14167C293, "f3 0f 10 75 64"),
    "water_surface_gate": (0x140B025D7, "80 3d ea 1d 1a 03 01 0f 85 60 06 00 00"),
}


def inspect(game, grammar_path):
    grammar = json.loads(grammar_path.read_text(encoding="utf-8"))
    opcodes = {r["opcode"]: r for r in grammar["instructions"]}
    modules = {}
    for key, (relative, offset, count) in MODULES.items():
        blob = (game / "compiled-shaders/country-core/compiled" / relative).read_bytes()
        if offset < 4 or offset + 4 * count > len(blob):
            raise ValueError(f"Unbacked selected module: {key}")
        if struct.unpack_from("<I", blob, offset - 4)[0] != count:
            raise ValueError(f"Selected module count changed: {key}")
        modules[key] = decode_module(blob, offset, count, opcodes)

    def row(key, word, op, operands=None):
        result = next((r for r in modules[key]["instructions"] if r["word_offset"] == word), None)
        if result is None or result["op"] != op or (operands is not None and result["operands"] != operands):
            raise ValueError(f"Instruction changed: {key} w{word}")
        return {"word": word, "op": op, "operands": result["operands"]}

    def constant(key, result_id, expected):
        value = modules[key]["constants"].get(str(result_id), {}).get("value")
        if not isinstance(value, (float, int)) or abs(value - expected) > 1e-6:
            raise ValueError(f"Constant changed: {key} %{result_id}")
        return value

    light = [
        row("light", 6531, "OpFMul", [6, 7367, 5868, 5868]),
        row("light", 6581, "OpFAdd", [6, 7392, 7384, 1197]),
        row("light", 6661, "OpFMul", [6, 7389, 7388, 2246]),
        row("light", 6792, "OpFDiv", [6, 7549, 7446, 7548]),
        row("light", 6827, "OpExtInst", [7, 7556, 365, 46, 2263, 2410, 7555]),
        row("light", 6951, "OpFDiv", [7, 7478, 7474, 7477]),
        row("light", 6967, "OpFAdd", [7, 22705, 7379, 18798]),
        row("light", 7000, "OpVectorTimesScalar", [7, 7270, 7617, 7224]),
    ]
    shadow = [
        row("shadow", 4310, "OpSLessThan", [20, 1863, 2351, 148]),
        row("shadow", 4479, "OpImageSampleExplicitLod"),
        row("shadow", 4496, "OpFOrdGreaterThan", [20, 1895, 1894, 1893]),
        row("shadow", 4639, "OpFOrdEqual", [20, 1941, 2352, 2390]),
        row("shadow", 4741, "OpSLessThan", [20, 1969, 2354, 148]),
        row("shadow", 4938, "OpImageSampleDrefExplicitLod"),
        row("shadow", 5012, "OpFSub", [11, 2173, 2170, 2172]),
        row("shadow", 5244, "OpExtInst", [11, 1283, 333, 43, 2365, 1280, 1281]),
        row("shadow", 5252, "OpExtInst", [11, 1284, 333, 46, 1283, 2165, 1285]),
    ]
    water = [
        row("water", 6123, "OpDot", [6, 811, 801, 11919]),
        row("water", 6158, "OpFAdd", [6, 5438, 833, 5437]),
        row("water", 8125, "OpImageSampleExplicitLod"),
        row("water", 11715, "OpBranchConditional", [14028, 74, 81]),
        row("water", 12308, "OpStore", [8323, 4160]),
        row("water", 12404, "OpAccessChain", [129, 3850, 935, 186]),
        row("water", 12431, "OpIEqual", [13, 8344, 205, 5383]),
        row("water", 12489, "OpImageSampleExplicitLod"),
        row("water", 14695, "OpVectorTimesScalar", [14, 4489, 4441, 5438]),
        row("water", 14705, "OpVectorTimesScalar", [14, 4491, 4490, 4488]),
    ]
    traversal = [
        row("deferred_water", 5354, "OpBranchConditional", [151, 29, 30]),
        row("deferred_water", 6226, "OpAccessChain", [138, 7260, 756, 135, 7136, 135, 135, 135]),
        row("deferred_water", 8691, "OpAccessChain", [1467, 8106, 1458, 135, 7175, 135, 135, 135]),
        row("deferred_water", 8843, "OpExtInst", [11, 8175, 271, 68, 16126, 8162]),
        row("deferred_water", 8985, "OpFOrdGreaterThanEqual", [1617, 8216, 18873, 1619]),
    ]
    offsets = [r for r in modules["tree"]["instructions"] if r["op"] == "OpMemberDecorate" and r["operands"][:3] == [283, 38, 35]]
    if len(offsets) != 1 or offsets[0]["operands"][3] != 308:
        raise ValueError("FrameConstants wind offset changed")
    wind_names = [r for r in modules["tree"]["member_names"] if r["type_id"] == 283 and r["member"] == 38]
    if len(wind_names) != 1 or wind_names[0]["name"] != "wind_strength":
        raise ValueError("FrameConstants wind member identity changed")
    if modules["deferred_water"]["names"].get("756") != "rt_scene.rt_bl_bvh" or modules["deferred_water"]["names"].get("1458") != "rt_scene.rt_triangles":
        raise ValueError("Selected traversal buffer identities changed")

    spec = importlib.util.spec_from_file_location("study_pe_reader", Path(__file__).with_name("atlas_budget_probe.py"))
    reader_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader_module)
    pe = reader_module.PeReader(game / "tiny-glade.exe")
    native = {}
    for key, (va, expected) in NATIVE.items():
        blob = bytes.fromhex(expected)
        if pe.read(va, len(blob)) != blob:
            raise ValueError(f"Native anchor changed: {key}")
        native[key] = {"preferred_va": hex(va), "bytes_matched": len(blob)}
    table = 0x14332458C
    target = table + struct.unpack("<i", pe.read(table + 7 * 4, 4))[0]
    if target != 0x14167BF5D:
        raise ValueError("Settings enum7 dispatch changed")
    calls = {}
    for site, expected in [(0x14060313D, 0x1409252D0), (0x1405DA51C, 0x140594EE0),
                           (0x1405DA5BA, 0x140E26410), (0x140B02A6C, 0x141758710)]:
        blob = pe.read(site, 5)
        actual = site + 5 + struct.unpack_from("<i", blob, 1)[0]
        if blob[0] != 0xE8 or actual != expected:
            raise ValueError(f"Direct call changed: {hex(site)}")
        calls[hex(site)] = hex(actual)

    return {
        "game": str(game.resolve()), "exe_bytes": (game / "tiny-glade.exe").stat().st_size,
        "selected_modules": {k: {"path": v[0], "offset": v[1], "words": v[2]} for k, v in MODULES.items()},
        "light_anchors": light, "shadow_anchors": shadow, "water_anchors": water,
        "traversal_anchors": traversal, "native_anchors": native, "direct_calls": calls,
        "settings_wind_enum7_target": hex(target), "frame_wind_offset": 308,
        "constants": {"diffuse_inv_pi": constant("light", 2246, 1 / 3.141592653589793),
                      "diffuse_bias": constant("light", 1197, -0.5),
                      "shadow_search_limit": constant("shadow", 148, 8),
                      "shadow_filter_limit": constant("shadow", 2390, 8),
                      "shadow_current_weight": constant("shadow", 1285, 0.125),
                      "water_f0": constant("water", 833, 0.04),
                      "water_one_minus_f0": constant("water", 13950, 0.96)},
        "deferred_water_rayquery_instructions": sum("RayQuery" in r["op"] for r in modules["deferred_water"]["instructions"]),
        "shipped_olden_wind": json.loads((game / "assets/glade/olden/settings.json").read_text(encoding="utf-8"))["wind_strength"],
        "limitations": ["Selected static anchors, not whole-program proof", "Not spirv-val or REA native Evidence",
                        "No target launch, GPU timings, Unity project inspection or runtime acceptance"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("--grammar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Fresh output required")
    result = inspect(args.game, args.grammar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"selected_modules": len(MODULES), "native_anchors": len(NATIVE),
                      "direct_calls": len(result["direct_calls"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
