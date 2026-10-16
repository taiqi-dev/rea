"""Focused offline validation for the SUMMERHOUSE reflection lifecycle study.

The managed target is parsed as PE/CIL bytes; no target code is loaded or run.
The receipt and reread are new ignored evidence files, never overwritten.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
REPORT = ROOT / "docs/studies/procedural-modeling/summerhouse/25-reflection-texture-lifecycle-and-binding.md"
REFLECTION = ROOT / ".cache/procedural-modeling/static-config-followup/summerhouse/planar-reflection-full.json"
SCENE = ROOT / ".cache/procedural-modeling/static-config-followup/summerhouse/scene-camera-components-final.json"
READER = ROOT / ".cache/procedural-modeling/static-chain-followup/summerhouse/managed-bin/net9.0/ManagedCilProbe.dll"
RAW = ROOT / ".cache/procedural-modeling/static-producer-followup/summerhouse"
EXPECTED_MVID = "dfe63f36-a582-4939-bd07-a189a923e050"
EXPECTED_BYTES = 40448


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def instruction(record, method_name, offset):
    methods = [m for m in record["methods"] if m["token"] == method_name] if method_name.startswith("0x") else [m for m in record["methods"] if m["name"] == method_name]
    if len(methods) != 1:
        raise AssertionError(f"{method_name}: expected one method, got {len(methods)}")
    matches = [i for i in methods[0]["instructions"] if i["offset"] == offset]
    if len(matches) != 1:
        raise AssertionError(f"{method_name} IL_{offset:04X}: expected one instruction")
    return matches[0]


def il_check(record, method, offset, opcode, resolved=None, operand=None):
    i = instruction(record, method, offset)
    if i["opcode"] != opcode:
        raise AssertionError(f"{method} IL_{offset:04X}: opcode {i['opcode']} != {opcode}")
    if resolved is not None and i["resolved"] != resolved:
        raise AssertionError(f"{method} IL_{offset:04X}: resolved {i['resolved']} != {resolved}")
    if operand is not None and i["operand"] != operand:
        raise AssertionError(f"{method} IL_{offset:04X}: operand {i['operand']} != {operand}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-data", required=True, type=Path)
    args = parser.parse_args()
    dll = args.game_data.resolve() / "Managed/sc.stylizedwater2.runtime.dll"
    reread_number = 1
    while (RAW / f"water-object-validation-reread-{reread_number}.json").exists():
        reread_number += 1
    reread = RAW / f"water-object-validation-reread-{reread_number}.json"
    receipt = RAW / "focused-validation.json"
    if receipt.exists():
        raise SystemExit("Refusing to overwrite an existing validation receipt")
    RAW.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(
        ["dotnet", str(READER), str(dll), "StylizedWater2.WaterObject", "*", str(reread)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    checks = []

    def check(name, action):
        try:
            action()
            checks.append({"name": name, "status": "Passed"})
        except Exception as error:
            checks.append({"name": name, "status": "Failed", "reason": str(error)})

    def require(condition, message):
        if not condition:
            raise AssertionError(message)

    def reader_check():
        require(run.returncode == 0, f"reader exit {run.returncode}: {run.stderr}")
        require(reread.is_file(), "reader produced no CIL output")

    check("offline reader completed against exact target DLL", reader_check)
    water = read_json(reread) if reread.exists() else None
    reflection = read_json(REFLECTION)
    scene = read_json(SCENE)

    def identity_check():
        for name, record in (("reflection", reflection), ("water reread", water)):
            require(record is not None, f"{name} missing")
            require(record["bytes"] == EXPECTED_BYTES, f"{name} byte count")
            require(record["mvid"] == EXPECTED_MVID, f"{name} MVID")
            require(Path(record["input"]).resolve() == dll, f"{name} input path")
        require(dll.stat().st_size == EXPECTED_BYTES, "on-disk DLL size")

    check("target byte length, MVID, and exact input path", identity_check)
    check("WaterObject 16 of 16 MethodDef bodies decoded", lambda: require(
        water is not None and water["coverage"]["selected_types"] == 1
        and water["coverage"]["examined_methods"] == 16
        and water["coverage"]["decoded_methods"] == 16
        and len(water["methods"]) == 16,
        "WaterObject method coverage differs",
    ))
    check("PlanarReflectionRenderer 34 of 34 MethodDef bodies decoded", lambda: require(
        reflection["coverage"]["selected_types"] == 1
        and reflection["coverage"]["examined_methods"] == 34
        and reflection["coverage"]["decoded_methods"] == 34,
        "reflection method coverage differs",
    ))

    def cache_check():
        fields = {f["name"]: f["field_type"] for f in reflection["declared_fields"]}
        require(fields["reflectionCameras"] == "System.Collections.Generic.Dictionary`2<UnityEngine.Camera,UnityEngine.Camera>", "dictionary type")
        il_check(reflection, ".ctor", 0x0006, "stfld", "StylizedWater2.PlanarReflectionRenderer::reflectionCameras")
        il_check(reflection, "OnWillRenderCamera", 0x006F, "ldarg.2")
        il_check(reflection, "OnWillRenderCamera", 0x0076, "callvirt")
        il_check(reflection, "OnWillRenderCamera", 0x008C, "call", "StylizedWater2.PlanarReflectionRenderer::CreateReflectionCamera")
        il_check(reflection, "CreateReflectionCamera", 0x00FA, "callvirt")

    check("per-instance source-Camera cache lookup and insertion", cache_check)

    def dimensions_check():
        il_check(reflection, "GetRenderScale", 0x0001, "ldfld", "StylizedWater2.PlanarReflectionRenderer::renderScale")
        il_check(reflection, "GetRenderScale", 0x000B, "callvirt", "UnityEngine.Rendering.Universal.UniversalRenderPipelineAsset::get_renderScale")
        il_check(reflection, "GetRenderScale", 0x0011, "ldc.r4", operand="0.25")
        il_check(reflection, "GetRenderScale", 0x001B, "call", "UnityEngine.Mathf::Clamp")
        il_check(reflection, "CreateRenderTexture", 0x0025, "callvirt", "UnityEngine.Camera::get_scaledPixelWidth")
        il_check(reflection, "CreateRenderTexture", 0x002D, "conv.i4")
        il_check(reflection, "CreateRenderTexture", 0x002F, "callvirt", "UnityEngine.Camera::get_scaledPixelHeight")
        il_check(reflection, "CreateRenderTexture", 0x0037, "conv.i4")
        il_check(reflection, "CreateRenderTexture", 0x0049, "call", "UnityEngine.RenderTexture::GetTemporary")
        il_check(reflection, "CreateRenderTexture", 0x004E, "callvirt", "UnityEngine.Camera::set_targetTexture")

    check("render-scale clamp, source dimensions, and temporary RT allocation", dimensions_check)

    def invalidation_check():
        il_check(reflection, "OnWillRenderCamera", 0x00A0, "ldfld", "StylizedWater2.PlanarReflectionRenderer::renderScale")
        il_check(reflection, "OnWillRenderCamera", 0x00A6, "ldfld", "StylizedWater2.PlanarReflectionRenderer::m_renderScale")
        il_check(reflection, "OnWillRenderCamera", 0x00AC, "call", "System.Math::Abs")
        il_check(reflection, "OnWillRenderCamera", 0x00B1, "ldc.r4", operand="0.02")
        il_check(reflection, "OnWillRenderCamera", 0x00B6, "ble.un.s", operand=225)
        il_check(reflection, "OnWillRenderCamera", 0x00C3, "call", "UnityEngine.RenderTexture::ReleaseTemporary")
        il_check(reflection, "OnWillRenderCamera", 0x00D0, "call", "StylizedWater2.PlanarReflectionRenderer::CreateRenderTexture")
        il_check(reflection, "OnWillRenderCamera", 0x00DC, "stfld", "StylizedWater2.PlanarReflectionRenderer::m_renderScale")
        il_check(reflection, "SetQuality", 0x0025, "stfld", "StylizedWater2.PlanarReflectionRenderer::renderScale")
        il_check(reflection, "SetQuality", 0x0045, "callvirt", "StylizedWater2.PlanarReflectionRenderer::InitializeValues")
        il_check(reflection, "InitializeValues", 0x0007, "stfld", "StylizedWater2.PlanarReflectionRenderer::m_renderScale")

    check("0.02 scale invalidation and SetQuality record synchronization", invalidation_check)

    def binding_check():
        il_check(reflection, ".cctor", 0x0010, "ldstr", resolved="\"_PlanarReflectionsEnabled\"")
        il_check(reflection, ".cctor", 0x001F, "ldstr", resolved="\"_PlanarReflection\"")
        il_check(reflection, "0x0600004E", 0x001A, "callvirt", "UnityEngine.MaterialPropertyBlock::SetFloat")
        il_check(reflection, "UpdateWaterProperties", 0x002F, "callvirt", "UnityEngine.Camera::get_targetTexture")
        il_check(reflection, "UpdateWaterProperties", 0x0034, "callvirt", "UnityEngine.MaterialPropertyBlock::SetTexture")
        il_check(reflection, "UpdateWaterProperties", 0x0045, "callvirt", "StylizedWater2.WaterObject::ApplyInstancedProperties")
        il_check(reflection, "OnWillRenderCamera", 0x00E8, "call", "StylizedWater2.PlanarReflectionRenderer::UpdateWaterProperties")
        il_check(reflection, "OnWillRenderCamera", 0x0141, "call", "UnityEngine.Rendering.Universal.UniversalRenderPipeline::RenderSingleCamera")
        il_check(water, "CreatePropertyBlock", 0x0012, "callvirt", "UnityEngine.Renderer::GetPropertyBlock")
        il_check(water, "ApplyInstancedProperties", 0x0014, "callvirt", "UnityEngine.Renderer::SetPropertyBlock")

    check("water property-block texture and sampling flag binding before render", binding_check)

    def cleanup_check():
        il_check(reflection, "OnDisable", 0x000D, "call", "StylizedWater2.PlanarReflectionRenderer::DisableReflections")
        il_check(reflection, "DisableReflections", 0x000C, "call", "UnityEngine.Rendering.RenderPipelineManager::remove_beginCameraRendering")
        il_check(reflection, "DisableReflections", 0x0013, "call", "StylizedWater2.PlanarReflectionRenderer::ToggleMaterialReflectionSampling")
        il_check(reflection, "DisableReflections", 0x0057, "call", "UnityEngine.RenderTexture::ReleaseTemporary")
        il_check(reflection, "DisableReflections", 0x0068, "call", "UnityEngine.Object::DestroyImmediate")
        il_check(reflection, "DisableReflections", 0x008C, "callvirt")

    check("disable unsubscribes, switches off sampling, releases RT, destroys camera, clears cache", cleanup_check)

    def scene_check():
        require(scene["water_mvid"] == EXPECTED_MVID, "scene parser water MVID")
        require(scene["schema_version"] == "2023.2.22f1", "scene schema")
        chosen = [item for item in scene["selected"] if item["script"]["class"] == "PlanarReflectionRenderer"]
        require(len(chosen) == 4, "expected four serialized reflection components")
        require(not any(item["scene"] == "level0" for item in chosen), "unexpected level0 reflection component")
        expected = {"level1": (513, 87), "level2": (434, 247), "level3": (626, 247), "level4": (472, 87)}
        for item in chosen:
            scene_name = item["scene"]
            require(scene_name in expected, f"unexpected scene {scene_name}")
            path_id, mask = expected[scene_name]
            field = item["reflection_fields"]
            require(item["component"]["path_id"] == path_id, f"{scene_name} component path")
            require(item["enabled"] == 1 and item["active_self"] == 1, f"{scene_name} activation")
            require(field["renderer_index"] == 1 and field["render_scale"] == 0.5, f"{scene_name} renderer/scale")
            require(field["render_range"] == 500 and field["culling_mask"] == mask, f"{scene_name} range/mask")
            require(len(field["water_object_path_ids"]) == 16, f"{scene_name} water count")
            require(field["bytes_consumed"] == item["component"]["bytes"] == 296, f"{scene_name} field consumption")

    check("five-scene reflection registration and complete four-component fields", scene_check)

    def links_check():
        body = REPORT.read_text(encoding="utf-8")
        links = re.findall(r"\]\(([^)]+)\)", body)
        require(len(links) >= 4, "too few report links")
        missing = [link for link in links if not (REPORT.parent / link).resolve().exists()]
        require(not missing, f"missing relative links: {missing}")

    check("all report relative links resolve", links_check)
    passed = sum(item["status"] == "Passed" for item in checks)
    failed = sum(item["status"] == "Failed" for item in checks)
    result = {
        "scope": "offline CIL and shipped-scene records only; no target execution",
        "inputs": {
            "target_dll": str(dll),
            "reader": str(READER),
            "reflection_cil": str(REFLECTION),
            "scene_parse": str(SCENE),
            "report": str(REPORT),
        },
        "reread": {"path": str(reread), "reader_exit_code": run.returncode, "reader_stdout": run.stdout.strip(), "reader_stderr": run.stderr.strip()},
        "counts": {"Passed": passed, "Failed": failed, "NotRun": 1},
        "checks": checks,
        "not_run": ["SUMMERHOUSE launch, attach, target method execution, save access, runtime frame/GPU, and native P/V validation"],
    }
    with receipt.open("x", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(json.dumps({"receipt": str(receipt), "counts": result["counts"]}))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
