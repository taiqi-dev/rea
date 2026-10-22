"""Read measured Tiny Glade menu, sparse-pool and render-publication anchors.

No target execution, input simulation, digest or runtime schedule extraction.
Selected anchors support studies 135-136, not complete reachability or frames.
"""

import argparse
import json
from pathlib import Path
import struct

from atlas_budget_probe import PeReader


CALLS = {
    "toolbar_click_consumer": (0x142389B2C, 0x142984C50),
    "toolbar_group": (0x140736033, 0x1411CE5A0),
    "mode_manager_group": (0x14064FA45, 0x140569E80),
    "mode_request_acceptance": (0x140B42B33, 0x141B6B0B0),
    "menu_close_request": (0x14033E862, 0x140A003A0),
    "menu_input_handlers": (0x14072D71B, 0x140732500),
    "timber_clear": (0x141F4F284, 0x14281A140),
    "wood_pool_prepare_registration": (0x1400CFB33, 0x140170980),
    "wood_flush_wrapper": (0x1405ECAA4, 0x14081DF30),
    "wood_flush": (0x14081E064, 0x1413F07A0),
    "game_update": (0x140360E58, 0x140E02350),
    "game_render": (0x140361080, 0x1400FD580),
    "render_maintenance": (0x1400FD8B3, 0x140962570),
    "execute_graph": (0x1400FECA9, 0x140355DF0),
    "execute_present_graph": (0x1400FED6D, 0x140353810),
    "update_executor_selection": (0x1405E9115, 0x140F255F0),
    "make_executor": (0x140F2562F, 0x140F239F0),
    "explicit_deferred_flush": (0x140ED6ED1, 0x140EDE370),
    "final_deferred_flush": (0x140ED72AB, 0x140EDE370),
}

ANCHORS = {
    "toolbar_stage_8": (0x140736038, "c6858700000008"),
    "mode_manager_stage_10": (0x14064FB6B, "41b00a"),
    "menu_apply_stage_10": (0x140736B64, "c685900300000a"),
    "menu_content_stage_36": (0x140736AFA, "41b024"),
    "clear_owned_count": (0x14281A1AD, "41c6040b00"),
    "clear_owned_bit": (0x14281A1CC, "f04e2134ce"),
    "new_executor_final_flag": (0x140F23AD4, "c683c800000001"),
    "executor_final_flag_gate": (0x140ED7293, "41807f4800"),
    "menu_closed_tag_2": (0x14033E84E, "48c784248000000002000000"),
    "accepted_mode_copy": (0x141B6B14A, "0f1100"),
    "preview_clear": (0x140ADCDCA, "41c7042400000000"),
}

VTABLES = {
    "mode_manager": (0x14056A0A8, 0x142E41C00, 0x1400F7640),
    "mode_button": (0x14238B4EC, 0x1434DED80, 0x142389890),
    "menu_state_apply": (0x140736B3C, 0x1432AD548, 0x1411D8C00),
    "wood_pool_prepare": (0x140170A85, 0x142F73C90, 0x1405EC990),
}


def inspect(binary):
    pe = PeReader(binary)
    if pe.base != 0x140000000:
        raise ValueError("Unexpected preferred base")
    for name, (site, target) in CALLS.items():
        raw = pe.read(site, 5)
        if raw[0] != 0xE8 or site + 5 + struct.unpack_from("<i", raw, 1)[0] != target:
            raise ValueError(f"Call mismatch: {name}")
    for name, (site, expected) in ANCHORS.items():
        if pe.read(site, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f"Anchor mismatch: {name}")
    for name, (site, table, target) in VTABLES.items():
        raw = pe.read(site, 7)
        if raw[:3].hex() != "4c8d05" or site + 7 + struct.unpack_from("<i", raw, 3)[0] != table:
            raise ValueError(f"Vtable registration mismatch: {name}")
        if struct.unpack("<Q", pe.read(table + 0x48, 8))[0] != target:
            raise ValueError(f"System entry mismatch: {name}")
    executor = struct.unpack("<QQQQQQQ", pe.read(0x14323ACF8, 56))
    if executor[1:3] != (0x50, 8) or executor[5:7] != (0x140ED6DE0, 0x140F0EC10):
        raise ValueError("Selected executor vtable changed")
    # The two codegen copies both identify the set as GameSystemSet.
    for table, formatter in ((0x1432A7688, 0x1411AD9F0), (0x14326E7E0, 0x140FE4230)):
        if struct.unpack("<Q", pe.read(table + 0x18, 8))[0] != formatter:
            raise ValueError("Stage vtable formatter changed")
    return {
        "binary": str(binary.resolve()), "binary_bytes": len(pe.data),
        "calls_checked": len(CALLS), "anchors_checked": len(ANCHORS),
        "system_vtables_checked": len(VTABLES), "stage_vtables_checked": 2,
        "executor_vtable": {"address": "0x14323acf8", "run": hex(executor[5]),
                            "set_apply_final_deferred": hex(executor[6])},
        "limitations": ["Ordinary file evidence, not REA provider Evidence.",
                        "No final schedule graph, target execution, GPU completion or presentation observation."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = inspect(args.binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("calls_checked", "anchors_checked", "system_vtables_checked")}))


if __name__ == "__main__":
    main()
