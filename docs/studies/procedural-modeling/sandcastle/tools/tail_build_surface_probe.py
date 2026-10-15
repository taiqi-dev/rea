"""Inventory Sandcastle's shipped serialized-file surfaces for class 129.

Reads only explicitly named files under the supplied installation directory.
No target code, Unity Editor, digest, or network operation is involved.
"""

import argparse
import importlib.util
import json
from pathlib import Path


FILES = (
    "globalgamemanagers", "globalgamemanagers.assets", "level0",
    "resources.assets", "sharedassets0.assets",
    "Resources/unity default resources", "Resources/unity_builtin_extra",
)
TOKEN_FILES = (
    "UnityPlayer.dll", "GameAssembly.dll",
    "Sandcastle_Data/il2cpp_data/Metadata/global-metadata.dat",
)
TOKENS = ("BuildProfile", "PlayerSettings", "allowedHttpConnections",
          "UnityEditor", "SerializedFile")


def token_locations(data: bytes, token: str, encoding: str) -> list[int]:
    needle = token.encode(encoding)
    positions = []
    at = 0
    while (at := data.find(needle, at)) >= 0:
        positions.append(at)
        at += len(needle)
    return positions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    root = args.install.resolve(strict=True)
    data_root = root / "Sandcastle_Data"
    helper_path = Path(__file__).resolve().parents[2] / "tools/unity22-compute-probe.py"
    spec = importlib.util.spec_from_file_location("unity22_compute_probe", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    results = []
    for name in FILES:
        path = (data_root / name).resolve(strict=True)
        if not path.is_relative_to(data_root.resolve(strict=True)):
            raise ValueError("Serialized file escaped selected installation")
        try:
            _, index = helper.resource_index(path)
        except ValueError as error:
            results.append({"file": str(path), "bytes": path.stat().st_size,
                            "status": "unsupported", "reason": str(error)})
            continue
        selected = [item for item in index["objects"] if item["class_id"] == 129]
        results.append({"file": str(path), "bytes": path.stat().st_size,
                        "status": "parsed", "unity": index["unity"],
                        "format": index["format"], "platform": index["platform"],
                        "type_trees": index["type_trees"],
                        "object_count": index["object_count"],
                        "class_129": selected})
    token_results = []
    for name in TOKEN_FILES:
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError("Binary escaped selected installation")
        data = path.read_bytes()
        token_results.append({"file": str(path), "bytes": len(data),
                              "literal_matches": [{"token": token,
                                  "encoding": encoding, "offsets": token_locations(data, token, encoding)}
                                  for token in TOKENS for encoding in ("ascii", "utf-16-le")]})
    output = args.output.resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump({"installation": str(root), "scope": list(FILES),
                   "results": results, "token_scope": list(TOKEN_FILES),
                   "token_results": token_results}, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"output": str(output),
                      "class_129_counts": {Path(item["file"]).name: len(item.get("class_129", []))
                                           for item in results},
                      "token_counts": {Path(item["file"]).name:
                                       {f'{hit["token"]}/{hit["encoding"]}': len(hit["offsets"])
                                        for hit in item["literal_matches"]}
                                       for item in token_results}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
