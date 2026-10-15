"""Read the two selected AdditionalCameraData objects using local DLL metadata.

Static 2023.2.22f1 profile. Checks SerializeField/type order, consumes 180 bytes,
and keeps serialized values separate from later setters and render execution.
"""
import argparse
import json
import math
import struct
from pathlib import Path

from camera_order_probe import probe as camera_order


PREFIX = "UnityEngine.Rendering.Universal."
FIELDS = [
    ("m_RenderShadows", "Boolean"),
    ("m_RequiresDepthTextureOption", PREFIX + "CameraOverrideOption"),
    ("m_RequiresOpaqueTextureOption", PREFIX + "CameraOverrideOption"),
    ("m_CameraType", PREFIX + "CameraRenderType"),
    ("m_Cameras", "System.Collections.Generic.List`1<UnityEngine.Camera>"),
    ("m_RendererIndex", "Int32"),
    ("m_VolumeLayerMask", "UnityEngine.LayerMask"),
    ("m_VolumeTrigger", "UnityEngine.Transform"),
    ("m_VolumeFrameworkUpdateModeOption", PREFIX + "VolumeFrameworkUpdateMode"),
    ("m_RenderPostProcessing", "Boolean"),
    ("m_Antialiasing", PREFIX + "AntialiasingMode"),
    ("m_AntialiasingQuality", PREFIX + "AntialiasingQuality"),
    ("m_StopNaN", "Boolean"), ("m_Dithering", "Boolean"),
    ("m_ClearDepth", "Boolean"), ("m_AllowXRRendering", "Boolean"),
    ("m_AllowHDROutput", "Boolean"), ("m_UseScreenCoordOverride", "Boolean"),
    ("m_ScreenSizeOverride", "UnityEngine.Vector4"),
    ("m_ScreenCoordScaleBias", "UnityEngine.Vector4"),
    ("m_RequiresDepthTexture", "Boolean"), ("m_RequiresColorTexture", "Boolean"),
    ("m_Version", "Single"), ("m_TaaSettings", PREFIX + "TemporalAA+Settings"),
]
TAA = [("m_Quality", PREFIX + "TemporalAAQuality")] + [
    (name, "Single") for name in ["m_FrameInfluence", "m_JitterScale", "m_MipBias",
                                  "m_VarianceClampScale", "m_ContrastAdaptiveSharpening"]]


def metadata_fields(path, expected_type, expected):
    value = json.loads(path.read_text(encoding="utf-8"))
    if value["type"] != expected_type or value["mvid"] != "441516f4-c7ab-401e-840b-a71a7013b536":
        raise ValueError("Unexpected selected URP metadata identity")
    rows = value["declared_fields"]
    fields = [f for f in rows if not f["flags"] & (0x10 | 0x80) and (
        f["flags"] & 7 == 6 or any(a["constructor"] == "UnityEngine.SerializeField::.ctor"
                                 for a in f["custom_attributes"]))]
    if [(f["name"], f["field_type"]) for f in fields] != expected:
        raise ValueError("Serialized field/type order changed")
    return {"path": str(path), "input": value["input"], "bytes": value["bytes"],
            "mvid": value["mvid"], "type": value["type"], "serialized_fields": fields}


def probe(scene, schema, metadata_path, taa_path):
    metadata = metadata_fields(metadata_path, PREFIX + "UniversalAdditionalCameraData", FIELDS)
    taa = metadata_fields(taa_path, PREFIX + "TemporalAA+Settings", TAA)
    cameras = camera_order(scene, schema)
    raw = scene.read_bytes()
    results = []
    for camera in cameras["cameras"]:
        item = camera["additional_data"]["object"]
        if item["bytes"] != 180:
            raise ValueError("Selected AdditionalCameraData size changed")
        payload = raw[item["offset"]:item["offset"] + item["bytes"]]
        pos = 32
        rows = []

        def read(name, kind):
            nonlocal pos
            start = pos
            if kind == "Boolean":
                value = payload[pos]
                if value not in (0, 1):
                    raise ValueError("Invalid serialized boolean")
                pos += 1
                aligned = (pos + 3) & ~3
                if any(payload[pos:aligned]):
                    raise ValueError("Nonzero boolean padding in selected profile")
                pos = aligned
            elif kind == "Single":
                value = struct.unpack_from("<f", payload, pos)[0]
                if not math.isfinite(value):
                    raise ValueError("Nonfinite selected setting")
                pos += 4
            elif kind == "UnityEngine.Vector4":
                value = list(struct.unpack_from("<4f", payload, pos))
                if not all(math.isfinite(x) for x in value):
                    raise ValueError("Nonfinite selected vector")
                pos += 16
            elif kind == "UnityEngine.Transform":
                file_id, path_id = struct.unpack_from("<iq", payload, pos)
                value = {"m_FileID": file_id, "m_PathID": path_id}
                if file_id != 0 or path_id != 0:
                    raise ValueError("This selected profile expects a null volume trigger")
                pos += 12
            elif kind.startswith("System.Collections.Generic.List"):
                value = struct.unpack_from("<i", payload, pos)[0]
                if value != 0:
                    raise ValueError("This selected profile expects an empty camera stack")
                pos += 4
            else:
                value = struct.unpack_from("<i", payload, pos)[0]
                pos += 4
            rows.append({"name": name, "field_type": kind, "offset": start,
                         "end": pos, "value": value})

        for name, kind in FIELDS:
            if name == "m_TaaSettings":
                for child, child_kind in TAA:
                    read(name + "." + child, child_kind)
            else:
                read(name, kind)
        if pos != len(payload):
            raise ValueError("AdditionalCameraData not completely consumed")
        values = {row["name"]: row["value"] for row in rows}
        if [values[x] for x in ["m_RenderShadows", "m_RequiresDepthTextureOption",
                               "m_RequiresOpaqueTextureOption", "m_CameraType", "m_RendererIndex"]] != [
                camera["additional_data"][x] for x in ["render_shadows", "depth_option",
                                                       "opaque_option", "camera_type", "renderer_index"]]:
            raise ValueError("Full layout disagrees with prior independent prefix projection")
        results.append({"camera": camera["camera"]["path_id"], "additional_object": item,
                        "base_bytes": 32, "end": pos, "remaining_bytes": len(payload) - pos,
                        "fields": rows, "on_after_deserialize_old_version_gate": values["m_Version"] <= 1})
    return {"scene": str(scene), "metadata": metadata, "taa_metadata": taa,
            "objects": results, "scope": "Selected field-order layout checked against local metadata; serialized values only",
            "runtime": "Not Run"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["scene", "schema", "metadata", "taa-metadata", "output"]:
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    result = probe(args.scene.resolve(strict=True), args.schema.resolve(strict=True),
                   args.metadata.resolve(strict=True), args.taa_metadata.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"objects": len(result["objects"]), "remaining_bytes": [x["remaining_bytes"] for x in result["objects"]]}))


if __name__ == "__main__":
    main()
