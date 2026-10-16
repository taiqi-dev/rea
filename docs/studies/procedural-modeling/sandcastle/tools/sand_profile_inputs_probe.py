"""Read the selected Sandcastle level0 configuration and Refs color defaults.

This is a fixed-layout, fail-closed probe for the named shipped Unity 6000.4.10f1
objects. It does not load assemblies, run the game, or establish frame colors.
"""

import argparse
import importlib.util
import json
import math
import struct
from pathlib import Path


def load_index_reader():
    path = Path(__file__).resolve().parents[2] / "tools/unity22-compute-probe.py"
    spec = importlib.util.spec_from_file_location("unity22_index", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resource_index


def obj(index, path_id, class_id):
    found = [item for item in index["objects"] if item["path_id"] == path_id]
    if len(found) != 1 or found[0]["class_id"] != class_id:
        raise ValueError(f"expected one pathID {path_id} of class {class_id}")
    return found[0]


def name(blob):
    if len(blob) < 32:
        raise ValueError("short named object")
    length = struct.unpack_from("<I", blob, 28)[0]
    if length > 128 or 32 + length > len(blob):
        raise ValueError("invalid object name length")
    return blob[32:32 + length].decode("utf-8")


def colors(blob, start, names):
    result = {}
    for ordinal, field in enumerate(names):
        offset = start + ordinal * 16
        values = struct.unpack_from("<4f", blob, offset)
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"nonfinite {field} at {offset:#x}")
        result[field] = {"object_offset": hex(offset), "rgba": list(values)}
    return result


def table(blob, count, stride, names):
    hits = []
    for start in range(36, len(blob) - count * stride + 1, 4):
        if struct.unpack_from("<I", blob, start - 4)[0] != count:
            continue
        if all(struct.unpack_from("<I", blob, start + row * stride)[0] == row
               for row in range(count)):
            hits.append(start)
    if len(hits) != 1:
        raise ValueError(f"expected unique {count} x {stride} profile table, got {hits}")
    start = hits[0]
    rows = []
    for ordinal in range(count):
        offset = start + ordinal * stride
        # SandProperty/WaterProperty: enum, two thumbnail PPtrs, unlockCost,
        # then inline Parameters. The selected first row has null thumbnails.
        first_file, first_path, second_file, second_path = struct.unpack_from("<iqiq", blob, offset + 4)
        cost = struct.unpack_from("<i", blob, offset + 28)[0]
        if first_file not in (0, 1, 2, 3) or second_file not in (0, 1, 2, 3):
            raise ValueError("invalid thumbnail PPtr file ID")
        rows.append({"ordinal": ordinal, "object_offset": hex(offset),
                     "thumbnail": [[first_file, first_path], [second_file, second_path]],
                     "unlock_cost": cost,
                     "colors": colors(blob, offset + 32, names)})
    return {"count_field_offset": hex(start - 4), "array_offset": hex(start),
            "stride": stride, "rows": rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("level0", type=Path)
    ap.add_argument("sharedassets0", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    read_index = load_index_reader()
    level, li = read_index(args.level0.resolve(strict=True), include_externals=True)
    shared, si = read_index(args.sharedassets0.resolve(strict=True))
    for index in (li, si):
        if (index["format"], index["unity"], index["type_trees"]) != (22, "6000.4.10f1", False):
            raise ValueError("unsupported SerializedFile profile")
    if li["externals"][1]["file_id"] != 2 or not li["externals"][1]["path"].endswith("sharedassets0.assets"):
        raise ValueError("level0 external 2 is not sharedassets0.assets")
    game_go = obj(li, 11, 1)
    go = level[game_go["offset"]:game_go["offset"] + game_go["bytes"]]
    if (go[48:52] != b"Game" or struct.unpack_from("<I", go, 44)[0] != 4
            or struct.unpack_from("<iq", go, 16) != (0, 476)):
        raise ValueError("pathID 11 is not the selected Game GameObject")
    game_obj = obj(li, 476, 114)
    game = level[game_obj["offset"]:game_obj["offset"] + game_obj["bytes"]]
    if struct.unpack_from("<iq", game, 0) != (0, 11):
        raise ValueError("Game component does not belong to GameObject 11")
    if struct.unpack_from("<iq", game, 0x38) != (2, 8784):
        raise ValueError("unexpected Game.profile reference")
    if struct.unpack_from("<iq", game, 0x5c) != (2, 8790):
        raise ValueError("unexpected Game.refs reference")
    profile_obj = obj(si, 8784, 114)
    profile = shared[profile_obj["offset"]:profile_obj["offset"] + profile_obj["bytes"]]
    if name(profile) != "GameProfile":
        raise ValueError("selected profile PPtr does not name GameProfile")
    refs_obj = obj(si, 8790, 114)
    refs = shared[refs_obj["offset"]:refs_obj["offset"] + refs_obj["bytes"]]
    if name(refs) != "Refs":
        raise ValueError("selected Refs PPtr does not name Refs")
    # Game.header starts at +0xdc: version 1 and five empty strings. The
    # following 7 ints are Configuration seed/layout/format/sand/waves/water/resolution.
    if struct.unpack_from("<6I", game, 0xdc) != (1, 0, 0, 0, 0, 0):
        raise ValueError("unexpected Game.header; Configuration boundary unknown")
    config = struct.unpack_from("<7i", game, 0xf4)
    fields = ("seed", "layout", "format", "sand", "waves", "water", "resolution")
    configuration = {field: {"object_offset": hex(0xf4 + 4 * n), "value": value}
                     for n, (field, value) in enumerate(zip(fields, config))}
    if not 0 <= config[3] < 7 or not 0 <= config[5] < 4:
        raise ValueError("selected color profile index outside table")
    serialized = {
        "sand": colors(game, 0x110, ("color", "color2", "wetColor", "sedimentColor")),
        "water": colors(game, 0x1c4, ("color", "scatteringColor")),
    }
    sands = table(refs, 7, 216, ("color", "color2", "wetColor", "sedimentColor"))
    waters = table(refs, 4, 80, ("color", "scatteringColor"))
    if not int(sands["array_offset"], 16) < int(waters["array_offset"], 16):
        raise ValueError("Refs tables do not follow declared field order")
    result = {"scope": "selected objects and six colors; static serialized values only",
              "level0": str(args.level0.resolve()), "sharedassets0": str(args.sharedassets0.resolve()),
              "level0_bytes": len(level), "sharedassets0_bytes": len(shared),
              "unity": li["unity"], "game_gameobject": game_go, "game_component": game_obj,
              "profile_asset": {**profile_obj, "name": name(profile)},
              "refs_asset": {**refs_obj, "name": name(refs)},
              "configuration": configuration, "serialized_configuration_colors": serialized,
              "sand_profiles": sands, "water_profiles": waters,
              "selected_profile_colors": {"sand": sands["rows"][config[3]],
                                          "water": waters["rows"][config[5]]}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"selected sand={config[3]} water={config[5]} -> {args.output}")


if __name__ == "__main__":
    main()
