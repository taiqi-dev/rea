"""Module56: exact two known TLSA keys, three SDK ordinary-idle identifiers.

At most six referenced ANIM resources: header/channel/component metadata and
whole predicate only. No curves/events/meshes are exported and no game executes.
Frozen existing format helpers are reused without modifying them.
"""
import json
import mmap
from pathlib import Path

from read_selected_ability_properties import FormatError, digest, key_json, read_index, refpack
from read_selected_action_channels import read_tlsa, read_anim_metadata
from read_selected_animation_predicates import decode_predicate

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("E:/Steam/steamapps/common/Spore/Data")
SELECTED_IDS = {0x04866D8E: "idle_walk_lookat_start",
                0x04866DAB: "idle_walk_lookat_loop",
                0x04866DB9: "idle_walk_lookat_stop"}
MAX_ANIM_RECORDS = 6  # Explicit task research budget, not a format limit.


def decode_selected(data, entry):
    if entry["memory_bytes"] > 1024 * 1024:
        raise FormatError("selected idle resource exceeds one-MiB research budget")
    start, size = entry["offset"], entry["stored_bytes"]
    if start < 96 or start + size > len(data):
        raise FormatError("selected idle resource outside package")
    raw = data[start:start+size]
    dec = refpack(raw, entry["memory_bytes"]) if entry["compression"] == 0xFFFF else raw
    if len(dec) != entry["memory_bytes"]:
        raise FormatError("selected idle decoded size mismatch")
    return dec, digest(raw), digest(dec)


def main():
    prior_path = ROOT / "evidence/local-selected-action-channels.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    prior_tlsa = [r for r in prior["records"] if "tlsa" in r]
    packages, tlsa_records, anim_records, diagnostics = [], [], [], []
    candidates = []
    for previous in prior_tlsa:
        name = previous["package"]
        if name not in {"Spore_Game.package", "PatchData.package"}:
            raise FormatError("unexpected package identity in prior TLSA manifest")
        path = DATA / name
        with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            known = next(p for p in prior["packages"] if Path(p["path"]).name == name)
            if len(data) != known["bytes"] or digest(data) != known["sha256"]:
                raise FormatError("package complete identity changed")
            entries, index = read_index(data)
            key = tuple(int(previous["key"][field], 16) for field in ("type", "group", "instance"))
            entry = entries.get(key)
            if entry is None or any(entry[f] != previous[f] for f in entry):
                raise FormatError("known TLSA index entry missing or changed")
            dec, stored_sha, decoded_sha = decode_selected(data, entry)
            if (stored_sha, decoded_sha) != (previous["stored_sha256"], previous["decoded_sha256"]):
                raise FormatError("known TLSA byte identity changed")
            groups = read_tlsa(dec, set(SELECTED_IDS))
            tlsa_records.append(dict(package=name, key=key_json(key), **entry,
                stored_sha256=stored_sha, decoded_sha256=decoded_sha, tlsa=groups))
            packages.append(dict(path=str(path), bytes=len(data), sha256=digest(data), **index))
            ids = {int(a["id"], 16) for g in groups["selected_groups"]
                   for c in g["choices"] for a in c["animations"]}
            for g in SELECTED_IDS:
                if not any(int(x["id"], 16) == g for x in groups["selected_groups"]):
                    diagnostics.append(dict(package=name, group=f"0x{g:08x}", status="selected-group-not-found"))
            for anim_id in sorted(ids):
                found = [(k, e) for k, e in entries.items() if k[0] == 0xEE17C6AD and k[2] == anim_id]
                if not found:
                    diagnostics.append(dict(package=name, animation=f"0x{anim_id:08x}", status="same-package-animation-not-found"))
                for k, e in sorted(found):
                    candidates.append(dict(package=name, key=key_json(k), **e))
                    if len(anim_records) >= MAX_ANIM_RECORDS:
                        diagnostics.append(dict(package=name, key=key_json(k), status="metadata-only-index-entry-budget"))
                        continue
                    body, s_sha, d_sha = decode_selected(data, e)
                    meta = read_anim_metadata(body)
                    if "\\creature\\" not in meta["embedded_path"].lower():
                        diagnostics.append(dict(package=name, key=key_json(k), status="embedded-path-not-Creature-labelled"))
                        continue
                    anim_records.append(dict(package=name, key=key_json(k), **e,
                        stored_sha256=s_sha, decoded_sha256=d_sha,
                        anim=meta, whole_predicate=decode_predicate(body, 0x154)))
    output = dict(schema_version=1, module=56, kind="bounded-idle-reference-metadata-not-REA-Evidence",
        rea_evidence_id=None, target_runtime_verified=False,
        selection_origin="SDK Anim/Animations.cpp lines26–38,40–69,71–88 ordinary idle IDs only; CSA/epic excluded",
        selected_ids={f"0x{k:08x}": v for k, v in SELECTED_IDS.items()},
        package_load_order="unknown; same-package references retained, no winning overlay guessed",
        prior=dict(path=str(prior_path), sha256=digest(prior_path.read_bytes())),
        reader=dict(path=str(Path(__file__).resolve()), sha256=digest(Path(__file__).read_bytes())),
        helper_sha256={name: digest((ROOT/"checks"/name).read_bytes()) for name in (
            "read_selected_ability_properties.py", "read_selected_action_channels.py", "read_selected_animation_predicates.py")},
        packages=packages, tlsa_records=tlsa_records, anim_records=anim_records,
        index_candidates=candidates, diagnostics=diagnostics,
        coverage=dict(tlsa_count=len(tlsa_records), selected_groups=sum(len(r["tlsa"]["selected_groups"]) for r in tlsa_records),
            anim_count=len(anim_records), channels=sum(len(r["anim"]["channels"]) for r in anim_records),
            curves_decoded=False, events_decoded=False, model_or_private_recipe_read=False),
        limits=["Name/idle flag does not establish neutral standing height, character personality or editor default selection.",
                "Whole predicates read, not executed; no body morphology classifier recovered.",
                "No reference-pose evaluation or original animation samples exported."])
    dest = ROOT / "evidence/local-selected-idle-posture-metadata.json"
    dest.write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(output["coverage"]))
    print(json.dumps(dict(diagnostics=diagnostics, keys=[r["key"] for r in anim_records])))


if __name__ == "__main__":
    main()
