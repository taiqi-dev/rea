"""Extract bounded static call-site evidence for the Sandcastle steady-cost study."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
SOURCE = Path(r"C:\Software\Steam\steamapps\common\Sandcastle Demo\GameAssembly.dll")
CACHE = ROOT / ".cache/procedural-modeling/sandcastle"
EXPECTED_BYTES = 47_654_400
EXPECTED_SHA256 = "147030ecf9527a25250238120364eb761390b99688b1812c4ea555b3b04e56a0"

SITES = {
    "game_fixed": (ROOT / ".cache/procedural-modeling/static-state-followup/sandcastle/Game_FixedUpdate_full.txt", ["18048A936", "18048A96A"]),
    "ground_run": (CACHE / "disasm/Ground_Run_full.txt", ["1804500DE", "1804500E2", "18045060C", "18045063A", "18045065A", "1804506A2", "1804506AF", "1804506D9"]),
    "water_run": (CACHE / "disasm/Water_Run_full.txt", ["180483401", "180483405", "180483881", "180483919", "18048394A", "18048396A", "180483990", "1804839D8", "180483A1F", "180483A5B", "180483A7C", "180483A8A", "180483AD1", "180483AE5"]),
    "readback_draw": (CACHE / "update-followup/Readback_Draw_full.txt", ["180464A47", "180464A49", "180464A75", "180464AA1", "180464AF9"]),
    "compute_step": (CACHE / "disasm/Compute_Step_39f.txt", ["180474ED4", "180474EDA", "180474EF6", "180474F06", "180474F4D", "180474F86"]),
    "compute_active": (CACHE / "disasm/Compute_get_Active_394.txt", ["180475160", "18047517A", "180475193"]),
    "readback_active": (CACHE / "disasm/Readback_get_Active_249.txt", ["1804655EB", "1804655FA", "1804655FE"]),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new JSON receipt path; existing files are refused")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt: {output}")
    if not SOURCE.is_file():
        raise SystemExit(f"missing target: {SOURCE}")
    actual_bytes = SOURCE.stat().st_size
    if actual_bytes != EXPECTED_BYTES:
        raise SystemExit(f"target byte count differs from pinned profile: {actual_bytes} != {EXPECTED_BYTES}")
    digest = hashlib.sha256()
    with SOURCE.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != EXPECTED_SHA256:
        raise SystemExit(f"target SHA-256 differs from pinned profile: {actual_sha256}")
    records = {}
    instruction_re = re.compile(r"^\s*(?P<va>[0-9A-F]{16}):\s*(?P<instruction>.+)$", re.I)
    for label, (path, sites) in SITES.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        by_address = {}
        for line in lines:
            match = instruction_re.match(line)
            if match:
                by_address[f"{int(match.group('va'), 16):X}"] = match.group("instruction").strip()
        missing = [site for site in sites if site.upper() not in by_address]
        if missing:
            raise SystemExit(f"{label}: missing addresses {missing} in {path}")
        records[label] = {
            "source": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sites": {site: by_address[site.upper()] for site in sites},
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "method": "reused existing dumpbin text; ordinary local file parsing, not fresh disassembly, REA Evidence, or runtime measurement",
        "target": {"path": str(SOURCE), "bytes": actual_bytes, "sha256": actual_sha256},
        "pinned_profile_matched": True,
        "all_sites_found": True,
        "records": records,
    }
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(output), "target_bytes": actual_bytes, "site_count": sum(len(x["sites"]) for x in records.values()), "pinned_profile_matched": True, "all_sites_found": True}))


if __name__ == "__main__":
    main()
