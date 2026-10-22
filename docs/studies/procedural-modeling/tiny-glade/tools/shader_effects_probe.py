"""Read selected native SPIR-V effect anchors for Tiny Glade studies 137-139.

Caller supplies the retained Khronos grammar. No downloads, digests, GPU work,
target execution or validation of the surrounding precomp container occur.
"""

import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from spirv_probe import decode_module


MODULES = {
    "tree_canopy_vertex": ("clearing/tree_canopy.precomp", 159, 5605),
    "reed_vertex": ("reed.precomp", 127, 5104),
    "bush_vertex": ("nani_bush.precomp", 137, 3694),
    "grass_vertex": ("grass2/lod0.precomp", 141, 6689),
    "water_vertex": ("water_plane.precomp", 141, 726),
    "water_fragment": ("water_plane.precomp", 3098, 16301),
    "water_noise_compute": ("lut/water_noise.precomp", 102, 3274),
    "solid_light_fragment": ("deferred/solid_light_sun_sky.precomp", 1243, 20348),
    "brick_fragment": ("wall/wall_brick_lod0.precomp", 33327, 4639),
}


def inspect(root, grammar_path):
    raw_grammar = json.loads(grammar_path.read_text(encoding="utf-8"))
    grammar = {entry["opcode"]: entry for entry in raw_grammar["instructions"]}
    modules = {}
    for name, (relative, offset, count) in MODULES.items():
        blob = (root / relative).read_bytes()
        if offset < 4 or offset + count * 4 > len(blob):
            raise ValueError(f"Unbacked module: {name}")
        if struct.unpack_from("<I", blob, offset - 4)[0] != count:
            raise ValueError(f"Module count changed: {name}")
        modules[name] = decode_module(blob, offset, count, grammar)

    source_language = next(kind for kind in raw_grammar["operand_kinds"] if kind["kind"] == "SourceLanguage")
    if not any(item["value"] == 11 and item["enumerant"] == "Slang" for item in source_language["enumerants"]):
        raise ValueError("Expected grammar declaration for SourceLanguage Slang")
    sources = {}
    for name, module in modules.items():
        source = [r["operands"] for r in module["instructions"] if r["op"] == "OpSource"]
        if source != [[11, 1]]:
            raise ValueError(f"Selected module source declaration changed: {name}")
        sources[name] = {"language": "Slang", "declared_version": 1}

    def row(name, word, op):
        match = next((entry for entry in modules[name]["instructions"] if entry["word_offset"] == word), None)
        if match is None or match["op"] != op:
            raise ValueError(f"Instruction changed: {name} word {word}")
        return match

    def member_read(name, word, expected, expected_name):
        module = modules[name]
        access = row(name, word, "OpAccessChain")
        index = module["constants"].get(str(access["operands"][3]), {}).get("value")
        if index != expected:
            raise ValueError(f"Member index changed: {name}")
        definitions = {r["result_id"]: r for r in module["instructions"] if "result_id" in r}
        variable = definitions[access["operands"][2]]
        pointer_type = definitions[variable["type_id"]]
        if variable["op"] != "OpVariable" or pointer_type["op"] != "OpTypePointer":
            raise ValueError(f"Expected frame variable: {name}")
        owner_type = pointer_type["operands"][2]
        fields = [r for r in module["member_names"] if r["type_id"] == owner_type and r["member"] == index]
        if len(fields) != 1 or fields[0]["name"] != expected_name:
            raise ValueError(f"Frame member name changed: {name}")
        uses = [r for r in module["instructions"] if r["op"] == "OpLoad" and r["operands"][2] == access["result_id"]]
        if not uses:
            raise ValueError(f"Member is not loaded: {name}")
        return {"access_word": word, "member": index, "name": expected_name,
                "load_words": [r["word_offset"] for r in uses]}

    reads = {
        "tree_time_sec": member_read("tree_canopy_vertex", 2576, 13, "game_time_sec"),
        "tree_time_frac": member_read("tree_canopy_vertex", 2599, 14, "game_time_frac"),
        "tree_wind": member_read("tree_canopy_vertex", 3448, 38, "wind_strength"),
        "reed_time": member_read("reed_vertex", 2529, 13, "game_time_sec"),
        "bush_time": member_read("bush_vertex", 2232, 13, "game_time_sec"),
        "grass_startup_time": member_read("grass_vertex", 4438, 8, "time_since_startup_secs"),
    }
    for word in (2633, 2679, 2731, 2767, 3533, 3574, 3591):
        instruction = row("tree_canopy_vertex", word, "OpExtInst")
        if instruction["operands"][3] != 13 or modules["tree_canopy_vertex"]["names"].get(str(instruction["operands"][2])) != "GLSL.std.450":
            raise ValueError("Tree sine chain changed")
    row("tree_canopy_vertex", 3681, "OpFAdd")
    water = modules["water_vertex"]
    position = row("water_vertex", 682, "OpCompositeConstruct")
    height_id = str(position["operands"][3])
    height = water["constants"].get(height_id, {}).get("value")
    if height is None or abs(height + 0.01) > 1e-7:
        raise ValueError("Water plane height changed")
    clamp = row("water_fragment", 5431, "OpExtInst")
    if clamp["operands"][3] != 38 or not any(
        modules["water_fragment"]["constants"].get(str(i), {}).get("value") == 32
        for i in clamp["operands"][4:]
    ):
        raise ValueError("Ripple-count upper clamp changed")
    noise = modules["water_noise_compute"]
    samples = noise["opcode_counts"].get("OpImageSampleExplicitLod", 0)
    if samples != 45:
        raise ValueError("Water LUT sample count changed")
    return {
        "shader_root": str(root.resolve()), "grammar": str(grammar_path.resolve()),
        "modules": {name: {key: value[key] for key in ("offset", "word_count", "instruction_count")}
                    for name, value in modules.items()},
        "source_declarations": sources,
        "loaded_members": reads, "tree_sine_rows_checked": 7,
        "water_height": height, "ripple_upper_clamp": 32, "lut_static_samples": samples,
        "limitations": ["Selected instruction anchors; not complete shader semantics or spirv-val.",
                        "No runtime variant selection, binding, sampler or pixel evidence."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shader_root", type=Path)
    parser.add_argument("--grammar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.shader_root, args.grammar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"modules": len(result["modules"]), "member_reads": len(result["loaded_members"]),
                      "water_lut_samples": result["lut_static_samples"]}))


if __name__ == "__main__":
    main()
